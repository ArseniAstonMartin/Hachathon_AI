from redis import asyncio as aioredis
from dependency_injector.wiring import Provide

from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.mixins.logger import LoggerMixin
from src.auth_manager.config import RedisSettings


@injectable()
class AsyncRedisClient(LoggerMixin):
    def __init__(
        self,
        redis_config: RedisSettings = Provide["settings.provided.redis"]
    ) -> None:
        self.__redis_config = redis_config
        self._logger.info(
            f"Async Redis client created (host={redis_config.host}, port={redis_config.port}, db={redis_config.db})"
        )

        self._client = aioredis.from_url(
            f"redis://{self.__redis_config.host}:{self.__redis_config.port}/{self.__redis_config.db}",
            password=self.__redis_config.password,
            decode_responses=True,
        )

    async def set(self, key: str, value: str, ex: int = None):
        return await self._client.set(key, value, ex=ex)

    async def exists(self, key: str) -> bool:
        return await self._client.exists(key)

    async def delete(self, key: str):
        return await self._client.delete(key)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        return self._client
