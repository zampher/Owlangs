# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Optional
from .base import Extractor, ExtractResult
from .markdown_extractor import MarkdownExtractor


class MarkdownBasedExtractor(Extractor):
    """
    Extractor for markdown_based workflow: expects already-converted Markdown content.
    """

    def __init__(self, markdown_text: str, chunk_size: int = 3000, deep_split: bool = False):
        self.markdown_text = markdown_text
        self.chunk_size = chunk_size
        self.deep_split = deep_split

    def extract(self) -> ExtractResult:
        return MarkdownExtractor(self.markdown_text, chunk_size=self.chunk_size, deep_split=self.deep_split).extract()


