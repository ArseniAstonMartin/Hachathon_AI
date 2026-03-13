from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from dependency_injector.wiring import Provide
from sqlalchemy.exc import IntegrityError

from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient
from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.mixins.logger import LoggerMixin
from src.auth_manager.config import WorkerSettings
from src.auth_manager.models import ComparisonJob, ComparisonJobStatus


@injectable()
class ComparisonJobQueue(LoggerMixin):
    def __init__(
        self,
        redis: AsyncRedisClient,
        worker_settings: WorkerSettings = Provide["settings.provided.worker"],
    ) -> None:
        self._redis = redis
        self._worker_settings = worker_settings

    @property
    def queue_name(self) -> str:
        return self._worker_settings.queue_name

    async def enqueue(self, job_id: UUID) -> None:
        await self._redis.client.lpush(self.queue_name, str(job_id))
        self._logger.info("Queued comparison job %s", job_id)

    async def dequeue(self, timeout_seconds: int = 1) -> UUID | None:
        message = await self._redis.client.brpop(self.queue_name, timeout=timeout_seconds)
        if message is None:
            return None

        _, job_id = message
        return UUID(job_id)


@injectable()
class ComparisonJobService(LoggerMixin):
    def __init__(
        self,
        db: AsyncDatabaseRelational,
        queue: ComparisonJobQueue,
    ) -> None:
        self._db = db
        self._queue = queue

    async def create_and_enqueue_job(self, tenant_id: UUID, pair_id: UUID) -> ComparisonJob:
        session = await self._db.get_session()
        job = ComparisonJob(
            tenant_id=tenant_id,
            pair_id=pair_id,
            status=ComparisonJobStatus.QUEUED,
            current_stage=ComparisonJobStatus.QUEUED.value,
        )

        try:
            session.add(job)
            await session.commit()
            await session.refresh(job)
            await self._queue.enqueue(job.id)
            return job
        except IntegrityError:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_job(self, job_id: UUID) -> ComparisonJob | None:
        session = await self._db.get_session()
        try:
            return await session.get(ComparisonJob, job_id)
        finally:
            await session.close()

    async def mark_processing(self, job_id: UUID) -> ComparisonJob | None:
        return await self._update_job(
            job_id=job_id,
            status=ComparisonJobStatus.PROCESSING,
            current_stage="diff-processing",
            started_at=datetime.now(timezone.utc),
            error_message=None,
        )

    async def mark_completed(self, job_id: UUID) -> ComparisonJob | None:
        return await self._update_job(
            job_id=job_id,
            status=ComparisonJobStatus.COMPLETED,
            current_stage=ComparisonJobStatus.COMPLETED.value,
            finished_at=datetime.now(timezone.utc),
            error_message=None,
        )

    async def mark_failed(self, job_id: UUID, error_message: str) -> ComparisonJob | None:
        return await self._update_job(
            job_id=job_id,
            status=ComparisonJobStatus.FAILED,
            current_stage=ComparisonJobStatus.FAILED.value,
            finished_at=datetime.now(timezone.utc),
            error_message=error_message,
        )

    async def process_job(self, job_id: UUID) -> ComparisonJob:
        job = await self.mark_processing(job_id)
        if job is None:
            raise LookupError(f"Comparison job {job_id} was not found")

        return await self.mark_completed(job_id)

    async def _update_job(
        self,
        job_id: UUID,
        status: ComparisonJobStatus,
        current_stage: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error_message: str | None = None,
    ) -> ComparisonJob | None:
        session = await self._db.get_session()
        try:
            job = await session.get(ComparisonJob, job_id)
            if job is None:
                return None

            job.status = status
            job.current_stage = current_stage
            if started_at is not None:
                job.started_at = started_at
            if finished_at is not None:
                job.finished_at = finished_at
            job.error_message = error_message

            await session.commit()
            await session.refresh(job)
            self._logger.info("Updated comparison job %s to %s", job_id, status.value)
            return job
        finally:
            await session.close()
