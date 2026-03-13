from abc import ABC, abstractmethod
from enum import StrEnum


class StorageArtifactType(StrEnum):
    SOURCE = "source"
    REPORT = "report"


class ObjectStorage(ABC):
    @abstractmethod
    async def save_bytes(
        self,
        *,
        tenant_id: str,
        artifact_type: StorageArtifactType,
        object_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def read_bytes(self, object_path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, object_path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def build_object_path(
        self,
        *,
        tenant_id: str,
        artifact_type: StorageArtifactType,
        object_name: str,
    ) -> str:
        raise NotImplementedError
