from datetime import date

from dependency_injector.wiring import Provide, inject
from fastapi import HTTPException, Query, status

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.domains.compliance.services import (
    ComplianceSourceService,
    PravoByRegistry,
    PravoByUnavailableError,
)
from src.auth_manager.routers.base import BaseRouter


class ComplianceRouter(BaseRouter):
    @inject
    def __init__(
        self,
        compliance_source_service: ComplianceSourceService = Provide["compliance_source_service"],
    ) -> None:
        self._compliance_source_service = compliance_source_service
        super().__init__()

    def _init_routes(self):
        self.init_handler(self.__overview, HTTPMethod.GET, "/compliance")
        self.init_handler(self.__publications, HTTPMethod.GET, "/compliance/sources/pravo-by/publications")
        self.init_handler(self.__document_metadata, HTTPMethod.GET, "/compliance/sources/pravo-by/documents/{source_code}")

    async def __overview(self) -> dict[str, object]:
        overview = self._compliance_source_service.source_overview()
        overview.update(
            {
                "domain": "compliance",
                "status": "ready",
                "capabilities": [
                    "legal-hierarchy-check",
                    "authority-linking",
                    "pravo-by-publications",
                    "pravo-by-document-metadata",
                ],
            }
        )
        return overview

    async def __publications(
        self,
        publication_date: date | None = Query(default=None),
        registry: PravoByRegistry = Query(default="official_publication"),
        limit: int | None = Query(default=None, ge=1, le=50),
    ) -> dict[str, object]:
        try:
            return await self._compliance_source_service.list_publications(
                publication_date=publication_date,
                registry=registry,
                limit=limit,
            )
        except PravoByUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": str(exc),
                    "fallback_behavior": "no_mock_data_returned",
                },
            ) from exc

    async def __document_metadata(
        self,
        source_code: str,
        registry: PravoByRegistry = Query(default="official_publication"),
    ) -> dict[str, object]:
        try:
            return await self._compliance_source_service.get_document_metadata(
                source_code=source_code,
                registry=registry,
            )
        except PravoByUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": str(exc),
                    "fallback_behavior": "no_mock_data_returned",
                },
            ) from exc
