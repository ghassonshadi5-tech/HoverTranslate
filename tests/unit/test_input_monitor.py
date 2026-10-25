from __future__ import annotations

from pathlib import Path

from pynput import keyboard

from hovertranslate.config.settings import SettingsService
from hovertranslate.core.types import TriggerContext
from hovertranslate.input.monitor import InputMonitor


class FakeKeyboardBackend:
    def __init__(self) -> None:
        self.on_press = None
        self.on_release = None
        self.started = False
        self.stopped = False
        self.position = (120, 240)

    def start(self, on_press, on_release) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.started = True
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def get_cursor_position(self) -> tuple[int, int]:
        return self.position


def _make_monitor(
    tmp_path: Path,
) -> tuple[InputMonitor, FakeKeyboardBackend, list[tuple[str, TriggerContext]]]:
    settings = SettingsService(base_dir=tmp_path)
    settings.load()

    backend = FakeKeyboardBackend()
    events: list[tuple[str, TriggerContext]] = []

    monitor = InputMonitor(
        settings=settings,
        backend=backend,
        on_trigger=lambda kind, context: events.append((kind, context)),
    )

    return monitor, backend, events


def test_f9_triggers_hover_event(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()

    assert backend.started is True

    backend.on_press(keyboard.Key.f9)

    assert len(events) == 1
    kind, context = events[0]
    assert kind == "hover"
    assert context.point_x == 120
    assert context.point_y == 240


def test_modifier_blocks_trigger(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()

    for modifier in (
        keyboard.Key.shift,
        keyboard.Key.ctrl,
        keyboard.Key.cmd,
    ):
        backend.on_press(modifier)
        backend.on_press(keyboard.Key.f9)
        backend.on_release(keyboard.Key.f9)
        backend.on_release(modifier)

    assert events == []


def test_repeated_f9_while_held_emits_once(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()

    backend.on_press(keyboard.Key.f9)
    backend.on_press(keyboard.Key.f9)
    backend.on_press(keyboard.Key.f9)

    assert len(events) == 1


def test_release_f9_allows_next_trigger(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()

    backend.on_press(keyboard.Key.f9)
    backend.on_release(keyboard.Key.f9)
    backend.on_press(keyboard.Key.f9)

    assert len(events) == 2


def test_pause_blocks_trigger(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()
    monitor.pause()

    backend.on_press(keyboard.Key.f9)

    assert events == []
    assert monitor.is_paused is True


def test_resume_allows_trigger(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()
    monitor.pause()
    monitor.resume()

    backend.on_press(keyboard.Key.f9)

    assert len(events) == 1


def test_stop_prevents_trigger_and_stops_backend(tmp_path: Path) -> None:
    monitor, backend, events = _make_monitor(tmp_path)
    monitor.start()
    monitor.stop()

    backend.on_press(keyboard.Key.f9)

    assert events == []
    assert backend.stopped is True
    assert monitor.is_running is False