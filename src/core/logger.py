import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Custom formatter to output logs as strictly structured JSON.
    Perfect for ELK, Datadog, or AWS CloudWatch ingestion.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger_name": record.name,
            "module": record.module,
            "funcName": record.funcName,
            "message": record.getMessage(),
        }

        # Include exception traceback if an error occurred
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_record["exception"] = record.exc_text

        # Merge any extra kwargs passed to the logger
        # (e.g., logger.info("msg", extra={"user": 1}))
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_record.update(record.extra_data)

        return json.dumps(log_record)


def get_logger(name: str = "alpha_extractor") -> logging.Logger:
    """
    Retrieves or creates a configured JSON logger.
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if get_logger is called multiple times
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # In Docker/Cloud environments, logging to stdout is best practice
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())

        logger.addHandler(handler)
        logger.propagate = False  # Prevent double logging to root logger

    return logger


# Instantiate a default global logger for easy imports
logger = get_logger()
