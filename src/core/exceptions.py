class AlphaExtractorError(Exception):
    """Base exception for all AlphaExtractor domain errors."""

    pass


class RateLimitExceeded(AlphaExtractorError):
    """Raised when an external API rate limit (e.g., HTTP 429) is hit."""

    def __init__(self, source: str, retry_after: int = 0):
        self.source = source
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {source}."
        if retry_after > 0:
            message += f" Retry available after {retry_after} seconds."
        super().__init__(message)


class SourceOfflineError(AlphaExtractorError):
    """Raised when a data source is completely unreachable
    (e.g., HTTP 50x or timeout).
    """

    def __init__(self, source: str, status_code: int | None = None):
        self.source = source
        self.status_code = status_code
        message = f"Data source {source} is currently offline or unreachable."
        if status_code:
            message += f" (HTTP Status: {status_code})"
        super().__init__(message)


class DataParsingError(AlphaExtractorError):
    """Raised when the HTML/XML/JSON structure from a source has
    changed unexpectedly.
    """

    def __init__(self, source: str, details: str):
        self.source = source
        self.details = details
        super().__init__(f"Failed to parse data from {source}. Details: {details}")
