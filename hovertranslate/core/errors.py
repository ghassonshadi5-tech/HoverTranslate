from __future__ import annotations


class HoverTranslateError(Exception):
    """Base application error."""


class TriggerError(HoverTranslateError):
    """Input trigger error."""


class ExtractionError(HoverTranslateError):
    """Text extraction error."""


class ProviderError(HoverTranslateError):
    """Translation provider error."""


class CacheError(HoverTranslateError):
    """Cache error."""


class SettingsError(HoverTranslateError):
    """Settings error."""


class SecretError(HoverTranslateError):
    """Secret storage error."""