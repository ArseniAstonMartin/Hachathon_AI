import asyncio
import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from src.auth_manager.domains.bot.integration import TelegramBackendGateway, TelegramBotApiClient
from src.auth_manager.models import Document, Tenant, User
from src.auth_manager.runtime.bot import BotRuntime
from tests.config import TestSettings


def _install_storage_fake(monkeypatch) -> dict[str, bytes]:
    stored_objects: dict[str, bytes] = {}

    async def fake_save_bytes(self, *, tenant_id, artifact_type, object_name, content, content_type=None):
        object_path = self.build_object_path(
            tenant_id=tenant_id,
            artifact_type=artifact_type,
            object_name=object_name,
        )
        stored_objects[object_path] = content
        return object_path

    async def fake_exists(self, object_path: str) -> bool:
        return object_path in stored_objects

    async def fake_read_bytes(self, object_path: str) -> bytes:
        return stored_objects[object_path]

    monkeypatch.setattr(
        "src.auth_manager.components.storage.s3.S3ObjectStorage.save_bytes",
        fake_save_bytes,
    )
    monkeypatch.setattr(
        "src.auth_manager.components.storage.s3.S3ObjectStorage.exists",
        fake_exists,
    )
    monkeypatch.setattr(
        "src.auth_manager.components.storage.s3.S3ObjectStorage.read_bytes",
        fake_read_bytes,
    )

    return stored_objects


@pytest_asyncio.fixture(scope="function")
async def telegram_identity_schema():
    sync_url = TestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    tables = [Tenant.__table__, User.__table__, Document.__table__]
    Tenant.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        session.execute(delete(Document))
        session.execute(delete(User))
        session.execute(delete(Tenant))
        session.commit()

    yield

    with Session(engine) as session:
        session.execute(delete(Document))
        session.execute(delete(User))
        session.execute(delete(Tenant))
        session.commit()
    engine.dispose()


@pytest.mark.asyncio
async def test_bot_runtime_handles_start_help_and_compare(
    container,
    telegram_identity_schema,
):
    bot_runtime = container.bot_runtime()
    start_reply = await bot_runtime.handle_update(user_id="test-user", text="/start")
    assert "сравнить две версии документа" in start_reply["message"].lower()
    assert "/compare" in start_reply["message"]
    assert start_reply["dialog_state"] == "idle"

    help_reply = await bot_runtime.handle_update(user_id="test-user", text="/help")
    assert ".docx" in help_reply["message"]
    assert ".pdf" in help_reply["message"]
    assert "слишком большие файлы" in help_reply["message"].lower()
    assert help_reply["dialog_state"] == "idle"

    compare_reply = await bot_runtime.handle_update(user_id="test-user", text="/compare")
    assert "отправьте старую редакцию документа" in compare_reply["message"].lower()
    assert compare_reply["dialog_state"] == "awaiting_source_document"
    assert bot_runtime.get_dialog_state("test-user") == "awaiting_source_document"


def test_bot_runtime_reports_startup_summary(
    container,
):
    bot_runtime = container.bot_runtime()
    summary = bot_runtime.startup_summary()
    assert "polling" in summary
    assert "bot" in summary


