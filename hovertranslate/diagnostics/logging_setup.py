from __future__ import annotations

import re
import sys
from typing import Any

from loguru import logger


SENSITIVE_KEYS = {
    "text",
    "source_text",
    "translated_text",
    "result",
    "translation",
    "secret",
    "api_key",
    "password",
    "token",
    "image",
    "region",
    "content",
}

_PII_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)(\S+)"),
]


def scrub_sensitive_message(message: str) -> str:
    """Removes obvious sensitive key/value patterns from a log message."""
    scrubbed = message

    for pattern in _PII_PATTERNS:
        scrubbed = pattern.sub(r"\1[REDACTED]", scrubbed)

    return scrubbed


def sensitive_filter(record: dict[str, Any]) -> bool:
    """Loguru filter that blocks explicit sensitive fields from being logged."""
    extra = record.get("extra") or {}

    for key in extra.keys():
        if key.lower() in SENSITIVE_KEYS:
            return False

    record["message"] = scrub_sensitive_message(record["message"])
    return True



def configure_logging(level: str = "INFO") -> None:
    """Configures Loguru with a mandatory privacy filter."""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    log_sink = sys.stderr

    if log_sink is None:
        logger.add(
            "hovertranslate.log",
            level=level,
            filter=sensitive_filter,
            format=log_format,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )
        return

    logger.add(
        log_sink,
        level=level,
        filter=sensitive_filter,
        format=log_format,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
