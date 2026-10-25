from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hovertranslate.core.errors import SettingsError


APP_DIR_NAME = "HoverTranslate"
SETTINGS_FILE_NAME = "settings.json"
BACKUP_FILE_NAME = "settings.json.bak"


@dataclass(slots=True)
class Settings:
    trigger_key: str = "F9"
    hold_ms: int = 500
    tap_max_ms: int = 300
    mouse_move_threshold_px: int = 8
    tooltip_offset_px: int = 16
    screen_edge_margin_px: int = 40
    tooltip_timeout_s: int = 10
    popup_timeout_s: int = 30
    default_lang_pair: str = "ar-ru"
    request_timeout_s: int = 4
    cache_ttl_hours: int = 72
    ocr_enabled: bool = True
    ocr_external_approved: bool = False
    crash_reports_opt_in: bool = False
    ui_language: str = "ar"
    excluded_apps: list[str] = field(default_factory=list)
    paused: bool = False


class SettingsService:
    """Loads and saves settings in %APPDATA%\\HoverTranslate."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or self._default_base_dir()
        self._settings_path = self._base_dir / SETTINGS_FILE_NAME
        self._backup_path = self._base_dir / BACKUP_FILE_NAME
        self._settings = Settings()

    @staticmethod
    def _default_base_dir() -> Path:
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise SettingsError("APPDATA environment variable is missing.")
        return Path(appdata) / APP_DIR_NAME

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    @property
    def current(self) -> Settings:
        return self._settings

    def load(self) -> Settings:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if not self._settings_path.exists():
            self._settings = Settings()
            self.save(self._settings)
            return self._settings

        try:
            raw = self._settings_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Settings JSON root must be an object.")
            self._settings = self._validate(data)
            return self._settings
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            try:
                self._backup_corrupt_file()
                self._settings = Settings()
                self.save(self._settings)
            except OSError as backup_exc:
                raise SettingsError(
                    f"Settings file is corrupt and recovery failed: {backup_exc}"
                ) from backup_exc
            # Continue with safe defaults after backing up the invalid file.
            print(f"[WARN] Settings were reset to defaults: {exc}")
            return self._settings

    def save(self, settings: Settings) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(settings), ensure_ascii=False, indent=2)
        tmp_path = self._settings_path.with_suffix(".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, self._settings_path)
        self._settings = settings

    def _backup_corrupt_file(self) -> None:
        if self._settings_path.exists():
            # Replace an older backup if present.
            if self._backup_path.exists():
                self._backup_path.unlink()
            self._settings_path.replace(self._backup_path)

    @staticmethod
    def _require_bool(value: Any, name: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean.")
        return value

    @staticmethod
    def _require_int(value: Any, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer.")
        return value

    def _validate(self, data: dict[str, Any]) -> Settings:
        defaults = asdict(Settings())
        unknown = set(data) - set(defaults)
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        merged = defaults | data

        trigger_key = str(merged["trigger_key"])
        if trigger_key not in {"F9", "ALT_TAP", "ALT_HOLD"}:
            raise ValueError("Invalid trigger_key.")

        hold_ms = self._require_int(merged["hold_ms"], "hold_ms")
        if not 300 <= hold_ms <= 1000:
            raise ValueError("hold_ms must be between 300 and 1000.")

        tap_max_ms = self._require_int(merged["tap_max_ms"], "tap_max_ms")
        if not 1 <= tap_max_ms <= 300:
            raise ValueError("tap_max_ms must be between 1 and 300.")

        mouse_move_threshold_px = self._require_int(
            merged["mouse_move_threshold_px"], "mouse_move_threshold_px"
        )
        if not 0 <= mouse_move_threshold_px <= 200:
            raise ValueError("mouse_move_threshold_px must be between 0 and 200.")

        tooltip_offset_px = self._require_int(merged["tooltip_offset_px"], "tooltip_offset_px")
        if not 0 <= tooltip_offset_px <= 200:
            raise ValueError("tooltip_offset_px must be between 0 and 200.")

        screen_edge_margin_px = self._require_int(
            merged["screen_edge_margin_px"], "screen_edge_margin_px"
        )
        if not 0 <= screen_edge_margin_px <= 300:
            raise ValueError("screen_edge_margin_px must be between 0 and 300.")

        tooltip_timeout_s = self._require_int(merged["tooltip_timeout_s"], "tooltip_timeout_s")
        if not 1 <= tooltip_timeout_s <= 120:
            raise ValueError("tooltip_timeout_s must be between 1 and 120.")

        popup_timeout_s = self._require_int(merged["popup_timeout_s"], "popup_timeout_s")
        if not 1 <= popup_timeout_s <= 600:
            raise ValueError("popup_timeout_s must be between 1 and 600.")

        default_lang_pair = str(merged["default_lang_pair"])
        if default_lang_pair not in {"ar-ru", "ru-ar"}:
            raise ValueError("default_lang_pair must be ar-ru or ru-ar.")

        request_timeout_s = self._require_int(merged["request_timeout_s"], "request_timeout_s")
        if not 1 <= request_timeout_s <= 60:
            raise ValueError("request_timeout_s must be between 1 and 60.")

        cache_ttl_hours = self._require_int(merged["cache_ttl_hours"], "cache_ttl_hours")
        if not 24 <= cache_ttl_hours <= 168:
            raise ValueError("cache_ttl_hours must be between 24 and 168.")

        ocr_enabled = self._require_bool(merged["ocr_enabled"], "ocr_enabled")
        ocr_external_approved = self._require_bool(
            merged["ocr_external_approved"], "ocr_external_approved"
        )
        crash_reports_opt_in = self._require_bool(
            merged["crash_reports_opt_in"], "crash_reports_opt_in"
        )

        ui_language = str(merged["ui_language"])
        if ui_language not in {"ar", "ru"}:
            raise ValueError("ui_language must be ar or ru.")

        excluded_raw = merged["excluded_apps"]
        if not isinstance(excluded_raw, list) or not all(
            isinstance(item, str) for item in excluded_raw
        ):
            raise ValueError("excluded_apps must be a list of strings.")
        excluded_apps = list(dict.fromkeys(item.strip() for item in excluded_raw if item.strip()))

        paused = self._require_bool(merged["paused"], "paused")

        return Settings(
            trigger_key=trigger_key,
            hold_ms=hold_ms,
            tap_max_ms=tap_max_ms,
            mouse_move_threshold_px=mouse_move_threshold_px,
            tooltip_offset_px=tooltip_offset_px,
            screen_edge_margin_px=screen_edge_margin_px,
            tooltip_timeout_s=tooltip_timeout_s,
            popup_timeout_s=popup_timeout_s,
            default_lang_pair=default_lang_pair,
            request_timeout_s=request_timeout_s,
            cache_ttl_hours=cache_ttl_hours,
            ocr_enabled=ocr_enabled,
            ocr_external_approved=ocr_external_approved,
            crash_reports_opt_in=crash_reports_opt_in,
            ui_language=ui_language,
            excluded_apps=excluded_apps,
            paused=paused,
        )
