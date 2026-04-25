"""
Object Storage Client Module.

Provides asynchronous S3-compatible storage operations for handling massive
data contexts that exceed standard message broker limits (the S3 Pointer pattern).
Configured specifically to maintain compatibility with strict S3 implementations
like Oracle Cloud Infrastructure (OCI) Object Storage.
"""

import io
import json
from typing import Any

import aioboto3
from botocore.config import Config

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncS3Client:
    """
    Handles asynchronous interactions with S3/MinIO/OCI for massive context payloads.

    This client is designed to be vendor-agnostic but includes specific configurations
    (like forcing Signature Version 4 and strict Content-Length declarations) to
    ensure compatibility with Oracle Cloud Object Storage.
    """

    def __init__(self) -> None:
        """
        Initializes the async S3 session and builds the connection configuration.
        Relies on global application settings for credentials and endpoints.
        """
        self.session = aioboto3.Session()
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.bucket = settings.S3_BUCKET_NAME  # Typically resolves to "alpha-extractor-raw"

        # OCI Object Storage strictly requires AWS Signature Version 4.
        self.oci_config = Config(signature_version="s3v4")

        self.client_kwargs = {
            "service_name": "s3",
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
        }

        # If an endpoint URL is provided (MinIO/OCI), use it.
        # Otherwise, boto3 defaults to standard AWS S3 routing.
        if self.endpoint_url:
            self.client_kwargs["endpoint_url"] = self.endpoint_url

    async def upload_json(self, data: dict[str, Any], key: str) -> str:
        """
        Serializes a Python dictionary to JSON and uploads it to the configured bucket.

        Args:
            data (dict[str, Any]): The raw dictionary payload to store.
            key (str): The destination object key (file path) within the bucket.

        Returns:
            str: The full S3 URI pointer (e.g., s3://bucket-name/path/to/file.json).

        Raises:
            botocore.exceptions.ClientError: If the upload fails due to auth or network issues.
        """
        # 1. Serialize and encode to raw UTF-8 bytes to determine the exact payload size.
        json_bytes = json.dumps(data).encode("utf-8")
        payload_length = len(json_bytes)

        # 2. OCI COMPATIBILITY FIX:
        # Under the hood, aiohttp will use "Chunked Transfer Encoding" if passed raw bytes.
        # OCI strictly rejects chunked uploads for basic PutObject calls. By wrapping the
        # bytes in an io.BytesIO stream, we force aiohttp to send it as a standard stream.
        body_stream = io.BytesIO(json_bytes)

        s3_uri = f"s3://{self.bucket}/{key}"
        logger.info(f"Uploading context payload to {s3_uri} ({payload_length} bytes)")

        # 3. Execute the upload, explicitly passing the ContentLength header.
        async with self.session.client(**self.client_kwargs, config=self.oci_config) as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body_stream,
                ContentType="application/json",
                ContentLength=payload_length,
            )

        return s3_uri

    async def download_json(self, s3_uri: str) -> dict[str, Any]:
        """
        Downloads a JSON file from an S3 URI and deserializes it back into a Python dict.

        Args:
            s3_uri (str): The full S3 URI pointer (e.g., s3://bucket-name/path/to/file.json).

        Returns:
            dict[str, Any]: The deserialized JSON payload.

        Raises:
            ValueError: If the provided URI does not start with 's3://'.
            botocore.exceptions.ClientError: If the object does not exist or access is denied.
        """
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}. Expected s3://bucket/key")

        # Parse the bucket and key from the URI string
        path_parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1]

        logger.info(f"Downloading context payload from {s3_uri}")

        async with self.session.client(**self.client_kwargs, config=self.oci_config) as client:
            response = await client.get_object(Bucket=bucket, Key=key)

            # Stream the response body into memory and decode
            async with response["Body"] as stream:
                body_bytes = await stream.read()

        return json.loads(body_bytes.decode("utf-8"))
