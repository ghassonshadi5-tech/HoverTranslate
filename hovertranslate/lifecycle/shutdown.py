from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(slots=True)
class ShutdownError:
    component: str
    error: str


@dataclass(slots=True)
class ShutdownReport:
    attempted: int = 0
    succeeded: int = 0
    errors: list[ShutdownError] = field(default_factory=list)


class ShutdownManager:
    """
    يوقف المكونات بأمان بترتيب عكسي.

    يدعم:
    - aclose() async
    - close() sync
    - stop() sync

    لا يرفع الاستثناءات من المكون الفاشل، بل يسجلها ويكمل إيقاف
    بقية المكونات.
    """

    def __init__(self, components: Sequence[Any]) -> None:
        self._components = list(components)

    async def shutdown(self) -> ShutdownReport:
        report = ShutdownReport(attempted=len(self._components))

        for component in reversed(self._components):
            name = type(component).__name__

            try:
                await self._close_component(component)
                report.succeeded += 1
            except Exception as exc:
                report.errors.append(
                    ShutdownError(
                        component=name,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return report

    @staticmethod
    async def _close_component(component: Any) -> None:
        aclose = getattr(component, "aclose", None)
        if callable(aclose):
            result = aclose()
            if asyncio.iscoroutine(result):
                await result
            return

        close = getattr(component, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result
            return

        stop = getattr(component, "stop", None)
        if callable(stop):
            result = stop()
            if asyncio.iscoroutine(result):
                await result
            return