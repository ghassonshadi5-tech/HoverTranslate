from __future__ import annotations

import pytest

from hovertranslate.core.errors import ExtractionError
from hovertranslate.extraction.clipboard_source import (
    ClipboardSnapshot,
    ClipboardSource,
)


class FakeClipboardBackend:
    def __init__(
        self,
        text: str = "",
        restore_fail: bool = False,
    ) -> None:
        self.text = text
        self.restore_fail = restore_fail
        self.snapshot_calls = 0
        self.restore_calls = 0
        self.read_calls = 0
        self.restored_snapshot: ClipboardSnapshot | None = None
    def clear(self) -> None:
        self.text = ""
    def snapshot(self) -> ClipboardSnapshot:
        self.snapshot_calls += 1
        return ClipboardSnapshot(items={"text/plain": b"original"})

    def restore(self, snapshot: ClipboardSnapshot) -> None:
        self.restore_calls += 1
        self.restored_snapshot = snapshot

        if self.restore_fail:
            raise RuntimeError("restore failed")

    def read_text(self) -> str:
        self.read_calls += 1
        return self.text


def test_extract_selected_text_success() -> None:
    backend = FakeClipboardBackend(text="مرحبا")
    source = ClipboardSource(backend)
    calls: list[str] = []

    result = source.extract_selected_text(lambda: calls.append("copy"))

    assert result.success is True
    assert result.text == "مرحبا"
    assert result.source == "clipboard"
    assert calls == ["copy"]
    assert backend.snapshot_calls == 1
    assert backend.restore_calls == 1


def test_extract_selected_text_empty() -> None:
    backend = FakeClipboardBackend(text="")
    source = ClipboardSource(backend)

    result = source.extract_selected_text(lambda: None)

    assert result.success is False
    assert result.text is None
    assert result.source == "none"
    assert backend.restore_calls == 1


def test_copy_action_failure_restores_and_raises() -> None:
    backend = FakeClipboardBackend()
    source = ClipboardSource(backend)

    def bad_copy() -> None:
        raise RuntimeError("copy failed")

    with pytest.raises(ExtractionError):
        source.extract_selected_text(bad_copy)

    assert backend.restore_calls == 1


def test_restore_failure_raises_extraction_error() -> None:
    backend = FakeClipboardBackend(text="مرحبا", restore_fail=True)
    source = ClipboardSource(backend)

    with pytest.raises(ExtractionError):
        source.extract_selected_text(lambda: None)

    assert backend.restore_calls == 1


def test_snapshot_repr_does_not_expose_content() -> None:
    snapshot = ClipboardSnapshot(
        items={"text/plain": "secret-content".encode("utf-8")}
    )

    assert "secret-content" not in repr(snapshot)