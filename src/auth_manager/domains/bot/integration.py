from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from src.auth_manager.components.injectable import injectable
from src.auth_manager.config import Settings
from src.auth_manager.domains.ingestion.services import DocumentIngestionService
from src.auth_manager.domains.bot.services import (
    AWAITING_SOURCE_DOCUMENT,
    AWAITING_TARGET_DOCUMENT,
    IDLE_DIALOG_STATE,
    TelegramBotService,
)
from src.auth_manager.domains.bot.security import (
    ResolvedTelegramPrincipal,
    TelegramAccessDenied,
    TelegramPrincipalResolver,
)


@dataclass(frozen=True, slots=True)
class ProcessedTelegramUpdate:
    update_id: int | None
    chat_id: str
    telegram_user_id: str
    event_type: str
    reply_message: str
    dialog_state: str
    internal_user_id: str | None = None
    tenant_id: str | None = None
    tenant_slug: str | None = None
    content_preview: str | None = None
    document_id: str | None = None
    storage_path: str | None = None
    checksum: str | None = None
    size_bytes: int | None = None


SUPPORTED_DOCUMENT_MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


@injectable()
class TelegramEventLog:
    def __init__(self) -> None:
        self._events: list[ProcessedTelegramUpdate] = []

    def append(self, event: ProcessedTelegramUpdate) -> None:
        self._events.append(event)
        if len(self._events) > 100:
            self._events = self._events[-100:]

    def recent(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self._events]


