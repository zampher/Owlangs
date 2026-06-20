# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MinerU OCR provider — wraps :class:`ConverterMineru` to implement
the :class:`OCRProvider` interface.
"""

import asyncio

from ir.document import Document
from ir.markdown_document import MarkdownDocument
from layout.ocr_provider.base import OCRProvider
from layout.ocr_provider.types import OCRProviderResult


class MinerUProvider(OCRProvider):
    """OCR provider backed by MinerU (cloud or local)."""

    def __init__(self, config):
        """
        Args:
            config: :class:`ConverterMineruConfig` instance.
        """
        from converter.x2md.converter_mineru import ConverterMineru
        self._config = config
        self._converter = ConverterMineru(config)

    async def convert(self, document: Document) -> OCRProviderResult:
        """Run MinerU OCR synchronously in a thread, return unified result."""
        converter = self._converter

        md_doc = await asyncio.to_thread(converter.convert, document)
        layout_doc = converter.layout_document

        return OCRProviderResult(
            layout_document=layout_doc,
            markdown_document=md_doc,
        )

    def support_format(self) -> list[str]:
        return [".pdf"]
