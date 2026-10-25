from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from hovertranslate.config.settings import Settings
from hovertranslate.translation.provider import TranslationOutcome


class TooltipWindow(QWidget):
    """Frameless, non-activating translation tooltip near the mouse cursor."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # The tooltip must never intercept clicks or selection in the app below it.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setMinimumWidth(120)
        self._label.setMaximumWidth(420)
        self._label.setContentsMargins(12, 8, 12, 8)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # The label must belong to a layout so adjustSize() measures the text
        # correctly. Without this, the tooltip can be too small and make a
        # successful translation look as if nothing happened.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._label)

        palette = self._label.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30, 230))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        self._label.setPalette(palette)
        self._label.setAutoFillBackground(True)
        self._label.setFont(QFont("Segoe UI", 11))

        self._fade_anim: QPropertyAnimation | None = None
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

    def show_waiting(self, cursor_pos: QPoint) -> None:
        """Show the persistent tooltip after the user chooses a direction."""
        self._label.setText("حدد النص وانتظر ثانية واحدة")
        self._label.setStyleSheet(
            "background-color: rgba(30,30,30,230); color: white; border-radius: 6px;"
        )
        self._prepare_and_show(cursor_pos)

    def show_status(self, text: str, cursor_pos: QPoint, error: bool = False) -> None:
        self._label.setText(text)
        background = "rgba(180,40,40,230)" if error else "rgba(30,30,30,230)"
        self._label.setStyleSheet(
            f"background-color: {background}; color: white; border-radius: 6px;"
        )
        self._prepare_and_show(cursor_pos)

    def show_translation(self, outcome: TranslationOutcome, cursor_pos: QPoint) -> None:
        if outcome.status == "ok" and outcome.result:
            self._label.setText(outcome.result)
            background = "rgba(30,30,30,230)"
        else:
            self._label.setText(self._error_message(outcome.status))
            background = "rgba(180,40,40,230)"

        self._label.setStyleSheet(
            f"background-color: {background}; color: white; border-radius: 6px;"
        )
        self._prepare_and_show(cursor_pos)

    def _prepare_and_show(self, cursor_pos: QPoint) -> None:
        # Translation remains visible until the next result or F9 disables it.
        self._dismiss_timer.stop()
        self._label.setMaximumHeight(360)
        self.adjustSize()

        screen_rect = self._available_geometry(cursor_pos)
        max_width = max(120, screen_rect.width() - 2 * self._settings.screen_edge_margin_px)
        max_height = max(60, screen_rect.height() - 2 * self._settings.screen_edge_margin_px)
        self.resize(min(self.width(), max_width), min(self.height(), max_height))
        self.move(self._compute_position(cursor_pos, screen_rect))
        if not self.isVisible():
            self._fade_in()

    def follow_cursor(self, cursor_pos: QPoint) -> None:
        """Keep the tooltip near the current pointer without taking focus."""
        if not self.isVisible():
            return
        screen_rect = self._available_geometry(cursor_pos)
        self.move(self._compute_position(cursor_pos, screen_rect))

    def dismiss(self) -> None:
        self._dismiss_timer.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
        self.hide()
        self.setWindowOpacity(1.0)

    def _compute_position(self, cursor_pos: QPoint, screen_rect: QRect | None = None) -> QPoint:
        offset = max(0, int(self._settings.tooltip_offset_px))
        margin = max(0, int(self._settings.screen_edge_margin_px))
        screen_rect = screen_rect or self._available_geometry(cursor_pos)
        size = self.size()

        x = cursor_pos.x() + offset
        y = cursor_pos.y() + offset
        if x + size.width() > screen_rect.right() - margin + 1:
            x = cursor_pos.x() - size.width() - offset
        if y + size.height() > screen_rect.bottom() - margin + 1:
            y = cursor_pos.y() - size.height() - offset

        min_x = screen_rect.left() + margin
        max_x = screen_rect.right() - margin - size.width() + 1
        min_y = screen_rect.top() + margin
        max_y = screen_rect.bottom() - margin - size.height() + 1

        x = min(max(x, min_x), max(min_x, max_x))
        y = min(max(y, min_y), max(min_y, max_y))
        return QPoint(x, y)

    @staticmethod
    def _available_geometry(cursor_pos: QPoint) -> QRect:
        for screen in QApplication.screens():
            geometry = screen.availableGeometry()
            if geometry.contains(cursor_pos):
                return geometry
        primary = QApplication.primaryScreen()
        return primary.availableGeometry() if primary is not None else QRect(0, 0, 1920, 1080)

    def _fade_in(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        if self._fade_anim is not None:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(90)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_anim.start()

    @staticmethod
    def _error_message(status: str) -> str:
        messages = {
            "timeout": "انتهت مهلة الطلب",
            "network_down": "لا يوجد اتصال بالشبكة",
            "provider_error": "فشل مزود الترجمة",
            "cancelled": "أُلغي الطلب",
            "ambiguous_input": "اتجاه النص غامض",
        }
        return messages.get(status, "خطأ غير معروف")
