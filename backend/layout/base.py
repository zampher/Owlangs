# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Platform-agnostic layout intermediate representation (IR).

This module defines generic data structures for representing document layout
information that are independent of any specific parsing engine (MinerU, Docling, etc.).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterator


@dataclass
class LayoutBlock:
    """
    A single layout block (text or image) with position information.

    Attributes:
        page_index: Zero-based page index where this block appears
        bbox: Bounding box as (x0, y0, x1, y1) in page coordinates
        type: Block type (e.g., 'text', 'image', 'header', 'footer', 'title')
        sub_type: Semantic sub-type (e.g., 'body', 'title', 'heading',
            'caption', 'header', 'footer', 'footnote', 'image_body',
            'table_body', 'display_formula', 'code_block', 'page_number')
        index: Optional global index for mapping to translation segments
        text: Text content (if type is text)
        image_path: Relative path to image file (if type is image)
        raw: Raw engine-specific data for debugging/extensions
        heading_level: Inferred heading level (0-6); 0 = no heading, 1-6 = H1-H6
        tags: Semantic tags (e.g., 'skip_translation', 'heading', 'title')
        should_translate: Whether this block should be translated
    """
    page_index: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    type: str
    sub_type: str = ""  # Semantic sub-type for finer-grained block classification
    index: Optional[int] = None  # Global index for segment mapping
    text: Optional[str] = None
    image_path: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    heading_level: int = 0  # 0 = body text/no heading, 1-6 = H1-H6 heading levels
    tags: List[str] = field(default_factory=list)
    should_translate: bool = True

    def has_text(self) -> bool:
        """Check if block has text content."""
        return bool(self.text and self.text.strip())

    def has_recognized_text(self) -> bool:
        """True when OCR/layout detected non-empty textual content in this block."""
        if self.text and self.text.strip():
            return True
        raw = self.raw if isinstance(self.raw, dict) else {}
        for key in ("block_content", "text", "content"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return True
        for line in raw.get("lines") or []:
            if not isinstance(line, dict):
                continue
            line_text = line.get("text")
            if isinstance(line_text, str) and line_text.strip():
                return True
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                for key in ("content", "text"):
                    span_text = span.get(key)
                    if isinstance(span_text, str) and span_text.strip():
                        return True
        return False

    def has_image(self) -> bool:
        """Check if block has image."""
        return bool(self.image_path)

    # -- semantic category convenience methods ---------------------------
    # These delegate to the canonical frozensets in layout.block_types so
    # that downstream code does not need to hard-code type strings.

    def is_visual(self) -> bool:
        """Image, table, or chart block -- rendered as image, never translated."""
        from layout.block_types import VISUAL_BLOCK_TYPES, BODY_SUB_TYPES
        return self.type in VISUAL_BLOCK_TYPES or self.sub_type in BODY_SUB_TYPES

    def is_equation(self) -> bool:
        """Formula / equation block -- never translated, may render as image or LaTeX."""
        from layout.block_types import EQUATION_BLOCK_TYPES
        return self.type in EQUATION_BLOCK_TYPES

    def is_structural(self) -> bool:
        """Header, footer, or page-number block -- never translated."""
        from layout.block_types import STRUCTURAL_BLOCK_TYPES
        return self.type in STRUCTURAL_BLOCK_TYPES

    def is_heading(self) -> bool:
        """Title or sub-title block -- translated with heading formatting."""
        from layout.block_types import HEADING_BLOCK_TYPES
        return self.type in HEADING_BLOCK_TYPES or self.sub_type == "heading"

    def is_list_container(self) -> bool:
        """List container block that should be expanded to child text blocks."""
        from layout.block_types import LIST_CONTAINER_TYPES
        return self.type in LIST_CONTAINER_TYPES

    def is_reference(self) -> bool:
        """Reference / citation entry block -- translated, special font handling."""
        from layout.block_types import REFERENCE_BLOCK_TYPES
        return self.type in REFERENCE_BLOCK_TYPES

    def is_footnote(self) -> bool:
        """Page footnote block -- translated, special formatting."""
        from layout.block_types import PAGE_FOOTNOTE
        return self.type == PAGE_FOOTNOTE or self.sub_type == "footnote"

    def is_code(self) -> bool:
        """Code block -- never translated."""
        from layout.block_types import CODE
        return self.type == CODE

    def should_skip_redaction(self) -> bool:
        """Block whose original PDF content should never be erased."""
        from layout.block_types import SKIP_REDACTION_TYPES
        return self.type in SKIP_REDACTION_TYPES

    def is_text_content(self) -> bool:
        """Block contains translatable text (not visual, not equation)."""
        return self.has_text() and not self.is_visual() and not self.is_equation()


@dataclass
class LayoutPage:
    """
    A single page with its layout blocks.
    
    Attributes:
        page_index: Zero-based page index
        blocks: List of layout blocks on this page
        width: Optional page width (for normalization)
        height: Optional page height (for normalization)
    """
    page_index: int
    blocks: List[LayoutBlock] = field(default_factory=list)
    width: Optional[float] = None
    height: Optional[float] = None
    
    def iter_text_blocks(self) -> Iterator[LayoutBlock]:
        """Iterate over blocks that have text content."""
        for block in self.blocks:
            if block.has_text():
                yield block
    
    def iter_image_blocks(self) -> Iterator[LayoutBlock]:
        """Iterate over blocks that have images."""
        for block in self.blocks:
            if block.has_image():
                yield block


@dataclass
class LayoutDocument:
    """
    Complete document layout representation.
    
    Attributes:
        pages: List of pages (ordered by page_index)
        engine: Source engine name (e.g., 'mineru', 'docling')
        metadata: Optional metadata dictionary
    """
    pages: List[LayoutPage] = field(default_factory=list)
    engine: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def page_count(self) -> int:
        """Total number of pages."""
        return len(self.pages)
    
    def get_page(self, page_index: int) -> Optional[LayoutPage]:
        """Get page by index, or None if not found."""
        for page in self.pages:
            if page.page_index == page_index:
                return page
        return None
    
    def iter_blocks(self) -> Iterator[LayoutBlock]:
        """Iterate over all blocks across all pages."""
        for page in self.pages:
            for block in page.blocks:
                yield block
    
    def iter_text_blocks(self) -> Iterator[LayoutBlock]:
        """Iterate over all text blocks across all pages."""
        for page in self.pages:
            for block in page.iter_text_blocks():
                yield block
    
    def iter_image_blocks(self) -> Iterator[LayoutBlock]:
        """Iterate over all image blocks across all pages."""
        for page in self.pages:
            for block in page.iter_image_blocks():
                yield block
