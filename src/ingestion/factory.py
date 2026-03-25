import enum

from .base import DataFetcher


class DataSource(enum.StrEnum):
    """Supported data sources for the ingestion engine."""

    YFINANCE = "yfinance"
    AMFI = "amfi"
    RSS_FEED = "rss_feed"
    NSE_PDF = "nse_pdf"


class FetcherFactory:
    """
    Factory Pattern utilizing a decorator-based registry to return the correct ingestion strategy.
    """

    _registry: dict[DataSource, type[DataFetcher]] = {}

    @classmethod
    def register(cls, source: DataSource):
        """
        Decorator to register a concrete Strategy implementation.
        """

        def wrapper(fetcher_class: type[DataFetcher]) -> type[DataFetcher]:
            cls._registry[source] = fetcher_class
            return fetcher_class

        return wrapper

    @classmethod
    def create(cls, source: DataSource) -> DataFetcher:
        """
        Instantiate and return the requested DataFetcher strategy.
        """
        fetcher_class = cls._registry.get(source)
        if not fetcher_class:
            raise ValueError(f"No ingestion strategy registered for data source: {source}")
        return fetcher_class()
