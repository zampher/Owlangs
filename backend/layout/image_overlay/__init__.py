# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Image overlay rendering: erase OCR text regions and write translated text on raster images."""

from layout.image_overlay.models import ImageOverlayConfig, ImageOverlayResult
from layout.image_overlay.pipeline import ImageOverlayPipeline

__all__ = [
    "ImageOverlayConfig",
    "ImageOverlayPipeline",
    "ImageOverlayResult",
]
