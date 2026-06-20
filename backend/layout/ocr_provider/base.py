# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Abstract base class for OCR providers.

All OCR engines (MinerU, PaddleOCR, etc.) implement this interface so
that workflows can consume any provider uniformly.
"""

from abc import ABC, abstractmethod

from ir.document import Document
from .types import OCRProviderResult


class OCRProvider(ABC):
    """Abstract interface for OCR / layout-parsing providers."""

    @abstractmethod
    async def convert(self, document: Document) -> OCRProviderResult:
        """
        Run OCR and layout parsing on *document*.

        Returns a unified :class:`OCRProviderResult` containing the
        platform-agnostic ``LayoutDocument``, the corresponding markdown
        text, and any provider-specific raw data or attachments.
        """
        ...

    @abstractmethod
    def support_format(self) -> list[str]:
        """Return the list of file suffixes this provider can handle."""
        ...
