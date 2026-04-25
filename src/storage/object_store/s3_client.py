import json
from typing import Any

import aioboto3

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncS3Client:
    """Handles asynchronous interactions with S3/MinIO/OCI for massive context payloads."""

    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.bucket = settings.S3_BUCKET_NAME  # Will resolve to "alpha-extractor-raw"

        self.client_kwargs = {
            "service_name": "s3",
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
        }
        if self.endpoint_url:
            self.client_kwargs["endpoint_url"] = self.endpoint_url

    async def upload_json(self, data: dict[str, Any], key: str) -> str:
        """Serializes a dict to JSON and uploads it to S3. Returns the S3 URI."""

        # 1. Convert to bytes for accurate length calculation
        json_bytes = json.dumps(data).encode("utf-8")
        payload_length = len(json_bytes)

        s3_uri = f"s3://{self.bucket}/{key}"

        logger.info(f"Uploading context payload to {s3_uri} ({payload_length} bytes)")

        async with self.session.client(**self.client_kwargs) as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json_bytes,
                ContentType="application/json",
                ContentLength=payload_length,  # <--- The OCI Fix
            )

        return s3_uri

    async def download_json(self, s3_uri: str) -> dict[str, Any]:
        """Downloads a JSON file from an S3 URI and deserializes it into a dict."""
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        path_parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1]

        logger.info(f"Downloading context payload from {s3_uri}")

        async with self.session.client(**self.client_kwargs) as client:
            response = await client.get_object(Bucket=bucket, Key=key)

            async with response["Body"] as stream:
                body_bytes = await stream.read()

        return json.loads(body_bytes.decode("utf-8"))
