from .amfi import AMFIFetcher
from .rss import RssFeedFetcher
from .screener import ScreenerFetcher
from .yfinance import YFinanceFetcher

__all__ = ["YFinanceFetcher", "AMFIFetcher", "RssFeedFetcher", "ScreenerFetcher"]


def register_strategies() -> None:
    """
    Bootstrapper function.
    Calling this explicitly prevents aggressive linters (like Ruff)
    from removing the module import, ensuring the @register decorators fire.
    """
    pass
