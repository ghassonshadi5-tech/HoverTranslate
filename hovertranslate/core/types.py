from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TriggerKind = Literal["hover", "selection"]
ExtractionSource = Literal["uia", "clipboard", "ocr", "none"]


@dataclass(slots=True)
class TriggerContext:
    kind: TriggerKind
    point_x: int
    point_y: int
    hwnd: int | None = None


@dataclass(slots=True)
class ExtractionResult:
    text: str | None
    source: ExtractionSource
    success: bool


@dataclass(slots=True)
class OcrRegion:
    x: int
    y: int
    width: int
    height: int


@dataclass(slots=True)
class OcrResult:
    text: str | None
    quality: float | None = None