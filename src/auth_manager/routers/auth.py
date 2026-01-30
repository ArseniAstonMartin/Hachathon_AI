from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import Request, status, Depends

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.components.get_current_user import get_current_user
from src.auth_manager.dto.auth.get_public_key import GetPublicKeyResponse
from src.auth_manager.dto.auth.register import RegisterRequest, RegisterResponse
from src.auth_manager.dto.auth.login import LoginRequest, LoginResponse
from src.auth_manager.dto.auth.refresh import RefreshRequest, RefreshResponse
from src.auth_manager.dto.auth.logout import LogoutResponse, LogoutResponsePayload
from src.auth_manager.dto.auth.me import MeResponse
from src.auth_manager.dto.auth.update import UpdateMeRequest, UpdateMeResponse
from src.auth_manager.dto.auth.delete import DeleteMeResponse, DeleteMeResponsePayload
from src.auth_manager.components.exceptions import ForbiddenException
from src.auth_manager.routers.base import BaseRouter
from src.auth_manager.services.auth import AuthService
from sqlalchemy import update, inspect


class AuthRouter(BaseRouter):
    """
    Роутер для аунтификации
    """

    @property
    @inject
    def service(
            self, service: AuthService = Provide["auth_service"]
    ) -> AuthService:
        return service

    def _init_routes(self):
        self.init_handler(self.__login, HTTPMethod.POST, self._urls.login, status.HTTP_200_OK)
        self.init_handler(self.__me, HTTPMethod.GET, self._urls.me, status.HTTP_200_OK)
        self.init_handler(self.__get_public_key, HTTPMethod.GET, self._urls.get_public_key, status.HTTP_200_OK)
        self.init_handler(self.__refresh, HTTPMethod.POST, self._urls.refresh, status.HTTP_200_OK)
        self.init_handler(self.__register, HTTPMethod.POST, self._urls.register, status.HTTP_201_CREATED)
        self.init_handler(self.__logout, HTTPMethod.POST, self._urls.logout, status.HTTP_200_OK)
        self.init_handler(self.__update_me, HTTPMethod.PATCH, "/me", status.HTTP_200_OK)
        self.init_handler(self.__delete_me, HTTPMethod.DELETE, "/me", status.HTTP_200_OK)
        self.init_handler(self.__admin_only_resource, HTTPMethod.GET, "/admin/check", status.HTTP_200_OK)

    async def __login(self, data: LoginRequest) -> LoginResponse:
        data = data.payload
        response = await self.service.login(data)
        return LoginResponse(payload=response)

    async def __me(self, user=Depends(get_current_user)) -> MeResponse:
        response = await self.service.me(user)
        return MeResponse(payload=response)

    async def __get_public_key(self) -> GetPublicKeyResponse:
        response = await self.service.get_public_key()
        return GetPublicKeyResponse(payload=response)

    async def __refresh(self, data: RefreshRequest) -> RefreshResponse:
        data = data.payload
        response = await self.service.refresh(data)
        return RefreshResponse(payload=response)

    async def __register(self, data: RegisterRequest) -> RegisterResponse:
        response_payload = await self.service.register(data.payload)
        return RegisterResponse(payload=response_payload)

    async def __logout(self, user=Depends(get_current_user)) -> LogoutResponse:
        user_id = user.get("sub")
        await self.service.logout(user_id)
        return LogoutResponse(payload=LogoutResponsePayload())

    async def __update_me(self, data: UpdateMeRequest, user=Depends(get_current_user)) -> UpdateMeResponse:
        user_id = user.get("sub")
        response_payload = await self.service.update_me(user_id, data.payload)
        return UpdateMeResponse(payload=response_payload)

    async def __delete_me(self, user=Depends(get_current_user)) -> DeleteMeResponse:
        user_id = user.get("sub")
        await self.service.delete_me(user_id)
        return DeleteMeResponse(payload=DeleteMeResponsePayload())

    async def __admin_only_resource(self, user=Depends(get_current_user)):
        """
        ТЗ: Если пользователь определен, но ресурс недоступен — 403 ошибка
        """
        if user.get("role") != "admin":
            raise ForbiddenException()
        return {"status": "success", "message": "Admin access granted"}