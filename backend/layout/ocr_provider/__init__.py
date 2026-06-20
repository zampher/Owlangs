# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
OCR Provider package.

Provides a unified interface for OCR / layout-parsing backends
(MinerU, PaddleOCR, etc.) through :class:`OCRProvider`.
"""

from .base import OCRProvider
from .types import OCRProviderResult

__all__ = ["OCRProvider", "OCRProviderResult"]
