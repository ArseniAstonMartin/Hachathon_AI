from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.routers.base import BaseRouter


class TenancyRouter(BaseRouter):
    def _init_routes(self):
        self.init_handler(self.__overview, HTTPMethod.GET, "/tenancy")

    async def __overview(self) -> dict[str, str | list[str]]:
        return {
            "domain": "tenancy",
            "status": "ready",
            "capabilities": ["tenant-resolution", "access-scoping"],
        }
