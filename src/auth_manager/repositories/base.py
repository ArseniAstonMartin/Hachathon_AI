from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar, Generic, Type, List, Optional, Any
from uuid import UUID

from dependency_injector.wiring import Provide
from sqlalchemy import select, update, delete, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta

from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient
from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.exceptions import NotFoundException
from src.auth_manager.config import Settings

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)


class AbstractRelationalRepository(Generic[ModelType], ABC):
    def __init__(
        self,
        db: AsyncDatabaseRelational = Provide['async_database_relational'],
        redis: AsyncRedisClient = Provide['async_redis_client'],
        settings: Settings = Provide['settings'],
    ):
        self._model_class = self.get_model_class()
        self._db = db
        self._redis = redis
        self._settings = settings
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> "AbstractRelationalRepository":
        self._session = await self._db.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            if exc_type is None:
                # Коммитим, если не было исключений
                await self._session.commit()
            else:
                # Откат при ошибке
                await self._session.rollback()
            await self._session.close()
            self._session = None

    @abstractmethod
    def get_model_class(self) -> Type[ModelType]:
        ...

    @abstractmethod
    def get_not_found_exception(self) -> NotFoundException:
        ...

    async def find_one_by_id_or_none(self, id: any) -> Optional[ModelType]:
        pk_column = inspect(self._model_class).primary_key[0]
        return await self.find_one_by_filter_or_none(pk_column == id)

    async def find_one_by_id(self, id: any) -> ModelType:
        obj = await self.find_one_by_id_or_none(id)
        if obj is None:
            raise self.get_not_found_exception()
        return obj

    async def find_one_by_filter_or_none(self, *conditions, include_deleted: bool = False) -> Optional[ModelType]:
        stmt = select(self._model_class).where(*conditions)

        if not include_deleted and hasattr(self._model_class, "is_active"):
            stmt = stmt.where(self._model_class.is_active.is_(True))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_one_by_filter(self, *conditions, include_deleted: bool = False) -> ModelType:
        obj = await self.find_one_by_filter_or_none(*conditions, include_deleted=include_deleted)
        if obj is None:
            raise self.get_not_found_exception()
        return obj

    async def find_many(self, offset=0, limit=100, filter_=None, sort=None) -> List[ModelType]:
        stmt = select(self._model_class)
        if filter_ is not None:
            stmt = stmt.where(filter_)
        if sort:
            stmt = stmt.order_by(*sort)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(self, *conditions) -> int:
        stmt = select(self._model_class).where(*conditions)
        result = await self._session.execute(stmt)
        return result.scalars().count()

    async def exists(self, *conditions) -> bool:
        stmt = select(self._model_class.id).where(*conditions)
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def save_one(self, model: ModelType) -> ModelType:
        self._session.add(model)
        await self._session.flush()
        return model

    async def create(self, **data) -> ModelType:
        obj = self._model_class(**data)
        self._session.add(obj)
        await self._session.flush()
        return obj

    async def save_many(self, models: List[ModelType]) -> List[ModelType]:
        self._session.add_all(models)
        await self._session.flush()
        return models

    async def update_many(self, models: List[ModelType]) -> None:
        for obj in models:
            self._session.add(obj)
        await self._session.flush()

    async def delete_by_filter(self, *conditions, force=False) -> int:
        if force:
            stmt = delete(self._model_class).where(*conditions)
            result = await self._session.execute(stmt)
        else:
            stmt = (
                update(self._model_class)
                .where(*conditions)
                .values(is_active=False)
            )
            result = await self._session.execute(stmt)
        return result.rowcount

    async def delete_one_by_filter(self, *conditions, force=False) -> None:
        count = await self.delete_by_filter(*conditions, force=force)
        if count == 0:
            raise self.get_not_found_exception()

    async def delete_one_by_id(self, id: UUID, force=False) -> None:
        await self.delete_one_by_filter(self._model_class.id == id, force=force)

    async def update(self, id: Any, **data) -> None:
        pk_column = inspect(self._model_class).primary_key[0]
        stmt = update(self._model_class).where(pk_column == id).values(**data)
        await self._session.execute(stmt)