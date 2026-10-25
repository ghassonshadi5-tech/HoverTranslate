from __future__ import annotations

from typing import Protocol

from hovertranslate.core.errors import ExtractionError
from hovertranslate.core.types import ExtractionResult, TriggerContext
from hovertranslate.extraction.clipboard_source import ClipboardSource
from hovertranslate.extraction.uia_source import UIASource


BIDI_CONTROL_CHARS = frozenset(
    {
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class OcrServiceLike(Protocol):
    def capture_and_read(self, region) -> object: ...


class TextExtractionService:
    """
    ينسق استخراج النص حسب الترتيب المعماري المعتمد.

    - get_hover_text: UIA ثم OCR (لا حافظة، لأن المستخدم لم يحدد نصاً).
    - get_selected_text: UIA ثم الحافظة ثم OCR.

    يزيل علامات التحكم الاتجاهية الخفية من أي نص مستخرج
    قبل إرجاعه، احتراماََ لمتطلبات الخصوصية ومنع تلويث مفتاح الكاش.
    """

    def __init__(
        self,
        uia_source: UIASource,
        clipboard_source: ClipboardSource | None = None,
        ocr_service: OcrServiceLike | None = None,
    ) -> None:
        self._uia = uia_source
        self._clipboard = clipboard_source
        self._ocr = ocr_service

    def get_hover_text(self, context: TriggerContext) -> ExtractionResult:
        result = self._try_uia_hover(context)
        if result.success:
            return result

        return self._try_ocr(context)

    def get_selected_text(self, context: TriggerContext) -> ExtractionResult:
        result = self._try_uia_hover(context)
        if result.success:
            return result

        result = self._try_clipboard(context)
        if result.success:
            return result

        return self._try_ocr(context)

    def _try_uia_hover(self, context: TriggerContext) -> ExtractionResult:
        try:
            result = self._uia.extract_hover(context)
        except ExtractionError:
            return ExtractionResult(text=None, source="none", success=False)

        if result.success and result.text:
            return ExtractionResult(
                text=self._clean(result.text),
                source=result.source,
                success=True,
            )

        return result

    def _try_clipboard(self, context: TriggerContext) -> ExtractionResult:
        if self._clipboard is None:
            return ExtractionResult(text=None, source="none", success=False)

        try:
            result = self._clipboard.extract_selected_text(
                copy_action=lambda: self._simulate_copy(context),
            )
        except ExtractionError:
            return ExtractionResult(text=None, source="none", success=False)

        if result.success and result.text:
            return ExtractionResult(
                text=self._clean(result.text),
                source=result.source,
                success=True,
            )

        return result

    def _try_ocr(self, context: TriggerContext) -> ExtractionResult:
        if self._ocr is None:
            return ExtractionResult(text=None, source="none", success=False)

        try:
            region = self._build_ocr_region(context)
            ocr_result = self._ocr.capture_and_read(region)
            text = getattr(ocr_result, "text", None)
        except Exception:
            return ExtractionResult(text=None, source="none", success=False)

        if not text:
            return ExtractionResult(text=None, source="none", success=False)

        return ExtractionResult(
            text=self._clean(str(text)),
            source="ocr",
            success=True,
        )

    @staticmethod
    def _simulate_copy(context: TriggerContext) -> None:
        """
        محاكاة أمر النسخ. في الإنتاج يُستبدل بإرسال Ctrl+C
        عبر win32 SendInput أو UIA SelectionPattern.
        """
        _ = context

    @staticmethod
    def _build_ocr_region(context: TriggerContext):
        from hovertranslate.core.types import OcrRegion

        return OcrRegion(
            x=max(0, context.point_x - 120),
            y=max(0, context.point_y - 20),
            width=240,
            height=40,
        )

    @staticmethod
    def _clean(text: str) -> str:
        return "".join(
            ch for ch in text if ch not in BIDI_CONTROL_CHARS
        ).strip()