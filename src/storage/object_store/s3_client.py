"""
Async OCI Object Storage client using manual AWS Signature V4 over httpx.

aioboto3/botocore is NOT used here because botocore 1.40+ unconditionally
injects chunked transfer encoding (Transfer-Encoding: chunked + CRC32 trailer)
on all PutObject calls. OCI requires a plain Content-Length header and rejects
chunked requests with MissingContentLength. Bypassing botocore and signing
requests manually with hmac/hashlib is the only reliable fix.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


def _sign(key: bytes, msg: str) -> bytes:
    """HMAC-SHA256 of msg using key. Core primitive for SigV4 signing."""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    """Derives a SigV4 signing key scoped to a specific date, region, and service."""
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _build_auth_headers(
    method: str,
    host: str,
    path: str,
    payload: bytes,
    region: str,
    access_key: str,
    secret_key: str,
    content_type: str = "application/json",
) -> dict[str, str]:
    """Returns SigV4-signed headers for a PUT request with a plain Content-Length.

    Args:
        method:       HTTP method, e.g. "PUT".
        host:         Bare hostname without scheme.
        path:         URL path including bucket and key, e.g. "/bucket/key.json".
        payload:      Raw request body bytes.
        region:       OCI region, e.g. "ap-hyderabad-1".
        access_key:   OCI S3-compatible access key ID.
        secret_key:   OCI S3-compatible secret key.
        content_type: Payload MIME type. Defaults to "application/json".
    """
    payload_hash = hashlib.sha256(payload).hexdigest()
    content_length = len(payload)

    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    # Headers must be lowercase and sorted alphabetically for SigV4.
    canonical_headers = (
        f"content-length:{content_length}\n"
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-length;content-type;host;x-amz-content-sha256;x-amz-date"

    canonical_request = "\n".join(
        [
            method,
            path,
            "",  # query string (empty)
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    signing_key = _get_signing_key(secret_key, date_stamp, region, "s3")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Length": str(content_length),
        "Content-Type": content_type,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }


class AsyncS3Client:
    """Async client for uploading and downloading JSON objects on OCI Object Storage."""

    def __init__(self) -> None:
        self.endpoint_url = settings.S3_ENDPOINT_URL.rstrip("/")
        self.bucket = settings.S3_BUCKET_NAME
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.host = self.endpoint_url.replace("https://", "").replace("http://", "")

        # Parse region from OCI endpoint URL, e.g. "ap-hyderabad-1" from
        # "https://<ns>.compat.objectstorage.ap-hyderabad-1.oraclecloud.com"
        self.region = "ap-hyderabad-1"
        if "objectstorage." in self.endpoint_url:
            try:
                self.region = self.endpoint_url.split("objectstorage.")[1].split(".")[0]
            except IndexError:
                pass

    async def upload_json(self, data: dict[str, Any], key: str) -> str:
        """Serializes data to JSON and uploads it to OCI Object Storage.

        Args:
            data: JSON-serializable dict to upload.
            key:  Object key within the bucket, e.g. "uploads/data.json".

        Returns:
            S3 URI of the uploaded object, e.g. "s3://my-bucket/uploads/data.json".

        Raises:
            httpx.HTTPStatusError: On a non-2xx response from OCI.
        """
        json_bytes = json.dumps(data).encode("utf-8")
        path = f"/{self.bucket}/{key}"
        s3_uri = f"s3://{self.bucket}/{key}"

        logger.info(f"Uploading to {s3_uri} ({len(json_bytes)} bytes)")

        headers = _build_auth_headers(
            method="PUT",
            host=self.host,
            path=path,
            payload=json_bytes,
            region=self.region,
            access_key=self.access_key,
            secret_key=self.secret_key,
        )

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.endpoint_url}{path}", content=json_bytes, headers=headers
            )
            response.raise_for_status()

        logger.info(f"Successfully uploaded to {s3_uri}")
        return s3_uri

    async def download_json(self, s3_uri: str) -> dict[str, Any]:
        """Downloads and deserializes a JSON object from OCI Object Storage.

        Args:
            s3_uri: S3 URI in "s3://<bucket>/<key>" format.

        Returns:
            Deserialized JSON object as a Python dict.

        Raises:
            ValueError:            If s3_uri is not a valid "s3://" URI.
            httpx.HTTPStatusError: On a non-2xx response from OCI.
            json.JSONDecodeError:  If the downloaded content is not valid JSON.
        """
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        # maxsplit=1 preserves "/" characters within the key itself.
        bucket, key = s3_uri.replace("s3://", "").split("/", 1)
        path = f"/{bucket}/{key}"

        logger.info(f"Downloading from {s3_uri}")

        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        # SigV4 requires this header even for GET requests with no body.
        empty_payload_hash = hashlib.sha256(b"").hexdigest()

        canonical_headers = (
            f"host:{self.host}\nx-amz-content-sha256:{empty_payload_hash}\nx-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            ["GET", path, "", canonical_headers, signed_headers, empty_payload_hash]
        )

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        signing_key = _get_signing_key(self.secret_key, date_stamp, self.region, "s3")
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        headers = {
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
            "x-amz-content-sha256": empty_payload_hash,
            "x-amz-date": amz_date,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.endpoint_url}{path}", headers=headers)
            response.raise_for_status()

        logger.info(f"Successfully downloaded from {s3_uri}")
        return json.loads(response.content.decode("utf-8"))
