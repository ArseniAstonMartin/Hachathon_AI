from io import BytesIO

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from src.auth_manager.components.storage.base import StorageArtifactType


@pytest.mark.asyncio
async def test_s3_object_storage_roundtrip_uses_tenant_prefixed_paths(container):
    storage = container.object_storage()
    tenant_id = "tenant-acme"
    artifact_type = StorageArtifactType.SOURCE
    file_name = "contracts/master-service-agreement.txt"
    payload = b"tenant scoped object storage payload"
    expected_path = "tenant-acme/source/contracts/master-service-agreement.txt"

    with Stubber(storage._client) as stubber:
        stubber.add_response(
            "head_bucket",
            {},
            {"Bucket": storage.bucket_name},
        )
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": storage.bucket_name,
                "Key": expected_path,
                "Body": payload,
                "ContentType": "text/plain",
            },
        )
        stubber.add_response(
            "head_object",
            {},
            {
                "Bucket": storage.bucket_name,
                "Key": expected_path,
            },
        )
        stubber.add_response(
            "get_object",
            {
                "Body": StreamingBody(BytesIO(payload), len(payload)),
            },
            {
                "Bucket": storage.bucket_name,
                "Key": expected_path,
            },
        )

        object_path = await storage.save_bytes(
            tenant_id=tenant_id,
            artifact_type=artifact_type,
            object_name=file_name,
            content=payload,
            content_type="text/plain",
        )

        assert object_path == expected_path
        assert await storage.exists(object_path) is True

        stored_object = await storage.read_bytes(object_path)

        assert stored_object == payload
