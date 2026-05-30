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
        index: Optional global index for mapping to translation segments
        text: Text content (if type is text)
        image_path: Relative path to image file (if type is image)
        raw: Raw engine-specific data for debugging/extensions
        heading_level: Inferred heading level (1-6) for title blocks, defaults to 1
    """
    page_index: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    type: str
    index: Optional[int] = None  # Global index for segment mapping
    text: Optional[str] = None
    image_path: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    heading_level: int = 1  # Inferred heading level for title blocks
    
    def has_text(self) -> bool:
        """Check if block has text content."""
        return bool(self.text and self.text.strip())
    
    def has_image(self) -> bool:
        """Check if block has image."""
        return bool(self.image_path)


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
