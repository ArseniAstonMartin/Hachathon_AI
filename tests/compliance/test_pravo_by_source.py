from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth_manager.domains.compliance.services import (
    PRAVO_BY_REGISTRY_GUIDS,
    ComplianceSourceService,
    PravoByUnavailableError,
    parse_pravo_by_document_metadata,
    parse_pravo_by_publications,
)

PUBLICATIONS_HTML = """
<div class="usercontent">
    <dl>
        <dt>6-1/55801<!-- --><br/><!-- -->(12.03.2026)<!-- --></dt>
        <dd>
            <p>
                <a href="/document/?guid=12551&amp;p0=C22600119" target="_blank">О Министерстве архитектуры и строительства Республики Беларусь</a><br/>
                Постановление Совета Министров Республики Беларусь от 11 марта 2026 г. № 119
            </p>
        </dd>
    </dl>
</div>
"""

REGISTRY_CARD_HTML = """
<html>
<head>
    <title>Информация о документе «О порядке взаимодействия при исполнении судебных решений о принудительном лечении» – Pravo.by</title>
</head>
<body>
<div class="reestrmap">
    <b>Название акта</b>
    <div>О порядке взаимодействия при исполнении судебных решений о принудительном лечении</div>

    <b>Вид акта, орган принятия, дата и номер принятия (издания)</b>
    <div>Постановление Совета Министров Республики Беларусь от 12 марта 2026 г. № 122</div>

    <b>Регистрационный номер Национального реестра</b>
    <div>6-1/55806</div>

    <b>Дата включения в Национальный реестр</b>
    <div>13.03.2026</div>

    <b>Дата вступления в силу</b>
    <div>15.03.2026</div>
</div>
</body>
</html>
"""


def test_parse_pravo_by_publications_returns_real_metadata() -> None:
    entries = parse_pravo_by_publications(
        PUBLICATIONS_HTML,
        base_url="https://pravo.by",
        registry="official_publication",
        registry_guid=PRAVO_BY_REGISTRY_GUIDS["official_publication"],
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.registry == "official_publication"
    assert entry.registry_number == "6-1/55801"
    assert entry.published_date == "12.03.2026"
    assert entry.source_code == "C22600119"
    assert entry.title == "О Министерстве архитектуры и строительства Республики Беларусь"
    assert entry.document_url == "https://pravo.by/document/?guid=12551&p0=C22600119"


def test_parse_pravo_by_document_metadata_returns_registry_card_fields() -> None:
    metadata = parse_pravo_by_document_metadata(
        REGISTRY_CARD_HTML,
        registry="national_registry",
        registry_guid=PRAVO_BY_REGISTRY_GUIDS["national_registry"],
        source_code="C22600122",
        document_url="https://pravo.by/document/?guid=3961&p0=C22600122",
    )

    assert metadata.registry == "national_registry"
    assert metadata.source_code == "C22600122"
    assert metadata.title == "О порядке взаимодействия при исполнении судебных решений о принудительном лечении"
    assert metadata.act_metadata == "Постановление Совета Министров Республики Беларусь от 12 марта 2026 г. № 122"
    assert metadata.registry_number == "6-1/55806"
    assert metadata.registry_inclusion_date == "13.03.2026"
    assert metadata.effective_date == "15.03.2026"


@pytest.mark.asyncio
async def test_compliance_route_returns_service_payload(container) -> None:
    app = container.fast_api_app().app

    async def fake_list_publications(**_: object) -> dict[str, object]:
        return {
            "source": {"selected_source": "pravo.by"},
            "registry": "official_publication",
            "publication_date": date(2026, 3, 13).isoformat(),
            "count": 1,
            "entries": [{"source_code": "C22600119", "title": "Real title"}],
        }

    service = container.compliance_source_service()
    original = service.list_publications
    service.list_publications = fake_list_publications  # type: ignore[method-assign]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/compliance/sources/pravo-by/publications",
                params={"publication_date": "2026-03-13", "registry": "official_publication"},
            )
    finally:
        service.list_publications = original  # type: ignore[method-assign]

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["entries"][0]["source_code"] == "C22600119"


@pytest.mark.asyncio
async def test_compliance_route_returns_503_when_source_unavailable(container) -> None:
    app = container.fast_api_app().app

    async def fail_document_metadata(**_: object) -> dict[str, object]:
        raise PravoByUnavailableError("pravo.by request failed: boom")

    service: ComplianceSourceService = container.compliance_source_service()
    original = service.get_document_metadata
    service.get_document_metadata = fail_document_metadata  # type: ignore[method-assign]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/compliance/sources/pravo-by/documents/C22600119")
    finally:
        service.get_document_metadata = original  # type: ignore[method-assign]

    assert response.status_code == 503
    assert "no_mock_data_returned" in response.text
