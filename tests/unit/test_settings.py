from __future__ import annotations

import json
from pathlib import Path

import pytest

from hovertranslate.config.settings import Settings, SettingsService
from hovertranslate.core.errors import SettingsError


def test_load_creates_default_settings(tmp_path: Path) -> None:
    service = SettingsService(base_dir=tmp_path)
    settings = service.load()

    assert settings.trigger_key == "F9"
    assert settings.cache_ttl_hours == 72
    assert service.settings_path.exists()


def test_save_and_reload_settings(tmp_path: Path) -> None:
    service = SettingsService(base_dir=tmp_path)
    service.load()

    updated = Settings(
        trigger_key="F9",
        cache_ttl_hours=48,
        excluded_apps=["notepad.exe"],
    )
    service.save(updated)

    reloaded = SettingsService(base_dir=tmp_path).load()
    assert reloaded.cache_ttl_hours == 48
    assert reloaded.excluded_apps == ["notepad.exe"]


def test_corrupt_settings_is_backed_up_and_reset(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{invalid json", encoding="utf-8")

    service = SettingsService(base_dir=tmp_path)

    with pytest.raises(SettingsError):
        service.load()

    backup_path = tmp_path / "settings.json.bak"
    assert backup_path.exists()
    assert service.current.cache_ttl_hours == 72


def test_invalid_hold_ms_raises_validation_error(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"hold_ms": 10}),
        encoding="utf-8",
    )

    service = SettingsService(base_dir=tmp_path)

    with pytest.raises(SettingsError):
        service.load()