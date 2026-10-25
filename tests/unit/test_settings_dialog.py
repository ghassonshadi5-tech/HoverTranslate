from __future__ import annotations

from pathlib import Path

from hovertranslate.config.settings import SettingsService
from hovertranslate.ui.settings_dialog import SettingsDialog


def test_dialog_loads_current_settings(tmp_path: Path, qtbot) -> None:
    service = SettingsService(base_dir=tmp_path)
    service.load()

    dialog = SettingsDialog(service)
    qtbot.addWidget(dialog)

    assert dialog.trigger_combo.currentText() == "F9"
    assert dialog.lang_pair_combo.currentText() == "ar-ru"
    assert dialog.request_timeout_spin.value() == 4
    assert dialog.cache_ttl_spin.value() == 72
    assert dialog.ocr_check.isChecked() is True
    assert dialog.ocr_external_check.isChecked() is False


def test_apply_saves_changed_settings(tmp_path: Path, qtbot) -> None:
    service = SettingsService(base_dir=tmp_path)
    service.load()

    dialog = SettingsDialog(service)
    qtbot.addWidget(dialog)

    dialog.lang_pair_combo.setCurrentText("ru-ar")
    dialog.request_timeout_spin.setValue(5)
    dialog.cache_ttl_spin.setValue(48)
    dialog.ocr_check.setChecked(False)
    dialog.excluded_apps_edit.setText("chrome.exe, firefox.exe")

    assert dialog.apply() is True

    reloaded = SettingsService(base_dir=tmp_path).load()

    assert reloaded.default_lang_pair == "ru-ar"
    assert reloaded.request_timeout_s == 5
    assert reloaded.cache_ttl_hours == 48
    assert reloaded.ocr_enabled is False
    assert reloaded.excluded_apps == ["chrome.exe", "firefox.exe"]



def test_empty_excluded_apps_becomes_empty_list(tmp_path: Path, qtbot) -> None:
    service = SettingsService(base_dir=tmp_path)
    service.load()

    dialog = SettingsDialog(service)
    qtbot.addWidget(dialog)

    dialog.excluded_apps_edit.setText("  ,  ,   ")

    assert dialog.apply() is True

    reloaded = SettingsService(base_dir=tmp_path).load()
    assert reloaded.excluded_apps == []


def test_preserves_paused_state(tmp_path: Path, qtbot) -> None:
    service = SettingsService(base_dir=tmp_path)
    settings = service.load()
    settings.paused = True
    service.save(settings)

    dialog = SettingsDialog(service)
    qtbot.addWidget(dialog)

    assert dialog.apply() is True

    reloaded = SettingsService(base_dir=tmp_path).load()
    assert reloaded.paused is True