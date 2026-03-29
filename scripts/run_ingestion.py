import argparse
import asyncio
import json
import time
from typing import Any

from src.core.logger import get_logger
from src.domain.models import AssetContext
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.strategies import register_strategies

logger = get_logger("alpha_cli")


async def gather_asset_context(asset: AssetContext) -> dict[str, Any]:
    """Concurrently fetches all available data for a given asset using the Security Master."""
    register_strategies()

    yf_fetcher = FetcherFactory.create(DataSource.YFINANCE)
    screener_fetcher = FetcherFactory.create(DataSource.SCREENER)
    rss_fetcher = FetcherFactory.create(DataSource.RSS_FEED)
    amfi_fetcher = FetcherFactory.create(DataSource.AMFI)
    nse_fetcher = FetcherFactory.create(DataSource.NSE_PDF)

    payload = {"asset": asset.model_dump(), "timestamp": time.time()}
    logger.info(f"Initiating concurrent data extraction for {asset.internal_symbol}...")

    tasks = [
        yf_fetcher.fetch_price_history(asset, period="1mo"),
        screener_fetcher.fetch_company_info(asset),
        rss_fetcher.fetch_news(asset),
        nse_fetcher.fetch_news(asset),
    ]

    if asset.amfi_code:
        tasks.append(amfi_fetcher.fetch_company_info(asset))
        tasks.append(amfi_fetcher.fetch_price_history(asset))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    payload["price_action"] = (
        results[0] if not isinstance(results[0], Exception) else str(results[0])
    )
    payload["fundamentals"] = (
        results[1] if not isinstance(results[1], Exception) else str(results[1])
    )
    payload["news"] = results[2] if not isinstance(results[2], Exception) else str(results[2])
    payload["corporate_filings"] = (
        results[3] if not isinstance(results[3], Exception) else str(results[3])
    )

    if asset.amfi_code:
        payload["mutual_fund_info"] = (
            results[4] if not isinstance(results[4], Exception) else str(results[4])
        )
        payload["mutual_fund_nav"] = (
            results[5] if not isinstance(results[5], Exception) else str(results[5])
        )

    return payload


async def main(
    internal_symbol: str,
    company_name: str,
    yfinance_symbol: str = None,
    screener_symbol: str = None,
    nse_symbol: str = None,
    amfi_code: str = None,
):
    start_time = time.time()

    # Intelligent Fallbacks: If vendor specific symbols aren't passed,
    # guess them from the internal symbol
    base_symbol = internal_symbol.split(".")[0]
    yf_sym = yfinance_symbol if yfinance_symbol is not None else internal_symbol
    screen_sym = screener_symbol if screener_symbol is not None else base_symbol
    nse_sym = nse_symbol if nse_symbol is not None else base_symbol

    # Helper to clean "None" strings coming from CLI arguments
    def clean_arg(val):
        return val if val and str(val).lower() != "none" else None

    # Build the full Security Master Entity
    asset = AssetContext(
        internal_symbol=internal_symbol,
        company_name=company_name,
        yfinance_symbol=clean_arg(yf_sym),
        screener_symbol=clean_arg(screen_sym),
        nse_symbol=clean_arg(nse_sym),
        amfi_code=clean_arg(amfi_code),
    )

    try:
        final_context = await gather_asset_context(asset)

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
    parser = argparse.ArgumentParser(description="Run asset context extraction via CLI.")

    # Switched to named arguments (--flag) for maximum flexibility
    parser.add_argument(
        "--internal",
        default="HDFCBANK.NS",
        help="Primary internal ticker (e.g. HDFCBANK.NS)",
    )
    parser.add_argument("--name", default="HDFC Bank", help="Natural language company name")
    parser.add_argument(
        "--yfinance", default=None, help="Yahoo Finance specific symbol (e.g. ^NSEI)"
    )
    parser.add_argument("--screener", default=None, help="Screener.in specific symbol")
    parser.add_argument("--nse", default=None, help="NSE specific symbol")
    parser.add_argument("--amfi", default=None, help="AMFI mutual fund code")

    args = parser.parse_args()

    asyncio.run(
        main(
            internal_symbol=args.internal,
            company_name=args.name,
            yfinance_symbol=args.yfinance,
            screener_symbol=args.screener,
            nse_symbol=args.nse,
            amfi_code=args.amfi,
        )
    )
