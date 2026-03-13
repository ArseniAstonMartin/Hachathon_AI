import asyncio
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import ClientError
from dependency_injector.wiring import Provide

from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.mixins.logger import LoggerMixin
from src.auth_manager.components.storage.base import ObjectStorage, StorageArtifactType
from src.auth_manager.config import StorageSettings


@injectable()
class S3ObjectStorage(LoggerMixin, ObjectStorage):
    def __init__(
        self,
        storage_config: StorageSettings = Provide["settings.provided.storage"],
    ) -> None:
        self._storage_config = storage_config
        self._client = boto3.client(
            "s3",
            endpoint_url=storage_config.endpoint_url,
            aws_access_key_id=storage_config.access_key,
            aws_secret_access_key=storage_config.secret_key,
            region_name=storage_config.region,
            use_ssl=storage_config.secure,
        )
        self._bucket_name = storage_config.bucket
        self._bucket_initialized = False

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def build_object_path(
        self,
        *,
        tenant_id: str,
        artifact_type: StorageArtifactType,
        object_name: str,
    ) -> str:
        tenant_prefix = tenant_id.strip().strip("/")
        object_suffix = object_name.strip().lstrip("/")
        if not tenant_prefix:
            raise ValueError("tenant_id must not be empty")
        if not object_suffix:
            raise ValueError("object_name must not be empty")

        normalized = PurePosixPath(tenant_prefix) / artifact_type.value / object_suffix
        return normalized.as_posix()

    async def save_bytes(
        self,
        *,
        tenant_id: str,
        artifact_type: StorageArtifactType,
        object_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        object_path = self.build_object_path(
            tenant_id=tenant_id,
            artifact_type=artifact_type,
            object_name=object_name,
        )
        await asyncio.to_thread(self._ensure_bucket_exists)

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket_name,
            Key=object_path,
            Body=content,
            **extra_args,
        )
        self._logger.info("Stored object in bucket=%s key=%s", self._bucket_name, object_path)
        return object_path

    async def read_bytes(self, object_path: str) -> bytes:
        await asyncio.to_thread(self._ensure_bucket_exists)
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket_name,
            Key=object_path,
        )
        body = response["Body"]
        return await asyncio.to_thread(body.read)

    async def exists(self, object_path: str) -> bool:
        await asyncio.to_thread(self._ensure_bucket_exists)
        try:
            await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket_name,
                Key=object_path,
            )
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey"}:
                return False
            raise

        return True

    def _ensure_bucket_exists(self) -> None:
        if self._bucket_initialized:
            return

        try:
            self._client.head_bucket(Bucket=self._bucket_name)
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code not in {"404", "NoSuchBucket"}:
                raise

            create_bucket_kwargs = {"Bucket": self._bucket_name}
            if self._storage_config.region != "us-east-1":
                create_bucket_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": self._storage_config.region,
                }

            self._client.create_bucket(**create_bucket_kwargs)
            self._logger.info("Created storage bucket=%s", self._bucket_name)

        self._bucket_initialized = True
