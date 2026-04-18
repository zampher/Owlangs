# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Optional, List
from .base import Extractor, ExtractResult
from utils.markdown_splitter import split_markdown_text, split_markdown_text_with_placeholder_awareness


class MarkdownExtractor(Extractor):
    def __init__(self, markdown_text: str, chunk_size: int = 3000, deep_split: bool = False):
        self.markdown_text = markdown_text
        self.chunk_size = chunk_size
        self.deep_split = deep_split

    def extract(self) -> ExtractResult:
        # Use placeholder-aware splitting if markdown contains placeholders
        # This handles images as separate chunks and excludes placeholders from size calculation
        import re
        ph_pattern = r"<ph-([a-zA-Z0-9]+)>"
        has_placeholders = bool(re.search(ph_pattern, self.markdown_text))
        
        if has_placeholders:
            # Use placeholder-aware splitting (images as separate chunks)
            segments, _ = split_markdown_text_with_placeholder_awareness(
                self.markdown_text,
                max_block_size=self.chunk_size,
                show_images_as_separate_chunks=True,
                deep_split=self.deep_split
            )
        else:
            # Use regular splitting for markdown without placeholders
            segments = split_markdown_text(self.markdown_text, max_block_size=self.chunk_size, deep_split=self.deep_split)
        
        return ExtractResult(segments=segments, separators_after=None)


