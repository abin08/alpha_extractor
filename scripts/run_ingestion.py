import argparse
import asyncio
import json
import time
from typing import Any

from src.core.logger import get_logger
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.strategies import register_strategies

logger = get_logger("alpha_cli")

DEFAULT_TARGET_TICKER = "HDFCBANK.NS"
DEFAULT_TARGET_COMPANY_NAME = "HDFC Bank"
DEFAULT_TARGET_AMFI = "120504"


async def gather_asset_context(
    ticker: str, amfi_code: str = None, company_name: str = ""
) -> dict[str, Any]:
    """Concurrently fetches all available data for a given asset."""

    register_strategies()

    # 1. Initialize our strategies via the Factory
    yf_fetcher = FetcherFactory.create(DataSource.YFINANCE)
    screener_fetcher = FetcherFactory.create(DataSource.SCREENER)
    rss_fetcher = FetcherFactory.create(DataSource.RSS_FEED)
    amfi_fetcher = FetcherFactory.create(DataSource.AMFI)

    payload = {"ticker": ticker, "timestamp": time.time()}
    logger.info(f"Initiating concurrent data extraction for {ticker}...")

    # 2. Define our async tasks
    # For Equities: We want Price Action, Fundamentals, and News
    tasks = [
        yf_fetcher.fetch_price_history(ticker, period="1mo"),
        screener_fetcher.fetch_company_info(ticker),
        rss_fetcher.fetch_news(ticker, company_name),
    ]

    # If an AMFI code is provided, fetch mutual fund data too
    if amfi_code:
        tasks.append(amfi_fetcher.fetch_company_info(amfi_code))

    # 3. Execute all network I/O concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. Map results back to our payload
    payload["price_action"] = (
        results[0] if not isinstance(results[0], Exception) else str(results[0])
    )
    payload["fundamentals"] = (
        results[1] if not isinstance(results[1], Exception) else str(results[1])
    )
    payload["news"] = results[2] if not isinstance(results[2], Exception) else str(results[2])

    if amfi_code:
        payload["mutual_fund"] = (
            results[3] if not isinstance(results[3], Exception) else str(results[3])
        )

    return payload


async def main(target_ticker=None, target_company_name=None, target_amfi=None):
    start_time = time.time()

    TARGET_TICKER = target_ticker or DEFAULT_TARGET_TICKER
    TARGET_COMPANY_NAME = target_company_name or DEFAULT_TARGET_COMPANY_NAME
    TARGET_AMFI = target_amfi or DEFAULT_TARGET_AMFI

    try:
        final_context = await gather_asset_context(TARGET_TICKER, TARGET_AMFI, TARGET_COMPANY_NAME)

        # Print the beautiful, raw data payload
        print("\n" + "=" * 50)
        print("🚀 ALPHA EXTRACTOR: RAW DATA PAYLOAD")
        print("=" * 50)
        print(json.dumps(final_context, indent=2, default=str))
        print("=" * 50)

        elapsed = time.time() - start_time
        logger.info(f"Extraction complete in {elapsed:.2f} seconds.")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run asset context extraction with optional overrides."
    )

    parser.add_argument(
        "TARGET_TICKER",
        nargs="?",
        default=None,
        help=f"Ticker symbol (default: {DEFAULT_TARGET_TICKER})",
    )
    parser.add_argument(
        "TARGET_COMPANY_NAME",
        nargs="?",
        default=None,
        help=f'Company name (default: "{DEFAULT_TARGET_COMPANY_NAME}")',
    )
    parser.add_argument(
        "TARGET_AMFI",
        nargs="?",
        default=None,
        help=f"AMFI code (default: {DEFAULT_TARGET_AMFI})",
    )

    args = parser.parse_args()
    # Ensure Windows compatibility for asyncio if necessary, otherwise standard run
    asyncio.run(
        main(
            target_ticker=args.TARGET_TICKER,
            target_company_name=args.TARGET_COMPANY_NAME,
            target_amfi=args.TARGET_AMFI,
        )
    )
