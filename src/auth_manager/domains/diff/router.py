from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.domains.diff.services import ComparisonJobService
from src.auth_manager.routers.base import BaseRouter


class CreateComparisonJobRequest(BaseModel):
    tenant_id: UUID
    pair_id: UUID


class ComparisonJobResponse(BaseModel):
    job_id: UUID
    status: str
    current_stage: str


class DiffRouter(BaseRouter):
    def __init__(self, comparison_job_service: ComparisonJobService):
        self._comparison_job_service = comparison_job_service
        super().__init__()

    def _init_routes(self):
        self.init_handler(self.__overview, HTTPMethod.GET, "/diff")
        self.init_handler(
            self.__create_job,
            HTTPMethod.POST,
            "/diff/jobs",
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.init_handler(self.__get_job, HTTPMethod.GET, "/diff/jobs/{job_id}")

    async def __overview(self) -> dict[str, str | list[str]]:
        return {
            "domain": "diff",
            "status": "ready",
            "capabilities": ["structural-diff", "semantic-diff"],
        }

    async def __create_job(self, payload: CreateComparisonJobRequest) -> ComparisonJobResponse:
        try:
            job = await self._comparison_job_service.create_and_enqueue_job(
                tenant_id=payload.tenant_id,
                pair_id=payload.pair_id,
            )
        except IntegrityError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Comparison job references unknown tenant or document pair",
            ) from error

        return ComparisonJobResponse(
            job_id=job.id,
            status=job.status.value,
            current_stage=job.current_stage,
        )

    async def __get_job(self, job_id: UUID) -> ComparisonJobResponse:
        job = await self._comparison_job_service.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comparison job {job_id} not found",
            )

        return ComparisonJobResponse(
            job_id=job.id,
            status=job.status.value,
            current_stage=job.current_stage,
        )
