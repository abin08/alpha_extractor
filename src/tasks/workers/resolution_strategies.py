import urllib.parse

import httpx

from src.core.config import settings
from src.core.exceptions import ResolutionError
from src.core.logger import get_logger

logger = get_logger(__name__)

# --- 1. THE INDEX BYPASS MAP ---
# Indices don't have standard NSE symbols or Screener profiles,
# so we hardcode the known routing symbols here to bypass the APIs.
INDEX_MAP = {
    "NIFTY 50": {
        "nse_symbol": "NIFTY 50",
        "yfinance_symbol": "^NSEI",
        "screener_symbol": None,
    },
    "NIFTY BANK": {
        "nse_symbol": "NIFTY BANK",
        "yfinance_symbol": "^NSEBANK",
        "screener_symbol": None,
    },
    "SENSEX": {
        "nse_symbol": "SENSEX",
        "yfinance_symbol": "^BSESN",
        "screener_symbol": None,
    },
}


def _sanitize_ticker(identifier: str) -> str:
    """Strips common suffixes and formatting issues from the raw identifier."""
    clean = identifier.strip().upper()

    # 1. Strip existing extensions if the user already provided them
    if clean.endswith(".NS"):
        clean = clean[:-3]
    elif clean.endswith(".BO"):
        clean = clean[:-3]

    # 2. Strip common brokerage series suffixes
    suffixes = [" EQ", "-EQ", " BE", "-BE", " SM", "-SM"]
    for suffix in suffixes:
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]

    # 3. NSE symbols do not have spaces (e.g., "TATA MOTORS" -> "TATAMOTORS")
    clean = clean.replace(" ", "")

    return clean


async def _verify_yfinance(ticker: str) -> str:
    """
    Pings Yahoo Finance's lightweight chart API to verify existence.
    Returns the valid yfinance symbol, or raises ResolutionError on 404.
    """
    yf_symbol = f"{ticker}.NS"
    url = f"{settings.YFINANCE_BASE_URL}/v8/finance/chart/{yf_symbol}"

    # Yahoo heavily rate-limits/blocks requests without a standard User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 404:
            # 404 means it's either an invalid ticker or a BSE-only micro-cap.
            # We raise ResolutionError to send it to MANUAL_INTERVENTION.
            raise ResolutionError(
                ticker,
                f"Yahoo Finance returned 404 for {yf_symbol}. May be BSE-only or invalid.",
            )

        # If it's a 50x error, this will raise an HTTPStatusError.
        # The AE38 Orchestrator catches this and retries the task later.
        response.raise_for_status()

    return yf_symbol


async def _verify_screener(ticker: str) -> str:
    """
    Queries Screener's autocomplete API and demands an EXACT string match.
    Returns the exact Screener symbol, or raises ResolutionError.
    """
    # URL encode to safely handle edge cases like "M&M" -> "M%26M"
    encoded_ticker = urllib.parse.quote(ticker)
    url = f"{settings.SCREENER_BASE_URL}/api/company/search/?q={encoded_ticker}"

    headers = {"User-Agent": "AlphaExtractor/1.0"}

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

        results = response.json()

        # Results look like: [{"id": 123, "name": "Reliance Inds",
        # "url": "/company/RELIANCE/consolidated/"}]
        for item in results:
            url_path = item.get("url", "")

            # Extract the middle slug from the URL path: /company/TICKER/ -> TICKER
            parts = [p for p in url_path.strip("/").split("/") if p]

            if len(parts) >= 2 and parts[0] == "company":
                # Unquote in case Screener returned encoded characters
                screener_symbol = urllib.parse.unquote(parts[1]).upper()

                # EXACT MATCH VERIFICATION
                if screener_symbol == ticker:
                    return screener_symbol

    raise ResolutionError(ticker, f"No exact match found on Screener for '{ticker}'")


async def resolve_equity_symbols(identifier: str) -> dict:
    """
    The main strategy for resolving Indian Equity symbols.
    """
    clean_id = identifier.strip().upper()

    # 1. The Index Bypass
    if clean_id in INDEX_MAP:
        logger.info(
            "Identifier matched Index Bypass map",
            extra={"extra_data": {"identifier": clean_id}},
        )
        return INDEX_MAP[clean_id]

    # 2. Input Sanitization
    sanitized_ticker = _sanitize_ticker(clean_id)
    logger.info(
        "Sanitized ticker",
        extra={"extra_data": {"original": identifier, "sanitized": sanitized_ticker}},
    )

    # 3. Network Verifications
    # We run these sequentially. If YFinance 404s, it immediately raises and we
    # save ourselves an unnecessary API call to Screener.
    yf_symbol = await _verify_yfinance(sanitized_ticker)
    screener_symbol = await _verify_screener(sanitized_ticker)

    return {
        "nse_symbol": sanitized_ticker,
        "yfinance_symbol": yf_symbol,
        "screener_symbol": screener_symbol,
    }


async def resolve_mutual_fund_symbols(identifier: str) -> dict:
    """
    STUB: Will hold the logic to resolve AMFI codes for Mutual Funds.
    """
    return {"amfi_code": f"STUB_{identifier}"}
