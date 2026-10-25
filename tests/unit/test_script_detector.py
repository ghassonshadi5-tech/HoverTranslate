from __future__ import annotations

from hovertranslate.extraction.script_detector import ScriptDetector


def test_detect_clear_arabic() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("مرحبا بك في المترجم")

    assert verdict.direction == "ar"
    assert verdict.ratio >= 0.60


def test_detect_clear_russian() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("Привет мир это тест")

    assert verdict.direction == "ru"
    assert verdict.ratio >= 0.60


def test_detect_short_text_is_ambiguous() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("مرحبا")

    assert verdict.direction == "ambiguous"
    assert verdict.ratio == 0.0


def test_detect_mixed_arabic_russian_is_ambiguous() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("مرحبا Привет")

    assert verdict.direction == "ambiguous"


def test_detect_latin_only_is_ambiguous() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("Hello World")

    assert verdict.direction == "ambiguous"


def test_detect_digits_and_symbols_are_ambiguous() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("12345 !@#$%")

    assert verdict.direction == "ambiguous"
    assert verdict.ratio == 0.0


def test_detect_arabic_dominant_with_some_latin() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("هذا نص عربي مع Word")

    assert verdict.direction == "ar"


def test_detect_russian_dominant_with_some_latin() -> None:
    detector = ScriptDetector()
    verdict = detector.detect("Это русский текст с Word")

    assert verdict.direction == "ru"