@injectable()
class TelegramUpdateProcessor:
    def __init__(
        self,
        settings: Settings,
        telegram_bot_service: TelegramBotService,
        telegram_event_log: TelegramEventLog,
        telegram_principal_resolver: TelegramPrincipalResolver,
        telegram_bot_api_client: "TelegramBotApiClient",
        document_ingestion_service: DocumentIngestionService,
    ) -> None:
        self._settings = settings
        self._telegram_bot_service = telegram_bot_service
        self._telegram_event_log = telegram_event_log
        self._telegram_principal_resolver = telegram_principal_resolver
        self._telegram_bot_api_client = telegram_bot_api_client
        self._document_ingestion_service = document_ingestion_service

    async def process(self, update: dict[str, Any]) -> ProcessedTelegramUpdate | None:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return None

        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = str(chat.get("id") or sender.get("id") or "")
        user_id = str(sender.get("id") or chat.get("id") or "")
        if not chat_id or not user_id:
            return None

        principal = await self._telegram_principal_resolver.resolve(
            telegram_user_id=user_id,
            telegram_username=self._extract_username(sender),
            telegram_full_name=self._extract_full_name(sender),
        )

        if isinstance(principal, TelegramAccessDenied):
            content_preview = message["text"].strip() if isinstance(message.get("text"), str) else None
            event = ProcessedTelegramUpdate(
                update_id=update.get("update_id"),
                chat_id=chat_id,
                telegram_user_id=user_id,
                event_type="access_denied",
                reply_message=principal.message,
                dialog_state=IDLE_DIALOG_STATE,
                content_preview=content_preview,
            )
            self._telegram_event_log.append(event)
            return event

        if isinstance(message.get("text"), str):
            text = message["text"].strip()
            reply = await self._telegram_bot_service.handle_message(user_id=user_id, text=text)
            event = ProcessedTelegramUpdate(
                update_id=update.get("update_id"),
                chat_id=chat_id,
                telegram_user_id=user_id,
                event_type="command",
                reply_message=reply.message,
                dialog_state=reply.dialog_state,
                internal_user_id=principal.internal_user_id,
                tenant_id=principal.tenant_id,
                tenant_slug=principal.tenant_slug,
                content_preview=text,
            )
        elif isinstance(message.get("document"), dict):
            event = await self._process_document_update(
                update_id=update.get("update_id"),
                chat_id=chat_id,
                user_id=user_id,
                principal=principal,
                document=message["document"],
            )
        else:
            return None

        self._telegram_event_log.append(event)
        return event

    def recent_events(self) -> list[dict[str, Any]]:
        return self._telegram_event_log.recent()

    async def _process_document_update(
        self,
        update_id: int | None,
        chat_id: str,
        user_id: str,
        principal: ResolvedTelegramPrincipal,
        document: dict[str, Any],
    ) -> ProcessedTelegramUpdate:
        file_name = str(document.get("file_name") or "document")
        validation_error = self._validate_document(file_name=file_name, document=document)
        if validation_error is not None:
            return ProcessedTelegramUpdate(
                update_id=update_id,
                chat_id=chat_id,
                telegram_user_id=user_id,
                event_type="document_rejected",
                reply_message=validation_error,
                dialog_state=self._telegram_bot_service.get_dialog_state(user_id),
                internal_user_id=principal.internal_user_id,
                tenant_id=principal.tenant_id,
                tenant_slug=principal.tenant_slug,
                content_preview=file_name,
            )

        current_state = self._telegram_bot_service.get_dialog_state(user_id)

        if current_state == AWAITING_SOURCE_DOCUMENT:
            metadata = await self._store_document(principal=principal, document=document, file_name=file_name)
            self._telegram_bot_service.set_dialog_state(user_id, AWAITING_TARGET_DOCUMENT)
            return ProcessedTelegramUpdate(
                update_id=update_id,
                chat_id=chat_id,
                telegram_user_id=user_id,
                event_type="document",
                reply_message=(
                    f"Файл {file_name} зафиксирован как исходная версия. "
                    "Теперь отправьте новую редакцию документа."
                ),
                dialog_state=AWAITING_TARGET_DOCUMENT,
                internal_user_id=principal.internal_user_id,
                tenant_id=principal.tenant_id,
                tenant_slug=principal.tenant_slug,
                content_preview=file_name,
                document_id=metadata.document_id,
                storage_path=metadata.storage_path,
                checksum=metadata.checksum,
                size_bytes=metadata.size_bytes,
            )

        if current_state == AWAITING_TARGET_DOCUMENT:
            metadata = await self._store_document(principal=principal, document=document, file_name=file_name)
            self._telegram_bot_service.set_dialog_state(user_id, IDLE_DIALOG_STATE)
            return ProcessedTelegramUpdate(
                update_id=update_id,
                chat_id=chat_id,
                telegram_user_id=user_id,
                event_type="document",
                reply_message=(
                    f"Файл {file_name} зафиксирован как новая версия. "
                    "Интеграционный слой принял обе версии без ошибки."
                ),
                dialog_state=IDLE_DIALOG_STATE,
                internal_user_id=principal.internal_user_id,
                tenant_id=principal.tenant_id,
                tenant_slug=principal.tenant_slug,
                content_preview=file_name,
                document_id=metadata.document_id,
                storage_path=metadata.storage_path,
                checksum=metadata.checksum,
                size_bytes=metadata.size_bytes,
            )

        return ProcessedTelegramUpdate(
            update_id=update_id,
            chat_id=chat_id,
            telegram_user_id=user_id,
            event_type="document",
            reply_message=(
                f"Файл {file_name} получен. Сначала отправьте команду /compare, "
                "чтобы выбрать сценарий загрузки документов."
            ),
            dialog_state=current_state,
            internal_user_id=principal.internal_user_id,
            tenant_id=principal.tenant_id,
            tenant_slug=principal.tenant_slug,
            content_preview=file_name,
        )

    def _validate_document(self, file_name: str, document: dict[str, Any]) -> str | None:
        extension = Path(file_name).suffix.lower()
        allowed_extensions = ", ".join(sorted(SUPPORTED_DOCUMENT_MIME_TYPES))
        expected_mime_type = SUPPORTED_DOCUMENT_MIME_TYPES.get(extension)
        mime_type = str(document.get("mime_type") or "").strip().lower()

        if expected_mime_type is None:
            return (
                f"Файл {file_name} отклонен: поддерживаются только {allowed_extensions}. "
                "Сохраните документ как .docx или .pdf и отправьте его повторно."
            )

        if mime_type != expected_mime_type:
            return (
                f"Файл {file_name} отклонен: MIME type {mime_type or 'не указан'} "
                f"не соответствует формату {extension}. "
                f"Экспортируйте документ заново в {extension} и повторите загрузку."
            )

        file_size = document.get("file_size")
        max_size = self._settings.telegram.max_document_size_bytes
        if isinstance(file_size, int) and file_size > max_size:
            return (
                f"Файл {file_name} отклонен: размер {file_size} байт превышает лимит {max_size} байт. "
                "Уменьшите размер файла или разделите документ и отправьте его снова."
            )

        return None

    async def _store_document(
        self,
        *,
        principal: ResolvedTelegramPrincipal,
        document: dict[str, Any],
        file_name: str,
    ):
        content = await self._load_document_content(document)
        mime_type = str(document.get("mime_type") or "").strip().lower()
        return await self._document_ingestion_service.persist_telegram_document(
            tenant_id=principal.tenant_id,
            user_id=principal.internal_user_id,
            file_name=file_name,
            mime_type=mime_type,
            content=content,
        )

    async def _load_document_content(self, document: dict[str, Any]) -> bytes:
        inline_content = document.get("content_base64")
        if isinstance(inline_content, str) and inline_content.strip():
            return base64.b64decode(inline_content.encode(), validate=True)

        file_id = str(document.get("file_id") or "").strip()
        if not file_id:
            raise ValueError("Telegram document payload does not contain file content or file_id")
        return await self._telegram_bot_api_client.download_file_bytes(file_id)

    @staticmethod
    def _extract_username(sender: dict[str, Any]) -> str | None:
        username = sender.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip()
        return None

    @staticmethod
    def _extract_full_name(sender: dict[str, Any]) -> str | None:
        parts = [
            str(sender.get("first_name") or "").strip(),
            str(sender.get("last_name") or "").strip(),
        ]
        full_name = " ".join(part for part in parts if part)
        return full_name or None


