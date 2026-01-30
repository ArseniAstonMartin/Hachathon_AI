from datetime import timedelta, datetime, UTC
from typing import Type, Optional

from dependency_injector.providers import Factory
from jose import jwt

from src.auth_manager.components.exceptions import NotFoundException
from src.auth_manager.components.injectable import injectable
from src.auth_manager.models.user import Users
from src.auth_manager.repositories.base import AbstractRelationalRepository

from sqlalchemy import update

@injectable(provider_class=Factory)
class AuthRepository(AbstractRelationalRepository[Users]):
    def get_model_class(self) -> Type[Users]:
        return Users

    def get_not_found_exception(self) -> NotFoundException:
        return NotFoundException("auth_manager.not-found")

    async def find_by_email(self, email: str) -> Optional[Users]:
        return await self.find_one_by_filter_or_none(self._model_class.email == email)

    async def create_refresh_token(self, name: str, data: dict, expires_delta: timedelta) -> str:
        client = await self._redis.client
        await client.delete(name)
        to_encode = data.copy()
        expire = datetime.now(UTC) + expires_delta
        to_encode.update({"exp": expire})
        token = jwt.encode(
            to_encode,
            self._settings.auth.private_key,
            algorithm=self._settings.auth.algorithm,
        )
        await client.set(name, token, ex=expires_delta)

        return token

    async def get_refresh_token(self, name: str) -> str:
        client = await self._redis.client
        return await client.get(name)

    async def delete_refresh_token(self, name: str) -> None:
        client = await self._redis.client
        await client.delete(name)

    async def get_user_by_email(self, email: str) -> Optional[Users]:
        return await self.find_one_by_filter_or_none(self._model_class.email == email)

    async def update_user_role(self, user_id: int, is_admin: bool, is_localadmin: bool) -> None:
        stmt = (
            update(self._model_class)
            .where(self._model_class.worker_id == user_id)
            .values(is_admin=is_admin, is_localadmin=is_localadmin)
        )
        await self._session.execute(stmt)