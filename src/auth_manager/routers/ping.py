from dependency_injector.wiring import Provide, inject
from fastapi import Request, status, Depends

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.dto.ping.ping import PingResponse
from src.auth_manager.routers.base import BaseRouter


class PingRouter(BaseRouter):
    """
    Роутер для проверки сервиса
    """

    def _init_routes(self):
        self.init_handler(self.__ping, HTTPMethod.GET, self._urls.ping, status.HTTP_200_OK)

    async def __ping(self)  -> PingResponse:
        return PingResponse(payload={})
