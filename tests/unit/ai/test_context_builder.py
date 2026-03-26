from src.ai.context_builder import ContextBuilder


def test_sanitize_html_string():
    dirty_html = "<p>Reliance announced a <b>massive</b> profit.</p><script>alert('hack');</script>"
    clean_text = ContextBuilder._sanitize_text(dirty_html)

    assert "Reliance announced a massive profit." in clean_text
    assert "<p>" not in clean_text
    assert "<script>" not in clean_text


def test_whitespace_compression():
    messy_text = "Here   is \n\n\n some    \t  poorly formatted  text."
    clean_text = ContextBuilder._sanitize_text(messy_text)

    assert clean_text == "Here is \n\n some poorly formatted text."


def test_recursive_payload_cleaning():
    raw_payload = {
        "ticker": "RELIANCE.NS",
        "price": 1400.50,
        "is_active": True,
        "news": [{"title": "<h1>Q3 Earnings</h1>", "summary": "Up   by 10%"}],
        "nested_data": {"description": "<div class='test'>Core business operations.</div>"},
    }

    cleaned_payload = ContextBuilder.build(raw_payload)

    assert cleaned_payload["price"] == 1400.50
    assert cleaned_payload["is_active"] is True
    assert cleaned_payload["news"][0]["title"] == "Q3 Earnings"
    assert cleaned_payload["news"][0]["summary"] == "Up by 10%"
    assert cleaned_payload["nested_data"]["description"] == "Core business operations."


def test_ascii_and_control_char_compression():
    # Contains a zero-width space (\u200b) and a massive line of hyphens
    dirty_text = "Headline\u200b\n--------------------------------------------------\nBody text"
    clean_text = ContextBuilder._sanitize_text(dirty_text)

    # The zero-width space should be gone, and hyphens capped at 3
    assert clean_text == "Headline\n---\nBody text"


def test_empty_node_pruning():
    raw_payload = {
        "ticker": "RELIANCE.NS",
        "valid_metric": 0,  # Should be kept
        "is_active": False,  # Should be kept
        "empty_string": "   ",  # Should be pruned
        "malicious_script": "<script>console.log('x');</script>",  # Becomes empty -> pruned
        "empty_list": [],  # Should be pruned
        "nested_empty": {"nothing_here": {}},  # Should be pruned
    }

    cleaned = ContextBuilder.build(raw_payload)

    assert "ticker" in cleaned
    assert cleaned["valid_metric"] == 0
    assert cleaned["is_active"] is False
    assert "empty_string" not in cleaned
    assert "malicious_script" not in cleaned
    assert "empty_list" not in cleaned
    assert "nested_empty" not in cleaned
