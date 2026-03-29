import io
from typing import Any

import aiohttp
from pypdf import PdfReader

from src.core.exceptions import DataParsingError, SourceOfflineError
from src.core.logger import get_logger
from src.ingestion.base import DataFetcher
from src.ingestion.factory import DataSource, FetcherFactory

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.NSE_PDF)
class NSEPDFStrategy(DataFetcher):
    """
    Scrapes the National Stock Exchange (NSE) of India for corporate announcements.
    Bypasses WAF protections via session cookie management and extracts text
    directly from the attached PDFs in memory.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.base_url = "https://www.nseindia.com"
        self.api_url = f"{self.base_url}/api/corporate-announcements"

    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        """Not applicable for NSE PDF strategy."""
        return {}

    async def fetch_price_history(self, ticker: str) -> dict[str, Any]:
        """Not applicable for NSE PDF strategy."""
        return {}

    async def fetch_news(self, ticker: str, company_name: str = "") -> dict[str, Any]:
        """Corporate filings act as our news source for this strategy."""
        return await self.fetch_data(ticker)

    async def fetch_data(self, target: str) -> dict[str, Any]:
        logger.info(f"Initiating NSE PDF extraction for ticker: {target}")
        extracted_announcements = []

        async with aiohttp.ClientSession(headers=self.headers) as session:
            # 1. Establish Session Cookies to bypass WAF
            try:
                await session.get(self.base_url, timeout=10)
            except Exception as e:
                logger.error(f"Failed to connect to NSE Homepage: {e}")
                raise SourceOfflineError(source="NSE_Homepage")

            # 2. Fetch the JSON list of recent announcements
            params = {"index": "equities", "symbol": target}
            try:
                async with session.get(self.api_url, params=params, timeout=10) as response:
                    if response.status != 200:
                        raise SourceOfflineError(source="NSE_API", status_code=response.status)
                    data = await response.json()
            except Exception as e:
                raise DataParsingError(source="NSE_API", details=str(e))

            # 3. Extract text from the latest 2 PDFs to respect the LLM context window
            recent_filings = data[:2]

            for filing in recent_filings:
                # get the attachment url
                pdf_url = filing.get("attchmntFile")
                if not pdf_url:
                    continue

                logger.debug(f"Downloading PDF from: {pdf_url}")

                try:
                    async with session.get(pdf_url, timeout=15) as pdf_resp:
                        if pdf_resp.status == 200:
                            # Read the binary data into a RAM buffer
                            pdf_bytes = await pdf_resp.read()
                            pdf_file = io.BytesIO(pdf_bytes)

                            # Parse the PDF text safely
                            reader = PdfReader(pdf_file)
                            text_content = " ".join(
                                page.extract_text() for page in reader.pages if page.extract_text()
                            )

                            extracted_announcements.append(
                                {
                                    "title": filing.get("desc", "Corporate Announcement"),
                                    "date": filing.get("an_dt"),  # Updated date key
                                    "content": text_content[:3000],  # Truncated to save tokens
                                }
                            )
                except Exception as e:
                    logger.warning(f"Failed to parse PDF {pdf_url}: {e}")

        return {
            "source": "NSE_Announcements",
            "ticker": target,
            "announcements": extracted_announcements,
        }
