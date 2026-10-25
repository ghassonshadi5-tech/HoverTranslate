from __future__ import annotations

from hovertranslate.diagnostics.logging_setup import (
    scrub_sensitive_message,
    sensitive_filter,
)


def test_scrub_sensitive_message() -> None:
    message = "api_key=abc123 password=secret"
    scrubbed = scrub_sensitive_message(message)

    assert "abc123" not in scrubbed
    assert "secret" not in scrubbed


def test_sensitive_filter_blocks_extra_content_field() -> None:
    record = {
        "message": "safe message",
        "extra": {"text": "user private text"},
    }

    assert sensitive_filter(record) is False


def test_sensitive_filter_allows_safe_record() -> None:
    record = {
        "message": "provider status ok",
        "extra": {"status": "ok"},
    }

    assert sensitive_filter(record) is True