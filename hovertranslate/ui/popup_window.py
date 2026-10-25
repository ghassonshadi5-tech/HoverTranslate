from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from hovertranslate.config.settings import Settings
from hovertranslate.translation.provider import TranslationOutcome


MAX_TEXT_LENGTH = 500


class PopupWindow(QWidget):
    """
    نافذة Popup frameless تعرض ترجمة النص المحدد.

    القواعد (HT-UX-02 §5):
    - مهلة إخفاء 30 ثانية.
    - اقتطاع النص عند 500 حرف.
    - لا تسرق التركيز.
    - دعم RTL للنص العربي.
    """

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._source_label = QLabel(self)
        self._source_label.setWordWrap(True)
        self._source_label.setMaximumWidth(480)
        self._source_label.setMinimumWidth(160)
        self._source_label.setContentsMargins(14, 10, 14, 4)
        self._source_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._source_label.setFont(QFont("Segoe UI", 10))

        self._arrow_label = QLabel("↓", self)
        self._arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow_label.setFont(QFont("Segoe UI", 12))
        self._arrow_label.setStyleSheet("color: rgba(255,255,255,120);")

        self._result_label = QLabel(self)
        self._result_label.setWordWrap(True)
        self._result_label.setMaximumWidth(480)
        self._result_label.setMinimumWidth(160)
        self._result_label.setContentsMargins(14, 4, 14, 10)
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._result_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        layout.addWidget(self._source_label)
        layout.addWidget(self._arrow_label)
        layout.addWidget(self._result_label)

        self._apply_dark_style()

        self._dismiss_timer: QTimer | None = None

    def show_selection(
        self,
        source_text: str,
        outcome: TranslationOutcome,
        cursor_pos: QPoint,
    ) -> None:
        """
        يعرض النص المصدر (مقتطعاً) والترجمة الناتجة.
        """
        truncated = self._truncate(source_text)
        self._source_label.setText(truncated)

        if outcome.status == "ok" and outcome.result:
            self._result_label.setText(outcome.result)
            self._result_label.setStyleSheet(
                "color: white; background: transparent;"
            )
        else:
            self._result_label.setText(self._error_message(outcome.status))
            self._result_label.setStyleSheet(
                "color: rgba(255,120,120,255); background: transparent;"
            )

        self._arrow_label.setVisible(outcome.status == "ok")

        self.adjustSize()
        pos = self._compute_position(cursor_pos)
        self.move(pos)
        self.show()
        self._start_dismiss_timer()

    def dismiss(self) -> None:
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
        self.hide()

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= MAX_TEXT_LENGTH:
            return text
        return text[:MAX_TEXT_LENGTH].rstrip() + "…"

    def _compute_position(self, cursor_pos: QPoint) -> QPoint:
        offset = self._settings.tooltip_offset_px
        margin = self._settings.screen_edge_margin_px

        screen_rect = self._screen_geometry(cursor_pos)
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

        x = max(min_x, min(x, max_x)) if max_x >= min_x else min_x
        y = max(min_y, min(y, max_y)) if max_y >= min_y else min_y

        return QPoint(x, y)

    @staticmethod
    def _screen_geometry(cursor_pos: QPoint):
        for screen in QApplication.screens():
            geo = screen.availableGeometry()
            if geo.contains(cursor_pos):
                return geo
        primary = QApplication.primaryScreen()
        if primary is not None:
            return primary.availableGeometry()
        from PySide6.QtCore import QRect
        return QRect(0, 0, 1920, 1080)

    def _start_dismiss_timer(self) -> None:
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)
        self._dismiss_timer.start(self._settings.popup_timeout_s * 1000)

    def _apply_dark_style(self) -> None:
        self.setStyleSheet(
            "background-color: rgba(25,25,25,235);"
            "border-radius: 8px;"
            "border: 1px solid rgba(255,255,255,30);"
        )
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        self.setPalette(palette)

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