from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon
import ctypes

from hovertranslate.config.settings import SettingsService
from hovertranslate.core.types import TriggerContext
from hovertranslate.diagnostics.logging_setup import configure_logging
from hovertranslate.extraction.clipboard_source import ClipboardSource, QtClipboardBackend
from hovertranslate.translation.provider import TranslationOutcome, TranslationProvider
from hovertranslate.ui.control_window import ControlWindow
from hovertranslate.ui.tooltip_window import TooltipWindow



def send_copy() -> None:
    """Send Ctrl+C using Windows virtual-key codes."""
    if sys.platform != "win32":
        raise RuntimeError("send_copy currently supports Windows only.")

    user32 = ctypes.windll.user32
    vk_control = 0x11
    vk_c = 0x43
    keyup = 0x0002

    user32.keybd_event(vk_control, 0, 0, 0)
    try:
        user32.keybd_event(vk_c, 0, 0, 0)
        try:
            time.sleep(0.04)
        finally:
            user32.keybd_event(vk_c, 0, keyup, 0)
    finally:
        user32.keybd_event(vk_control, 0, keyup, 0)


class TranslateWorker(QObject):
    finished = Signal(object, int, int, int)
    error = Signal(str, int, int, int)

    def __init__(self, timeout_s: float) -> None:
        super().__init__()
        self._timeout_s = float(timeout_s)

    @Slot(str, str, int, int, int)
    def do_translate(
        self, text: str, lang_pair: str, x: int, y: int, generation: int
    ) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        provider: TranslationProvider | None = None
        try:
            provider = TranslationProvider(timeout_s=self._timeout_s)
            outcome = loop.run_until_complete(
                provider.translate(text=text, lang_pair=lang_pair, generation=generation)
            )
            self.finished.emit(outcome, x, y, generation)
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}", x, y, generation)
        finally:
            try:
                if provider is not None:
                    loop.run_until_complete(provider.aclose())
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as exc:
                print(f"[ERROR] Translation cleanup failed: {type(exc).__name__}: {exc}")
            finally:
                asyncio.set_event_loop(None)
                loop.close()


