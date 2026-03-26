import asyncio
import json
import time
from typing import Any

from src.core.logger import get_logger
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.strategies import register_strategies

logger = get_logger("alpha_cli")


async def gather_asset_context(ticker: str, amfi_code: str = None) -> dict[str, Any]:
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
        rss_fetcher.fetch_news(ticker),
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


async def main():
    start_time = time.time()

    # Let's test with a heavyweight Indian equity and a random AMFI code
    TARGET_TICKER = "RELIANCE.NS"
    TARGET_AMFI = "120504"  # Example: Nippon India Growth Fund

    try:
        final_context = await gather_asset_context(TARGET_TICKER, TARGET_AMFI)

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
    # Ensure Windows compatibility for asyncio if necessary, otherwise standard run
    asyncio.run(main())
