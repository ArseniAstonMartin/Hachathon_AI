from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.routers.base import BaseRouter


class HealthRouter(BaseRouter):
    def _init_routes(self):
        self.init_handler(self.__health, HTTPMethod.GET, "/health")

    async def __health(self) -> dict[str, str]:
        return {"status": "ok", "service": "fastapi-auth-service"}