@pytest.mark.asyncio
async def test_bot_update_endpoint_processes_commands_and_documents(container, telegram_identity_schema, monkeypatch):
    app = container.fast_api_app().app
    storage = container.object_storage()
    stored_objects = _install_storage_fake(monkeypatch)
    old_content = b"old contract revision"
    new_content = b"new contract revision"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compare_response = await client.post(
            "/bot/telegram/updates",
            json=BotRuntime.build_text_update(user_id=42, text="/compare", update_id=1),
        )
        assert compare_response.status_code == 200
        assert compare_response.json()["dialog_state"] == "awaiting_source_document"
        assert compare_response.json()["tenant_slug"] == "acme-mvp"
        assert compare_response.json()["tenant_id"]
        assert compare_response.json()["internal_user_id"]

        document_response = await client.post(
            "/bot/telegram/updates",
            json={
                "update_id": 2,
                "message": {
                    "message_id": 2,
                    "from": {"id": 42, "is_bot": False},
                    "chat": {"id": 42, "type": "private"},
                    "document": {
                        "file_id": "file-1",
                        "file_name": "old.docx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "file_size": len(old_content),
                        "content_base64": base64.b64encode(old_content).decode(),
                    },
                },
            },
        )
        assert document_response.status_code == 200
        assert document_response.json()["event_type"] == "document"
        assert document_response.json()["dialog_state"] == "awaiting_target_document"
        assert document_response.json()["tenant_slug"] == "acme-mvp"
        assert document_response.json()["document_id"]
        assert document_response.json()["storage_path"]
        assert document_response.json()["checksum"] == hashlib.sha256(old_content).hexdigest()
        assert document_response.json()["size_bytes"] == len(old_content)

        target_document_response = await client.post(
            "/bot/telegram/updates",
            json={
                "update_id": 3,
                "message": {
                    "message_id": 3,
                    "from": {"id": 42, "is_bot": False},
                    "chat": {"id": 42, "type": "private"},
                    "document": {
                        "file_id": "file-2",
                        "file_name": "new.pdf",
                        "mime_type": "application/pdf",
                        "file_size": len(new_content),
                        "content_base64": base64.b64encode(new_content).decode(),
                    },
                },
            },
        )
        assert target_document_response.status_code == 200
        assert target_document_response.json()["event_type"] == "document"
        assert target_document_response.json()["dialog_state"] == "idle"
        assert target_document_response.json()["tenant_slug"] == "acme-mvp"
        assert target_document_response.json()["document_id"]
        assert target_document_response.json()["storage_path"]
        assert target_document_response.json()["checksum"] == hashlib.sha256(new_content).hexdigest()
        assert target_document_response.json()["size_bytes"] == len(new_content)

        events_response = await client.get("/bot/telegram/events")
        assert events_response.status_code == 200
        events = events_response.json()["events"]
        assert any(event["event_type"] == "command" for event in events)
        assert any(event["content_preview"] == "old.docx" for event in events)
        assert any(event["content_preview"] == "new.pdf" for event in events)

    sync_url = TestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == "acme-mvp"))
        assert tenant is not None
        user = session.scalar(select(User).where(User.telegram_user_id == "42"))
        assert user is not None
        assert user.tenant_id == tenant.id
        documents = session.scalars(select(Document).where(Document.uploaded_by_user_id == user.id)).all()
        assert len(documents) == 2
        documents_by_name = {document.file_name: document for document in documents}
        old_document = documents_by_name["old.docx"]
        assert old_document.tenant_id == tenant.id
        assert old_document.storage_path.startswith(f"{tenant.id}/source/documents/{user.id}/")
        assert old_document.checksum == hashlib.sha256(old_content).hexdigest()
        assert old_document.size_bytes == len(old_content)
        assert old_document.storage_path in stored_objects
        assert stored_objects[old_document.storage_path] == old_content
        new_document = documents_by_name["new.pdf"]
        assert new_document.tenant_id == tenant.id
        assert new_document.storage_path.startswith(f"{tenant.id}/source/documents/{user.id}/")
        assert new_document.checksum == hashlib.sha256(new_content).hexdigest()
        assert new_document.size_bytes == len(new_content)
        assert new_document.storage_path in stored_objects
        assert stored_objects[new_document.storage_path] == new_content
    engine.dispose()
    assert await storage.exists(old_document.storage_path) is True
    assert await storage.read_bytes(new_document.storage_path) == new_content


@pytest.mark.asyncio
async def test_bot_update_endpoint_keeps_metadata_on_repeated_document_uploads(
    container,
    telegram_identity_schema,
    monkeypatch,
):
    app = container.fast_api_app().app
    stored_objects = _install_storage_fake(monkeypatch)
    first_content = b"repeat upload version one"
    second_content = b"repeat upload version two"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for update_id, payload in (
            (
                41,
                {
                    "file_id": "repeat-1",
                    "file_name": "same.pdf",
                    "mime_type": "application/pdf",
                    "file_size": len(first_content),
                    "content_base64": base64.b64encode(first_content).decode(),
                },
            ),
            (
                43,
                {
                    "file_id": "repeat-2",
                    "file_name": "same.pdf",
                    "mime_type": "application/pdf",
                    "file_size": len(second_content),
                    "content_base64": base64.b64encode(second_content).decode(),
                },
            ),
        ):
            compare_response = await client.post(
                "/bot/telegram/updates",
                json=BotRuntime.build_text_update(user_id=42, text="/compare", update_id=update_id - 1),
            )
            assert compare_response.status_code == 200
            assert compare_response.json()["dialog_state"] == "awaiting_source_document"

            document_response = await client.post(
                "/bot/telegram/updates",
                json={
                    "update_id": update_id,
                    "message": {
                        "message_id": update_id,
                        "from": {"id": 42, "is_bot": False},
                        "chat": {"id": 42, "type": "private"},
                        "document": payload,
                    },
                },
            )
            assert document_response.status_code == 200
            assert document_response.json()["event_type"] == "document"
            assert document_response.json()["document_id"]
            assert document_response.json()["storage_path"]

    sync_url = TestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.telegram_user_id == "42"))
        assert user is not None
        documents = session.scalars(
            select(Document)
            .where(Document.uploaded_by_user_id == user.id, Document.file_name == "same.pdf")
            .order_by(Document.created_at.asc())
        ).all()
        assert len(documents) == 2
        assert documents[0].storage_path != documents[1].storage_path
        assert {document.checksum for document in documents} == {
            hashlib.sha256(first_content).hexdigest(),
            hashlib.sha256(second_content).hexdigest(),
        }
        assert {document.size_bytes for document in documents} == {
            len(first_content),
            len(second_content),
        }
        assert {stored_objects[path] for path in stored_objects} == {first_content, second_content}
    engine.dispose()


