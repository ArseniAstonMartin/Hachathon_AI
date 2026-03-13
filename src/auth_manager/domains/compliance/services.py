from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from time import monotonic
from typing import Literal
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from dependency_injector.wiring import Provide

from src.auth_manager.components.injectable import injectable
from src.auth_manager.config import ComplianceSettings

PravoByRegistry = Literal["official_publication", "national_registry"]

PRAVO_BY_REGISTRY_GUIDS: dict[PravoByRegistry, str] = {
    "official_publication": "12551",
    "national_registry": "3961",
}

PRAVO_BY_PUBLICATION_PATHS: dict[PravoByRegistry, str] = {
    "official_publication": "/ofitsialnoe-opublikovanie/novye-postupleniya/",
    "national_registry": "/natsionalnyy-reestr/novye-postupleniya/",
}


class PravoByUnavailableError(RuntimeError):
    """Raised when the official source cannot be reached or parsed reliably."""


@dataclass(frozen=True, slots=True)
class PravoByPublicationEntry:
    registry: PravoByRegistry
    registry_guid: str
    source_code: str
    registry_number: str
    published_date: str
    title: str
    act_metadata: str
    document_url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PravoByDocumentMetadata:
    registry: PravoByRegistry
    registry_guid: str
    source_code: str
    title: str
    act_metadata: str
    document_url: str
    registry_number: str | None = None
    registry_inclusion_date: str | None = None
    effective_date: str | None = None
    pdf_url: str | None = None
    source_kind: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _clean_text(value: str) -> str:
    normalized = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    normalized = re.sub(r"<!--.*?-->", "", normalized, flags=re.DOTALL)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = unescape(normalized)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _parse_document_url(document_url: str) -> tuple[str, str]:
    parsed = urlparse(document_url)
    query = parse_qs(parsed.query)
    guid = query.get("guid", [None])[0]
    source_code = query.get("p0", [None])[0]
    if guid is None or source_code is None:
        raise ValueError(f"Unsupported pravo.by document URL: {document_url}")
    return guid, source_code


