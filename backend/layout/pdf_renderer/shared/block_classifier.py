# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Block type classification for font size calculation.

This module provides utilities for classifying and normalizing block types,
and checking whether blocks should be included in baseline calculations.
"""

from typing import Optional, Dict, Set
from layout.base import LayoutBlock


class FrontendStyleOverride:
    """
    Frontend style override configuration for a block.
    
    If frontend sets style overrides, they take priority over calculated styles.
    Blocks with frontend overrides are excluded from baseline calculations.
    """
    
    def __init__(
        self,
        font_size: Optional[float] = None,
        font_name: Optional[str] = None,
        alignment: Optional[str] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        strikethrough: Optional[bool] = None,
        table_border_width: Optional[float] = None,
        table_border_color: Optional[str] = None,
        table_cell_padding: Optional[float] = None,
    ):
        self.font_size = font_size
        self.font_name = font_name
        self.alignment = alignment
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.strikethrough = strikethrough
        self.table_border_width = table_border_width
        self.table_border_color = table_border_color
        self.table_cell_padding = table_cell_padding


# Type alias for frontend style overrides mapping
FrontendStyleOverrides = Dict[int, FrontendStyleOverride]


class BlockClassifier:
    """
    Block type classification for font size calculation.
    
    Provides utilities for:
    - Classifying blocks into unified font size types vs adjustable types
    - Normalizing block types (e.g., image_caption -> caption)
    - Checking if blocks should be included in baseline calculations
    """
    
    # 统一字号类型（0.5pt 步长，无微调）
    UNIFIED_FONT_SIZE_TYPES_05PT: Set[str] = {
        "header",
        "footer",
        "caption",  # image_caption + table_caption
        "table_notes",  # table_footnote
        "table_body",
        "ref_text",
    }
    
    # 统一字号类型（1.0pt 步长，需要微调）
    UNIFIED_FONT_SIZE_TYPES_10PT: Set[str] = {
        "text",
        "title",
    }
    
    # 所有统一字号类型
    UNIFIED_FONT_SIZE_TYPES: Set[str] = (
        UNIFIED_FONT_SIZE_TYPES_05PT | UNIFIED_FONT_SIZE_TYPES_10PT
    )
    
    @staticmethod
    def get_font_size_strategy(block_type: str) -> str:
        """
        Get font size calculation strategy for a block type.
        
        Returns:
            - 'unified_05pt': Use unified font size with 0.5pt step (no adjustment)
            - 'unified_10pt': Use unified font size with 1.0pt step (with adjustment)
            - 'default': Use default strategy
        """
        if block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_05PT:
            return "unified_05pt"
        elif block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_10PT:
            return "unified_10pt"
        else:
            return "default"
    
    @staticmethod
    def normalize_block_type(block: LayoutBlock) -> str:
        """
        Normalize block type, handling special cases.
        
        Rules:
        - image_caption, table_caption -> caption
        - table_footnote -> table_notes
        
        Args:
            block: LayoutBlock instance
            
        Returns:
            Normalized block type string
        """
        block_type = getattr(block, "type", "unknown") or "unknown"
        
        # Handle caption types
        if block_type in ("image_caption", "table_caption"):
            return "caption"
        
        # Handle table footnote
        if block_type == "table_footnote":
            return "table_notes"
        
        return block_type
    
    @staticmethod
    def should_include_in_baseline_calculation(
        block: LayoutBlock,
        frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
    ) -> bool:
        """
        Check if block should be included in baseline calculation.
        
        Rules:
        - If frontend sets font_size or font_name override, exclude from baseline
        - Otherwise, include in baseline calculation
        
        Args:
            block: LayoutBlock instance
            frontend_style_overrides: Optional frontend style overrides mapping
            
        Returns:
            True if block should be included in baseline calculation, False otherwise
        """
        if frontend_style_overrides is None:
            return True
        
        block_index = getattr(block, "index", None)
        if block_index is None:
            return True
        
        override = frontend_style_overrides.get(block_index)
        if override is None:
            return True
        
        # If frontend sets font_size or font_name, exclude from baseline
        if override.font_size is not None or override.font_name is not None:
            return False
        
        return True
    
    @staticmethod
    def get_quantize_step(block_type: str) -> float:
        """
        Get quantization step for a block type.
        
        Args:
            block_type: Normalized block type
            
        Returns:
            Quantization step in points (0.5 or 1.0)
        """
        if block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_10PT:
            return 1.0
        elif block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_05PT:
            return 0.5
        else:
            # Default to 0.5pt for unknown types
            return 0.5
    
    @staticmethod
    def needs_adjustment(block_type: str) -> bool:
        """
        Check if block type needs per-block adjustment.
        
        Args:
            block_type: Normalized block type
            
        Returns:
            True if block needs adjustment (text, title), False otherwise
        """
        return block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_10PT

