from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.routers.base import BaseRouter


class ReportRouter(BaseRouter):
    def _init_routes(self):
        self.init_handler(self.__overview, HTTPMethod.GET, "/report")

    async def __overview(self) -> dict[str, str | list[str]]:
        return {
            "domain": "report",
            "status": "ready",
            "capabilities": ["summary-generation", "docx-export"],
        }
