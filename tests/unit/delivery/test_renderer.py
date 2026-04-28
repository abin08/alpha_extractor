import pytest
from jinja2 import TemplateNotFound

from src.delivery.renderer import EmailRenderer


@pytest.fixture
def renderer():
    return EmailRenderer()


def test_render_template_success(renderer):
    """Verify that the engine successfully loads a file and injects variables."""
    context = {
        "subject": "System Alert",
        "header": "Alpha Extractor Ready",
        "message": "The templating engine is online.",
    }

    # We use our dummy base.html to verify functionality
    result = renderer.render_template("base.html", context)

    assert "<title>System Alert</title>" in result
    assert "<h1>Alpha Extractor Ready</h1>" in result
    assert "<p>The templating engine is online.</p>" in result


def test_render_template_autoescape(renderer):
    """Verify that Jinja2 autoescape is active to prevent HTML injection."""
    context = {
        "subject": "Test",
        "header": "Test",
        "message": "<script>alert('hack');</script>",
    }

    result = renderer.render_template("base.html", context)

    # The brackets should be escaped into HTML entities
    assert "&lt;script&gt;alert(&#39;hack&#39;);&lt;/script&gt;" in result
    assert "<script>" not in result


def test_render_template_not_found(renderer):
    """Verify that missing templates raise the appropriate Jinja exception."""
    with pytest.raises(TemplateNotFound):
        renderer.render_template("does_not_exist.html", {})
