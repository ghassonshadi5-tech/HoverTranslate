from __future__ import annotations

from enum import Enum
from typing import Callable, Protocol


class TrayAction(str, Enum):
    TOGGLE_PAUSE = "toggle_pause"
    OPEN_SETTINGS = "open_settings"
    QUIT = "quit"


class TrayBackendLike(Protocol):
    def set_tooltip(self, text: str) -> None: ...

    def show_message(self, title: str, message: str) -> None: ...


class TrayController:
    """
    منطق أيقونة النظام.

    المسؤوليات:
    - تتبع حالة الإيقاف المؤقت.
    - تحديث tooltip.
    - توجيه أوامر المستخدم إلى التطبيق.
    """

    def __init__(
        self,
        backend: TrayBackendLike | None = None,
        on_action: Callable[[TrayAction], None] | None = None,
    ) -> None:
        self._backend = backend
        self._on_action = on_action
        self._paused = False

        if self._backend is not None:
            self._update_tooltip()

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._update_tooltip()

    def toggle_pause(self) -> bool:
        self._paused = not self._paused
        self._update_tooltip()
        return self._paused

    def handle_action(self, action: TrayAction | str) -> None:
        resolved = action if isinstance(action, TrayAction) else TrayAction(action)

        if resolved is TrayAction.TOGGLE_PAUSE:
            self.toggle_pause()

        if self._on_action is not None:
            self._on_action(resolved)

    def notify(self, title: str, message: str) -> None:
        if self._backend is not None:
            self._backend.show_message(title, message)

    def _update_tooltip(self) -> None:
        if self._backend is None:
            return

        if self._paused:
            text = "HoverTranslate - متوقف مؤقتاً"
        else:
            text = "HoverTranslate - يعمل"

        self._backend.set_tooltip(text)