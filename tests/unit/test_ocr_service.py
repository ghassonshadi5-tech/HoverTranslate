from __future__ import annotations

from hovertranslate.core.types import OcrRegion, OcrResult
from hovertranslate.ocr.ocr_service import OcrService


class FakeProvider:
    def __init__(
        self,
        result: OcrResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result or OcrResult(text=None)
        self._error = error
        self.calls = 0

    def extract(self, image: object, languages: str) -> OcrResult:
        self.calls += 1

        if self._error is not None:
            raise self._error

        return self._result


class FakeCapture:
    def __init__(
        self,
        image: object = object(),
        error: Exception | None = None,
    ) -> None:
        self._image = image
        self._error = error
        self.calls = 0

    def grab(self, region: OcrRegion) -> object:
        self.calls += 1

        if self._error is not None:
            raise self._error

        return self._image


def test_ocr_service_success() -> None:
    provider = FakeProvider(result=OcrResult(text="مرحبا\x00 "))
    capture = FakeCapture()
    service = OcrService(provider=provider, screen_capture=capture)

    result = service.capture_and_read(OcrRegion(x=0, y=0, width=10, height=10))

    assert result.text == "مرحبا"
    assert capture.calls == 1
    assert provider.calls == 1


def test_ocr_service_without_capture_returns_none() -> None:
    provider = FakeProvider(result=OcrResult(text="مرحبا"))
    service = OcrService(provider=provider, screen_capture=None)

    result = service.capture_and_read(OcrRegion(x=0, y=0, width=10, height=10))

    assert result.text is None
    assert provider.calls == 0


def test_ocr_service_capture_error_returns_none() -> None:
    provider = FakeProvider(result=OcrResult(text="مرحبا"))
    capture = FakeCapture(error=RuntimeError("capture failed"))
    service = OcrService(provider=provider, screen_capture=capture)

    result = service.capture_and_read(OcrRegion(x=0, y=0, width=10, height=10))

    assert result.text is None
    assert provider.calls == 0


def test_ocr_service_provider_error_returns_none() -> None:
    provider = FakeProvider(error=RuntimeError("ocr failed"))
    capture = FakeCapture()
    service = OcrService(provider=provider, screen_capture=capture)

    result = service.capture_and_read(OcrRegion(x=0, y=0, width=10, height=10))

    assert result.text is None
    assert provider.calls == 1