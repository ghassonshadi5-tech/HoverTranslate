from __future__ import annotations

import pytest

from hovertranslate.lifecycle.shutdown import ShutdownManager


class AsyncComponent:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    async def aclose(self) -> None:
        self.log.append(self.name)


class SyncCloseComponent:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def close(self) -> None:
        self.log.append(self.name)


class StopComponent:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def stop(self) -> None:
        self.log.append(self.name)


class BrokenComponent:
    def close(self) -> None:
        raise RuntimeError("shutdown failed")


@pytest.mark.asyncio
async def test_shutdown_calls_components_in_reverse_order() -> None:
    log: list[str] = []

    manager = ShutdownManager(
        [
            AsyncComponent("first", log),
            SyncCloseComponent("second", log),
            StopComponent("third", log),
        ]
    )

    report = await manager.shutdown()

    assert log == ["third", "second", "first"]
    assert report.attempted == 3
    assert report.succeeded == 3
    assert report.errors == []


@pytest.mark.asyncio
async def test_shutdown_continues_after_failure() -> None:
    log: list[str] = []

    manager = ShutdownManager(
        [
            SyncCloseComponent("good", log),
            BrokenComponent(),
        ]
    )

    report = await manager.shutdown()

    assert log == ["good"]
    assert report.attempted == 2
    assert report.succeeded == 1
    assert len(report.errors) == 1
    assert report.errors[0].component == "BrokenComponent"
    assert "shutdown failed" in report.errors[0].error


@pytest.mark.asyncio
async def test_shutdown_empty_components() -> None:
    manager = ShutdownManager([])
    report = await manager.shutdown()

    assert report.attempted == 0
    assert report.succeeded == 0
    assert report.errors == []


@pytest.mark.asyncio
async def test_async_component_prefers_aclose_over_close() -> None:
    log: list[str] = []

    class Both:
        async def aclose(self) -> None:
            log.append("aclose")

        def close(self) -> None:
            log.append("close")

    manager = ShutdownManager([Both()])
    await manager.shutdown()

    assert log == ["aclose"]