from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Protocol

from hovertranslate.core.errors import ExtractionError
from hovertranslate.core.types import ExtractionResult, TriggerContext


class UIAElementLike(Protocol):
    def get_text(self) -> str | None: ...


class UIAFacadeLike(Protocol):
    def element_from_point(self, x: int, y: int) -> UIAElementLike: ...

    def focused_element(self) -> UIAElementLike: ...

    def close(self) -> None: ...


class ComTypesUIAElement:
    def __init__(self, element, uia_module) -> None:
        self._element = element
        self._uia = uia_module

    def get_text(self) -> str | None:
        try:
            pattern = self._element.GetCurrentPattern(self._uia.UIA_TextPatternId)
            text_pattern = pattern.QueryInterface(self._uia.IUIAutomationTextPattern)
            text = text_pattern.DocumentRange.GetText(-1)
            if text:
                return str(text)
        except Exception:
            pass

        try:
            pattern = self._element.GetCurrentPattern(self._uia.UIA_ValuePatternId)
            value_pattern = pattern.QueryInterface(self._uia.IUIAutomationValuePattern)
            text = value_pattern.CurrentValue
            if text:
                return str(text)
        except Exception:
            pass

        try:
            pattern = self._element.GetCurrentPattern(
                self._uia.UIA_LegacyIAccessiblePatternId
            )
            legacy = pattern.QueryInterface(
                self._uia.IUIAutomationLegacyIAccessiblePattern
            )
            text = legacy.CurrentValue or legacy.CurrentName
            if text:
                return str(text)
        except Exception:
            pass

        return None


class ComTypesUIAFacade:
    def __init__(self) -> None:
        import comtypes.client as cc

        cc.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA  # type: ignore[import-not-found]

        self._UIA = UIA
        ctypes.windll.ole32.CoInitialize(None)
        self._uia = cc.CreateObject(
            UIA.CUIAutomation._reg_clsid_,
            interface=UIA.IUIAutomation,
        )

    def element_from_point(self, x: int, y: int) -> UIAElementLike:
        point = ctypes.wintypes.POINT(x, y)
        element = self._uia.ElementFromPoint(point)
        return ComTypesUIAElement(element, self._UIA)

    def focused_element(self) -> UIAElementLike:
        element = self._uia.GetFocusedElement()
        return ComTypesUIAElement(element, self._UIA)

    def close(self) -> None:
        ctypes.windll.ole32.CoUninitialize()


class UIASource:
    def __init__(self, facade: UIAFacadeLike | None = None) -> None:
        self._facade = facade
        self._owns_facade = facade is None

    def _ensure_facade(self) -> UIAFacadeLike:
        if self._facade is None:
            self._facade = ComTypesUIAFacade()
        return self._facade

    def extract_hover(self, context: TriggerContext) -> ExtractionResult:
        try:
            element = self._ensure_facade().element_from_point(
                context.point_x,
                context.point_y,
            )
            text = element.get_text()
        except Exception as exc:
            raise ExtractionError(f"UIA hover extraction failed: {exc}") from exc

        if not text:
            return ExtractionResult(text=None, source="none", success=False)

        return ExtractionResult(text=text, source="uia", success=True)

    def extract_focused(self) -> ExtractionResult:
        try:
            element = self._ensure_facade().focused_element()
            text = element.get_text()
        except Exception as exc:
            raise ExtractionError(f"UIA focused extraction failed: {exc}") from exc

        if not text:
            return ExtractionResult(text=None, source="none", success=False)

        return ExtractionResult(text=text, source="uia", success=True)

    def close(self) -> None:
        if self._owns_facade and self._facade is not None:
            self._facade.close()