@injectable()
class TelegramBotApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": self._settings.telegram.polling_timeout_seconds,
        }
        if offset is not None:
            payload["offset"] = offset

        async with httpx.AsyncClient(timeout=self._settings.telegram.polling_timeout_seconds + 5) as client:
            response = await client.get(self._build_api_url("getUpdates"), params=payload)
            response.raise_for_status()
            data = response.json()
        return list(data.get("result", []))

    async def send_message(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self._build_api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()

    async def download_file_bytes(self, file_id: str) -> bytes:
        file_path = await self._resolve_file_path(file_id)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self._build_file_url(file_path))
            response.raise_for_status()
            return response.content

    async def _resolve_file_path(self, file_id: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self._build_api_url("getFile"), params={"file_id": file_id})
            response.raise_for_status()
            data = response.json()

        result = data.get("result") or {}
        file_path = result.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError(f"Telegram API did not return file_path for file_id={file_id}")
        return file_path.strip()

    def _build_api_url(self, method_name: str) -> str:
        base_url = self._settings.telegram.api_base_url.rstrip("/")
        return f"{base_url}/bot{self._settings.telegram.bot_token}/{method_name}"

    def _build_file_url(self, file_path: str) -> str:
        base_url = self._settings.telegram.api_base_url.rstrip("/")
        normalized_path = file_path.lstrip("/")
        return f"{base_url}/file/bot{self._settings.telegram.bot_token}/{normalized_path}"


@injectable()
class TelegramBackendGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def deliver_update(self, update: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self._settings.telegram.backend_updates_url,
                json=update,
            )
            response.raise_for_status()
            return response.json()
