from __future__ import annotations

from typing import Protocol

from hovertranslate.core.types import OcrRegion, OcrResult


class OcrProviderLike(Protocol):
    def extract(self, image: object, languages: str) -> OcrResult: ...


class ScreenCaptureLike(Protocol):
    def grab(self, region: OcrRegion) -> object: ...


class OcrService:
    """
    خدمة OCR محلية.

    لا ترسل أي بيانات إلى الخارج.
    لا تسجل محتوى الصورة أو النص المستخرج.
    """

    DEFAULT_LANGUAGES = "ara+rus+eng"

    def __init__(
        self,
        provider: OcrProviderLike,
        screen_capture: ScreenCaptureLike | None = None,
        languages: str = DEFAULT_LANGUAGES,
    ) -> None:
        self._provider = provider
        self._screen_capture = screen_capture
        self._languages = languages

    def capture_and_read(
        self,
        region: OcrRegion,
        languages: str | None = None,
    ) -> OcrResult:
        if self._screen_capture is None:
            return OcrResult(text=None)

        try:
            image = self._screen_capture.grab(region)
            result = self._provider.extract(
                image=image,
                languages=languages or self._languages,
            )
        except Exception:
            return OcrResult(text=None)

        cleaned = (result.text or "").replace("\x00", "").strip()

        return OcrResult(
            text=cleaned or None,
            quality=result.quality,
        )