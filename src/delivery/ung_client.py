import uuid

import httpx

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class UNGClient:
    """
    HTTP Client for interacting with the Unified Notification Gateway (UNG).
    Implements a bypass pattern if MOCK_UNG_DELIVERY is enabled.
    """

    def __init__(self):
        self.url = settings.UNG_API_URL
        self.headers = {"X-API-Key": settings.UNG_API_KEY} if settings.UNG_API_KEY else {}
        self.is_mock = settings.MOCK_UNG_DELIVERY

    async def dispatch_brief(
        self,
        ticker: str,
        html_payload: str,
        recipients: list[str],
        trace_id: str = None,
    ) -> bool:
        """
        Dispatches the fully rendered HTML payload to the UNG endpoint.
        """
        if self.is_mock:
            logger.info(
                f"[MOCK UNG] Simulating delivery for {ticker} to {recipients}. "
                f"Length: {len(html_payload)} chars. (Email generation disabled)"
            )
            return True

        if not recipients:
            logger.warning(f"Skipping delivery for {ticker}: No recipients provided.")
            return False

        if not self.url or not self.headers.get("X-API-Key"):
            logger.error("UNG_API_URL or UNG_API_KEY is not configured properly.")
            return False

        # Use provided trace_id for cross-service tracking, or generate a fallback
        active_trace_id = trace_id or f"alpha-extractor-email-{uuid.uuid4()}"

        # Construct the nested payload
        payload = {
            "channel": "email",
            "recipient": {"to": recipients},
            "content": {
                "subject": f"Alpha Extractor: {ticker} Brief",
                "html_body": html_payload,
            },
            "metadata": {
                "source_service": "alpha-extractor",
                "trace_id": active_trace_id,
            },
        }

        logger.info(
            f"Dispatching {ticker} brief to UNG at {self.url} with trace_id: {active_trace_id}..."
        )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=15.0,
                )
                response.raise_for_status()
                logger.info(
                    f"Successfully dispatched {ticker} brief to UNG. Trace ID: {active_trace_id}"
                )
                return True

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"UNG API rejected payload for {ticker}: HTTP {e.response.status_code}"
                    f" - {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Network error while connecting to UNG for {ticker}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error delivering {ticker} brief via UNG: {e}")
                raise