@pytest.mark.asyncio
async def test_bot_update_endpoint_rejects_unmapped_telegram_user(container, telegram_identity_schema):
    app = container.fast_api_app().app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/bot/telegram/updates",
            json=BotRuntime.build_text_update(user_id=404, text="/start", update_id=11),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_type"] == "access_denied"
    assert payload["tenant_id"] is None
    assert payload["internal_user_id"] is None
    assert "Обратитесь к администратору" in payload["reply_message"]

    sync_url = TestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        denied_user = session.scalar(select(User).where(User.telegram_user_id == "404"))
        assert denied_user is None
    engine.dispose()


@pytest.mark.asyncio
async def test_bot_update_endpoint_rejects_unsupported_document_type(container, telegram_identity_schema):
    app = container.fast_api_app().app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compare_response = await client.post(
            "/bot/telegram/updates",
            json=BotRuntime.build_text_update(user_id=42, text="/compare", update_id=20),
        )
        assert compare_response.status_code == 200
        assert compare_response.json()["dialog_state"] == "awaiting_source_document"

        invalid_document_response = await client.post(
            "/bot/telegram/updates",
            json={
                "update_id": 21,
                "message": {
                    "message_id": 21,
                    "from": {"id": 42, "is_bot": False},
                    "chat": {"id": 42, "type": "private"},
                    "document": {
                        "file_id": "file-3",
                        "file_name": "notes.txt",
                        "mime_type": "text/plain",
                        "file_size": 128,
                    },
                },
            },
        )

    assert invalid_document_response.status_code == 200
    payload = invalid_document_response.json()
    assert payload["event_type"] == "document_rejected"
    assert payload["dialog_state"] == "awaiting_source_document"
    assert "поддерживаются только .docx, .pdf" in payload["reply_message"].lower()
    assert "отправьте его повторно" in payload["reply_message"].lower()


@pytest.mark.asyncio
async def test_bot_update_endpoint_rejects_too_large_document(container, telegram_identity_schema):
    app = container.fast_api_app().app
    max_size = container.settings().telegram.max_document_size_bytes
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compare_response = await client.post(
            "/bot/telegram/updates",
            json=BotRuntime.build_text_update(user_id=42, text="/compare", update_id=30),
        )
        assert compare_response.status_code == 200
        assert compare_response.json()["dialog_state"] == "awaiting_source_document"

        oversized_document_response = await client.post(
            "/bot/telegram/updates",
            json={
                "update_id": 31,
                "message": {
                    "message_id": 31,
                    "from": {"id": 42, "is_bot": False},
                    "chat": {"id": 42, "type": "private"},
                    "document": {
                        "file_id": "file-4",
                        "file_name": "large.docx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "file_size": max_size + 1,
                    },
                },
            },
        )

    assert oversized_document_response.status_code == 200
    payload = oversized_document_response.json()
    assert payload["event_type"] == "document_rejected"
    assert payload["dialog_state"] == "awaiting_source_document"
    assert "превышает лимит" in payload["reply_message"].lower()
    assert "уменьшите размер файла" in payload["reply_message"].lower()


class _FakeTelegramApiHandler(BaseHTTPRequestHandler):
    updates: list[dict] = []
    sent_messages: list[dict] = []

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/bottest-telegram-token/getUpdates"):
            payload = {"ok": True, "result": self.__class__.updates[:1]}
            if self.__class__.updates:
                self.__class__.updates = self.__class__.updates[1:]
            self._write_json(200, payload)
            return
        self._write_json(404, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/bottest-telegram-token/sendMessage"):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b"{}"
            self.__class__.sent_messages.append(json.loads(body.decode()))
            self._write_json(200, {"ok": True, "result": {"message_id": 1}})
            return
        self._write_json(404, {"ok": False})

    def log_message(self, format: str, *args) -> None:
        return

    def _write_json(self, status_code: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@pytest.mark.asyncio
async def test_polling_runtime_forwards_updates_to_backend_and_replies(container, telegram_identity_schema):
    app = container.fast_api_app().app

    class BackendGatewayStub(TelegramBackendGateway):
        async def deliver_update(self, update: dict) -> dict:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/bot/telegram/updates", json=update)
                response.raise_for_status()
                return response.json()

    _FakeTelegramApiHandler.updates = [BotRuntime.build_text_update(user_id=1001, text="/start", update_id=10)]
    _FakeTelegramApiHandler.sent_messages = []
    server = ThreadingHTTPServer(("127.0.0.1", 8999), _FakeTelegramApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    bot_runtime = BotRuntime(
        settings=container.settings(),
        telegram_bot_service=container.telegram_bot_service(),
        telegram_update_processor=container.telegram_update_processor(),
        telegram_bot_api_client=TelegramBotApiClient(container.settings()),
        telegram_backend_gateway=BackendGatewayStub(container.settings()),
    )

    try:
        updates = await bot_runtime._telegram_bot_api_client.get_updates()
        assert len(updates) == 1
        result = await bot_runtime.process_polled_update(updates[0])
        assert result["status"] == "processed"
        assert result["event_type"] == "command"

        await asyncio.sleep(0.1)
        assert _FakeTelegramApiHandler.sent_messages
        assert _FakeTelegramApiHandler.sent_messages[0]["chat_id"] == "1001"
        assert "/compare" in _FakeTelegramApiHandler.sent_messages[0]["text"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
