from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")


class RequestCoalescer:
    """
    يدمج الطلبات المتطابقة الجارية.

    إذا وصل طلب بنفس المفتاح أثناء تنفيذ طلب سابق، ينتظر الجديد
    نتيجة الطلب الجاري بدل إنشاء طلب duplicate.
    """

    def __init__(self) -> None:
        self._inflight: dict[Any, asyncio.Task[Any]] = {}

    async def run(
        self,
        key: Any,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        task = self._inflight.get(key)

        if task is None:
            task = asyncio.create_task(factory())
            self._inflight[key] = task
            task.add_done_callback(
                lambda done, k=key: self._cleanup(k, done)
            )

        return cast(T, await asyncio.shield(task))

    def _cleanup(self, key: Any, task: asyncio.Task[Any]) -> None:
        if self._inflight.get(key) is task:
            self._inflight.pop(key, None)