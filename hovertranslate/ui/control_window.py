from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from hovertranslate.config.settings import Settings
from hovertranslate.translation.provider import TranslationOutcome


class ControlWindow(QWidget):
    """Small always-on-top panel that follows the mouse and selects translation direction."""

    def __init__(
        self,
        settings: Settings,
        on_direction_changed: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_direction_changed = on_direction_changed
        self._enabled = False
        self._direction = settings.default_lang_pair

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        self._title = QLabel("HoverTranslate")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        self._ar_ru = QPushButton("العربية ← الروسية")
        self._ru_ar = QPushButton("الروسية ← العربية")
        self._ar_ru.setCheckable(True)
        self._ru_ar.setCheckable(True)
        self._ar_ru.clicked.connect(lambda: self._select_direction("ar-ru"))
        self._ru_ar.clicked.connect(lambda: self._select_direction("ru-ar"))

        self._status = QLabel("اضغط F9 لتفعيل الترجمة")
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(6)
        self._layout.addWidget(self._title)
        self._layout.addWidget(self._ar_ru)
        self._layout.addWidget(self._ru_ar)
        self._layout.addWidget(self._status)

        self.setStyleSheet("""
            ControlWindow {
                background-color: rgba(35, 35, 40, 245);
                border: 1px solid #777;
                border-radius: 9px;
            }
            QLabel { color: white; background: transparent; }
            QPushButton {
                color: white;
                background-color: #45454d;
                border: 1px solid #777;
                border-radius: 5px;
                padding: 6px 8px;
            }
            QPushButton:checked {
                background-color: #176b87;
                border: 1px solid #5cc9e8;
            }
            QPushButton:hover { background-color: #565660; }
        """)

        self._select_direction(self._direction, notify=False)
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self._status.setText("حدد النص وانتظر ثانية واحدة")
            self.show()
            self.raise_()
        else:
            self._status.setText("الترجمة متوقفة — اضغط F9")
            self.hide()

    def cursor_near_window(self, cursor_pos: QPoint, margin: int = 120) -> bool:
        """Return True while the pointer is on or close to the panel.

        The expanded area is intentional: polling the cursor every 100 ms can
        otherwise move the panel away before the pointer reaches a button.
        """
        if not self._enabled or not self.isVisible():
            return False
        return self.geometry().adjusted(-margin, -margin, margin, margin).contains(cursor_pos)

    def follow_cursor(self, cursor_pos: QPoint) -> None:
        if not self._enabled:
            return
        # Keep the panel still while the user approaches or interacts with it.
        if self.cursor_near_window(cursor_pos):
            return
        screen = self._screen_geometry(cursor_pos)
        offset = max(12, int(self._settings.tooltip_offset_px))
        x = cursor_pos.x() + offset
        y = cursor_pos.y() + offset
        self.adjustSize()
        if x + self.width() > screen.right() - 8:
            x = cursor_pos.x() - self.width() - offset
        if y + self.height() > screen.bottom() - 8:
            y = cursor_pos.y() - self.height() - offset
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 3))
        y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 3))
        self.move(x, y)

    def show_status(self, text: str) -> None:
        self._status.setText(text)
        self.adjustSize()

    def show_outcome(self, outcome: TranslationOutcome, cursor_pos: QPoint) -> None:
        if outcome.status == "ok" and outcome.result:
            self._status.setText(outcome.result)
        else:
            messages = {
                "timeout": "انتهت مهلة الاتصال",
                "network_down": "لا يوجد اتصال بالإنترنت",
                "provider_error": "تعذرت الترجمة من المزود",
                "cancelled": "تم إلغاء الترجمة",
                "ambiguous_input": "لم أتمكن من تحديد النص",
            }
            self._status.setText(messages.get(outcome.status, "حدث خطأ أثناء الترجمة"))
        self.adjustSize()
        self.follow_cursor(cursor_pos)

    def clear_translation(self) -> None:
        self._status.setText("حدد النص وانتظر ثانية واحدة")

    def _select_direction(self, lang_pair: str, notify: bool = True) -> None:
        self._direction = lang_pair
        self._ar_ru.setChecked(lang_pair == "ar-ru")
        self._ru_ar.setChecked(lang_pair == "ru-ar")
        if notify:
            # The direction is now selected. Keep translation enabled, but hide
            # the direction chooser until F9 is used to disable and re-enable it.
            self._on_direction_changed(lang_pair)
            if self._enabled:
                self.hide()

    @staticmethod
    def _screen_geometry(cursor_pos: QPoint):
        for screen in QApplication.screens():
            geometry = screen.availableGeometry()
            if geometry.contains(cursor_pos):
                return geometry
        primary = QApplication.primaryScreen()
        if primary is not None:
            return primary.availableGeometry()
        from PySide6.QtCore import QRect
        return QRect(0, 0, 1920, 1080)
