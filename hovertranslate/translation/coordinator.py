from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from hovertranslate.cache.cache_service import CacheService
from hovertranslate.core.types import (
    ExtractionResult,
    TriggerContext,
    TriggerKind,
)
from hovertranslate.extraction.script_detector import ScriptDetector
from hovertranslate.translation.coalescer import RequestCoalescer
from hovertranslate.translation.provider import (
    TranslationOutcome,
    TranslationProvider,
)


class HoverView(Protocol):
    def show_translation(
        self,
        outcome: TranslationOutcome,
        point_x: int,
        point_y: int,
    ) -> None: ...


class SelectionView(Protocol):
    def show_selection(
        self,
        source_text: str,
        outcome: TranslationOutcome,
        point_x: int,
        point_y: int,
    ) -> None: ...


@dataclass(slots=True)
class TranslationCoordinator:
    extraction: TextExtractionService
    detector: ScriptDetector
    cache: CacheService
    provider: TranslationProvider
    coalescer: RequestCoalescer
    hover_view: HoverView
    selection_view: SelectionView
    _current_generation: int = 0
    _task: asyncio.Task[TranslationOutcome | None] | None = None

    def schedule_trigger(
        self,
        kind: TriggerKind,
        context: TriggerContext,
    ) -> int:
        self._current_generation += 1
        generation = self._current_generation

        if self._task is not None and not self._task.done():
            self._task.cancel()

        self._task = asyncio.create_task(
            self.process_trigger(kind, context, generation)
        )
        return generation

    async def process_trigger(
        self,
        kind: TriggerKind,
        context: TriggerContext,
        generation: int,
    ) -> TranslationOutcome | None:
        # إذا كان هذا الجيل هو الأحدث، نتابع.
        # في الاختبارات المباشرة، قد نحتاج لتحديث الذاكرة الداخلية للتزامن.
        if generation > self._current_generation:
             self._current_generation = generation

        try:
            extraction = self._extract(kind, context)
        except Exception:
            extraction = ExtractionResult(
                text=None,
                source="none",
                success=False,
            )

        if not extraction.success or not extraction.text:
            return None

        text = extraction.text
        verdict = self.detector.detect(text)

        if verdict.direction == "ambiguous":
            outcome = TranslationOutcome(
                result=None,
                status="ambiguous_input",
                elapsed_ms=0,
            )
            self._present(kind, text, outcome, context, generation)
            return outcome

        lang_pair = "ar-ru" if verdict.direction == "ar" else "ru-ar"
        provider_name = getattr(self.provider, "PROVIDER_NAME", "provider")

        cached = self.cache.get(
            text=text,
            direction=verdict.direction,
            provider=provider_name,
            lang_pair=lang_pair,
        )

        if cached is not None:
            outcome = TranslationOutcome(
                result=cached,
                status="ok",
                elapsed_ms=0,
            )
            self._present(kind, text, outcome, context, generation)
            return outcome

        key = (text, verdict.direction, provider_name, lang_pair)

        async def factory() -> TranslationOutcome:
            return await self.provider.translate(
                text=text,
                lang_pair=lang_pair,
                generation=generation,
            )

        try:
            outcome = await self.coalescer.run(key, factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            outcome = TranslationOutcome(
                result=None,
                status="provider_error",
                elapsed_ms=0,
            )

        # التحقق النهائي من عدم وجود طلب أحدث ألغى هذا الطلب
        if generation < self._current_generation:
            return outcome

        if outcome.status == "ok" and outcome.result:
            self.cache.put(
                text=text,
                direction=verdict.direction,
                provider=provider_name,
                lang_pair=lang_pair,
                result=outcome.result,
            )

        self._present(kind, text, outcome, context, generation)
        return outcome

    def _extract(
        self,
        kind: TriggerKind,
        context: TriggerContext,
    ) -> ExtractionResult:
        if kind == "hover":
            return self.extraction.get_hover_text(context)

        return self.extraction.get_selected_text(context)

    def _present(
        self,
        kind: TriggerKind,
        text: str,
        outcome: TranslationOutcome,
        context: TriggerContext,
        generation: int,
    ) -> None:
        # لا تعرض إذا تم إلغاء الطلب بسبب طلب أحدث
        if generation < self._current_generation:
            return

        if kind == "hover":
            self.hover_view.show_translation(
                outcome=outcome,
                point_x=context.point_x,
                point_y=context.point_y,
            )
            return

        self.selection_view.show_selection(
            source_text=text,
            outcome=outcome,
            point_x=context.point_x,
            point_y=context.point_y,
        )