class HoverTranslateApp(QObject):
    _trigger_received = Signal(str, object)
    _translate_requested = Signal(str, str, int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        configure_logging()

        self._settings_service = SettingsService()
        self._settings_service.load()
        settings = self._settings_service.current

        self._clipboard_source = ClipboardSource(
            backend=QtClipboardBackend(self._app.clipboard())
        )
        self._window = ControlWindow(
            settings=settings,
            on_direction_changed=self._on_direction_changed,
        )
        self._direction = settings.default_lang_pair
        self._enabled = False
        # A direction must be selected each time F9 re-enables translation.
        self._direction_selected = False
        self._tooltip_window = TooltipWindow(settings)
        self._generation = 0
        self._last_cursor_pos: tuple[int, int] | None = None
        self._stationary_since = time.monotonic()
        self._idle_handled = False
        self._last_translated_signature: tuple[str, str] | None = None
        self._pending_snapshot = None
        self._copy_in_progress = False
        self._copy_deadline = 0.0
        self._copy_attempts = 0

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_cursor)

        self._copy_finish_timer = QTimer(self)
        self._copy_finish_timer.setSingleShot(True)
        self._copy_finish_timer.timeout.connect(self._finish_copy)

        self._worker_obj = TranslateWorker(timeout_s=float(settings.request_timeout_s))
        self._worker_thread = QThread(self)
        self._worker_obj.moveToThread(self._worker_thread)
        self._translate_requested.connect(
            self._worker_obj.do_translate,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._worker_obj.finished.connect(
            self._on_translation_ready,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._worker_obj.error.connect(
            self._on_error,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._worker_thread.start()

        from hovertranslate.input.monitor import InputMonitor
        self._monitor = InputMonitor(
            settings=self._settings_service,
            on_trigger=self._handle_trigger_from_monitor,
        )
        self._trigger_received.connect(self._process_trigger_in_main)

        self._tray = QSystemTrayIcon(self._app)
        self._tray.setIcon(
            self._app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self._tray.setToolTip("HoverTranslate")
        menu = QMenu()
        toggle_action = menu.addAction("تشغيل / إيقاف الترجمة (F9)")
        toggle_action.triggered.connect(self._toggle_enabled)
        quit_action = menu.addAction("خروج")
        quit_action.triggered.connect(self.shutdown)
        self._tray.setContextMenu(menu)
        self._tray.show()

        self._monitor.start()
        print("=" * 50)
        print("HoverTranslate جاهز. اضغط F9 لتشغيل الترجمة أو إيقافها.")
        print("بعد التشغيل، حدد النص وانتظر ثانية واحدة.")
        print("=" * 50)

    def _handle_trigger_from_monitor(self, kind: Any, context: TriggerContext) -> None:
        self._trigger_received.emit(str(kind), context)

    @Slot(str, object)
    def _process_trigger_in_main(self, kind: str, context: object) -> None:
        self._toggle_enabled()

    @Slot()
    def _toggle_enabled(self) -> None:
        self._enabled = not self._enabled
        self._window.set_enabled(self._enabled)
        if self._enabled:
            self._direction_selected = False
            self._tooltip_window.dismiss()
            self._last_cursor_pos = None
            self._stationary_since = time.monotonic()
            self._idle_handled = False
            self._poll_timer.start()
            print("[INFO] Translation enabled. Choose a direction.")
        else:
            self._direction_selected = False
            self._poll_timer.stop()
            self._cancel_pending_copy()
            self._tooltip_window.dismiss()
            self._window.clear_translation()
            print("[INFO] Translation disabled.")

    def _on_direction_changed(self, lang_pair: str) -> None:
        if lang_pair in {"ar-ru", "ru-ar"} and self._enabled:
            self._direction = lang_pair
            self._direction_selected = True
            self._last_translated_signature = None
            self._last_cursor_pos = None
            self._stationary_since = time.monotonic()
            self._idle_handled = False
            self._tooltip_window.show_waiting(QCursor.pos())
            print(f"[INFO] Translation direction: {lang_pair}")

    @Slot()
    def _poll_cursor(self) -> None:
        if not self._enabled or self._copy_in_progress:
            return
        pos = QCursor.pos()
        current = (pos.x(), pos.y())

        # Before choosing a direction, keep the direction panel reachable and
        # do not interpret time spent over its buttons as text-hover time.
        if not self._direction_selected:
            if self._window.cursor_near_window(pos):
                self._last_cursor_pos = current
                self._stationary_since = time.monotonic()
                self._idle_handled = False
                return
            self._window.follow_cursor(pos)
            self._last_cursor_pos = current
            self._stationary_since = time.monotonic()
            self._idle_handled = False
            return

        # Once a direction is selected, the result tooltip follows the pointer.
        self._tooltip_window.follow_cursor(pos)

        if self._last_cursor_pos is None:
            self._last_cursor_pos = current
            self._stationary_since = time.monotonic()
            return

        dx = current[0] - self._last_cursor_pos[0]
        dy = current[1] - self._last_cursor_pos[1]
        if dx * dx + dy * dy >= 9:
            self._last_cursor_pos = current
            self._stationary_since = time.monotonic()
            self._idle_handled = False
            return

        if not self._idle_handled and time.monotonic() - self._stationary_since >= 1.0:
            self._idle_handled = True
            self._begin_copy(pos)

    def _begin_copy(self, pos: QPoint) -> None:
        if not self._enabled or self._copy_in_progress:
            return
        try:
            # Save the user's current clipboard before changing it.
            self._pending_snapshot = self._clipboard_source.snapshot_clipboard()

            # Clear old clipboard contents so a failed Ctrl+C cannot make the
            # app translate a previously copied string.
            self._clipboard_source.clear_clipboard()

            self._copy_in_progress = True
            self._copy_attempts = 1
            send_copy()

            # Some applications may miss the first Ctrl+C immediately after the
            # clipboard is cleared. Retry while the clipboard is still empty.
            self._copy_deadline = time.monotonic() + 1.5
            self._copy_finish_timer.start(150)
        except Exception as exc:
            print(f"[ERROR] Could not copy selected text: {type(exc).__name__}: {exc}")
            self._cancel_pending_copy()

    @Slot()
    def _finish_copy(self) -> None:
        snapshot = self._pending_snapshot
        if snapshot is None:
            self._copy_in_progress = False
            return

        try:
            copied_text = self._clipboard_source.read_current_text()
        except Exception as exc:
            if time.monotonic() < self._copy_deadline:
                self._copy_finish_timer.start(60)
                return
            self._pending_snapshot = None
            self._copy_in_progress = False
            self._copy_deadline = 0.0
            try:
                # Make one final read attempt; finish_extraction always restores
                # the original clipboard, including when that read fails.
                self._clipboard_source.finish_extraction(snapshot)
            except Exception as final_exc:
                print(
                    f"[ERROR] Clipboard extraction failed: "
                    f"{type(final_exc).__name__}: {final_exc}"
                )
            return

        if not copied_text or not copied_text.strip():
            if time.monotonic() < self._copy_deadline:
                try:
                    # Re-issue Ctrl+C because some target apps can miss the first
                    # key event after a clipboard clear. The clipboard was cleared
                    # first, so old text cannot be mistaken for the new selection.
                    send_copy()
                    self._copy_attempts += 1
                except Exception as exc:
                    print(
                        f"[WARN] Ctrl+C retry {self._copy_attempts} failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                self._copy_finish_timer.start(150)
                return

        self._pending_snapshot = None
        self._copy_in_progress = False
        self._copy_deadline = 0.0
        self._copy_attempts = 0
        try:
            result = self._clipboard_source.finish_extraction(
                snapshot,
                copied_text=copied_text,
            )
        except Exception as exc:
            print(f"[ERROR] Clipboard extraction failed: {type(exc).__name__}: {exc}")
            return

        if not self._enabled:
            return
        if not result.success or not result.text:
            self._last_translated_signature = None
            print(
                "[WARN] No selected text was captured from the clipboard "
                f"after {max(self._copy_attempts, 1)} Ctrl+C attempt(s)."
            )
            self._tooltip_window.show_status(
                "لم يتم التقاط النص المحدد. حدّد النص ثم انتظر ثانية واحدة.",
                QCursor.pos(),
                error=True,
            )
            return
        text = result.text.strip()
        if len(text) < 2:
            print(f"[WARN] Captured text is too short (length={len(text)}).")
            self._tooltip_window.show_status(
                "النص المحدد قصير جدًا أو لم يُنسخ بشكل صحيح.",
                QCursor.pos(),
                error=True,
            )
            return

        print(f"[INFO] Selected text captured successfully (length={len(text)}).")
        print(
            f"[DEBUG] Translation input ready "
            f"(direction={self._direction}, length={len(text)})."
        )

        signature = (text, self._direction)
        if signature == self._last_translated_signature:
            return
        self._last_translated_signature = signature

        pos = QCursor.pos()
        self._generation += 1
        self._tooltip_window.show_status("جارٍ الترجمة…", pos)
        self._translate_requested.emit(
            text, self._direction, pos.x(), pos.y(), self._generation
        )

    def _cancel_pending_copy(self) -> None:
        self._copy_finish_timer.stop()
        self._copy_in_progress = False
        self._copy_deadline = 0.0
        self._copy_attempts = 0
        snapshot = self._pending_snapshot
        self._pending_snapshot = None
        if snapshot is not None:
            try:
                self._clipboard_source.restore_clipboard(snapshot)
            except Exception as exc:
                print(f"[ERROR] Clipboard restore failed: {type(exc).__name__}: {exc}")

    @Slot(object, int, int, int)
    def _on_translation_ready(
        self, outcome: TranslationOutcome, x: int, y: int, generation: int
    ) -> None:
        if not self._enabled or generation != self._generation:
            return
        print(
            f"[INFO] Translation provider finished: status={outcome.status}, "
            f"elapsed_ms={outcome.elapsed_ms}."
        )
        print(
            f"[DEBUG] Translation output received "
            f"(length={len(outcome.result or '')})."
        )
        if outcome.status != "ok" or not outcome.result:
            # Permit another attempt for the same text after a provider failure.
            self._last_translated_signature = None
        self._tooltip_window.show_translation(outcome, QCursor.pos())

    @Slot(str, int, int, int)
    def _on_error(self, message: str, x: int, y: int, generation: int) -> None:
        print(f"[ERROR] Translation worker failed: {message}")
        if not self._enabled or generation != self._generation:
            return
        self._last_translated_signature = None
        self._tooltip_window.show_status(
            "تعذرت الترجمة. راجع رسالة الخطأ في نافذة PowerShell.",
            QCursor.pos(),
            error=True,
        )

    def shutdown(self) -> None:
        self._poll_timer.stop()
        self._cancel_pending_copy()
        self._monitor.stop()
        self._window.hide()
        self._tooltip_window.dismiss()
        self._tray.hide()
        self._worker_thread.quit()
        self._worker_thread.wait()
        self._app.quit()

    def run(self) -> int:
        try:
            return self._app.exec()
        except KeyboardInterrupt:
            self.shutdown()
            return 0


if __name__ == "__main__":
    app = HoverTranslateApp()
    sys.exit(app.run())
