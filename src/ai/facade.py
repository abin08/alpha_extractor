# src/ai/facade.py
import json
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.core.config import settings
from src.core.exceptions import (
    LLMGenerationError,
    RateLimitExceeded,
    SourceOfflineError,
)
from src.core.logger import get_logger
from src.domain.schemas.ai_response import MacroAnalysis
from src.ingestion.resilience import circuit_breaker, with_retry_and_jitter

logger = get_logger(__name__)


class LLMServiceFacade:
    """
    Facade wrapping the Google GenAI SDK.
    Isolates all API interaction, enforces strict JSON schemas, and implements
    enterprise resilience (Retries & Circuit Breakers) mapping to core domain exceptions.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL

    # 1. Protect with Circuit Breaker (Trip after 3 consecutive fatal failures)
    @circuit_breaker("google_genai", failure_threshold=3, recovery_timeout=60)
    # 2. Protect with Retry & Jitter (Retry 3 times for transient 429s/503s)
    @with_retry_and_jitter(max_retries=3, base_delay=2.0)
    async def _execute_llm_call(
        self, contents: str, config: types.GenerateContentConfig
    ) -> MacroAnalysis:
        """The private, heavily protected method that actually touches the network."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=contents, config=config
            )

            # Inspect for safety blocks or empty candidates
            if not response.candidates:
                raise LLMGenerationError("Gemini returned an empty response with no candidates.")

            finish_reason = response.candidates[0].finish_reason
            if finish_reason != "STOP":
                raise LLMGenerationError(
                    f"Generation halted abnormally. Finish reason: {finish_reason}"
                )

            if not response.parsed:
                raise LLMGenerationError(
                    "Gemini returned STOP, but Pydantic parsing evaluated to None."
                )

            return response.parsed

        except APIError as e:
            # Map Google's proprietary errors to our Core Domain Exceptions
            if e.code == 429:
                logger.warning(f"Google GenAI Rate Limit hit. Code 429: {e.message}")
                raise RateLimitExceeded(source="Google GenAI", retry_after=10)
            elif e.code in [500, 502, 503, 504]:
                logger.warning(f"Google GenAI Offline/Unavailable. Code {e.code}: {e.message}")
                raise SourceOfflineError(source="Google GenAI", status_code=e.code)
            else:
                logger.error(f"Fatal Google GenAI Error ({e.code}): {e.message}")
                raise

    async def generate_brief(
        self, sanitized_context: dict[str, Any], system_prompt: str
    ) -> MacroAnalysis:
        """
        Public interface. Prepares the configuration and
        delegates to the resilient execution method.
        """
        logger.info(f"Preparing to trigger Gemini LLM ({self.model_name}) for analysis.")

        # Native System Instructions for absolute prompt security
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=MacroAnalysis,
            temperature=0.2,
        )

        # Delegate the actual network call to the protected inner method
        return await self._execute_llm_call(contents=json.dumps(sanitized_context), config=config)
