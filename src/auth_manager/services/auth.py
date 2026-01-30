from datetime import datetime, timedelta, timezone
import bcrypt
from dependency_injector.providers import Factory
from jose import jwt
from fastapi import Request, Depends

from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.exceptions import BadRequestException, NotAuthorizedException, ForbiddenException
from src.auth_manager.components.injectable import injectable
from src.auth_manager.config import Settings
from src.auth_manager.dto.auth.register import RegisterRequestPayload, RegisterResponsePayload
from src.auth_manager.dto.auth.get_public_key import GetPublicKeyPayload
from src.auth_manager.dto.auth.login import LoginResponsePayload, LoginRequestPayload
from src.auth_manager.dto.auth.refresh import RefreshRequestPayload, RefreshResponsePayload
from src.auth_manager.dto.auth.update import UpdateMeRequestPayload
from src.auth_manager.dto.auth.me import MeResponsePayload
from src.auth_manager.models.user import Users
from src.auth_manager.repositories.auth import AuthRepository
from src.auth_manager.services.base import BaseService
from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient


@injectable(provider_class=Factory)
class AuthService(BaseService):
    """
    Логика работы с аутентификацией
    """

    def __init__(
            self,
            repository: AuthRepository,
            settings: Settings,
            database: AsyncDatabaseRelational,
            redis: AsyncRedisClient
    ,
    ):
        self._repository = repository
        self._database = database
        self._settings = settings
        self._redis = redis

    def _create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
        to_encode.update({"exp": expire})
        return jwt.encode(
            to_encode,
            self._settings.auth.private_key,
            algorithm=self._settings.auth.algorithm,
        )

    def _get_salt(self, string, rounds: int = 12, prefix: bytes = b"2b") -> bytes:
        str_res = ''
        for i in range(16):
            if len(str_res) >= 16:
                string = str_res[0:16]
                break
            else:
                str_res += string
        salt = bytes(string, 'ascii')
        output = bcrypt._bcrypt.encode_base64(salt)
        result = (
                b"$" + prefix + b"$" + str(rounds).encode("ascii") + b"$" + output
        )
        return result

    async def register(self, data: RegisterRequestPayload) -> RegisterResponsePayload:
        async with self._repository as repository:
            if data.password != data.password_repeat:
                raise BadRequestException("Passwords do not match")
            existing_user = await repository.find_one_by_filter_or_none(
                Users.email == data.email,
                include_deleted=True
            )
            if existing_user:
                raise BadRequestException("Email already taken")

            salt = self._get_salt(data.email)
            hashed_password = "sha256$" + bcrypt.hashpw(data.password.encode(), salt).decode()

            user = await repository.create(
                email=data.email,
                password=hashed_password,
                first_name=data.first_name,
                last_name=data.last_name,
                middle_name=data.middle_name,
                is_admin=False,
                is_localadmin=False,
                is_active=True
            )

            return RegisterResponsePayload(
                worker_id=str(user.worker_id),
                email=user.email,
                role="user",
                first_name=user.first_name,
                middle_name=user.middle_name,
                last_name=user.last_name
            )

    async def login(self, data: LoginRequestPayload):
        async with self._repository as repository:
            user = await repository.find_one_by_filter_or_none(
                Users.email == data.email,
                include_deleted=True
            )

            if not user:
                raise NotAuthorizedException()

            if not user.is_active:
                raise ForbiddenException()

            hash_pass = "sha256$" + bcrypt.hashpw(data.password.encode(), self._get_salt(data.email)).decode()
            if hash_pass != user.password:
                raise NotAuthorizedException()

            role = "admin" if user.is_admin else ("localadmin" if user.is_localadmin else "user")
            data_payload = {
                "sub": str(user.worker_id),
                "email": user.email,
                "role": role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "middle_name": user.middle_name
            }

            await self._redis.set(
                f"auth_session:{user.worker_id}",
                "active",
                ex=self._settings.auth.access_expires_delta * 60
            )

            access_token = self._create_access_token(
                data=data_payload,
                expires_delta=timedelta(minutes=self._settings.auth.access_expires_delta)
            )
            refresh_token = await repository.create_refresh_token(
                str(user.worker_id),
                data=data_payload,
                expires_delta=timedelta(minutes=self._settings.auth.refresh_expires_delta)
            )

        return LoginResponsePayload(
            access_token=access_token,
            refresh_token=refresh_token
        )

    async def update_me(self, user_id: str, data: UpdateMeRequestPayload):
        async with self._repository as repository:
            update_data = data.model_dump(exclude_unset=True)
            int_user_id = int(user_id)

            if not update_data:
                user = await repository.find_one_by_id(int_user_id)
            else:
                await repository.update(int_user_id, **update_data)
                user = await repository.find_one_by_id(int_user_id)
            return MeResponsePayload(
                id=str(user.worker_id),
                email=user.email,
                role="admin" if user.is_admin else ("localadmin" if user.is_localadmin else "user"),
                first_name=user.first_name,
                last_name=user.last_name,
                middle_name=user.middle_name
            )

    async def me(self, user):
        return MeResponsePayload(
            id=user['sub'],
            email=user.get('email'),
            role=user.get('role', 'user'),
            first_name=user.get('first_name', ''),
            middle_name=user.get('middle_name', ''),
            last_name=user.get('last_name', '')
        )

    async def logout(self, user_id: str):
        await self._redis.delete(f"auth_session:{user_id}")
        async with self._repository as repository:
            await repository.delete_refresh_token(user_id)

    async def get_public_key(self):
        return GetPublicKeyPayload(public_key=self._settings.auth.public_key)

    async def delete_me(self, user_id: str):
        int_id = int(user_id)
        async with self._repository as repository:
            await repository.update(int_id, is_active=False)
            await repository.delete_refresh_token(user_id)
        client = await self._redis.client
        await client.delete(f"auth_session:{user_id}")

    async def refresh(self, data: RefreshRequestPayload):
        async with self._repository as repository:
            try:
                payload = jwt.decode(
                    data.refresh_token,
                    self._settings.auth.public_key,
                    algorithms=[self._settings.auth.algorithm]
                )
            except:
                raise NotAuthorizedException()

            data_payload = {
                "sub": payload['sub'],
                "email": payload.get('email'),
                "role": payload.get('role', 'user'),
                "first_name": payload.get('first_name', ''),
                "last_name": payload.get('last_name', ''),
                "middle_name": payload.get('middle_name', '')
            }

            new_access_token = self._create_access_token(
                data=data_payload,
                expires_delta=timedelta(minutes=self._settings.auth.access_expires_delta)
            )
            new_refresh_token = await repository.create_refresh_token(
                str(payload['sub']),
                data=data_payload,
                expires_delta=timedelta(minutes=self._settings.auth.refresh_expires_delta)
            )
        return RefreshResponsePayload(access_token=new_access_token, refresh_token=new_refresh_token)