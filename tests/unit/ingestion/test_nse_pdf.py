from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.strategies.nse_pdf import NSEPDFStrategy


# Helper class to perfectly mock aiohttp's dual-purpose response object
class MockAiohttpResponse:
    def __init__(self, status=200, json_data=None, read_data=b""):
        self.status = status
        self._json_data = json_data or []
        self._read_data = read_data

    # Allows: async with session.get(...) as response:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    # Allows: await session.get(...)
    def __await__(self):
        async def _return_self():
            return self

        return _return_self().__await__()

    async def json(self):
        return self._json_data

    async def read(self):
        return self._read_data


@pytest.mark.asyncio
async def test_nse_pdf_strategy_success():
    strategy = NSEPDFStrategy()

    with (
        patch("src.ingestion.strategies.nse_pdf.aiohttp.ClientSession") as mock_session_class,
        patch("src.ingestion.strategies.nse_pdf.PdfReader") as mock_pdf_reader,
    ):
        # CRITICAL FIX: mock_session must be a MagicMock, not an AsyncMock
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Chain our perfect dummy responses
        mock_session.get.side_effect = [
            # 1. Homepage response
            MockAiohttpResponse(status=200),
            # 2. API JSON response
            MockAiohttpResponse(
                status=200,
                json_data=[
                    {
                        "desc": "Q3 Earnings",
                        "an_dt": "26-Mar-2026 22:48:00",
                        "attchmntFile": "https://nsearchives.nseindia.com/fake.pdf",
                    }
                ],
            ),
            # 3. PDF Binary response
            MockAiohttpResponse(status=200, read_data=b"fake binary data"),
        ]

        # Mock the PDF text extraction
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Profit increased by 20%"
        mock_pdf_reader.return_value.pages = [mock_page]

        # Execute
        result = await strategy.fetch_data("RELIANCE")

        # Assertions
        assert result["ticker"] == "RELIANCE"
        assert len(result["announcements"]) == 1
        assert result["announcements"][0]["title"] == "Q3 Earnings"
        assert result["announcements"][0]["date"] == "26-Mar-2026 22:48:00"
        assert "Profit increased" in result["announcements"][0]["content"]
        assert mock_session.get.call_count == 3
