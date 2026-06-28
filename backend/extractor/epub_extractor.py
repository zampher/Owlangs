# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from logger import unified_logger as logger
from logger.logger import LogModule

from .base import Extractor, ExtractResult
from utils.epub_html_segments import (
    collect_epub_paragraph_segments,
    read_epub_all_files,
)


class EpubExtractor(Extractor):
    """
    Extract textual content from an EPUB archive and split into preview segments.

    Uses HtmlExtractor paragraph splitting (same as HTML workflow) so Extract
    preview segments align with translation segments.
    """

    def __init__(self, file_bytes: bytes, chunk_size: int = 3000):
        self.file_bytes = file_bytes
        self.chunk_size = chunk_size

    def extract(self) -> ExtractResult:
        try:
            all_files = read_epub_all_files(self.file_bytes)
            if not all_files:
                return ExtractResult(segments=[])

            _, segments = collect_epub_paragraph_segments(
                all_files,
                chunk_size=self.chunk_size,
                deep_split=True,
            )

            if not segments:
                return ExtractResult(segments=[])

            return ExtractResult(
                segments=segments,
                segment_info=[
                    {"source": "epub", "index": idx} for idx in range(len(segments))
                ],
            )
        except Exception as exc:
            logger.error(
                f"EPUB extraction failed: {exc}",
                module=LogModule.EXTRACT,
                exc_info=True,
            )
            return ExtractResult(segments=[])
