import re
import warnings
from typing import Any

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from src.core.logger import get_logger

logger = get_logger(__name__)

# Suppress the noisy URL warning
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


class ContextBuilder:
    """
    Utility class for assembling and sanitizing the final context payload
    before it is sent to the LLM. Focuses on token-efficiency and defense.
    """

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Strips HTML/XML tags, control chars, and
        aggressively compresses whitespace."""
        if not text:
            return ""

        # 1. Strip HTML/XML
        soup = BeautifulSoup(text, "lxml")
        clean_text = soup.get_text(separator=" ", strip=True)

        # 2. Strip invisible control characters and zero-width spaces
        # Removes ASCII control chars (except \n, \t) and common Unicode ghosts
        clean_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\ufeff]", "", clean_text)

        # 3. Compress repetitive ASCII dividers (e.g., "--------" becomes "---")
        clean_text = re.sub(r"([=\-_*~])\1{3,}", r"\1\1\1", clean_text)

        # 4. Compress Whitespace
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
        clean_text = re.sub(r"[ \t]{2,}", " ", clean_text)

        return clean_text.strip()

    @classmethod
    def _recursively_clean(cls, data: Any) -> Any:
        """Recursively traverses dicts/lists,
        sanitizing strings and pruning empty nodes."""
        if isinstance(data, str):
            return cls._sanitize_text(data)

        elif isinstance(data, list):
            # Clean items and drop purely empty elements
            cleaned_list = [cls._recursively_clean(item) for item in data]
            return [item for item in cleaned_list if item or item in (False, 0)]

        elif isinstance(data, dict):
            cleaned_dict = {}
            for key, value in data.items():
                cleaned_val = cls._recursively_clean(value)
                # PRUNING: Only keep the key if the value contains actual data
                # (We explicitly check for False and 0 so we don't
                # accidentally delete valid metrics)
                if cleaned_val or cleaned_val in (False, 0):
                    cleaned_dict[key] = cleaned_val
            return cleaned_dict

        else:
            return data

    @classmethod
    def build(cls, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Sanitizes raw ingestion payload for the LLM context window."""
        logger.info(
            f"Initiating context sanitization for payload: {raw_payload.get('ticker', 'Unknown')}"
        )
        sanitized_payload = cls._recursively_clean(raw_payload)
        logger.info("Context sanitization complete.")
        return sanitized_payload
