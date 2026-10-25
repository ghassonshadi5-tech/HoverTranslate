from __future__ import annotations

from PIL import ImageGrab

from hovertranslate.core.types import OcrRegion


class PillowScreenCapture:
    """
    يلتقط منطقة شاشة باستخدام Pillow.

    يُستخدم محليًا فقط، ولا يرسل أي بيانات إلى الخارج.
    """

    def grab(self, region: OcrRegion) -> object:
        bbox = (
            region.x,
            region.y,
            region.x + region.width,
            region.y + region.height,
        )

        return ImageGrab.grab(bbox=bbox)