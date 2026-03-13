from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.storage import ObjectStorage, StorageArtifactType
from src.auth_manager.models import Document, DocumentExtension


@dataclass(frozen=True, slots=True)
class StoredDocumentMetadata:
    document_id: str
    storage_path: str
    checksum: str
    size_bytes: int


@injectable()
class DocumentIngestionService:
    def __init__(
        self,
        db: AsyncDatabaseRelational,
        object_storage: ObjectStorage,
    ) -> None:
        self._db = db
        self._object_storage = object_storage

    async def persist_telegram_document(
        self,
        *,
        tenant_id: str,
        user_id: str,
        file_name: str,
        mime_type: str,
        content: bytes,
    ) -> StoredDocumentMetadata:
        extension = DocumentExtension(Path(file_name).suffix.lower().lstrip("."))
        checksum = hashlib.sha256(content).hexdigest()
        size_bytes = len(content)
        object_name = self._build_object_name(user_id=user_id, file_name=file_name)

        storage_path = await self._object_storage.save_bytes(
            tenant_id=tenant_id,
            artifact_type=StorageArtifactType.SOURCE,
            object_name=object_name,
            content=content,
            content_type=mime_type,
        )

        session = await self._db.get_session()
        try:
            document = Document(
                tenant_id=uuid.UUID(tenant_id),
                uploaded_by_user_id=uuid.UUID(user_id),
                file_name=file_name,
                mime_type=mime_type,
                extension=extension,
                storage_path=storage_path,
                checksum=checksum,
                size_bytes=size_bytes,
            )
            session.add(document)
            await session.commit()
            return StoredDocumentMetadata(
                document_id=str(document.id),
                storage_path=storage_path,
                checksum=checksum,
                size_bytes=size_bytes,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @staticmethod
    def _build_object_name(*, user_id: str, file_name: str) -> str:
        sanitized_name = Path(file_name).name or "document"
        return f"documents/{user_id}/{uuid.uuid4()}-{sanitized_name}"
