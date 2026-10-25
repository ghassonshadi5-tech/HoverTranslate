from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hovertranslate.core.types import (
    ExtractionResult,
    TriggerContext,
    TriggerKind,
)
from hovertranslate.extraction.script_detector import ScriptDetector
from hovertranslate.translation.coalescer import RequestCoalescer
from hovertranslate.translation.coordinator import TranslationCoordinator
from hovertranslate.translation.provider import TranslationOutcome


class FakeExtraction:
    def __init__(
        self,
        hover_text: str | None = None,
        selection_text: str | None = None,
    ) -> None:
        self.hover_text = hover_text
        self.selection_text = selection_text

    def get_hover_text(self, context: TriggerContext) -> ExtractionResult:
        if self.hover_text is None:
            return ExtractionResult(text=None, source="none", success=False)

        return ExtractionResult(
            text=self.hover_text,
            source="uia",
            success=True,
        )

    def get_selected_text(self, context: TriggerContext) -> ExtractionResult:
        if self.selection_text is None:
            return ExtractionResult(text=None, source="none", success=False)

        return ExtractionResult(
            text=self.selection_text,
            source="clipboard",
            success=True,
        )


class FakeCache:
    def __init__(self, cached: str | None = None) -> None:
        self.cached = cached
        self.getCalls: list[dict[str, Any]] = []
        self.putCalls: list[dict[str, Any]] = []

    def get(
        self,
        text: str,
        direction: str,
        provider: str,
        lang_pair: str,
    ) -> str | None:
        self.getCalls.append(
            {
                "text": text,
                "direction": direction,
                "provider": provider,
                "lang_pair": lang_pair,
            }
        )
        return self.cached

    def put(
        self,
        text: str,
        direction: str,
        provider: str,
        lang_pair: str,
        result: str,
    ) -> None:
        self.putCalls.append(
            {
                "text": text,
                "direction": direction,
                "provider": provider,
                "lang_pair": lang_pair,
                "result": result,
            }
        )


class FakeProvider:
    PROVIDER_NAME = "fake"

    def __init__(
        self,
        outcome: TranslationOutcome | None = None,
        delay: float = 0.0,
    ) -> None:
        self.outcome = outcome
        self.delay = delay
        self.calls: list[tuple[str, str, int]] = []

    async def translate(
        self,
        text: str,
        lang_pair: str,
        generation: int,
    ) -> TranslationOutcome:
        self.calls.append((text, lang_pair, generation))

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.outcome is not None:
            return self.outcome

        return TranslationOutcome(
            result="Привет",
            status="ok",
            elapsed_ms=10,
        )


class FakeHoverView:
    def __init__(self) -> None:
        self.records: list[tuple[str, str | None, int, int]] = []

    def show_translation(
        self,
        outcome: TranslationOutcome,
        point_x: int,
        point_y: int,
    ) -> None:
        self.records.append(
            (outcome.status, outcome.result, point_x, point_y)
        )


class FakeSelectionView:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, str | None, int, int]] = []

    def show_selection(
        self,
        source_text: str,
        outcome: TranslationOutcome,
        point_x: int,
        point_y: int,
    ) -> None:
        self.records.append(
            (
                source_text,
                outcome.status,
                outcome.result,
                point_x,
                point_y,
            )
        )


def _ctx(kind: TriggerKind = "hover") -> TriggerContext:
    return TriggerContext(kind=kind, point_x=10, point_y=20)


@pytest.mark.asyncio
async def test_hover_arabic_calls_provider_and_caches() -> None:
    extraction = FakeExtraction(hover_text="مرحبا بك في المترجم")
    cache = FakeCache()
    provider = FakeProvider()
    hover = FakeHoverView()
    selection = FakeSelectionView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=selection,
    )

    outcome = await coordinator.process_trigger(
        "hover",
        _ctx("hover"),
        generation=1,
    )

    assert outcome is not None
    assert outcome.status == "ok"
    assert outcome.result == "Привет"
    assert provider.calls == [("مرحبا بك في المترجم", "ar-ru", 1)]
    assert cache.putCalls[0]["result"] == "Привет"
    assert cache.putCalls[0]["lang_pair"] == "ar-ru"
    assert hover.records == [("ok", "Привет", 10, 20)]
    assert selection.records == []


@pytest.mark.asyncio
async def test_cache_hit_skips_provider() -> None:
    extraction = FakeExtraction(hover_text="مرحبا بك في المترجم")
    cache = FakeCache(cached="Привет")
    provider = FakeProvider()
    hover = FakeHoverView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=FakeSelectionView(),
    )

    outcome = await coordinator.process_trigger(
        "hover",
        _ctx("hover"),
        generation=1,
    )

    assert outcome is not None
    assert outcome.result == "Привет"
    assert provider.calls == []
    assert hover.records == [("ok", "Привет", 10, 20)]


@pytest.mark.asyncio
async def test_ambiguous_text_does_not_call_provider() -> None:
    extraction = FakeExtraction(hover_text="Hi")
    cache = FakeCache()
    provider = FakeProvider()
    hover = FakeHoverView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=FakeSelectionView(),
    )

    outcome = await coordinator.process_trigger(
        "hover",
        _ctx("hover"),
        generation=1,
    )

    assert outcome is not None
    assert outcome.status == "ambiguous_input"
    assert provider.calls == []
    assert hover.records[0][0] == "ambiguous_input"


@pytest.mark.asyncio
async def test_selection_uses_selection_view_and_ru_ar() -> None:
    extraction = FakeExtraction(selection_text="Привет мир это тест")
    cache = FakeCache()
    provider = FakeProvider(outcome=TranslationOutcome(
        result="مرحبا",
        status="ok",
        elapsed_ms=10,
    ))
    hover = FakeHoverView()
    selection = FakeSelectionView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=selection,
    )

    outcome = await coordinator.process_trigger(
        "selection",
        _ctx("selection"),
        generation=1,
    )

    assert outcome is not None
    assert outcome.result == "مرحبا"
    assert provider.calls[0][1] == "ru-ar"
    assert selection.records[0][0] == "Привет мир это тест"
    assert hover.records == []


@pytest.mark.asyncio
async def test_stale_generation_does_not_present_or_cache() -> None:
    extraction = FakeExtraction(hover_text="مرحبا بك في المترجم")
    cache = FakeCache()
    provider = FakeProvider(delay=0.01)
    hover = FakeHoverView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=FakeSelectionView(),
    )

    coordinator._current_generation = 2

    outcome = await coordinator.process_trigger(
        "hover",
        _ctx("hover"),
        generation=1,
    )

    assert outcome is not None
    assert hover.records == []
    assert cache.putCalls == []


@pytest.mark.asyncio
async def test_provider_error_is_presented_and_not_cached() -> None:
    extraction = FakeExtraction(hover_text="مرحبا بك في المترجم")
    cache = FakeCache()
    provider = FakeProvider(
        outcome=TranslationOutcome(
            result=None,
            status="provider_error",
            elapsed_ms=0,
        )
    )
    hover = FakeHoverView()

    coordinator = TranslationCoordinator(
        extraction=extraction,
        detector=ScriptDetector(),
        cache=cache,
        provider=provider,
        coalescer=RequestCoalescer(),
        hover_view=hover,
        selection_view=FakeSelectionView(),
    )

    outcome = await coordinator.process_trigger(
        "hover",
        _ctx("hover"),
        generation=1,
    )

    assert outcome is not None
    assert outcome.status == "provider_error"
    assert hover.records[0][0] == "provider_error"
    assert cache.putCalls == []
