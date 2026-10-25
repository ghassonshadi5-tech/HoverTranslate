from __future__ import annotations

from hovertranslate.core.types import ExtractionResult, TriggerContext
from hovertranslate.extraction.text_service import TextExtractionService


class FakeUIASource:
    def __init__(self, text: str | None = None) -> None:
        self._text = text
        self.hover_calls = 0

    def extract_hover(self, context: TriggerContext) -> ExtractionResult:
        self.hover_calls += 1
        if self._text is None:
            return ExtractionResult(text=None, source="none", success=False)
        return ExtractionResult(text=self._text, source="uia", success=True)

    def extract_focused(self) -> ExtractionResult:
        return ExtractionResult(text=None, source="none", success=False)

    def close(self) -> None:
        pass


class FakeClipboardSource:
    def __init__(self, text: str | None = None) -> None:
        self._text = text
        self.calls = 0

    def extract_selected_text(self, copy_action) -> ExtractionResult:
        self.calls += 1
        copy_action()
        if self._text is None:
            return ExtractionResult(text=None, source="none", success=False)
        return ExtractionResult(text=self._text, source="clipboard", success=True)


class FakeOcrService:
    def __init__(self, text: str | None = None) -> None:
        self._text = text
        self.calls = 0

    def capture_and_read(self, region):
        self.calls += 1

        class R:
            text = self._text
            quality = None

        return R()


def _ctx() -> TriggerContext:
    return TriggerContext(kind="hover", point_x=100, point_y=200)


def test_hover_uses_uia_when_available() -> None:
    svc = TextExtractionService(uia_source=FakeUIASource(text="مرحبا"))
    result = svc.get_hover_text(_ctx())

    assert result.success is True
    assert result.text == "مرحبا"
    assert result.source == "uia"


def test_hover_falls_back_to_ocr() -> None:
    uia = FakeUIASource(text=None)
    ocr = FakeOcrService(text="Привет")
    svc = TextExtractionService(uia_source=uia, ocr_service=ocr)

    result = svc.get_hover_text(_ctx())

    assert result.success is True
    assert result.text == "Привет"
    assert result.source == "ocr"
    assert ocr.calls == 1


def test_hover_without_ocr_returns_none() -> None:
    svc = TextExtractionService(uia_source=FakeUIASource(text=None))
    result = svc.get_hover_text(_ctx())

    assert result.success is False
    assert result.text is None


def test_selection_uses_uia_first() -> None:
    clip = FakeClipboardSource(text="should not be used")
    svc = TextExtractionService(
        uia_source=FakeUIASource(text="نص مباشر"),
        clipboard_source=clip,
    )

    result = svc.get_selected_text(_ctx())

    assert result.text == "نص مباشر"
    assert result.source == "uia"
    assert clip.calls == 0


def test_selection_falls_back_to_clipboard() -> None:
    clip = FakeClipboardSource(text="نص من الحافظة")
    svc = TextExtractionService(
        uia_source=FakeUIASource(text=None),
        clipboard_source=clip,
    )

    result = svc.get_selected_text(_ctx())

    assert result.success is True
    assert result.text == "نص من الحافظة"
    assert result.source == "clipboard"


def test_selection_falls_back_to_ocr() -> None:
    ocr = FakeOcrService(text="OCR text")
    svc = TextExtractionService(
        uia_source=FakeUIASource(text=None),
        clipboard_source=FakeClipboardSource(text=None),
        ocr_service=ocr,
    )

    result = svc.get_selected_text(_ctx())

    assert result.success is True
    assert result.text == "OCR text"
    assert result.source == "ocr"


def test_strips_bidi_control_chars() -> None:
    svc = TextExtractionService(
        uia_source=FakeUIASource(text="مرحبا\u200f HOVERTRANSLATE\u200e"),
    )

    result = svc.get_hover_text(_ctx())

    assert result.text == "مرحبا HOVERTRANSLATE"
    assert "\u200f" not in result.text
    assert "\u200e" not in result.text


def test_no_clipboard_in_hover_path() -> None:
    clip = FakeClipboardSource(text="must not appear")
    svc = TextExtractionService(
        uia_source=FakeUIASource(text=None),
        clipboard_source=clip,
    )

    result = svc.get_hover_text(_ctx())

    assert clip.calls == 0
    assert result.success is False