import uuid

import httpx
import markdown

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
        # Auth Update: Using X-API-Key per the new spec
        self.headers = {"X-API-Key": settings.UNG_API_KEY} if settings.UNG_API_KEY else {}
        self.is_mock = settings.MOCK_UNG_DELIVERY

    async def dispatch_brief(
        self, ticker: str, markdown_payload: str, recipients: list[str]
    ) -> bool:
        """
        Converts the AI Markdown payload to HTML and dispatches it to the UNG endpoint.
        Requires a dynamic list of recipients from the database.
        """
        if self.is_mock:
            logger.info(
                f"[MOCK UNG] Simulating delivery for {ticker} to {recipients}. "
                f"Length: {len(markdown_payload)} chars. (Email generation disabled)"
            )
            return True

        if not recipients:
            logger.warning(f"Skipping delivery for {ticker}: No recipients provided.")
            return False

        if not self.url or not self.headers.get("X-API-Key"):
            logger.error("UNG_API_URL or UNG_API_KEY is not configured properly.")
            return False

        # 1. Convert Markdown to HTML
        try:
            html_content = markdown.markdown(markdown_payload, extensions=["tables", "fenced_code"])
        except Exception as e:
            logger.error(f"Failed to convert markdown to HTML for {ticker}: {e}")
            raise

        # 2. Generate trace ID for log tracking across microservices
        trace_id = f"alpha-extractor-email-{uuid.uuid4()}"

        # 3. Construct the nested payload
        payload = {
            "channel": "email",
            "recipient": {"to": recipients},
            "content": {
                "subject": f"🦅 Alpha Extractor: {ticker} Brief",
                "html_body": html_content,
            },
            "metadata": {"source_service": "alpha-extractor", "trace_id": trace_id},
        }

        # 4. Dispatch the HTTP Request
        logger.info(f"Dispatching {ticker} brief to UNG at {self.url} with trace_id: {trace_id}...")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=15.0,  # Generous timeout for notification gateways
                )
                response.raise_for_status()
                logger.info(f"Successfully dispatched {ticker} brief to UNG. Trace ID: {trace_id}")
                return True

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"UNG API rejected the payload for {ticker}: "
                    f"HTTP {e.response.status_code} - {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Network error while connecting to UNG for {ticker}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error delivering {ticker} brief via UNG: {e}")
                raise
