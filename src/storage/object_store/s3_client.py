"""
Object Storage Client Module.

Provides asynchronous S3-compatible storage operations for handling massive
data contexts. Configured specifically to maintain compatibility with strict
S3 implementations like Oracle Cloud Infrastructure (OCI) Object Storage.
"""

import json
from typing import Any

import aioboto3
from botocore.config import Config

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncS3Client:
    """Handles asynchronous interactions with S3/MinIO/OCI for massive context payloads."""

    def __init__(self) -> None:
        self.session = aioboto3.Session()
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.bucket = settings.S3_BUCKET_NAME

        # THE OCI FIX: Force Path-Style addressing.
        # OCI's S3 load balancers strip the Content-Length header when
        # routing Virtual-Hosted style URLs. Path-Style bypasses the rewrite.
        self.oci_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )

        # Extract region dynamically from OCI URL (e.g., ap-mumbai-1) to satisfy s3v4
        region = "us-east-1"
        if self.endpoint_url and "objectstorage." in self.endpoint_url:
            try:
                region = self.endpoint_url.split("objectstorage.")[1].split(".")[0]
            except IndexError:
                pass

        self.client_kwargs = {
            "service_name": "s3",
            "region_name": region,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
        }
        if self.endpoint_url:
            self.client_kwargs["endpoint_url"] = self.endpoint_url

    async def upload_json(self, data: dict[str, Any], key: str) -> str:
        """Serializes a dict to JSON and uploads it to S3."""

        # Use raw bytes. With Path-Style addressing, aiohttp's native Content-Length survives.
        json_bytes = json.dumps(data).encode("utf-8")

        s3_uri = f"s3://{self.bucket}/{key}"
        logger.info(f"Uploading context payload to {s3_uri} ({len(json_bytes)} bytes)")

        async with self.session.client(**self.client_kwargs, config=self.oci_config) as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json_bytes,
                ContentType="application/json",
            )

        return s3_uri

    async def download_json(self, s3_uri: str) -> dict[str, Any]:
        """Downloads a JSON file from an S3 URI and deserializes it."""
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        path_parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1]

        logger.info(f"Downloading context payload from {s3_uri}")

        async with self.session.client(**self.client_kwargs, config=self.oci_config) as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                body_bytes = await stream.read()

        return json.loads(body_bytes.decode("utf-8"))