def parse_pravo_by_publications(
    html: str,
    *,
    base_url: str,
    registry: PravoByRegistry,
    registry_guid: str,
) -> list[PravoByPublicationEntry]:
    entries: list[PravoByPublicationEntry] = []
    pattern = re.compile(
        r"<dl>\s*<dt>(?P<dt>.*?)</dt>\s*<dd>\s*<p>\s*<a href=\"(?P<href>[^\"]+)\"[^>]*>"
        r"(?P<title>.*?)</a>.*?<br/>\s*(?P<act_metadata>.*?)</p>",
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.finditer(html):
        dt_text = _clean_text(match.group("dt"))
        parts = [part.strip() for part in dt_text.split(" ") if part.strip()]
        registry_number = parts[0] if parts else ""
        published_date_match = re.search(r"\((?P<date>\d{2}\.\d{2}\.\d{4})\)", match.group("dt"))
        published_date = published_date_match.group("date") if published_date_match else ""
        document_url = urljoin(base_url, unescape(match.group("href")))
        _, source_code = _parse_document_url(document_url)

        entries.append(
            PravoByPublicationEntry(
                registry=registry,
                registry_guid=registry_guid,
                source_code=source_code,
                registry_number=registry_number,
                published_date=published_date,
                title=_clean_text(match.group("title")),
                act_metadata=_clean_text(match.group("act_metadata")),
                document_url=document_url,
            )
        )

    return entries


def parse_pravo_by_document_metadata(
    html: str,
    *,
    registry: PravoByRegistry,
    registry_guid: str,
    source_code: str,
    document_url: str,
) -> PravoByDocumentMetadata:
    heading_match = re.search(r"<title>(?P<title>.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
    page_title = _clean_text(heading_match.group("title")) if heading_match else ""
    source_kind = "official_publication" if registry == "official_publication" else "national_registry"

    if registry == "official_publication":
        quoted_title_match = re.search(r"«(?P<title>.*?)»", page_title)
        parsed_title = quoted_title_match.group("title") if quoted_title_match else page_title
        act_metadata = _clean_text(page_title.replace("– Pravo.by", ""))
        pdf_match = re.search(
            r'data=\"(?P<pdf>/upload/docs/op/[^\"]+\.pdf)\"',
            html,
            flags=re.IGNORECASE,
        )
        return PravoByDocumentMetadata(
            registry=registry,
            registry_guid=registry_guid,
            source_code=source_code,
            title=_clean_text(parsed_title),
            act_metadata=act_metadata,
            document_url=document_url,
            pdf_url=urljoin("https://pravo.by", pdf_match.group("pdf")) if pdf_match else None,
            source_kind=source_kind,
        )

    title_match = re.search(
        r"<b>\s*Название акта\s*</b>\s*<div>\s*(?P<title>.*?)\s*</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    act_metadata_match = re.search(
        r"<b>\s*Вид акта, орган принятия, дата и номер принятия \(издания\)\s*</b>\s*<div>\s*(?P<value>.*?)\s*</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    registry_number_match = re.search(
        r"<b>\s*Регистрационный номер Национального реестра\s*</b>\s*<div>\s*(?P<value>.*?)\s*</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    inclusion_date_match = re.search(
        r"<b>\s*Дата включения в Национальный реестр\s*</b>\s*<div>\s*(?P<value>.*?)\s*</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    effective_date_match = re.search(
        r"<b>\s*Дата вступления в силу\s*</b>\s*<div>\s*(?P<value>.*?)\s*</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return PravoByDocumentMetadata(
        registry=registry,
        registry_guid=registry_guid,
        source_code=source_code,
        title=_clean_text(title_match.group("title")) if title_match else page_title,
        act_metadata=_clean_text(act_metadata_match.group("value")) if act_metadata_match else page_title,
        document_url=document_url,
        registry_number=_clean_text(registry_number_match.group("value")) if registry_number_match else None,
        registry_inclusion_date=_clean_text(inclusion_date_match.group("value")) if inclusion_date_match else None,
        effective_date=_clean_text(effective_date_match.group("value")) if effective_date_match else None,
        source_kind=source_kind,
    )


@injectable()
class PravoBySourceClient:
    def __init__(
        self,
        settings: ComplianceSettings = Provide["settings.provided.compliance"],
    ) -> None:
        self._settings = settings
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_monotonic = 0.0

    async def list_publications(
        self,
        *,
        publication_date: date | None = None,
        registry: PravoByRegistry = "official_publication",
        limit: int | None = None,
    ) -> list[PravoByPublicationEntry]:
        registry_guid = PRAVO_BY_REGISTRY_GUIDS[registry]
        path = PRAVO_BY_PUBLICATION_PATHS[registry]
        params = None
        if publication_date is not None:
            date_string = publication_date.strftime("%d.%m.%Y")
            params = {"p0": date_string, "p1": date_string}

        html = await self._get_text(path=path, params=params)
        entries = parse_pravo_by_publications(
            html,
            base_url=self._settings.pravo_by_base_url,
            registry=registry,
            registry_guid=registry_guid,
        )
        capped_limit = limit or self._settings.max_publication_results
        return entries[:capped_limit]

    async def get_document_metadata(
        self,
        *,
        source_code: str,
        registry: PravoByRegistry = "official_publication",
    ) -> PravoByDocumentMetadata:
        registry_guid = PRAVO_BY_REGISTRY_GUIDS[registry]
        document_url = (
            f"{self._settings.pravo_by_base_url}/document/?guid={registry_guid}&p0={source_code}"
        )
        html = await self._get_text(path="/document/", params={"guid": registry_guid, "p0": source_code})
        return parse_pravo_by_document_metadata(
            html,
            registry=registry,
            registry_guid=registry_guid,
            source_code=source_code,
            document_url=document_url,
        )

    async def _get_text(self, *, path: str, params: dict[str, str] | None = None) -> str:
        await self._respect_rate_limit()
        url = urljoin(self._settings.pravo_by_base_url, path)
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.request_timeout_seconds,
                headers={"User-Agent": self._settings.user_agent},
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise PravoByUnavailableError(f"pravo.by request failed: {exc}") from exc

    async def _respect_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            elapsed = monotonic() - self._last_request_monotonic
            if elapsed < self._settings.min_interval_seconds:
                await asyncio.sleep(self._settings.min_interval_seconds - elapsed)
            self._last_request_monotonic = monotonic()


@injectable()
class ComplianceSourceService:
    def __init__(
        self,
        pravo_by_source_client: PravoBySourceClient,
        settings: ComplianceSettings = Provide["settings.provided.compliance"],
    ) -> None:
        self._pravo_by_source_client = pravo_by_source_client
        self._settings = settings

    def source_overview(self) -> dict[str, object]:
        return {
            "selected_source": "pravo.by",
            "official_owner": "Национальный центр законодательства и правовой информации Республики Беларусь",
            "integration_mode": "public-html-pages",
            "allowed_entrypoints": [
                "/ofitsialnoe-opublikovanie/novye-postupleniya/",
                "/natsionalnyy-reestr/novye-postupleniya/",
                "/document/?guid=12551&p0=<source_code>",
                "/document/?guid=3961&p0=<source_code>",
            ],
            "restricted_entrypoints": [
                "/search/",
                "/natsionalnyy-reestr/poisk-v-reestre/?*",
                "/ofitsialnoe-opublikovanie/poisk/?*",
            ],
            "access_constraints": {
                "link_attribution_required": True,
                "self_imposed_min_interval_seconds": self._settings.min_interval_seconds,
                "no_mock_fallback": True,
            },
            "fallback_behavior": {
                "when_source_unavailable": "raise_source_unavailable_and_return_503",
                "data_substitution": "forbidden",
            },
        }

    async def list_publications(
        self,
        *,
        publication_date: date | None = None,
        registry: PravoByRegistry = "official_publication",
        limit: int | None = None,
    ) -> dict[str, object]:
        entries = await self._pravo_by_source_client.list_publications(
            publication_date=publication_date,
            registry=registry,
            limit=limit,
        )
        return {
            "source": self.source_overview(),
            "registry": registry,
            "publication_date": publication_date.isoformat() if publication_date else None,
            "count": len(entries),
            "entries": [entry.to_dict() for entry in entries],
        }

    async def get_document_metadata(
        self,
        *,
        source_code: str,
        registry: PravoByRegistry = "official_publication",
    ) -> dict[str, object]:
        metadata = await self._pravo_by_source_client.get_document_metadata(
            source_code=source_code,
            registry=registry,
        )
        return {
            "source": self.source_overview(),
            "document": metadata.to_dict(),
        }
