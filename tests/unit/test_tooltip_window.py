from __future__ import annotations

from PySide6.QtCore import QPoint

import pytest

from hovertranslate.config.settings import Settings
from hovertranslate.translation.provider import TranslationOutcome
from hovertranslate.ui.tooltip_window import TooltipWindow


@pytest.fixture()
def settings() -> Settings:
    return Settings(tooltip_offset_px=16, screen_edge_margin_px=40)


@pytest.fixture()
def tooltip(qtbot, settings: Settings) -> TooltipWindow:
    widget = TooltipWindow(settings)
    qtbot.addWidget(widget)
    return widget


def test_show_translation_sets_text(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result="Привет",
        status="ok",
        elapsed_ms=120,
    )
    tooltip.show_translation(outcome, QPoint(500, 400))

    assert tooltip.isVisible()
    assert tooltip._label.text() == "Привет"


def test_show_error_sets_red_style(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result=None,
        status="timeout",
        elapsed_ms=4000,
    )
    tooltip.show_translation(outcome, QPoint(500, 400))

    assert tooltip.isVisible()
    assert "مهلة" in tooltip._label.text()
    assert "180,40,40" in tooltip._label.styleSheet()


def test_dismiss_hides_window(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result="مرحبا",
        status="ok",
        elapsed_ms=50,
    )
    tooltip.show_translation(outcome, QPoint(500, 400))
    tooltip.dismiss()

    assert not tooltip.isVisible()


def test_position_offset(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result="test",
        status="ok",
        elapsed_ms=10,
    )
    cursor = QPoint(500, 400)
    tooltip.show_translation(outcome, cursor)

    pos = tooltip.pos()
    # يجب أن يكون الموضع = المؤشر + الإزاحة (ما لم يُقيد بالحافة)
    assert pos.x() >= cursor.x() + 16 - 1  # tolerance 1px
    assert pos.y() >= cursor.y() + 16 - 1


def test_position_clamped_to_screen(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result="x" * 200,
        status="ok",
        elapsed_ms=10,
    )
    # مؤشر قريب جداََ من الحافة اليمنى السفلية
    cursor = QPoint(1900, 1050)
    tooltip.show_translation(outcome, cursor)

    pos = tooltip.pos()
    screen = tooltip._available_geometry(cursor)

    # يجب ألا يتجاوز الحافة اليمنى - الهامش
    assert pos.x() + tooltip.width() <= screen.right() - 40 + 1
    # يجب ألا يتجاوز الحافة السفلية - الهامش
    assert pos.y() + tooltip.height() <= screen.bottom() - 40 + 1


def test_ambiguous_input_shows_message(tooltip: TooltipWindow) -> None:
    outcome = TranslationOutcome(
        result=None,
        status="ambiguous_input",
        elapsed_ms=0,
    )
    tooltip.show_translation(outcome, QPoint(300, 300))

    assert "غامض" in tooltip._label.text()