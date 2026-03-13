from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.auth_manager.components.register_modules import register_modules
from src.auth_manager.di import DependencyInjector
from src.auth_manager.models import ComparisonJob, Document, DocumentExtension, DocumentVersionPair, Tenant, User
from tests.config import TestSettings as DiffTestSettings


def _create_test_container():
    DependencyInjector.settings.reset_override()
    DependencyInjector.settings.override(DiffTestSettings())
    register_modules(package_name="src", container=DependencyInjector)
    container = DependencyInjector()
    container.wire(packages=["src"])
    return container


@pytest_asyncio.fixture(scope="function")
async def comparison_job_schema():
    sync_url = DiffTestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    tables = [
        Tenant.__table__,
        User.__table__,
        Document.__table__,
        DocumentVersionPair.__table__,
        ComparisonJob.__table__,
    ]

    ComparisonJob.metadata.create_all(engine, tables=tables)

    yield

    ComparisonJob.metadata.drop_all(engine, tables=tables)
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def comparison_job_payload(comparison_job_schema):
    sync_url = DiffTestSettings().database.url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url)
    session = Session(engine)

    tenant = Tenant(id=uuid4(), name="Tenant A", slug=f"tenant-{uuid4().hex[:8]}")
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        telegram_user_id=str(uuid4().int),
        username="queue-user",
        full_name="Queue User",
    )
    old_document = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        uploaded_by_user_id=user.id,
        file_name="old.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        extension=DocumentExtension.DOCX,
        storage_path="tenant-a/documents/old.docx",
        checksum="old-checksum",
        size_bytes=128,
    )
    new_document = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        uploaded_by_user_id=user.id,
        file_name="new.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        extension=DocumentExtension.DOCX,
        storage_path="tenant-a/documents/new.docx",
        checksum="new-checksum",
        size_bytes=256,
    )
    pair = DocumentVersionPair(
        id=uuid4(),
        tenant_id=tenant.id,
        old_document_id=old_document.id,
        new_document_id=new_document.id,
        created_by_user_id=user.id,
    )

    session.add(tenant)
    session.flush()
    session.add(user)
    session.flush()
    session.add_all([old_document, new_document])
    session.flush()
    session.add(pair)
    session.commit()
    tenant_id = tenant.id
    pair_id = pair.id
    session.close()
    engine.dispose()

    return {"tenant_id": str(tenant_id), "pair_id": str(pair_id)}


@pytest.mark.asyncio
async def test_comparison_job_is_queued_and_processed(comparison_job_payload):
    container = _create_test_container()
    app = container.fast_api_app().app
    redis = container.async_redis_client().client
    worker_runtime = container.worker_runtime()

    await redis.delete(container.settings().worker.queue_name)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/diff/jobs", json=comparison_job_payload)

        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["current_stage"] == "queued"

        queue_depth = await redis.llen(container.settings().worker.queue_name)
        assert queue_depth == 1

        processed = await worker_runtime.run_once(timeout_seconds=1)
        assert processed is True

        job_response = await client.get(f"/diff/jobs/{payload['job_id']}")

    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert job_response.json()["current_stage"] == "completed"
