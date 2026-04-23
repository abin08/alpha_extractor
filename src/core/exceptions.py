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


class CircuitBreakerOpenError(AlphaExtractorError):
    """Raised when a data source's circuit breaker is OPEN due to consecutive failures.
    Prevents the system from making network calls to a known-down service.
    """

    def __init__(self, source: str):
        self.source = source
        super().__init__(f"Circuit breaker is OPEN for {source}. Requests are temporarily halted.")


class LLMGenerationError(AlphaExtractorError):
    """Raised when the LLM API responds successfully, but the generation fails
    (e.g., safety filters tripped, empty response, or Pydantic parsing failure).
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"LLM generation failed safely: {reason}")


class ResolutionError(AlphaExtractorError):
    """Raised when the Resolution Engine cannot find valid vendor symbols for an asset."""

    def __init__(self, identifier: str, reason: str):
        self.identifier = identifier
        self.reason = reason
        super().__init__(f"Failed to resolve symbols for '{identifier}': {reason}")
