from __future__ import annotations

from PySide6.QtCore import QPoint

import pytest

from hovertranslate.config.settings import Settings
from hovertranslate.translation.provider import TranslationOutcome
from hovertranslate.ui.popup_window import MAX_TEXT_LENGTH, PopupWindow


@pytest.fixture()
def settings() -> Settings:
    return Settings(popup_timeout_s=30, tooltip_offset_px=16, screen_edge_margin_px=40)


@pytest.fixture()
def popup(qtbot, settings: Settings) -> PopupWindow:
    widget = PopupWindow(settings)
    qtbot.addWidget(widget)
    return widget


def test_show_selection_displays_source_and_result(popup: PopupWindow) -> None:
    outcome = TranslationOutcome(result="Привет", status="ok", elapsed_ms=100)
    popup.show_selection("مرحبا بك", outcome, QPoint(400, 300))

    assert popup.isVisible()
    assert popup._source_label.text() == "مرحبا بك"
    assert popup._result_label.text() == "Привет"
    assert popup._arrow_label.isVisible()


def test_long_text_is_truncated(popup: PopupWindow) -> None:
    long_text = "أ" * 600
    outcome = TranslationOutcome(result="ok", status="ok", elapsed_ms=10)
    popup.show_selection(long_text, outcome, QPoint(400, 300))

    displayed = popup._source_label.text()
    assert len(displayed) <= MAX_TEXT_LENGTH + 1  # +1 for ellipsis
    assert displayed.endswith("…")


def test_error_status_shows_message(popup: PopupWindow) -> None:
    outcome = TranslationOutcome(result=None, status="timeout", elapsed_ms=4000)
    popup.show_selection("نص", outcome, QPoint(400, 300))

    assert "مهلة" in popup._result_label.text()
    assert not popup._arrow_label.isVisible()


def test_dismiss_hides_window(popup: PopupWindow) -> None:
    outcome = TranslationOutcome(result="test", status="ok", elapsed_ms=10)
    popup.show_selection("source", outcome, QPoint(400, 300))
    popup.dismiss()

    assert not popup.isVisible()


def test_position_within_screen(popup: PopupWindow) -> None:
    outcome = TranslationOutcome(result="x" * 100, status="ok", elapsed_ms=10)
    cursor = QPoint(1400, 800)
    popup.show_selection("source", outcome, cursor)

    pos = popup.pos()
    screen = popup._screen_geometry(cursor)

    assert pos.x() + popup.width() <= screen.right() + 1
    assert pos.y() + popup.height() <= screen.bottom() + 1