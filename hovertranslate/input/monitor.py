from __future__ import annotations

import threading
from typing import Any, Callable, Protocol

from pynput import keyboard, mouse

from hovertranslate.config.settings import SettingsService
from hovertranslate.core.types import TriggerContext, TriggerKind


TRIGGER_KEY = keyboard.Key.f9
MODIFIER_KEYS: set[Any] = {
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
}
TriggerCallback = Callable[[TriggerKind, TriggerContext], None]


class KeyboardBackendLike(Protocol):
    def start(self, on_press: Callable[[Any], None], on_release: Callable[[Any], None]) -> None: ...
    def stop(self) -> None: ...
    def get_cursor_position(self) -> tuple[int, int]: ...


class PynputKeyboardBackend:
    def __init__(self) -> None:
        self._listener: keyboard.Listener | None = None
        self._mouse = mouse.Controller()

    def start(self, on_press: Callable[[Any], None], on_release: Callable[[Any], None]) -> None:
        if self._listener is not None:
            self.stop()
        self._listener = keyboard.Listener(
            on_press=on_press, on_release=on_release, suppress=False
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()
            if listener.is_alive():
                listener.join(timeout=1.0)

    def get_cursor_position(self) -> tuple[int, int]:
        position = self._mouse.position
        return int(position.x), int(position.y)


class InputMonitor:
    """Watches F9; main-window logic toggles the translation mode."""

    def __init__(
        self,
        settings: SettingsService,
        backend: KeyboardBackendLike | None = None,
        on_trigger: TriggerCallback | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend or PynputKeyboardBackend()
        self._on_trigger = on_trigger
        self._lock = threading.RLock()
        self._running = False
        self._paused = False
        self._pressed_modifiers: set[Any] = set()
        self._trigger_active = False

    def set_trigger_callback(self, callback: TriggerCallback) -> None:
        self._on_trigger = callback

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = False
            self._pressed_modifiers.clear()
            self._trigger_active = False
        try:
            self._backend.start(self._handle_press, self._handle_release)
        except Exception:
            with self._lock:
                self._running = False
            raise

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._pressed_modifiers.clear()
            self._trigger_active = False
        self._backend.stop()

    def _handle_press(self, key: Any) -> None:
        callback = None
        context = None
        with self._lock:
            if not self._running:
                return
            if key in MODIFIER_KEYS:
                self._pressed_modifiers.add(key)
                return
            if key != TRIGGER_KEY or self._pressed_modifiers or self._trigger_active:
                return
            self._trigger_active = True
            try:
                x, y = self._backend.get_cursor_position()
            except Exception:
                x, y = 0, 0
            context = TriggerContext(kind="hover", point_x=x, point_y=y)
            callback = self._on_trigger

        if callback is not None and context is not None:
            callback("hover", context)

    def _handle_release(self, key: Any) -> None:
        with self._lock:
            if key in MODIFIER_KEYS:
                self._pressed_modifiers.discard(key)
            elif key == TRIGGER_KEY:
                self._trigger_active = False
