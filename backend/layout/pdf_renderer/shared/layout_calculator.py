# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Layout calculation utilities for PDF rendering.

This module provides shared layout calculation logic that can be used
by all PDF renderer implementations (ReportLab, HTML-to-PDF, etc.).
"""

from typing import Optional, List, Tuple


class LayoutCalculator:
    """
    Layout calculation utilities.
    
    Provides methods for calculating available space, line heights,
    and other layout-related metrics.
    """
    
    @staticmethod
    def calculate_available_height(
        height: float,
        font_size: float,
        font_ascent_ratio: float = 0.75,
    ) -> float:
        """
        Calculate available height for text rendering within a block.
        
        This method accounts for font metrics space (ascent + descent)
        and ensures the available height doesn't become too small.
        
        Args:
            height: Total block height in points
            font_size: Font size in points
            font_ascent_ratio: Ratio of font ascent to font size (default: 0.75)
            
        Returns:
            Available height in points for text rendering
        """
        # For very small blocks, use 90% of height as available space
        if height < font_size * 1.5:
            available_height = height * 0.9
        else:
            # For normal blocks, account for font metrics space
            estimated_font_ascent = font_size * font_ascent_ratio
            font_metrics_space = estimated_font_ascent + font_size * (1.0 - font_ascent_ratio)
            available_height = height - font_metrics_space
        
        # Ensure available_height is at least 30% of height (safety margin)
        available_height = max(available_height, height * 0.3)
        
        return available_height
    
    @staticmethod
    def calculate_max_allowed_height(
        available_height: float,
        line_count: int,
        estimated_line_height: float,
        tolerance_per_line_ratio: float = 0.05,
    ) -> float:
        """
        Calculate maximum allowed height with line-based tolerance.
        
        Args:
            available_height: Base available height in points
            line_count: Number of text lines
            estimated_line_height: Estimated height per line in points
            tolerance_per_line_ratio: Tolerance ratio per line (default: 0.05 = 5%)
            
        Returns:
            Maximum allowed height in points (with tolerance)
        """
        tolerance_per_line = estimated_line_height * tolerance_per_line_ratio
        max_allowed_height = available_height + line_count * tolerance_per_line
        return max_allowed_height
    
    @staticmethod
    def calculate_line_height_bounds(
        font_size: float,
        min_ratio: float = 1.15,
        max_ratio: float = 1.4,
    ) -> tuple[float, float]:
        """
        Calculate reasonable line height bounds.
        
        Args:
            font_size: Font size in points
            min_ratio: Minimum line height ratio (default: 1.15 = 15% spacing)
            max_ratio: Maximum line height ratio (default: 1.4 = 40% spacing)
            
        Returns:
            Tuple of (min_line_height, max_line_height) in points
        """
        min_line_height = font_size * min_ratio
        max_line_height = font_size * max_ratio
        return (min_line_height, max_line_height)
    
    @staticmethod
    def clamp_line_height(
        line_height: float,
        font_size: float,
        min_ratio: float = 1.15,
        max_ratio: float = 1.4,
    ) -> float:
        """
        Clamp line height to reasonable bounds.
        
        Ensures line_height >= font_size and within reasonable range.
        
        Args:
            line_height: Current line height in points
            font_size: Font size in points
            min_ratio: Minimum line height ratio (default: 1.15)
            max_ratio: Maximum line height ratio (default: 1.4)
            
        Returns:
            Clamped line height in points
        """
        min_line_height, max_line_height = LayoutCalculator.calculate_line_height_bounds(
            font_size, min_ratio, max_ratio
        )
        # Ensure line_height >= font_size (prevent negative spacing)
        clamped = max(font_size, line_height)
        # Clamp to reasonable bounds
        clamped = max(min_line_height, min(clamped, max_line_height))
        return clamped
    
    @staticmethod
    def calculate_available_height_for_lines(
        bbox_height: float,
        line_count: int,
        font_size: float,
        line_spacing_ratio: float = 1.2
    ) -> float:
        """
        Calculate available height based on line count.
        
        Key insight:
        - Single line bbox: height = font height (no line spacing)
        - Two line bbox: height = font height + 1 line spacing
        - Multi line bbox: height = font height + (n-1) line spacings
        
        This is a more accurate calculation than the generic calculate_available_height
        because it accounts for the fact that bbox heights don't include line spacing
        for single lines, and include (n-1) spacings for multi-line blocks.
        
        Args:
            bbox_height: Bounding box height in points
            line_count: Number of lines
            font_size: Font size in points
            line_spacing_ratio: Line spacing ratio (default 1.2, meaning 20% spacing)
            
        Returns:
            Available height for text rendering in points
        """
        if line_count <= 0 or bbox_height <= 0:
            return 0.0
        
        if line_count == 1:
            # Single line: bbox height is just font height (no line spacing)
            # Use 95% of bbox height as available height (5% safety margin)
            return bbox_height * 0.95
        else:
            # Multi-line: bbox height = font height + (n-1) line spacings
            # Line spacing increment = font_size * (line_spacing_ratio - 1.0)
            line_spacing_increment = font_size * (line_spacing_ratio - 1.0)
            total_line_spacing = (line_count - 1) * line_spacing_increment
            
            # Available height = bbox height - total line spacing
            # But we need to account for font ascent/descent margins
            available_height = bbox_height - total_line_spacing
            
            # Subtract extra space for font ascent/descent (beyond font center line)
            # Font ascent is typically 75% of font size, descent is 25%
            # The extra space beyond font center is: (ascent - font_size/2) + (descent - font_size/2)
            font_ascent = font_size * 0.75
            font_descent = font_size * 0.25
            extra_space = (font_ascent - font_size * 0.5) + (font_descent - font_size * 0.5)
            available_height = available_height - extra_space
            
            # Ensure at least 30% of bbox height as safety margin
            return max(available_height, bbox_height * 0.3)
    
    @staticmethod
    def build_page_block_bbox_index(layout_doc: "LayoutDocument") -> List[List[Tuple[float, float, float, float, str, int, int]]]:
        """
        Build a per-page list of block bboxes for collision checking.

        Each page entry is a list of tuples:
            (x0, y0, x1, y1, block_type, block_index, page_block_idx)

        All coordinates are in layout space (MinerU coordinates).
        
        Args:
            layout_doc: LayoutDocument instance
            
        Returns:
            List of page block info lists
        """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from layout.base import LayoutDocument
        
        pages_info: List[List[Tuple[float, float, float, float, str, int, int]]] = []
        for page in layout_doc.pages:
            page_blocks: List[Tuple[float, float, float, float, str, int, int]] = []
            for page_block_idx, block in enumerate(page.blocks):
                try:
                    x0, y0, x1, y1 = block.bbox
                    btype = getattr(block, "type", "unknown") or "unknown"
                    bindex = getattr(block, "index", -1)
                    page_blocks.append(
                        (float(x0), float(y0), float(x1), float(y1), str(btype), int(bindex) if isinstance(bindex, int) else -1, int(page_block_idx))
                    )
                except Exception:
                    # Ignore blocks with invalid bbox
                    continue
            pages_info.append(page_blocks)
        return pages_info
    
    @staticmethod
    def check_block_collision_with_page(
        page_blocks: List[Tuple[float, float, float, float, str, int, int]],
        page_idx: int,
        page_block_idx: int,
        x0: float,
        y0: float,
        x1: float,
        rendered_height: float,
        current_block_type: str,
    ) -> bool:
        """
        Check whether the rendered region of the current block collides with any other block on the same page.

        The rendered region is approximated as a vertical strip:
            [x0, x1] × [y0, y0 + rendered_height] in layout coordinates.

        A collision occurs if this region intersects another block's bbox in both X and Y.
        The current block itself (matching page_block_idx) is excluded.
        
        Args:
            page_blocks: List of block info tuples for the page
            page_idx: Page index (for logging)
            page_block_idx: Current block index within the page
            x0, y0, x1: Current block bbox coordinates
            rendered_height: Height of rendered region
            current_block_type: Type of current block
            
        Returns:
            True if collision detected, False otherwise
        """
        if rendered_height <= 0:
            return False

        y_top = y0
        y_bottom = y0 + rendered_height

        for bx0, by0, bx1, by1, btype, bindex, b_page_block_idx in page_blocks:
            # Skip self
            if b_page_block_idx == page_block_idx:
                continue

            # Check horizontal overlap
            overlap_x0 = max(x0, bx0)
            overlap_x1 = min(x1, bx1)
            if overlap_x0 >= overlap_x1:
                continue

            # Check vertical overlap
            overlap_y0 = max(y_top, by0)
            overlap_y1 = min(y_bottom, by1)
            if overlap_y0 >= overlap_y1:
                continue

            # Found a collision
            return True

        return False

