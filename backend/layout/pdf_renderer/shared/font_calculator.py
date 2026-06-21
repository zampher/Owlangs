# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Font size calculation utilities for PDF rendering.

This module provides shared font size calculation logic that can be used
by all PDF renderer implementations (ReportLab, HTML-to-PDF, etc.).
"""

from typing import Dict, Optional, List, Tuple, Callable
from layout.base import LayoutDocument, LayoutBlock
from logger.logger import unified_logger, LogModule
from layout.block_types import IMAGE_CAPTION, TABLE_CAPTION, CAPTION
from layout.pdf_renderer.shared.block_classifier import (
    BlockClassifier,
    FrontendStyleOverrides,
)


class FontSizeCalculator:
    """
    Font size calculation utilities.
    
    Provides methods for estimating initial font sizes, calculating
    type-specific font baselines, and quantizing font sizes.
    """
    
    def __init__(
        self,
        type_font_baselines: Optional[Dict[str, float]] = None,
        config: Optional[object] = None,  # PDFRendererConfig (to avoid circular import)
    ):
        """
        Initialize font size calculator.
        
        Args:
            type_font_baselines: Optional pre-calculated type font baselines
            config: Optional renderer config (for accessing shared utilities)
        """
        self.type_font_baselines = type_font_baselines or {}
        self.config = config
    
    @staticmethod
    def estimate_line_count_from_font_size(
        text: str,
        font_size: float,
        block_width: float,
        block_raw: Optional[dict] = None
    ) -> int:
        """
        Estimate number of lines for given text, font size, and block width.
        
        Args:
            text: Text content
            font_size: Font size in points
            block_width: Block width in points
            block_raw: Optional raw block data from MinerU layout
            
        Returns:
            Estimated number of lines
        """
        if not text or block_width <= 0:
            return 1
        
        # Try to get actual line count from MinerU layout first
        if block_raw:
            lines = block_raw.get("lines", [])
            if lines:
                return len(lines)
        
        # Count explicit newlines
        explicit_lines = text.count('\n') + 1
        
        # Estimate wrapping: average character width is approximately font_size * 0.6
        # (this is a rough estimate, actual width depends on font and characters)
        avg_char_width = font_size * 0.6
        if avg_char_width > 0:
            chars_per_line = max(1, int(block_width / avg_char_width))
            estimated_wrapped_lines = max(1, int(len(text) / chars_per_line))
            return max(explicit_lines, estimated_wrapped_lines)
        
        return explicit_lines
    
    @staticmethod
    def calculate_block_height_from_font_size(
        font_size: float,
        line_count: int
    ) -> float:
        """
        Calculate block height from font size and line count.
        
        Args:
            font_size: Font size in points
            line_count: Number of lines
            
        Returns:
            Estimated block height in points
        """
        if line_count <= 0:
            return font_size
        
        # Line height is typically font_size * 1.2 (20% line spacing)
        line_height = font_size * 1.2
        
        # For single line, height is approximately font_size (with some ascent/descent)
        if line_count == 1:
            return font_size * 1.1  # Slight margin for ascent/descent
        
        # For multiple lines: first line needs font_ascent, then (n-1) * line_height
        font_ascent = font_size * 0.75
        total_height = font_ascent + (line_count - 1) * line_height + font_size * 0.25
        
        return total_height
    
    @staticmethod
    def estimate_initial_font_size(
        block_height: float,
        text: str = "",
        block_width: float = 0.0,
        block_raw: Optional[dict] = None
    ) -> float:
        """
        Initial font size estimation from block height (first iteration).
        
        Args:
            block_height: Height of the block in points
            text: Text content (for estimating line count)
            block_width: Width of the block in points (for estimating line count)
            block_raw: Optional raw block data from MinerU layout
            
        Returns:
            Initial estimated font size in points
        """
        if block_height <= 0:
            return 12  # Default

        # Estimate initial line count
        # 1) 从 layout.raw 中读取的行数（MinerU 的行信息）
        # 2) 如果文本中没有显式换行，则根据「宽度」估算自动换行行数
        # 最终取两者中的较大值，避免 MinerU 把整段长文本当成一行导致字号被放大
        estimated_lines_layout = 0
        estimated_lines_wrap = 0

        # 来自 layout 的行数（如果有）
        if block_raw and isinstance(block_raw, dict):
            lines = block_raw.get("lines", [])
            if lines:
                estimated_lines_layout = len(lines)

        # 根据宽度估算自动换行行数
        if text and block_width > 0:
            # 估算平均字符宽度（中文字符约为 font_size，英文字符约为 font_size * 0.6）
            # 使用一个折中的值：font_size * 0.8
            avg_char_width = 12 * 0.8  # 使用12pt作为初始估算值
            if avg_char_width > 0:
                chars_per_line = max(1, int(block_width / avg_char_width))
                estimated_lines_wrap = max(1, int(len(text) / chars_per_line))
        
        # 取两者中的较大值
        estimated_lines = max(estimated_lines_layout, estimated_lines_wrap, 1)

        # 根据行数计算字号
        if estimated_lines <= 1:
            # 单行：字号约为高度的95%
            font_size = block_height * 0.95
        else:
            # 多行：字号 = (高度 / 行数) * 0.92
            # 0.92 系数考虑了行间距和字体 ascent/descent
            font_size = (block_height / estimated_lines) * 0.92
        
        # 限制字号范围：最小7pt，最大24pt
        font_size = max(7, min(24, font_size))
        
        return round(font_size, 1)
    
    @staticmethod
    def quantize_font_size(font_size: float) -> float:
        """
        Quantize font size to commonly used discrete sizes.
        
        使用类似"四舍五入"的方式，将连续字号映射到常用字号刻度：
        - 最小不小于 6.0
        - 最大不超过 24.0
        - 四舍五入到最近的整数
        
        Args:
            font_size: Input font size in points
            
        Returns:
            Quantized font size in points
        """
        clamped = max(6.0, min(24.0, font_size))
        quantized = float(int(clamped + 0.5))
        return quantized
    
    @staticmethod
    def quantize_font_size_with_step(font_size: float, step: float = 0.5) -> float:
        """
        Quantize font size to specified step size.
        
        Uses rounding to nearest step multiple.
        - Minimum: step (e.g., 0.5pt or 1.0pt)
        - Maximum: 24.0pt
        - Rounds to nearest step multiple
        
        Args:
            font_size: Input font size in points
            step: Quantization step in points (default: 0.5pt)
            
        Returns:
            Quantized font size in points
        """
        if step <= 0:
            step = 0.5  # Default step
        
        clamped = max(step, min(24.0, font_size))
        quantized = round(clamped / step) * step
        return quantized
    
    @staticmethod
    def get_font_size_from_type_baseline(
        type_baselines: Dict[str, float],
        block_type: str,
        text: str = "",
        block: Optional[LayoutBlock] = None,
        canvas_obj=None,
        font_name: str = "Helvetica",
    ) -> float:
        """
        Get font size from type-specific baseline.
        
        For text and title types, this method will use adjustable font size calculation
        based on the unified baseline. For other types, it returns the baseline directly.
        
        Args:
            type_baselines: Dictionary mapping block type to baseline font size
            block_type: Type of the block (text, title, header, footer, etc.)
            text: Text content (for potential language-based adjustments)
            block: Optional LayoutBlock instance (required for text/title adjustment)
            canvas_obj: Optional canvas object for text width measurement (for text/title)
            font_name: Font name for text width calculation (for text/title)
            
        Returns:
            Font size in points
        """
        from layout.pdf_renderer.shared.text_utils import TextUtils
        from layout.pdf_renderer.shared.block_classifier import BlockClassifier
        
        # Normalize block type
        normalized_type = BlockClassifier.normalize_block_type(block) if block else block_type
        
        # Get baseline for this block type, fallback to "unknown" or default
        baseline = type_baselines.get(normalized_type)
        if baseline is None:
            baseline = type_baselines.get("unknown", 12.0)
        
        # For text and title types, use adjustable font size calculation
        if normalized_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES_10PT and block is not None:
            try:
                adjusted_size = FontSizeCalculator.calculate_adjustable_font_size_for_block(
                    block=block,
                    text=text,
                    unified_baseline=baseline,
                    canvas_obj=canvas_obj,
                    font_name=font_name,
                    adjust_step=1.0,
                )
                return adjusted_size
            except Exception:
                # If adjustment fails, fall back to baseline
                pass
        
        # For other types, use baseline with minimal language-based adjustment
        font_size = baseline
        
        # Optional: small language-based adjustment (minimal, since baseline is already type-specific)
        try:
            lang_dist = TextUtils.analyze_language_distribution(text or "")
            if lang_dist:
                cjk_ratio = lang_dist.get("zh", 0.0) + lang_dist.get("ja", 0.0) + lang_dist.get("ko", 0.0)
                
                # Very small adjustment for CJK-heavy blocks (reduced from 1.03 to 1.02)
                if cjk_ratio >= 0.7:
                    font_size *= 1.02
        except Exception:
            pass
        
        # Final clamp to reasonable range (baseline ± 10% max, very conservative)
        min_size = max(6, baseline * 0.9)
        max_size = min(24, baseline * 1.1)
        font_size = max(min_size, min(max_size, font_size))
        
        # Quantize to 0.5pt step for non-text/title types
        quantize_step = BlockClassifier.get_quantize_step(normalized_type)
        font_size = FontSizeCalculator.quantize_font_size_with_step(font_size, step=quantize_step)
        
        return font_size
    
    @staticmethod
    def fine_tune_font_size_to_prevent_overflow(
        canvas_obj,
        text: str,
        font_name: str,
        font_size: float,
        text_lines: List[str],
        text_width_for_wrapping: float,
        height: float,
        block_type: str,
        page_idx: int,
        block_idx: int,
        original_font_size: float,
        line_height_ratio: float = 1.2,
        font_ascent_ratio: float = 0.75,
        overflow_tolerance: float = 1.02,
        increment_step: float = 0.1,
        max_iterations: int = 10
    ) -> Tuple[float, List[str], str]:
        """
        Fine-tune font size by incrementally increasing it to find the maximum size
        that doesn't cause text overflow, while preventing overflow.
        
        This function is useful for block types (e.g., ref_text) where we want to
        maximize font size usage while ensuring text fits within the bounding box.
        
        Args:
            canvas_obj: ReportLab canvas object for font metrics
            text: Original text content
            font_name: Current font name
            font_size: Current font size (starting point)
            text_lines: Current wrapped text lines
            text_width_for_wrapping: Available width for text wrapping
            height: Block bounding box height
            block_type: Type of the block (e.g., "ref_text")
            page_idx: Page index for logging
            block_idx: Block index for logging
            original_font_size: Original font size before adjustments (for logging)
            line_height_ratio: Ratio of line height to font size (default: 1.2)
            font_ascent_ratio: Ratio of font ascent to font size (default: 0.75)
            overflow_tolerance: Tolerance factor for overflow detection (default: 1.02 = 2%)
            increment_step: Font size increment per iteration in points (default: 0.1pt)
            max_iterations: Maximum number of fine-tuning iterations (default: 10)
            
        Returns:
            Tuple of (optimized_font_size, optimized_text_lines, final_font_name)
        """
        from layout.pdf_renderer.shared.text_utils import TextUtils
        
        # Check if current text overflows bbox
        # Improved available_height calculation to prevent it from becoming too small
        if height < font_size * 1.5:
            # For very small blocks, use 90% of height as available space
            available_height = height * 0.9
        else:
            # For normal blocks, account for font metrics space
            estimated_font_ascent = font_size * font_ascent_ratio
            font_metrics_space = estimated_font_ascent + font_size * (1.0 - font_ascent_ratio)
            available_height = height - font_metrics_space
        
        # Ensure available_height is at least 30% of height (safety margin)
        available_height = max(available_height, height * 0.3)
        
        current_total_height = sum([font_size * line_height_ratio] * len(text_lines)) if text_lines else 0
        current_overflows = current_total_height > available_height * overflow_tolerance
        
        # Always start fine-tuning: try to find the maximum font size that doesn't overflow
        # If current text overflows, we'll find the last non-overflow size
        # If current text doesn't overflow, we'll try to increase it up to max_iterations
        # (Logging removed - this function is no longer used for ref_text)
        
        best_font_size = font_size
        best_text_lines = text_lines
        best_font_name = font_name
        fine_tune_iterations = 0
        
        # Start from current font_size and increase by increment_step each iteration
        test_font_size = font_size
        
        for fine_tune_iter in range(max_iterations):
            test_font_size += increment_step
            
            # Apply test font size
            test_font_name = font_name
            try:
                canvas_obj.setFont(test_font_name, test_font_size)
            except Exception as e:
                # (Debug logging removed)
                test_font_name = "Helvetica"
                canvas_obj.setFont(test_font_name, test_font_size)
            
            # Re-wrap with test font size
            if '\n' in text:
                test_text_lines = []
                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    wrapped = TextUtils.wrap_text_to_width(
                        line, text_width_for_wrapping,
                        font_name=test_font_name, font_size=test_font_size,
                        canvas_obj=canvas_obj
                    )
                    test_text_lines.extend(wrapped)
            else:
                test_text_lines = TextUtils.wrap_text_to_width(
                    text, text_width_for_wrapping,
                    font_name=test_font_name, font_size=test_font_size,
                    canvas_obj=canvas_obj
                )
            
            if not test_text_lines and text.strip():
                test_text_lines = [text.strip()]
            
            # Calculate total height with test font size
            test_line_height = test_font_size * line_height_ratio
            test_total_height = len(test_text_lines) * test_line_height
            test_font_ascent = test_font_size * font_ascent_ratio
            test_font_metrics_space = test_font_ascent + test_font_size * (1.0 - font_ascent_ratio)
            test_available_height = height - test_font_metrics_space
            
            # Check if this font size causes overflow
            if test_total_height > test_available_height * overflow_tolerance:  # Overflow
                # Use the last non-overflow font size
                break
            else:
                # No overflow, this is a valid font size
                best_font_size = test_font_size
                best_text_lines = test_text_lines
                best_font_name = test_font_name
                fine_tune_iterations = fine_tune_iter + 1
                
                # If we've reached max_iterations without overflow, stop here
                # This means we've successfully increased font size by max_iterations * increment_step
                if fine_tune_iterations >= max_iterations:
                    break
        
        # Apply the best font size found
        # Always apply the best font size, even if it's the same (to ensure canvas state is correct)
        try:
            canvas_obj.setFont(best_font_name, best_font_size)
        except Exception as e:
            # (Debug logging removed)
            best_font_name = "Helvetica"
            canvas_obj.setFont(best_font_name, best_font_size)
        
        # (Logging removed - this function is no longer used for ref_text)
        
        return best_font_size, best_text_lines, best_font_name
    
    @staticmethod
    def calculate_type_font_baselines(
        layout_doc: LayoutDocument,
        translated_text_by_block_index: Dict[int, str],
        frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
    ) -> Dict[str, float]:
        """
        Calculate font size baseline for each block type using iterative optimization.
        
        Algorithm:
        1. For each block: initial font size estimation based on height and line count
        2. For each type: calculate weighted average font size (weighted by character count)
        3. For each block: recalculate line count based on new font size, then adjust font size
           by comparing calculated block height with actual layout height
        4. Repeat steps 2-3 for 3 iterations
        5. Each type is processed independently
        
        Args:
            layout_doc: LayoutDocument instance
            translated_text_by_block_index: Mapping from block index to translated text
            
        Returns:
            Dictionary mapping block type to baseline font size in points
        """
        from layout.pdf_renderer.shared.block_processor import BlockProcessor
        from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
        
        # Group blocks by type, collecting (text_length, block, height, width, text, page_idx, page_block_idx) tuples
        # page_idx and page_block_idx are needed for collision checking in global baseline search
        type_blocks: Dict[str, List[Tuple[int, LayoutBlock, float, float, str, int, int]]] = {}
        
        total_blocks_processed = 0
        for page_idx, page in enumerate(layout_doc.pages):
            for page_block_idx, block in enumerate(page.blocks):
                total_blocks_processed += 1
                if block.type == "image":
                    # Extract nested image_caption blocks for unified caption font sizing
                    if hasattr(block, "raw") and isinstance(block.raw, dict):
                        nested_blocks = block.raw.get("blocks", [])
                        for sub in nested_blocks:
                            if not isinstance(sub, dict):
                                continue
                            sub_type = str(sub.get("type", ""))
                            if sub_type in (IMAGE_CAPTION, CAPTION):
                                # Extract caption text and bbox
                                caption_text = BlockProcessor.extract_text_from_raw_layout(sub) or ""
                                if not caption_text.strip():
                                    continue
                                caption_bbox = sub.get("bbox")
                                if not isinstance(caption_bbox, list) or len(caption_bbox) != 4:
                                    continue
                                try:
                                    cap_x0, cap_y0, cap_x1, cap_y1 = tuple(float(x) for x in caption_bbox)
                                    cap_height = float(cap_y1) - float(cap_y0)
                                    cap_width = float(cap_x1) - float(cap_x0)
                                except Exception:
                                    continue
                                if cap_height <= 0 or cap_width <= 0:
                                    continue
                                # Use parent block's index for translated text lookup
                                if block.index is not None and block.index in translated_text_by_block_index:
                                    caption_translated_text = translated_text_by_block_index[block.index] or ""
                                else:
                                    caption_translated_text = caption_text
                                # Add to caption type blocks
                                if "caption" not in type_blocks:
                                    type_blocks["caption"] = []
                                # Create a pseudo-block for caption (we'll use parent block's structure)
                                # Store as (text_length, block, height, width, text, page_idx, page_block_idx)
                                # For caption, we use a special marker in block.type to identify it
                                caption_block = type('CaptionBlock', (), {
                                    'type': 'caption',
                                    'index': block.index,
                                    'bbox': (cap_x0, cap_y0, cap_x1, cap_y1),
                                    'raw': sub
                                })()
                                type_blocks["caption"].append((len(caption_text), caption_block, cap_height, cap_width, caption_translated_text, page_idx, page_block_idx))
                    continue
                
                # Use translated text if available, otherwise use original
                if block.index is not None and block.index in translated_text_by_block_index:
                    text = translated_text_by_block_index[block.index] or ""
                else:
                    text = block.text or ""
                
                if not text.strip():
                    continue
                
                try:
                    x0, y0, x1, y1 = block.bbox
                    height = float(y1) - float(y0)
                    width = float(x1) - float(x0)
                except Exception:
                    continue
                
                if height <= 0 or width <= 0:
                    continue
                
                block_type = getattr(block, "type", "unknown") or "unknown"
                text_length = len(text)
                
                # Extract nested table_caption blocks for unified caption font sizing
                if block_type == "table" and hasattr(block, "raw") and isinstance(block.raw, dict):
                    nested_blocks = block.raw.get("blocks", [])
                    for sub in nested_blocks:
                        if not isinstance(sub, dict):
                            continue
                        sub_type = str(sub.get("type", ""))
                        if sub_type == TABLE_CAPTION:
                            # Extract caption text and bbox
                            caption_text = BlockProcessor.extract_text_from_raw_layout(sub) or ""
                            if not caption_text.strip():
                                continue
                            caption_bbox = sub.get("bbox")
                            if not isinstance(caption_bbox, list) or len(caption_bbox) != 4:
                                continue
                            try:
                                cap_x0, cap_y0, cap_x1, cap_y1 = tuple(float(x) for x in caption_bbox)
                                cap_height = float(cap_y1) - float(cap_y0)
                                cap_width = float(cap_x1) - float(cap_x0)
                            except Exception:
                                continue
                            if cap_height <= 0 or cap_width <= 0:
                                continue
                            # Use parent block's index for translated text lookup
                            if block.index is not None and block.index in translated_text_by_block_index:
                                caption_translated_text = translated_text_by_block_index[block.index] or ""
                            else:
                                caption_translated_text = caption_text
                            # Add to caption type blocks
                            if "caption" not in type_blocks:
                                type_blocks["caption"] = []
                            # Create a pseudo-block for caption
                            caption_block = type('CaptionBlock', (), {
                                'type': 'caption',
                                'index': block.index,
                                'bbox': (cap_x0, cap_y0, cap_x1, cap_y1),
                                'raw': sub
                            })()
                            type_blocks["caption"].append((len(caption_text), caption_block, cap_height, cap_width, caption_translated_text, page_idx, page_block_idx))
                
                # Normalize block type using BlockClassifier
                normalized_type = BlockClassifier.normalize_block_type(block)
                
                # Check if should be included in baseline calculation
                if not BlockClassifier.should_include_in_baseline_calculation(
                    block, frontend_style_overrides
                ):
                    continue
                
                if normalized_type not in type_blocks:
                    type_blocks[normalized_type] = []
                
                type_blocks[normalized_type].append((text_length, block, height, width, text, page_idx, page_block_idx))
        
        # Build page block bbox index for collision checking (needed for ref_text global baseline search)
        page_block_bboxes = LayoutCalculator.build_page_block_bbox_index(layout_doc)
        
        # Calculate baseline for each type using iterative optimization
        type_baselines: Dict[str, float] = {}
        
        for type_idx, (block_type, blocks_data) in enumerate(type_blocks.items()):
            if not blocks_data:
                continue
            
            # Initialize font sizes for all blocks (first iteration)
            block_font_sizes: List[float] = []
            # Store (block, height, width, text, text_length, page_idx, page_block_idx) for collision checking
            block_data_list: List[Tuple[LayoutBlock, float, float, str, int, int, int]] = []
            
            for idx, (text_length, block, height, width, text, page_idx, page_block_idx) in enumerate(blocks_data):
                # Initial font size estimation
                initial_font_size = FontSizeCalculator.estimate_initial_font_size(
                    height,
                    text=text,
                    block_width=width,
                    block_raw=block.raw if hasattr(block, 'raw') else None
                )
                block_font_sizes.append(initial_font_size)
                
                # Estimate initial line count
                initial_line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                    text,
                    initial_font_size,
                    width,
                    block_raw=block.raw if hasattr(block, 'raw') else None
                )
                
                # Get actual line count from layout if available
                actual_lines_from_layout = None
                if hasattr(block, 'raw') and block.raw:
                    lines = block.raw.get("lines", [])
                    if lines:
                        actual_lines_from_layout = len(lines)
                
                block_data_list.append((block, height, width, text, text_length, page_idx, page_block_idx))
            
            # Calculate initial baseline
            if block_data_list:
                initial_baseline = sum(block_font_sizes[i] * text_length for i, (_, _, _, _, text_length, _, _) in enumerate(block_data_list)) / sum(text_length for _, _, _, _, text_length, _, _ in block_data_list)
            
            # Use new unified font size calculation method for all unified font size types
            # This includes: ref_text, text, title, caption, header, footer, table_notes, table_body
            strategy = BlockClassifier.get_font_size_strategy(block_type)
            quantize_step = BlockClassifier.get_quantize_step(block_type)
            
            if strategy in ("unified_05pt", "unified_10pt"):
                # Use new unified calculation method (reuses existing 15-iteration algorithm)
                unified_baseline = FontSizeCalculator.calculate_unified_font_size_for_type(
                    layout_doc=layout_doc,
                    block_type=block_type,
                    translated_text_by_block_index=translated_text_by_block_index,
                    frontend_style_overrides=frontend_style_overrides,
                    quantize_step=quantize_step,
                    max_iterations=15,
                )
                type_baselines[block_type] = unified_baseline
                continue
            
            # For backward compatibility: keep old algorithm for non-unified types
            # Special global baseline optimization for ref_text, text, and caption:
            # - Use a fixed 15-step search on a single baseline for the whole type
            # - Try to find the maximum baseline that does not overflow any block
            # - Step starts larger and is halved whenever overall state flips between overflow / non-overflow
            # - caption includes both image_caption and table_caption (unified for consistent font sizing)
            if block_type in ("ref_text", "text", "caption"):
                max_iterations = 15
                overflow_tolerance = 1.02
                step = 1.0  # initial step in points
                
                # Start from initial baseline estimated from all blocks
                type_baseline = initial_baseline
                best_baseline = type_baseline
                best_safe_found = False
                direction = 1.0  # 1: try larger first, -1: try smaller
                last_safe_state = None  # True = safe, False = overflow, None = unknown
                
                test_baseline = type_baseline
                
                for iteration in range(max_iterations):
                    # Evaluate whether this baseline overflows any block or collides with other blocks
                    # Use the same calculation as in rendering: account for font metrics space
                    # Tolerance: 5% of line height per line (not 5% of bbox height)
                    # Also check for collisions with other blocks on the same page
                    overflow_any = False
                    for block, layout_height, width, text, text_length, page_idx, page_block_idx in block_data_list:
                        if layout_height <= 0 or width <= 0 or not text:
                            continue
                        # Skip blocks with invalid test_baseline (should not happen after clamp, but safety check)
                        if test_baseline < 6.0:
                            overflow_any = True  # Treat as overflow to force search upward
                            break
                        
                        line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                            text,
                            test_baseline,
                            width,
                            block_raw=block.raw if hasattr(block, "raw") else None,
                        )
                        # Calculate total rendered height (same as in rendering loop)
                        estimated_line_height = test_baseline * 1.2  # Standard line height
                        calculated_total_height = line_count * estimated_line_height
                        # Account for font metrics space (same as in rendering)
                        estimated_font_ascent = test_baseline * 0.75
                        font_metrics_space = estimated_font_ascent + test_baseline * 0.25
                        available_height = layout_height - font_metrics_space
                        # Tolerance: 5% of line height per line (for multi-line, this allows more tolerance)
                        tolerance_per_line = estimated_line_height * 0.05
                        max_allowed_height = available_height + line_count * tolerance_per_line
                        # Check overflow with line-based tolerance
                        if calculated_total_height > max_allowed_height:
                            overflow_any = True
                            break
                        
                        # Check collision with other blocks on the same page (excluding self)
                        # Always check collision, even if text fits in its own bbox
                        # If any block collides with others, mark as unsafe to trigger font size reduction
                        try:
                            x0, y0, x1, y1 = block.bbox
                            page_blocks_info = page_block_bboxes[page_idx] if page_idx < len(page_block_bboxes) else None
                            if page_blocks_info:
                                # Calculate actual rendered region: from y0 downward by calculated_total_height
                                # This is the region that would be occupied if we render with test_baseline
                                has_collision = LayoutCalculator.check_block_collision_with_page(
                                    page_blocks_info,
                                    page_idx,
                                    page_block_idx,
                                    float(x0),
                                    float(y0),
                                    float(x1),
                                    calculated_total_height,
                                    block.type or block_type,
                                )
                                if has_collision:
                                    overflow_any = True
                                    break
                        except Exception:
                            # If collision check fails, skip it (don't fail the whole search)
                            pass
                    
                    safe = not overflow_any
                    
                    unified_logger.info(
                        LogModule.RESTOR,
                        "[REPORTLAB] Type '{block_type}' iteration {iteration}/{max_iterations}: "
                        "test_baseline={test_baseline:.2f}pt, safe={safe}",
                        block_type=block_type,
                        iteration=iteration + 1,
                        max_iterations=max_iterations,
                        test_baseline=test_baseline,
                        safe=safe,
                    )
                    
                    if iteration == 0:
                        # First evaluation decides initial direction
                        if safe:
                            best_safe_found = True
                            best_baseline = test_baseline
                            type_baseline = test_baseline
                            last_safe_state = True
                            # If initial baseline is safe, try to increase it
                            direction = 1.0
                        else:
                            # Initial baseline already overflows: search downward
                            last_safe_state = False
                            direction = -1.0
                            # Ensure we don't go below minimum
                            if type_baseline <= 6.0:
                                # Already at minimum, can't search downward
                                break
                    else:
                        if safe:
                            best_safe_found = True
                            # Update best_baseline only if current test_baseline is larger (better)
                            if test_baseline > best_baseline:
                                best_baseline = test_baseline
                            type_baseline = test_baseline
                        elif not safe:
                            # When overflow occurs:
                            # - If searching upward (direction > 0), don't update type_baseline (keep last safe value)
                            # - If searching downward (direction < 0), update type_baseline to continue downward search
                            if direction < 0:
                                type_baseline = test_baseline
                                # Ensure we don't go below minimum
                                if type_baseline < 6.0:
                                    type_baseline = 6.0
                                    # Can't search further downward, use best safe baseline
                                    if best_safe_found:
                                        type_baseline = best_baseline
                                        break
                            # else: keep type_baseline as the last safe value (don't update)
                        
                        # If overall state flips between overflow and non-overflow, reduce step and reverse direction
                        if last_safe_state is not None and safe != last_safe_state:
                            step *= 0.5
                            direction = -direction
                            # When flipping from safe to overflow (searching upward), ensure we use the last safe baseline
                            if last_safe_state and not safe and direction < 0:
                                # We just flipped from safe to overflow while searching upward
                                # type_baseline should already be the last safe value, but ensure it's set correctly
                                if best_safe_found:
                                    type_baseline = best_baseline
                        
                        last_safe_state = safe
                        
                        # Early exit if step becomes too small (converged)
                        if step < 0.01:
                            break
                    
                    # Prepare next test baseline
                    test_baseline = type_baseline + direction * step
                    # Clamp test_baseline to reasonable range to avoid negative or invalid values
                    # Minimum 6pt, maximum 24pt (will be clamped again at the end)
                    test_baseline = max(6.0, min(24.0, test_baseline))
                    
                    # If test_baseline was clamped and we're searching downward, we've hit the minimum
                    # Use the best safe baseline found so far and stop searching
                    if test_baseline == 6.0 and direction < 0 and type_baseline < 6.0:
                        if best_safe_found:
                            type_baseline = best_baseline
                            break
                        else:
                            # No safe baseline found, use minimum
                            type_baseline = 6.0
                            break
                
                # Use the best safe baseline found (if any), otherwise fall back to the last tested baseline
                # Ensure we never use a negative or invalid baseline
                candidate_baseline = best_baseline if best_safe_found else type_baseline
                candidate_baseline = max(6.0, min(24.0, candidate_baseline))  # Clamp before rounding
                final_baseline_before_clamp = candidate_baseline
                final_baseline = round(candidate_baseline, 1)
                final_baseline = max(6, min(24, final_baseline))
                
                type_baselines[block_type] = final_baseline
                
                unified_logger.info(
                    LogModule.RESTOR,
                    "[REPORTLAB] ===== Type '{block_type}' FINAL RESULTS (global baseline search) =====",
                    block_type=block_type,
                )
                unified_logger.info(
                    LogModule.RESTOR,
                    "[REPORTLAB] Type '{block_type}' font baseline: {final_baseline_before_clamp:.2f}pt -> {final_baseline}pt (after clamp) "
                    "(from {block_count} blocks, after {max_iterations} iterations)",
                    block_type=block_type,
                    final_baseline_before_clamp=final_baseline_before_clamp,
                    final_baseline=final_baseline,
                    block_count=len(block_data_list),
                    max_iterations=max_iterations,
                )
                continue
            
            # Default path: iterative optimization (3 iterations) for other types
            for iteration in range(3):
                # Step 1: Calculate weighted average font size for this type
                total_weight = 0
                weighted_sum = 0
                for i, (block, height, width, text, text_length, page_idx, page_block_idx) in enumerate(block_data_list):
                    weight = text_length
                    weighted_sum += block_font_sizes[i] * weight
                    total_weight += weight
                
                if total_weight > 0:
                    type_baseline = weighted_sum / total_weight
                else:
                    type_baseline = 12.0  # Default
                
                # Step 2: For each block, recalculate line count and adjust font size
                adjustment_count = 0
                for i, (block, layout_height, width, text, text_length, page_idx, page_block_idx) in enumerate(block_data_list):
                    # Use current block font size (not type baseline) for calculation
                    current_font_size = block_font_sizes[i]
                    
                    # Recalculate line count based on current block font size
                    line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                        text,
                        current_font_size,
                        width,
                        block_raw=block.raw if hasattr(block, 'raw') else None
                    )
                    
                    # Calculate block height with current font size
                    calculated_height = FontSizeCalculator.calculate_block_height_from_font_size(current_font_size, line_count)
                    
                    # Adjust font size based on ratio of layout height to calculated height
                    if calculated_height > 0 and layout_height > 0:
                        height_ratio = layout_height / calculated_height
                        
                        # Adjust font size based on height ratio
                        # If calculated_height > layout_height (ratio < 1), we need to reduce font size
                        # If calculated_height < layout_height (ratio > 1), we can increase font size
                        if calculated_height > layout_height:
                            # Overflow: calculated height exceeds layout height, reduce font size
                            # Use the ratio directly to scale down, but ensure we don't go too small
                            adjusted_font_size = current_font_size * height_ratio * 0.95  # 5% safety margin
                            adjustment_reason = f"overflow (calculated={calculated_height:.1f} > layout={layout_height:.1f}, ratio={height_ratio:.3f})"
                        elif calculated_height < layout_height * 0.9:
                            # Underflow: calculated height is much smaller than layout, can increase
                            # But limit increase to 10% per iteration
                            adjusted_font_size = current_font_size * min(height_ratio, 1.10)
                            adjustment_reason = f"underflow (calculated={calculated_height:.1f} < layout={layout_height:.1f}*0.9, ratio={height_ratio:.3f})"
                        else:
                            # Close match: within 10% of layout height, keep current size
                            adjusted_font_size = current_font_size
                            adjustment_reason = f"close match (calculated={calculated_height:.1f} ≈ layout={layout_height:.1f}, ratio={height_ratio:.3f})"
                        
                        # Verify: recalculate with adjusted size and iterate until it fits
                        # This ensures we don't overflow the block
                        max_verify_iterations = 3
                        for verify_iter in range(max_verify_iterations):
                            adjusted_line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                                text,
                                adjusted_font_size,
                                width,
                                block_raw=block.raw if hasattr(block, 'raw') else None
                            )
                            adjusted_calculated_height = FontSizeCalculator.calculate_block_height_from_font_size(
                                adjusted_font_size, 
                                adjusted_line_count
                            )
                            
                            # If adjusted height still exceeds layout height, reduce font size more aggressively
                            if adjusted_calculated_height > layout_height:
                                # Still too large, reduce more aggressively
                                scale_factor = layout_height / adjusted_calculated_height
                                old_adjusted = adjusted_font_size
                                adjusted_font_size = adjusted_font_size * scale_factor * 0.92  # 8% safety margin
                                if verify_iter == 0:
                                    adjustment_reason += f", verify: overflow (reduced {old_adjusted:.2f}->{adjusted_font_size:.2f})"
                                else:
                                    adjustment_reason += f", verify_iter{verify_iter}: still overflow (reduced {old_adjusted:.2f}->{adjusted_font_size:.2f})"
                            else:
                                # Fits within layout height, break
                                if verify_iter > 0:
                                    adjustment_reason += f", verify_iter{verify_iter}: fits (height={adjusted_calculated_height:.1f} <= layout={layout_height:.1f})"
                                break
                        
                        # Final check: if still overflowing after verification, use more aggressive reduction
                        final_line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                            text,
                            adjusted_font_size,
                            width,
                            block_raw=block.raw if hasattr(block, 'raw') else None
                        )
                        final_calculated_height = FontSizeCalculator.calculate_block_height_from_font_size(
                            adjusted_font_size, 
                            final_line_count
                        )
                        if final_calculated_height > layout_height:
                            # Final aggressive reduction to ensure it fits
                            final_scale = layout_height / final_calculated_height
                            adjusted_font_size = adjusted_font_size * final_scale * 0.90  # 10% safety margin
                            adjustment_reason += f", final_reduction (to {adjusted_font_size:.2f}pt to fit {layout_height:.1f}pt)"
                        
                        if abs(adjusted_font_size - current_font_size) > 0.01:
                            adjustment_count += 1
                    else:
                        adjusted_font_size = current_font_size
                    
                    # Clamp to reasonable range, but raise minimum from 6 to 7 for better readability
                    adjusted_font_size = max(7, min(24, adjusted_font_size))
                    block_font_sizes[i] = adjusted_font_size
                
                # Step 3: Recalculate type baseline from adjusted font sizes
                total_weight = 0
                weighted_sum = 0
                for i, (block, height, width, text, text_length, page_idx, page_block_idx) in enumerate(block_data_list):
                    weight = text_length
                    weighted_sum += block_font_sizes[i] * weight
                    total_weight += weight
                
                if total_weight > 0:
                    new_type_baseline = weighted_sum / total_weight
                else:
                    new_type_baseline = 12.0
                
                type_baseline = new_type_baseline
            
            # Final clamp and round
            type_baseline_before_clamp = type_baseline
            type_baseline = round(type_baseline, 1)
            type_baseline = max(6, min(24, type_baseline))
            
            type_baselines[block_type] = type_baseline
            
            # Final statistics (only for non-ref_text and non-text types, they already logged)
            if block_data_list and block_type not in ("ref_text", "text", "caption"):
                pass  # Skip detailed logging for types that already logged
        
        # If no baselines calculated, return default
        if not type_baselines:
            unified_logger.warning(
                LogModule.RESTOR,
                "[REPORTLAB] No type baselines calculated, using default 12pt"
            )
            return {"unknown": 12.0}
        
        return type_baselines
    
    @staticmethod
    def calculate_font_size_for_bbox(
        text: str,
        bbox_width: float,
        bbox_height: float,
        baseline_font_size: Optional[float] = None,
        min_font_size: float = 6.0,
        max_font_size: float = 12.0,
        line_height_ratio: float = 1.15,
        wrap_text_func: Optional[Callable[[str, float, str, float, Optional[object]], List[str]]] = None,
        set_font_func: Optional[Callable[[str, float], None]] = None,
        initial_font_name: str = "Helvetica",
    ) -> Tuple[float, List[str], str]:
        """
        Calculate optimal font size for text to fit within a bounding box using binary search.
        
        This method finds the largest font size that allows all text to fit within the given
        bbox dimensions, using binary search for efficiency.
        
        Args:
            text: Text content to render
            bbox_width: Width of bounding box in points
            bbox_height: Height of bounding box in points
            baseline_font_size: Optional baseline font size to start from (e.g., from type baselines)
            min_font_size: Minimum font size in points (default: 6.0)
            max_font_size: Maximum font size in points (default: 12.0)
            line_height_ratio: Ratio of line height to font size (default: 1.15)
            wrap_text_func: Function to wrap text: (text, width, font_name, font_size, canvas_obj) -> List[str]
            set_font_func: Function to set font: (font_name, font_size) -> None
            initial_font_name: Initial font name to try (default: "Helvetica")
            
        Returns:
            Tuple of (optimal_font_size, wrapped_lines, final_font_name)
        """
        if not text or not text.strip():
            return min_font_size, [], initial_font_name
        
        if bbox_width <= 0 or bbox_height <= 0:
            return min_font_size, [], initial_font_name
        
        # Use wrap_text_func from TextUtils if not provided
        if wrap_text_func is None:
            from layout.pdf_renderer.shared.text_utils import TextUtils
            wrap_text_func = TextUtils.wrap_text_to_width
        
        font_name = initial_font_name
        best_font_size = min_font_size
        best_lines: List[str] = []
        
        # Determine search range
        if baseline_font_size is not None:
            # Start from baseline, but ensure it fits
            max_font_size = min(baseline_font_size, bbox_height * 0.9, max_font_size)
            # First check if baseline fits
            try:
                if set_font_func:
                    set_font_func(font_name, baseline_font_size)
                lines = wrap_text_func(text, bbox_width, font_name, baseline_font_size, None)
                if lines:
                    line_height = baseline_font_size * line_height_ratio
                    max_lines = int(bbox_height / line_height) if line_height > 0 else len(lines)
                    if max_lines <= 0:
                        max_lines = 1
                    if len(lines) <= max_lines:
                        # Baseline fits, use it
                        return baseline_font_size, lines, font_name
            except Exception:
                font_name = "Helvetica"
                if set_font_func:
                    set_font_func(font_name, baseline_font_size)
                try:
                    lines = wrap_text_func(text, bbox_width, font_name, baseline_font_size, None)
                    if lines:
                        line_height = baseline_font_size * line_height_ratio
                        max_lines = int(bbox_height / line_height) if line_height > 0 else len(lines)
                        if max_lines <= 0:
                            max_lines = 1
                        if len(lines) <= max_lines:
                            return baseline_font_size, lines, font_name
                except Exception:
                    pass
        else:
            # No baseline, estimate initial font size
            estimated_chars_per_line = int(bbox_width / (bbox_height * 0.1)) if bbox_height > 0 else 50
            estimated_lines = max(1, (len(text) + estimated_chars_per_line - 1) // estimated_chars_per_line)
            estimated_font_size = bbox_height / estimated_lines / line_height_ratio * 0.95
            max_font_size = min(bbox_height * 0.9, max_font_size, estimated_font_size * 1.2)
        
        # Binary search for optimal font size
        low = min_font_size
        high = max_font_size
        max_iterations = 15
        iteration = 0
        
        while iteration < max_iterations and (high - low) > 0.1:
            font_size = (low + high) / 2.0
            
            try:
                if set_font_func:
                    set_font_func(font_name, font_size)
            except Exception:
                font_name = "Helvetica"
                if set_font_func:
                    set_font_func(font_name, font_size)
            
            lines = wrap_text_func(text, bbox_width, font_name, font_size, None)
            if not lines:
                high = font_size
                iteration += 1
                continue
            
            # Check if lines fit in height
            line_height = font_size * line_height_ratio
            max_lines = int(bbox_height / line_height) if line_height > 0 else len(lines)
            if max_lines <= 0:
                max_lines = 1
            
            if len(lines) <= max_lines:
                # Text fits, try larger font size
                best_font_size = font_size
                best_lines = lines
                low = font_size
            else:
                # Text doesn't fit, try smaller font size
                high = font_size
            
            iteration += 1
        
        # Final safety check: if still doesn't fit, reduce font size
        if best_lines:
            line_height = best_font_size * line_height_ratio
            max_lines = int(bbox_height / line_height) if line_height > 0 else len(best_lines)
            if max_lines <= 0:
                max_lines = 1
            
            if len(best_lines) > max_lines:
                # Calculate exact font size needed
                exact_font_size = bbox_height / len(best_lines) / line_height_ratio * 0.98
                best_font_size = max(min_font_size, exact_font_size)
                
                try:
                    if set_font_func:
                        set_font_func(font_name, best_font_size)
                except Exception:
                    font_name = "Helvetica"
                    if set_font_func:
                        set_font_func(font_name, best_font_size)
                
                # Re-wrap with adjusted font size
                best_lines = wrap_text_func(text, bbox_width, font_name, best_font_size, None)
                if not best_lines:
                    best_lines = [text.strip()] if text.strip() else []
                
                # Final truncation check
                line_height = best_font_size * line_height_ratio
                max_lines = int(bbox_height / line_height) if line_height > 0 else len(best_lines)
                if max_lines <= 0:
                    max_lines = 1
                if len(best_lines) > max_lines:
                    best_lines = best_lines[:max_lines]
        
        return best_font_size, best_lines, font_name
    
    @staticmethod
    def calculate_adjustable_font_size_for_block(
        block: LayoutBlock,
        text: str,
        unified_baseline: float,
        canvas_obj=None,
        font_name: str = "Helvetica",
        adjust_step: float = 1.0,
    ) -> float:
        """
        Calculate adjustable font size for a block (applies to text and title types).
        
        Algorithm:
        1. Start from unified baseline
        2. Calculate optimal font size for this specific block using binary search
        3. If optimal > baseline, try to adjust upward by adjust_step (1.0pt)
        4. If upward adjustment would overflow, keep baseline
        5. Quantize to adjust_step
        
        Args:
            block: LayoutBlock instance
            text: Text content
            unified_baseline: Unified baseline font size for this type
            canvas_obj: Optional canvas object for text width measurement
            font_name: Font name for text width calculation
            adjust_step: Adjustment step in points (default: 1.0pt)
            
        Returns:
            Adjusted font size in points (quantized to adjust_step)
        """
        from layout.pdf_renderer.shared.text_utils import TextUtils
        from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
        
        try:
            x0, y0, x1, y1 = block.bbox
            bbox_width = float(x1) - float(x0)
            bbox_height = float(y1) - float(y0)
        except Exception:
            return unified_baseline
        
        if bbox_width <= 0 or bbox_height <= 0:
            return unified_baseline
        
        # Calculate optimal font size for this block using binary search
        # Use calculate_font_size_for_bbox which already implements binary search
        optimal_font_size, _, _ = FontSizeCalculator.calculate_font_size_for_bbox(
            text=text,
            bbox_width=bbox_width,
            bbox_height=bbox_height,
            baseline_font_size=unified_baseline,
            min_font_size=6.0,
            max_font_size=24.0,
            line_height_ratio=1.2,
            wrap_text_func=TextUtils.wrap_text_to_width,
            set_font_func=None,  # Not needed for calculation
            initial_font_name=font_name,
        )
        
        # If optimal font size is greater than baseline, try to adjust upward
        if optimal_font_size > unified_baseline:
            adjusted_size = unified_baseline + adjust_step
            
            # Check if adjusted size would overflow
            # Estimate line count and total height
            line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                text,
                adjusted_size,
                bbox_width,
                block_raw=block.raw if hasattr(block, 'raw') else None,
            )
            
            # Calculate total rendered height
            estimated_line_height = adjusted_size * 1.2
            calculated_total_height = line_count * estimated_line_height
            
            # Account for font metrics space
            estimated_font_ascent = adjusted_size * 0.75
            font_metrics_space = estimated_font_ascent + adjusted_size * 0.25
            available_height = bbox_height - font_metrics_space
            
            # Tolerance: 5% of line height per line
            tolerance_per_line = estimated_line_height * 0.05
            max_allowed_height = available_height + line_count * tolerance_per_line
            
            # Check if adjusted size fits
            if calculated_total_height <= max_allowed_height:
                # Can adjust upward
                final_size = adjusted_size
            else:
                # Would overflow, keep baseline
                final_size = unified_baseline
        else:
            # Optimal size is less than or equal to baseline, use baseline
            final_size = unified_baseline
        
        # Quantize to adjust_step (1.0pt for text/title)
        final_size = FontSizeCalculator.quantize_font_size_with_step(
            final_size,
            step=adjust_step
        )
        
        return final_size
    
    @staticmethod
    def calculate_unified_font_size_for_type(
        layout_doc: LayoutDocument,
        block_type: str,
        translated_text_by_block_index: Dict[int, str],
        frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
        quantize_step: float = 0.5,
        max_iterations: int = 15,
    ) -> float:
        """
        Calculate unified font size for a block type using iterative optimization.
        
        This method extracts the core algorithm from calculate_type_font_baselines()
        and makes it reusable with configurable step size and frontend override support.
        
        Algorithm:
        1. Collect all blocks of the specified type (excluding frontend overrides)
        2. Estimate initial font size for each block
        3. Calculate weighted average baseline
        4. Use 15-iteration global baseline search to find maximum safe baseline
        5. Quantize to specified step size
        
        Args:
            layout_doc: LayoutDocument instance
            block_type: Block type (e.g., "text", "title", "ref_text", "caption")
            translated_text_by_block_index: Mapping from block index to translated text
            frontend_style_overrides: Optional frontend style overrides (blocks with overrides are excluded)
            quantize_step: Quantization step in points (0.5pt or 1.0pt)
            max_iterations: Maximum iterations for baseline search (default: 15)
            
        Returns:
            Unified font size in points (quantized to step size)
        """
        from layout.pdf_renderer.shared.block_processor import BlockProcessor
        from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
        
        # Collect blocks of this type
        blocks_data: List[Tuple[int, LayoutBlock, float, float, str, int, int]] = []
        
        for page_idx, page in enumerate(layout_doc.pages):
            for page_block_idx, block in enumerate(page.blocks):
                # Normalize block type
                normalized_type = BlockClassifier.normalize_block_type(block)
                
                # Skip if not the target type
                if normalized_type != block_type:
                    continue
                
                # Check if should be included in baseline calculation
                if not BlockClassifier.should_include_in_baseline_calculation(
                    block, frontend_style_overrides
                ):
                    continue
                
                # Get text
                if block.index is not None and block.index in translated_text_by_block_index:
                    text = translated_text_by_block_index[block.index] or ""
                else:
                    text = block.text or ""
                
                if not text.strip():
                    continue
                
                # Get bbox
                try:
                    x0, y0, x1, y1 = block.bbox
                    height = float(y1) - float(y0)
                    width = float(x1) - float(x0)
                except Exception:
                    continue
                
                if height <= 0 or width <= 0:
                    continue
                
                text_length = len(text)
                blocks_data.append((text_length, block, height, width, text, page_idx, page_block_idx))
        
        # If no blocks found, return default
        if not blocks_data:
            return 12.0  # Default font size
        
        # Build page block bbox index for collision checking
        page_block_bboxes = LayoutCalculator.build_page_block_bbox_index(layout_doc)
        
        # Initialize font sizes for all blocks
        block_font_sizes: List[float] = []
        block_data_list: List[Tuple[LayoutBlock, float, float, str, int, int, int]] = []
        
        for text_length, block, height, width, text, page_idx, page_block_idx in blocks_data:
            # Initial font size estimation
            initial_font_size = FontSizeCalculator.estimate_initial_font_size(
                height,
                text=text,
                block_width=width,
                block_raw=block.raw if hasattr(block, 'raw') else None
            )
            block_font_sizes.append(initial_font_size)
            block_data_list.append((block, height, width, text, text_length, page_idx, page_block_idx))
        
        # Calculate initial baseline (weighted average)
        if block_data_list:
            initial_baseline = sum(
                block_font_sizes[i] * text_length 
                for i, (_, _, _, _, text_length, _, _) in enumerate(block_data_list)
            ) / sum(text_length for _, _, _, _, text_length, _, _ in block_data_list)
        else:
            initial_baseline = 12.0
        
        # Global baseline optimization using 15-iteration search
        step = 1.0  # initial step in points
        type_baseline = initial_baseline
        best_baseline = type_baseline
        best_safe_found = False
        direction = 1.0  # 1: try larger first, -1: try smaller
        last_safe_state = None  # True = safe, False = overflow, None = unknown
        
        test_baseline = type_baseline
        
        for iteration in range(max_iterations):
            # Evaluate whether this baseline overflows any block or collides with other blocks
            overflow_any = False
            for block, layout_height, width, text, text_length, page_idx, page_block_idx in block_data_list:
                if layout_height <= 0 or width <= 0 or not text:
                    continue
                
                # Skip blocks with invalid test_baseline
                if test_baseline < 6.0:
                    overflow_any = True
                    break
                
                # Estimate line count
                line_count = FontSizeCalculator.estimate_line_count_from_font_size(
                    text,
                    test_baseline,
                    width,
                    block_raw=block.raw if hasattr(block, "raw") else None,
                )
                
                # Calculate total rendered height
                estimated_line_height = test_baseline * 1.2
                calculated_total_height = line_count * estimated_line_height
                
                # Account for font metrics space
                estimated_font_ascent = test_baseline * 0.75
                font_metrics_space = estimated_font_ascent + test_baseline * 0.25
                available_height = layout_height - font_metrics_space
                
                # Tolerance: 5% of line height per line (for multi-line, this allows more tolerance)
                tolerance_per_line = estimated_line_height * 0.05
                max_allowed_height = available_height + line_count * tolerance_per_line
                
                # Check overflow with line-based tolerance
                if calculated_total_height > max_allowed_height:
                    overflow_any = True
                    break
                
                # Check collision with other blocks on the same page
                try:
                    x0, y0, x1, y1 = block.bbox
                    page_blocks_info = page_block_bboxes[page_idx] if page_idx < len(page_block_bboxes) else None
                    if page_blocks_info:
                        has_collision = LayoutCalculator.check_block_collision_with_page(
                            page_blocks_info,
                            page_idx,
                            page_block_idx,
                            float(x0),
                            float(y0),
                            float(x1),
                            calculated_total_height,
                            block.type or block_type,
                        )
                        if has_collision:
                            overflow_any = True
                            break
                except Exception:
                    pass
            
            safe = not overflow_any
            
            if iteration == 0:
                # First evaluation decides initial direction
                if safe:
                    best_safe_found = True
                    best_baseline = test_baseline
                    type_baseline = test_baseline
                    last_safe_state = True
                    direction = 1.0
                else:
                    last_safe_state = False
                    direction = -1.0
                    if type_baseline <= 6.0:
                        break
            else:
                if safe:
                    best_safe_found = True
                    if test_baseline > best_baseline:
                        best_baseline = test_baseline
                    type_baseline = test_baseline
                elif not safe:
                    if direction < 0:
                        type_baseline = test_baseline
                        if type_baseline < 6.0:
                            type_baseline = 6.0
                            if best_safe_found:
                                type_baseline = best_baseline
                                break
                
                # If overall state flips, reduce step and reverse direction
                if last_safe_state is not None and safe != last_safe_state:
                    step *= 0.5
                    direction = -direction
                    if last_safe_state and not safe and direction < 0:
                        if best_safe_found:
                            type_baseline = best_baseline
                
                last_safe_state = safe
                
                # Early exit if step becomes too small
                if step < 0.01:
                    break
            
            # Prepare next test baseline
            test_baseline = type_baseline + direction * step
            test_baseline = max(6.0, min(24.0, test_baseline))
            
            # If test_baseline was clamped and we're searching downward, we've hit the minimum
            if test_baseline == 6.0 and direction < 0 and type_baseline < 6.0:
                if best_safe_found:
                    type_baseline = best_baseline
                    break
                else:
                    type_baseline = 6.0
                    break
        
        # Use the best safe baseline found
        candidate_baseline = best_baseline if best_safe_found else type_baseline
        candidate_baseline = max(6.0, min(24.0, candidate_baseline))
        
        # Quantize to specified step size
        final_baseline = FontSizeCalculator.quantize_font_size_with_step(
            candidate_baseline,
            step=quantize_step
        )
        
        return final_baseline

