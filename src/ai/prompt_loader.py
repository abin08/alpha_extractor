from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

# Resolve the absolute path to the prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"


def get_system_prompt(version: str = "v1") -> str:
    """
    Loads the versioned system prompt from the filesystem.
    """
    file_path = PROMPTS_DIR / f"morning_brief_{version}.txt"

    try:
        prompt_text = file_path.read_text(encoding="utf-8")
        logger.debug(f"Successfully loaded system prompt: morning_brief_{version}.txt")
        return prompt_text
    except FileNotFoundError:
        logger.error(f"System prompt file not found at path: {file_path}")
        raise ValueError(f"Prompt template {version} does not exist.")
