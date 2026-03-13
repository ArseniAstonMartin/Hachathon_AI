from __future__ import annotations

import asyncio

from src.auth_manager.config import Settings
from src.auth_manager.domains import DOMAIN_DESCRIPTORS
from src.auth_manager.domains.diff.services import ComparisonJobQueue, ComparisonJobService
from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient


class WorkerRuntime:
    def __init__(
        self,
        settings: Settings,
        redis: AsyncRedisClient,
        comparison_job_queue: ComparisonJobQueue,
        comparison_job_service: ComparisonJobService,
    ):
        self._settings = settings
        self._redis = redis
        self._comparison_job_queue = comparison_job_queue
        self._comparison_job_service = comparison_job_service
        self._domains = tuple(
            descriptor for descriptor in DOMAIN_DESCRIPTORS if descriptor.layer == "worker"
        )

    @property
    def queue_name(self) -> str:
        return self._settings.worker.queue_name

    @property
    def domains(self):
        return self._domains

    async def run_once(self, timeout_seconds: int = 1) -> bool:
        job_id = await self._comparison_job_queue.dequeue(timeout_seconds=timeout_seconds)
        if job_id is None:
            return False

        try:
            await self._comparison_job_service.process_job(job_id)
        except Exception as error:
            await self._comparison_job_service.mark_failed(job_id, str(error))
            raise

        return True

    async def run(self) -> None:
        await self._redis.ping()
        self._log_startup()

        while True:
            await self.run_once(timeout_seconds=1)
            await asyncio.sleep(0)

    def _log_startup(self) -> None:
        domain_names = ", ".join(descriptor.name for descriptor in self._domains)
        print(
            f"Worker runtime connected to Redis queue '{self.queue_name}' "
            f"for domains: {domain_names}"
        )
