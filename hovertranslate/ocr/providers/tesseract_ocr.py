from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytesseract
from PIL.Image import Image as PILImage

from hovertranslate.core.types import OcrResult


DEFAULT_TESSERACT_PATHS: tuple[Path, ...] = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def resolve_tesseract_cmd() -> str | None:
    """
    يحدد مسار Tesseract التنفيذي.

    الأولوية:
    1. متغير البيئة HOVERTRANSLATE_TESSERACT_CMD
    2. المسارات الافتراضية في Program Files
    3. PATH
    """
    env_value = os.getenv("HOVERTRANSLATE_TESSERACT_CMD")

    if env_value and Path(env_value).exists():
        return env_value

    for path in DEFAULT_TESSERACT_PATHS:
        if path.exists():
            return str(path)

    found = shutil.which("tesseract")

    if found:
        return found

    return None


class TesseractOcrProvider:
    """
    مزود OCR محلي عبر Tesseract.

    لا يستخدم أي خدمة خارجية.
    """

    def __init__(
        self,
        tesseract_cmd: str | None = None,
        config: str = "--oem 3 --psm 6",
    ) -> None:
        self._tesseract_cmd = tesseract_cmd or resolve_tesseract_cmd()
        self._config = config

        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd

    def extract(self, image: object, languages: str) -> OcrResult:
        if not self._tesseract_cmd:
            return OcrResult(text=None)

        if not isinstance(image, PILImage):
            return OcrResult(text=None)

        try:
            text = pytesseract.image_to_string(
                image,
                lang=languages,
                config=self._config,
            )
        except pytesseract.TesseractError:
            try:
                text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config=self._config,
                )
            except Exception:
                return OcrResult(text=None)
        except Exception:
            return OcrResult(text=None)

        cleaned = text.replace("\x00", "").strip()

        return OcrResult(
            text=cleaned or None,
            quality=None,
        )