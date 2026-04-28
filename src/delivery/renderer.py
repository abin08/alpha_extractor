from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from src.core.logger import get_logger

logger = get_logger(__name__)


class EmailRenderer:
    """
    Handles the compilation of HTML templates and injection of dynamic variables using Jinja2.
    Isolates the presentation layer from the core orchestration logic.
    """

    def __init__(self):
        # Dynamically resolve the absolute path to the templates directory
        # This ensures it works whether run from tests, local dev, or inside Docker
        base_dir = Path(__file__).parent.resolve()
        self.template_dir = base_dir / "templates"

        # Initialize Jinja2 environment with strict
        # undefined behavior (fails fast if variable missing)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,  # Protects against XSS injection
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.debug(f"EmailRenderer initialized. Template directory set to: {self.template_dir}")

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """
        Loads an HTML template and compiles it with the provided context dictionary.

        Args:
            template_name (str): The filename of the template (e.g., 'base.html')
            context (dict): The variables to inject into the template

        Returns:
            str: The fully rendered HTML string
        """
        try:
            template = self.env.get_template(template_name)
            rendered_html = template.render(**context)
            logger.debug(f"Successfully rendered template: {template_name}")
            return rendered_html
        except TemplateNotFound:
            logger.error(f"Template '{template_name}' not found in {self.template_dir}")
            raise
        except Exception as e:
            logger.error(f"Error rendering template '{template_name}': {e}")
            raise
