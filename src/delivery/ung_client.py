import os

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
        self.headers = {"Authorization": f"Bearer {settings.UNG_API_KEY}"}
        self.is_mock = settings.MOCK_UNG_DELIVERY

    async def dispatch_brief(self, ticker: str, markdown_payload: str) -> bool:
        """
        Sends the formatted Markdown payload to the UNG endpoint.
        """
        payload = {
            "channel": "TELEGRAM",  # Configurable later based on target preferences
            "subject": f"🦅 Alpha Extractor: {ticker} Brief",
            "body": markdown_payload,
        }

        # THE FEATURE FLAG BYPASS
        if self.is_mock:
            logger.info(
                f"[MOCK UNG] Simulating delivery for {ticker}. "
                f"Length: {len(markdown_payload)} chars."
            )

            # Let's write it to a local file so you can actually see the output!
            os.makedirs("deliveries", exist_ok=True)
            file_path = f"deliveries/{ticker}_mock_delivery.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_payload)

            logger.debug(f"[MOCK UNG] Payload written to {file_path}")
            return True

        # THE REAL HTTP CALL
        logger.info(f"Dispatching {ticker} brief to UNG at {self.url}...")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=15.0,  # Generous timeout for notification gateways
                )
                response.raise_for_status()
                logger.info(f"Successfully dispatched {ticker} brief to UNG.")
                return True

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"UNG API rejected the payload: "
                    f"HTTP {e.response.status_code} - {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Network error while connecting to UNG: {e}")
                raise
