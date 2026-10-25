from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal



Direction = Literal["ar", "ru", "ambiguous"]


@dataclass(slots=True)
class ScriptVerdict:
    direction: Direction
    ratio: float


class ScriptDetector:
    """
    يكشف اتجاه النص: عربي أو سيريلي أو غامض.

    القواعد:
    - أقل من 6 حروف قابلة للتصنيف => ambiguous.
    - نسبة 60% أو أكثر من الحروف القابلة للتصنيف => ar أو ru.
    - غير ذلك => ambiguous.
    """

    MIN_CLASSIFIABLE_CHARS: int = 3
    THRESHOLD: float = 0.60

    def detect(self, text: str) -> ScriptVerdict:
        arabic_count = 0
        cyrillic_count = 0
        total_classifiable = 0

        for char in text:
            if not char.isalpha():
                continue

            try:
                char_name = unicodedata.name(char)
            except ValueError:
                continue

            total_classifiable += 1

            if "ARABIC" in char_name:
                arabic_count += 1
            elif "CYRILLIC" in char_name:
                cyrillic_count += 1

        if total_classifiable < self.MIN_CLASSIFIABLE_CHARS:
            return ScriptVerdict(direction="ambiguous", ratio=0.0)

        arabic_ratio = arabic_count / total_classifiable
        cyrillic_ratio = cyrillic_count / total_classifiable

        if arabic_ratio >= self.THRESHOLD:
            return ScriptVerdict(direction="ar", ratio=arabic_ratio)

        if cyrillic_ratio >= self.THRESHOLD:
            return ScriptVerdict(direction="ru", ratio=cyrillic_ratio)

        return ScriptVerdict(
            direction="ambiguous",
            ratio=max(arabic_ratio, cyrillic_ratio),
        )