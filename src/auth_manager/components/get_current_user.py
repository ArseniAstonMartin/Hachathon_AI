from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError

from src.auth_manager.components.exceptions import NotAuthorizedException
from src.auth_manager.config import Settings
from dependency_injector.wiring import Provide, inject
from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient

@inject
def decode(token, settings: Settings = Provide['settings']):
    return jwt.decode(token, settings.auth.public_key, algorithms=[settings.auth.algorithm])


@inject
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
        redis: AsyncRedisClient = Depends(Provide['async_redis_client'])
):
    if credentials is None:
        raise NotAuthorizedException()

    try:
        token = credentials.credentials
        payload = decode(token)
        user_id = payload.get("sub")

        session_exists = await redis.exists(f"auth_session:{user_id}")

        if not session_exists:
            raise NotAuthorizedException()

        return payload
    except Exception:
        raise NotAuthorizedException()