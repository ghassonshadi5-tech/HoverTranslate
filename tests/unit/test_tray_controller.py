from __future__ import annotations

import pytest

from hovertranslate.ui.tray_controller import TrayAction, TrayController


class FakeTrayBackend:
    def __init__(self) -> None:
        self.tooltips: list[str] = []
        self.messages: list[tuple[str, str]] = []

    def set_tooltip(self, text: str) -> None:
        self.tooltips.append(text)

    def show_message(self, title: str, message: str) -> None:
        self.messages.append((title, message))


def test_initial_tooltip_is_active() -> None:
    backend = FakeTrayBackend()
    TrayController(backend=backend)

    assert backend.tooltips == ["HoverTranslate - يعمل"]


def test_toggle_pause_updates_tooltip_and_state() -> None:
    backend = FakeTrayBackend()
    controller = TrayController(backend=backend)

    paused = controller.toggle_pause()

    assert paused is True
    assert controller.paused is True
    assert backend.tooltips[-1] == "HoverTranslate - متوقف مؤقتاً"


def test_set_paused_false_restores_active_tooltip() -> None:
    backend = FakeTrayBackend()
    controller = TrayController(backend=backend)

    controller.set_paused(True)
    controller.set_paused(False)

    assert controller.paused is False
    assert backend.tooltips[-1] == "HoverTranslate - يعمل"


def test_handle_toggle_pause_action_calls_callback_and_toggles() -> None:
    received: list[TrayAction] = []
    controller = TrayController(on_action=received.append)

    controller.handle_action(TrayAction.TOGGLE_PAUSE)

    assert received == [TrayAction.TOGGLE_PAUSE]
    assert controller.paused is True


def test_handle_string_action_is_resolved() -> None:
    received: list[TrayAction] = []
    controller = TrayController(on_action=received.append)

    controller.handle_action("open_settings")

    assert received == [TrayAction.OPEN_SETTINGS]
    assert controller.paused is False


def test_quit_action_calls_callback() -> None:
    received: list[TrayAction] = []
    controller = TrayController(on_action=received.append)

    controller.handle_action(TrayAction.QUIT)

    assert received == [TrayAction.QUIT]


def test_notify_sends_message_to_backend() -> None:
    backend = FakeTrayBackend()
    controller = TrayController(backend=backend)

    controller.notify("HoverTranslate", "تم إيقاف الخدمة مؤقتاً")

    assert backend.messages == [("HoverTranslate", "تم إيقاف الخدمة مؤقتاً")]


def test_invalid_action_string_raises_value_error() -> None:
    controller = TrayController()

    with pytest.raises(ValueError):
        controller.handle_action("unknown_action")