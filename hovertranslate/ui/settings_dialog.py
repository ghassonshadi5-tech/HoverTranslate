from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from hovertranslate.config.settings import Settings, SettingsService
from hovertranslate.core.errors import SettingsError


class SettingsDialog(QDialog):
    """
    نافذة تعديل إعدادات HoverTranslate.

    تحفظ الإعدادات عبر SettingsService حتى تُطبَّق قواعد التحقق
    المركزية نفسها المستخدمة عند التحميل.
    """

    def __init__(
        self,
        service: SettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service

        self.setWindowTitle("إعدادات HoverTranslate")
        self.setMinimumWidth(460)

        root_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        root_layout.addLayout(form_layout)

        current = service.current

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["F9", "ALT_TAP", "ALT_HOLD"])
        self.trigger_combo.setCurrentText(current.trigger_key)
        form_layout.addRow("المشغّل:", self.trigger_combo)

        self.lang_pair_combo = QComboBox()
        self.lang_pair_combo.addItems(["ar-ru", "ru-ar"])
        self.lang_pair_combo.setCurrentText(current.default_lang_pair)
        form_layout.addRow("زوج اللغات:", self.lang_pair_combo)

        self.ui_language_combo = QComboBox()
        self.ui_language_combo.addItems(["ar", "ru"])
        self.ui_language_combo.setCurrentText(current.ui_language)
        form_layout.addRow("لغة الواجهة:", self.ui_language_combo)

        self.request_timeout_spin = QSpinBox()
        self.request_timeout_spin.setRange(1, 30)
        self.request_timeout_spin.setValue(current.request_timeout_s)
        self.request_timeout_spin.setSuffix(" ثانية")
        form_layout.addRow("مهلة الطلب:", self.request_timeout_spin)

        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(24, 168)
        self.cache_ttl_spin.setValue(current.cache_ttl_hours)
        self.cache_ttl_spin.setSuffix(" ساعة")
        form_layout.addRow("مدة صلاحية الكاش:", self.cache_ttl_spin)

        self.tooltip_timeout_spin = QSpinBox()
        self.tooltip_timeout_spin.setRange(1, 300)
        self.tooltip_timeout_spin.setValue(current.tooltip_timeout_s)
        self.tooltip_timeout_spin.setSuffix(" ثانية")
        form_layout.addRow("مهلة Tooltip:", self.tooltip_timeout_spin)

        self.popup_timeout_spin = QSpinBox()
        self.popup_timeout_spin.setRange(1, 300)
        self.popup_timeout_spin.setValue(current.popup_timeout_s)
        self.popup_timeout_spin.setSuffix(" ثانية")
        form_layout.addRow("مهلة Popup:", self.popup_timeout_spin)

        self.ocr_check = QCheckBox("تفعيل OCR المحلي")
        self.ocr_check.setChecked(current.ocr_enabled)
        form_layout.addRow("", self.ocr_check)

        self.ocr_external_check = QCheckBox("السماح بخدمات OCR الخارجية")
        self.ocr_external_check.setChecked(current.ocr_external_approved)
        form_layout.addRow("", self.ocr_external_check)

        self.crash_reports_check = QCheckBox("المشاركة الطوعية في تقارير الأعطال")
        self.crash_reports_check.setChecked(current.crash_reports_opt_in)
        form_layout.addRow("", self.crash_reports_check)

        self.excluded_apps_edit = QLineEdit()
        self.excluded_apps_edit.setPlaceholderText("مثال: chrome.exe, firefox.exe")
        self.excluded_apps_edit.setText(", ".join(current.excluded_apps))
        form_layout.addRow("تطبيقات مستثناة:", self.excluded_apps_edit)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        root_layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def apply(self) -> bool:
        """
        يحاول حفظ الإعدادات الحالية.

        يعيد True عند النجاح، وFalse عند فشل التحقق أو الحفظ.
        لا يعرض رسائل واجهة هنا حتى يبقى قابلاً للاختبار.
        """
        try:
            self._service.save(self._gather_settings())
            return True
        except SettingsError:
            return False
        except Exception:
            return False

    def accept(self) -> None:
        """
        يحفظ ثم يغلق النافذة.
        إذا فشل الحفظ، يعرض رسالة خطأ ويبقي النافذة مفتوحة.
        """
        if self.apply():
            super().accept()
            return

        QMessageBox.critical(
            self,
            "خطأ في الإعدادات",
            "تعذر حفظ الإعدادات. تحقق من القيم المدخلة.",
        )

    def _gather_settings(self) -> Settings:
        base = self._service.current

        return Settings(
            trigger_key=self.trigger_combo.currentText(),
            hold_ms=base.hold_ms,
            tap_max_ms=base.tap_max_ms,
            mouse_move_threshold_px=base.mouse_move_threshold_px,
            tooltip_offset_px=base.tooltip_offset_px,
            screen_edge_margin_px=base.screen_edge_margin_px,
            tooltip_timeout_s=self.tooltip_timeout_spin.value(),
            popup_timeout_s=self.popup_timeout_spin.value(),
            default_lang_pair=self.lang_pair_combo.currentText(),
            request_timeout_s=self.request_timeout_spin.value(),
            cache_ttl_hours=self.cache_ttl_spin.value(),
            ocr_enabled=self.ocr_check.isChecked(),
            ocr_external_approved=self.ocr_external_check.isChecked(),
            crash_reports_opt_in=self.crash_reports_check.isChecked(),
            ui_language=self.ui_language_combo.currentText(),
            excluded_apps=self._parse_excluded_apps(),
            paused=base.paused,
        )

    def _parse_excluded_apps(self) -> list[str]:
        raw = self.excluded_apps_edit.text()

        return [
            item.strip()
            for item in raw.split(",")
            if item.strip()
        ]