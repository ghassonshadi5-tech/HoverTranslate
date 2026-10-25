
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol

from hovertranslate.core.errors import ExtractionError
from hovertranslate.core.types import ExtractionResult

if TYPE_CHECKING:
    from PySide6.QtGui import QClipboard


@dataclass(slots=True)
class ClipboardSnapshot:
    """Stores clipboard formats temporarily without exposing payloads in repr."""

    items: dict[str, bytes] = field(default_factory=dict)
    skipped_formats: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return (
            f"ClipboardSnapshot(formats={len(self.items)}, "
            f"skipped={len(self.skipped_formats)})"
        )


class ClipboardBackendLike(Protocol):
    def snapshot(self) -> ClipboardSnapshot: ...
    def restore(self, snapshot: ClipboardSnapshot) -> None: ...
    def read_text(self) -> str: ...
    def clear(self) -> None: ...


class ClipboardSource:
    def __init__(self, backend: ClipboardBackendLike) -> None:
        self._backend = backend

    def snapshot_clipboard(self) -> ClipboardSnapshot:
        try:
            return self._backend.snapshot()
        except Exception as exc:
            raise ExtractionError(
                f"Could not snapshot clipboard: {exc}"
            ) from exc

    def clear_clipboard(self) -> None:
        """Clear old clipboard data before copying newly selected text."""
        try:
            self._backend.clear()
        except Exception as exc:
            raise ExtractionError(
                f"Could not clear clipboard: {exc}"
            ) from exc

    def read_current_text(self) -> str:
        """Read the clipboard without restoring the previous contents."""
        try:
            return self._backend.read_text()
        except Exception as exc:
            raise ExtractionError(
                f"Clipboard read failed: {exc}"
            ) from exc

    def finish_extraction(
        self,
        snapshot: ClipboardSnapshot,
        copied_text: str | None = None,
    ) -> ExtractionResult:
        """Read the copied text, then restore the previous clipboard."""
        text = copied_text
        read_error: Exception | None = None

        try:
            if copied_text is None:
                try:
                    text = self._backend.read_text()
                except Exception as exc:
                    read_error = exc
        finally:
            self._safe_restore(snapshot)

        if read_error is not None:
            raise ExtractionError(
                f"Clipboard read failed: {read_error}"
            ) from read_error

        if not text or not text.strip():
            return ExtractionResult(
                text=None,
                source="none",
                success=False,
            )

        return ExtractionResult(
            text=text,
            source="clipboard",
            success=True,
        )

    def restore_clipboard(self, snapshot: ClipboardSnapshot) -> None:
        self._safe_restore(snapshot)

    def extract_selected_text(
        self,
        copy_action: Callable[[], None],
    ) -> ExtractionResult:
        """Synchronous compatibility method; asynchronous GUI flow is preferred."""
        snapshot = self.snapshot_clipboard()

        try:
            self.clear_clipboard()
            copy_action()
            return self.finish_extraction(snapshot)
        except Exception:
            self._safe_restore(snapshot)
            raise

    def _safe_restore(self, snapshot: ClipboardSnapshot) -> None:
        try:
            self._backend.restore(snapshot)
        except Exception as exc:
            raise ExtractionError(
                f"Clipboard restore failed: {exc}"
            ) from exc


class QtClipboardBackend:
    def __init__(self, clipboard: "QClipboard") -> None:
        self._clipboard = clipboard

    def snapshot(self) -> ClipboardSnapshot:
        mime = self._clipboard.mimeData()

        if mime is None:
            return ClipboardSnapshot()

        items: dict[str, bytes] = {}
        skipped: list[str] = []

        for fmt in mime.formats():
            name = str(fmt)
            try:
                items[name] = bytes(mime.data(fmt))
            except Exception:
                skipped.append(name)

        return ClipboardSnapshot(
            items=items,
            skipped_formats=tuple(skipped),
        )

    def restore(self, snapshot: ClipboardSnapshot) -> None:
        from PySide6.QtCore import QByteArray, QMimeData

        mime = QMimeData()

        for fmt, raw in snapshot.items.items():
            mime.setData(fmt, QByteArray(raw))

        self._clipboard.setMimeData(mime)

    def read_text(self) -> str:
        return str(self._clipboard.text())

    def clear(self) -> None:
        self._clipboard.clear()
