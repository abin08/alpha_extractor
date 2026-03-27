import pytest

from src.ai.prompt_loader import get_system_prompt


def test_load_existing_prompt():
    # Should successfully load our new v1 prompt
    prompt = get_system_prompt(version="v1")

    assert "You are an elite Quantitative Analyst" in prompt
    assert "NO HALLUCINATIONS" in prompt


def test_load_missing_prompt():
    # Should raise a ValueError if we ask for a version that doesn't exist
    with pytest.raises(ValueError) as excinfo:
        get_system_prompt(version="v99")

    assert "Prompt template v99 does not exist" in str(excinfo.value)
