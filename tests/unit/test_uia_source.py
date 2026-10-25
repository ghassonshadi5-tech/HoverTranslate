from __future__ import annotations

from hovertranslate.core.types import TriggerContext
from hovertranslate.extraction.uia_source import UIASource


class FakeElement:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def get_text(self) -> str | None:
        return self._text


class FakeFacade:
    def __init__(
        self,
        point_text: str | None = None,
        focused_text: str | None = None,
    ) -> None:
        self.point_text = point_text
        self.focused_text = focused_text
        self.closed = False

    def element_from_point(self, x: int, y: int) -> FakeElement:
        return FakeElement(self.point_text)

    def focused_element(self) -> FakeElement:
        return FakeElement(self.focused_text)

    def close(self) -> None:
        self.closed = True


def test_extract_hover_success() -> None:
    source = UIASource(facade=FakeFacade(point_text="مرحبا"))
    result = source.extract_hover(
        TriggerContext(kind="hover", point_x=10, point_y=20)
    )

    assert result.success is True
    assert result.text == "مرحبا"
    assert result.source == "uia"


def test_extract_hover_empty_returns_none_source() -> None:
    source = UIASource(facade=FakeFacade(point_text=""))
    result = source.extract_hover(
        TriggerContext(kind="hover", point_x=10, point_y=20)
    )

    assert result.success is False
    assert result.text is None
    assert result.source == "none"


def test_extract_focused_success() -> None:
    source = UIASource(facade=FakeFacade(focused_text="Привет"))
    result = source.extract_focused()

    assert result.success is True
    assert result.text == "Привет"
    assert result.source == "uia"


def test_close_does_not_close_injected_facade() -> None:
    facade = FakeFacade()
    source = UIASource(facade=facade)
    source.close()

    assert facade.closed is False