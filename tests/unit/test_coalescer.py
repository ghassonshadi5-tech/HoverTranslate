from __future__ import annotations

import asyncio

import pytest

from hovertranslate.translation.coalescer import RequestCoalescer


@pytest.mark.asyncio
async def test_same_key_runs_factory_once() -> None:
    coalescer = RequestCoalescer()
    calls = 0

    started = asyncio.Event()
    release = asyncio.Event()

    async def factory() -> str:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return "ok"

    task_a = asyncio.create_task(coalescer.run("same", factory))
    await started.wait()

    task_b = asyncio.create_task(coalescer.run("same", factory))
    await asyncio.sleep(0)

    release.set()

    assert await task_a == "ok"
    assert await task_b == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_different_keys_run_separately() -> None:
    coalescer = RequestCoalescer()
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return "ok"

    results = await asyncio.gather(
        coalescer.run("a", factory),
        coalescer.run("b", factory),
    )

    assert results == ["ok", "ok"]
    assert calls == 2


@pytest.mark.asyncio
async def test_exception_propagates_and_key_is_removed() -> None:
    coalescer = RequestCoalescer()
    calls = 0

    async def failing_factory() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await coalescer.run("err", failing_factory)

    async def ok_factory() -> str:
        return "ok"

    result = await coalescer.run("err", ok_factory)

    assert result == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_cancelling_one_waiter_does_not_cancel_shared_task() -> None:
    coalescer = RequestCoalescer()
    calls = 0

    started = asyncio.Event()
    release = asyncio.Event()

    async def factory() -> str:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return "ok"

    task_a = asyncio.create_task(coalescer.run("cancel", factory))
    await started.wait()

    task_b = asyncio.create_task(coalescer.run("cancel", factory))
    await asyncio.sleep(0)

    task_a.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task_a

    release.set()

    assert await task_b == "ok"
    assert calls == 1