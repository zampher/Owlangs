# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

"""
ReportLab-based PDF renderer for layout-based document rendering.

This module provides a direct PDF generation approach using ReportLab,
avoiding HTML-to-PDF conversion issues and providing high-fidelity
positioning and text rendering.

Advantages over HTML → PDF:
- Direct coordinate control (no CSS pixel → PDF point conversion errors)
- Precise text wrapping and font metrics
- Consistent rendering across platforms
- No browser rendering engine dependencies

Architecture Overview:
=====================

This module has been refactored to use a shared component architecture:

1. **Shared Components** (in `layout/pdf_renderer/shared/`):
   - `LayoutCalculator`: Layout calculations (available height, collision detection)
   - `TextUtils`: Text processing (wrapping, language detection, alignment)
   - `FontUtils`: Font management (registration, fallback, language-based selection)
   - `FontSizeCalculator`: Font size estimation and baseline calculation
   - `BlockProcessor`: Block data extraction from raw layout
   - `TableUtils`: Table parsing and column width calculation

2. **ReportLab-Specific Rendering** (this file):
   - `render_layout_pdf_reportlab()`: Main entry point for ReportLab PDF generation
   - `_render_table_block()`: Table rendering with caption, body, and footnotes
   - `_render_text_in_bbox_simple()`: Simple text rendering for captions
   - ReportLab canvas operations and coordinate transformations

3. **Wrapper Functions**:
   - Most utility functions in this file are now thin wrappers that delegate
     to the shared components, maintaining backward compatibility while
     enabling code reuse across different PDF rendering backends.

4. **Migration Status**:
   - Text processing, font utilities, layout calculations, and table parsing
     have been migrated to shared components.
   - ReportLab-specific rendering logic (canvas operations, coordinate transforms)
     remains in this file as it's backend-specific.

Future improvements:
- Further extract common rendering patterns into shared components
- Consider moving table rendering logic to a shared renderer if other backends
  need similar functionality
"""

import io
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from logger.logger import unified_logger, LogModule

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch, mm
    # Note: 'pt' (point) is the default unit in ReportLab, no need to import it
    # 1 point = 1/72 inch, and ReportLab uses points as default unit
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import black, white
    from reportlab.platypus import Table as RLTable, TableStyle as RLTableStyle
    REPORTLAB_AVAILABLE = True
    _reportlab_import_error = None
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    _reportlab_import_error = str(e)
    unified_logger.warning(
        LogModule.RESTOR,
        "ReportLab not available. Import error: {error}. Install with: pip install reportlab",
        error=e,
    )

from layout.base import LayoutDocument, LayoutBlock
from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
from layout.pdf_renderer.shared.text_utils import TextUtils
from utils.font_utils import FontUtils
from layout.pdf_renderer.shared.font_calculator import FontSizeCalculator
from layout.block_types import IMAGE_CAPTION, TABLE_CAPTION, TABLE_BODY, CAPTION, LEGACY_FIGURE
from layout.pdf_renderer.shared.block_processor import BlockProcessor
from layout.pdf_renderer.shared.table_utils import TableUtils

class _UnifiedLoggerAdapter:
    """
    Small adapter so existing `logger.debug/info/warning/error` calls
    are routed through the application's `unified_logger`.
    
    This avoids having to touch all call sites in this file while still
    ensuring consistent logging format/handlers.
    """

    def _fmt(self, msg, args, kwargs):
        # Best‑effort formatting compatible with both %-style and str.format
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        if kwargs:
            try:
                msg = msg.format(**kwargs)
            except Exception:
                pass
        return msg

    def debug(self, msg, *args, **kwargs):
        unified_logger.debug(
            LogModule.RESTOR,
            self._fmt(msg, args, kwargs),
        )

    def info(self, msg, *args, **kwargs):
        unified_logger.info(
            LogModule.RESTOR,
            self._fmt(msg, args, kwargs),
        )

    def warning(self, msg, *args, **kwargs):
        unified_logger.warning(
            LogModule.RESTOR,
            self._fmt(msg, args, kwargs),
        )

    def error(self, msg, *args, **kwargs):
        unified_logger.error(
            LogModule.RESTOR,
            self._fmt(msg, args, kwargs),
        )


# For backwards compatibility inside this module, keep a `logger` name,
# but route all its calls through the unified logger.
logger = _UnifiedLoggerAdapter()


# ============================================================================
# ReportLab-specific utility functions (to reduce code duplication)
# ============================================================================

def _layout_to_pdf_y(page_height: float, layout_y: float) -> float:
    """
    Convert layout Y coordinate to PDF Y coordinate.
    
    Layout coordinates: origin at top-left, Y increases downward
    PDF coordinates: origin at bottom-left, Y increases upward
    
    Args:
        page_height: Total page height in points
        layout_y: Y coordinate in layout system (from top)
        
    Returns:
        Y coordinate in PDF system (from bottom)
    """
    return page_height - layout_y


def _set_font_safe(c: canvas.Canvas, font_name: str, font_size: float, fallback: str = "Helvetica") -> str:
    """
    Set font on canvas with automatic fallback to Helvetica if font fails.
    
    Args:
        c: ReportLab canvas object
        font_name: Font name to try
        font_size: Font size in points
        fallback: Fallback font name (default: "Helvetica")
        
    Returns:
        Font name that was successfully set (may be fallback)
    """
    try:
        c.setFont(font_name, font_size)
        return font_name
    except Exception:
        try:
            c.setFont(fallback, font_size)
            return fallback
        except Exception:
            # Last resort: try Helvetica again
            c.setFont("Helvetica", font_size)
            return "Helvetica"


def _calculate_image_scale_and_position(
    img_width: float,
    img_height: float,
    bbox_width: float,
    bbox_height: float,
    bbox_x0: float,
    bbox_y0: float,
    page_height: float,
) -> Tuple[float, float, float, float]:
    """
    Calculate image scale and position to fit within bounding box while preserving aspect ratio.
    
    Args:
        img_width: Original image width in points
        img_height: Original image height in points
        bbox_width: Bounding box width in points
        bbox_height: Bounding box height in points
        bbox_x0: Bounding box left X coordinate (layout coordinates)
        bbox_y0: Bounding box top Y coordinate (layout coordinates)
        page_height: Total page height for coordinate conversion
        
    Returns:
        Tuple of (scaled_width, scaled_height, pdf_x, pdf_y) where pdf_x and pdf_y are in PDF coordinates
    """
    # Calculate scaling to fit within bbox while preserving aspect ratio
    scale_x = bbox_width / img_width if img_width > 0 else 1.0
    scale_y = bbox_height / img_height if img_height > 0 else 1.0
    scale = min(scale_x, scale_y)
    
    scaled_width = img_width * scale
    scaled_height = img_height * scale
    
    # Center image in bbox
    img_x = bbox_x0 + (bbox_width - scaled_width) / 2
    pdf_y0 = _layout_to_pdf_y(page_height, bbox_y0 + bbox_height)
    img_y = pdf_y0 + (bbox_height - scaled_height) / 2
    
    return scaled_width, scaled_height, img_x, img_y


def _check_and_fix_line_width(
    line: str,
    font_name: str,
    font_size: float,
    max_width: float,
    c: canvas.Canvas,
) -> List[str]:
    """
    Check if line width exceeds max_width and split if necessary.
    
    This function ensures text never exceeds the bounding box width,
    even by a small amount.
    
    Args:
        line: Text line to check
        font_name: Font name for width calculation
        font_size: Font size in points
        max_width: Maximum allowed width in points
        c: ReportLab canvas object for width measurement
        
    Returns:
        List of lines (may be split if original line was too wide)
    """
    try:
        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
        if line_width <= max_width:
            return [line]
        
        # Line exceeds width, need to split
        split_lines = _wrap_text_to_width(line, max_width, font_name, font_size, canvas_obj=c)
        if split_lines:
            return split_lines
        
        # Wrapping failed, truncate character by character
        truncated_line = ""
        for char in line:
            test_line = truncated_line + char
            test_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
            if test_width <= max_width:
                truncated_line = test_line
            else:
                break
        return [truncated_line] if truncated_line else [line]
    except Exception:
        # Fallback: return original line if measurement fails
        return [line]



def _parse_markdown_table(text: str) -> List[List[str]]:
    """Delegate to TableUtils from new architecture."""
    return TableUtils.parse_markdown_table(text)

def _parse_html_table(html_str: str) -> Tuple[List[List[str]], List[Tuple[int, int, int, int]]]:
    """Delegate to TableUtils from new architecture."""
    def log_warning(msg: str, error: Exception):
        unified_logger.warning(
            LogModule.RESTOR,
            f"[REPORTLAB] {msg}: {{error}}",
            error=error,
        )
    return TableUtils.parse_html_table(html_str, log_warning=log_warning)

def _calculate_table_column_widths(
    rows: List[List[str]],
    total_width: float,
    font_size: float,
    font_name: str,
    canvas_obj=None
) -> List[float]:
    """Delegate to TableUtils from new architecture."""
    return TableUtils.calculate_table_column_widths(rows, total_width, font_size, font_name, canvas_obj)


def _render_table_block(
    c: canvas.Canvas,
    block: LayoutBlock,
    text: str,
    page_height: float,
    table_body_format: str = "html",
    image_data_map: Optional[Dict[str, bytes]] = None,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    target_language: Optional[str] = None,
    type_font_baselines: Optional[Dict[str, float]] = None,
) -> bool:
    """
    Render a table block with caption, body, and footnotes.
    
    Structure analysis:
    - table_caption: Usually above table_body (may extend beyond outer bbox)
    - table_body: Main table content (usually matches outer bbox)
    - table_footnote: Usually below table_body (may extend beyond outer bbox)
    
    All parts share the outer table block's bbox conceptually, but have their own bboxes.
    
    Table formats supported:
    1. HTML format: Direct HTML table string from layout.raw (preferred, has rowspan/colspan)
    2. Markdown format: Markdown table from text parameter (converted from HTML, loses rowspan/colspan)
    3. Image format: Table rendered as image (fallback)
    """
    # Try to parse table from text (markdown format, converted from HTML)
    # But we'll prefer HTML format if available, as it preserves rowspan/colspan
    rows = _parse_markdown_table(text or "")
    use_markdown_table = bool(rows)

    try:
        outer_x0, outer_y0, outer_x1, outer_y1 = block.bbox
    except Exception:
        return False

    outer_width = max(outer_x1 - outer_x0, 10)
    outer_height = max(outer_y1 - outer_y0, 10)
    num_rows = len(rows)
    
    # Extract caption, body, and footnotes from block.raw
    raw_block = block.raw if hasattr(block, "raw") and isinstance(block.raw, dict) else {}
    nested_blocks = raw_block.get("blocks", []) if isinstance(raw_block, dict) else []
    
    caption_text = None
    caption_text_from_layout = None  # When format=image, use only this to avoid drawing table content as caption
    caption_bbox = None
    body_bbox = None
    table_html = None
    table_image_path = None
    footnote_texts: List[Tuple[Tuple[float, float, float, float], str]] = []
    
    for sub in nested_blocks:
        if not isinstance(sub, dict):
            continue
        sub_type = str(sub.get("type", ""))
        
        if sub_type == TABLE_CAPTION:
            original_caption_text = _extract_text_from_raw_layout(sub) or ""
            caption_text_from_layout = original_caption_text
            caption_bbox = sub.get("bbox")
            # Try to find translated caption text (skip when body will be image - avoid table fragment as caption)
            # In markdown_builder, segments are added in this order:
            # 1. Table placeholder (markdown table or HTML) - may be multiple lines
            # 2. Caption (as separate text segment, may be multi-line)
            # 3. Footnotes (each as separate text segment)
            # All use the same block.index (table block's index)
            caption_text = original_caption_text
            if block.index is not None and translated_text_by_block_index:
                block_translated_text = translated_text_by_block_index.get(block.index)
                if block_translated_text and original_caption_text.strip():
                    # Strategy: Match caption by comparing with original caption text
                    # 1. Extract original caption keywords/features
                    original_caption_lower = original_caption_text.lower().strip()
                    original_caption_words = set(original_caption_lower.split())
                    original_caption_len = len(original_caption_text.strip())
                    
                    # 2. Split translated text into lines and filter
                    all_lines = [line.strip() for line in block_translated_text.split('\n') if line.strip()]
                    
                    # 3. Filter out table lines (markdown/HTML)
                    non_table_lines = []
                    for line in all_lines:
                        # Skip markdown table lines
                        if '|' in line and '---' in '\n'.join(all_lines[max(0, all_lines.index(line)-2):all_lines.index(line)+3]):
                            continue
                        # Skip HTML table tags
                        if '<table' in line.lower() or '<tr' in line.lower() or '<td' in line.lower():
                            continue
                        # Skip very short lines that are likely table separators
                        if len(line) < 3:
                            continue
                        non_table_lines.append(line)
                    
                    # 4. Find best matching line(s) for caption
                    # Caption usually starts with "Table" or similar, and has similar length
                    best_match_lines = []
                    best_score = 0
                    
                    # Try to find caption by matching keywords and length
                    for i, line in enumerate(non_table_lines):
                        line_lower = line.lower()
                        line_words = set(line_lower.split())
                        line_len = len(line)
                        
                        # Calculate similarity score
                        score = 0
                        # Check for caption keywords
                        caption_keywords = ['table', '图', '表', 'caption', '标题', 'tab']
                        if any(kw in line_lower for kw in caption_keywords):
                            score += 10
                        # Check length similarity (within 50% difference)
                        if abs(line_len - original_caption_len) <= original_caption_len * 0.5:
                            score += 5
                        # Check word overlap
                        word_overlap = len(original_caption_words & line_words)
                        if word_overlap > 0:
                            score += word_overlap
                        
                        if score > best_score:
                            best_score = score
                            # Collect consecutive lines starting from this one (for multi-line caption)
                            best_match_lines = [line]
                            # Look ahead for more caption lines (usually caption is 1-3 lines)
                            for j in range(i + 1, min(i + 3, len(non_table_lines))):
                                next_line = non_table_lines[j]
                                # Stop if next line looks like a footnote (short, starts with symbol/number)
                                if len(next_line) < 30 and (next_line[0] in '*†‡§¶' or next_line[0].isdigit()):
                                    break
                                # Stop if next line is very different in length (likely a footnote)
                                if abs(len(next_line) - line_len) > line_len * 0.8:
                                    break
                                best_match_lines.append(next_line)
                    
                    # 5. Use best match if found, otherwise use first non-table line
                    if best_match_lines:
                        caption_text = '\n'.join(best_match_lines)
                    elif non_table_lines:
                        # Fallback: use first non-table line (assuming it's caption)
                        caption_text = non_table_lines[0]
        elif sub_type == TABLE_BODY:
            body_bbox = sub.get("bbox")
            
            # Extract HTML table and/or image_path from table_body
            lines = sub.get("lines", [])
            for line in lines:
                if not isinstance(line, dict):
                    continue
                spans = line.get("spans", [])
                for span in spans:
                    if not isinstance(span, dict):
                        continue
                    if span.get("type") == "table":
                        # Check for HTML format
                        html = span.get("html")
                        if isinstance(html, str) and html.strip():
                            table_html = html
                        
                        # Check for image format (fallback)
                        img_path = span.get("image_path")
                        if isinstance(img_path, str) and img_path.strip():
                            table_image_path = img_path
        elif sub_type == "table_footnote":
            original_fn_text = _extract_text_from_raw_layout(sub) or ""
            fn_bbox = sub.get("bbox")
            if original_fn_text and fn_bbox and isinstance(fn_bbox, list) and len(fn_bbox) == 4:
                try:
                    fn_bbox_tuple = tuple(float(x) for x in fn_bbox)
                    # Store original footnote text (will be replaced with translation later if available)
                    footnote_texts.append((fn_bbox_tuple, original_fn_text))
                except (TypeError, ValueError):
                    pass
    
    # Prefer HTML table parsing if available, as it preserves rowspan/colspan information
    # Markdown tables lose this information during conversion
    table_spans: List[Tuple[int, int, int, int]] = []  # (row_start, col_start, row_end, col_end)
    if table_html:
        html_rows, html_spans = _parse_html_table(table_html)
        if html_rows:
            # Use HTML parsed rows (they have correct structure for colspan/rowspan)
            rows = html_rows
            table_spans = html_spans
            use_markdown_table = False
        elif not rows:
            # HTML parsing failed, but we have HTML - log warning
            pass
    
    # If still no rows and we have image, use image rendering (fallback)
    if not rows and table_image_path:
        # TODO: Render table as image if needed
        # For now, return False to fall back to other rendering
        return False
    
    if not rows:
        log_msg = (
            f"[REPORTLAB] Table (index={block.index}) failed to parse table: "
            f"no rows from markdown or HTML, text_length={len(text) if text else 0}, "
            f"has_html={bool(table_html)}, has_image={bool(table_image_path)}"
        )
        logger.warning(log_msg)
        return False
    
    # Sort footnotes by y coordinate (top to bottom)
    # In layout.json, y increases downward, so smaller y0 means higher position
    footnote_texts.sort(key=lambda x: x[0][1])  # Sort by y0 (smaller = higher on page)
    
    # Determine actual table body bbox
    # Strategy: Use the space from caption bottom to first footnote top
    # This eliminates gaps between caption and table, and between table and footnotes
    body_x0 = outer_x0
    body_x1 = outer_x1
    body_y0 = outer_y0  # Start from outer bbox top by default
    body_y1 = outer_y1  # End at outer bbox bottom by default
    
    # Adjust body_y0: start from caption bottom if caption exists
    # For now, use caption bbox bottom as reference
    # We'll refine this after calculating actual caption height during rendering
    if caption_bbox and isinstance(caption_bbox, list) and len(caption_bbox) == 4:
        try:
            cap_x0, cap_y0, cap_x1, cap_y1 = tuple(float(x) for x in caption_bbox)
            # Use caption bbox bottom (cap_y1) as initial reference
            # This will be adjusted based on actual rendered caption height
            caption_gap = 1.5  # Fixed small gap
            body_y0 = cap_y1 + caption_gap
        except (TypeError, ValueError):
            pass
    
    # Adjust body_y1: end at first footnote top if footnotes exist
    if footnote_texts:
        try:
            # Get the topmost footnote (first in sorted list)
            first_footnote_bbox = footnote_texts[0][0]
            fn_y0 = first_footnote_bbox[1]  # y0 of first footnote
            # Use footnote top (fn_y0) as table bottom, with small gap
            footnote_gap = 2.0  # Small gap between table and footnote
            body_y1 = fn_y0 - footnote_gap
        except (TypeError, ValueError, IndexError):
            pass
    
    # Ensure body_y0 < body_y1 and use valid values
    if body_y0 >= body_y1:
        # Fallback to original body_bbox or outer bbox
        if body_bbox and isinstance(body_bbox, list) and len(body_bbox) == 4:
            try:
                body_x0, body_y0, body_x1, body_y1 = tuple(float(x) for x in body_bbox)
            except (TypeError, ValueError):
                body_x0, body_y0, body_x1, body_y1 = outer_x0, outer_y0, outer_x1, outer_y1
        else:
            body_x0, body_y0, body_x1, body_y1 = outer_x0, outer_y0, outer_x1, outer_y1
        unified_logger.warning(
            LogModule.RESTOR,
            "[REPORTLAB] Table (index={index}) adjusted bbox invalid (y0={y0:.1f} >= y1={y1:.1f}), using fallback bbox",
            index=getattr(block, "index", None),
            y0=body_y0,
            y1=body_y1,
        )
    
    body_width = max(body_x1 - body_x0, 10)
    body_height = max(body_y1 - body_y0, 10)

    # Decide whether to use image as table body (when requested and available)
    table_body_format_normalized = (table_body_format or "html").strip().lower()
    use_image_body = False
    table_image_bytes: Optional[bytes] = None
    
    unified_logger.info(
        LogModule.RESTOR,
        "[REPORTLAB] Table (index={index}) format check: requested_format={format}, "
        "has_table_image_path={has_path}, image_path={path}, "
        "has_image_data_map={has_map}, image_data_map_keys_count={count}",
        index=getattr(block, "index", None),
        format=table_body_format_normalized,
        has_path=bool(table_image_path),
        path=table_image_path or "None",
        has_map=bool(image_data_map),
        count=len(image_data_map) if image_data_map else 0,
    )
    
    if (
        table_body_format_normalized == "image"
        and table_image_path
        and image_data_map
    ):
        # Try exact path and a normalized variant (without leading "./")
        table_image_bytes = image_data_map.get(table_image_path) or image_data_map.get(
            table_image_path.lstrip("./")
        )
        
        # Also try to find by filename if path doesn't match exactly
        if not table_image_bytes:
            import os
            table_image_filename = os.path.basename(table_image_path) if table_image_path else None
            if table_image_filename:
                for key, value in image_data_map.items():
                    if os.path.basename(key) == table_image_filename:
                        table_image_bytes = value
                        unified_logger.info(
                            LogModule.RESTOR,
                            "[REPORTLAB] Table (index={index}) found image by filename: "
                            "requested_path={req_path}, found_key={found_key}",
                            index=getattr(block, "index", None),
                            req_path=table_image_path,
                            found_key=key,
                        )
                        break
        
        if table_image_bytes:
            use_image_body = True
            # When rendering table as image, use only layout caption to avoid drawing table content fragment as caption
            if caption_text_from_layout is not None:
                caption_text = caption_text_from_layout
            unified_logger.info(
                LogModule.RESTOR,
                "[REPORTLAB] Table (index={index}) will render as image: "
                "image_path={path}, image_size={size} bytes",
                index=getattr(block, "index", None),
                path=table_image_path,
                size=len(table_image_bytes),
            )
        else:
            unified_logger.warning(
                LogModule.RESTOR,
                "[REPORTLAB] Table (index={index}) image format requested but image not found: "
                "requested_path={path}, available_keys={keys}",
                index=getattr(block, "index", None),
                path=table_image_path,
                keys=list(image_data_map.keys())[:10] if image_data_map else [],
            )

    # Ensure all rows have same number of columns
    max_cols = max(len(r) for r in rows)
    norm_rows: List[List[str]] = []
    for r in rows:
        if len(r) < max_cols:
            r = r + [""] * (max_cols - len(r))
        norm_rows.append(r)

    # Calculate font size and row height for table body to fit within body_bbox
    # Strategy: 
    # 1. Start with a reasonable font size estimate
    # 2. Calculate row height = font_size + leading (leading should be 15-25% of font_size)
    # 3. If total height exceeds bbox, reduce font size iteratively until it fits
    # 4. Ensure row_height >= font_size + min_leading at all times
    
    if num_rows > 0 and body_height > 0:
        # Initial estimate: allocate ~75% of available height for content (25% for padding/grid)
        available_height_per_row = body_height / num_rows
        # Font size should be ~70% of available height (leaving 30% for leading and padding)
        initial_font_size = available_height_per_row * 0.7
        font_size = max(6.0, min(12.0, initial_font_size))
    else:
        font_size = 9.0  # Default fallback
        available_height_per_row = 12.0
    
    # Leading should be 15-25% of font size for readable spacing
    # Use tighter leading (15%) to maximize space efficiency
    min_leading_ratio = 0.15
    max_leading_ratio = 0.25
    leading_ratio = min_leading_ratio
    
    # Calculate initial row height
    leading = font_size * leading_ratio
    row_height = font_size + leading
    
    # Iteratively adjust font size if total height exceeds body_bbox
    max_iterations = 10
    iteration = 0
    while row_height * num_rows > body_height and iteration < max_iterations:
        # Reduce font size to fit
        max_row_height = body_height / num_rows
        # Font size should be ~85% of max_row_height (leaving 15% for leading)
        font_size = max_row_height * 0.85
        # Ensure font size doesn't go below minimum
        font_size = max(6.0, font_size)
        
        # Recalculate leading and row height
        leading = font_size * leading_ratio
        row_height = font_size + leading
        
        # If still too tall, try tighter leading (reduce leading_ratio)
        if row_height * num_rows > body_height and leading_ratio > min_leading_ratio:
            leading_ratio = max(min_leading_ratio, leading_ratio - 0.02)
            leading = font_size * leading_ratio
            row_height = font_size + leading
        
        iteration += 1
    
    # Final validation: ensure row_height >= font_size + min_leading
    min_row_height = font_size * (1 + min_leading_ratio)
    if row_height < min_row_height:
        row_height = min_row_height
        leading = row_height - font_size
    
    # Adjust to fill body_bbox: scale up if too small, scale down if too large
    total_table_height = row_height * num_rows
    
    if total_table_height > body_height:
        # Scale down if exceeds bbox
        # Safety check: avoid division by zero
        if total_table_height <= 0:
            logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Table (index={getattr(block, 'index', 'unknown')}) total_table_height is zero or negative: {total_table_height}")
            total_table_height = body_height if body_height > 0 else 1.0
        scale_factor = body_height / total_table_height
        font_size = font_size * scale_factor
        if font_size < 6.0:
            font_size = 6.0
        leading = font_size * leading_ratio
        row_height = font_size + leading
        # If still too tall, reduce leading ratio further
        if row_height * num_rows > body_height:
            max_row_height = body_height / num_rows
            if max_row_height >= font_size * (1 + min_leading_ratio):
                row_height = max_row_height
                leading = row_height - font_size
            else:
                font_size = max_row_height / (1 + min_leading_ratio)
                font_size = max(6.0, font_size)
                leading = font_size * min_leading_ratio
                row_height = font_size + leading
    elif total_table_height < body_height * 0.95:  # If significantly smaller than bbox
        # Scale up to fill bbox (but don't exceed max font size)
        # Safety check: avoid division by zero
        if total_table_height <= 0:
            logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Table (index={getattr(block, 'index', 'unknown')}) total_table_height is zero or negative: {total_table_height}")
            total_table_height = body_height if body_height > 0 else 1.0
        scale_factor = body_height / total_table_height
        new_font_size = font_size * scale_factor
        # Don't exceed reasonable max font size (12pt)
        if new_font_size <= 12.0:
            font_size = new_font_size
            leading = font_size * leading_ratio
            row_height = font_size + leading
        else:
            # If scaling would exceed max font size, increase leading instead
            font_size = 12.0
            # Calculate row height to fill bbox
            target_row_height = body_height / num_rows
            if target_row_height >= font_size * (1 + min_leading_ratio):
                row_height = target_row_height
                leading = row_height - font_size
            else:
                # Even with max font size, can't fill bbox with min leading
                # Use max font size and min leading
                leading = font_size * min_leading_ratio
                row_height = font_size + leading
    
    # Final check: ensure total height matches body_height as closely as possible
    total_table_height = row_height * num_rows
    if abs(total_table_height - body_height) > 1.0 and num_rows > 0:
        # Fine-tune row height to exactly match body_height
        target_row_height = body_height / num_rows
        if target_row_height >= font_size * (1 + min_leading_ratio):
            row_height = target_row_height
            leading = row_height - font_size
            # Recalculate font_size if needed to maintain reasonable leading ratio
            if leading < font_size * min_leading_ratio:
                # Leading too small, increase font size if possible
                if font_size < 12.0:
                    font_size = min(12.0, row_height / (1 + min_leading_ratio))
                    leading = row_height - font_size
            elif leading > font_size * max_leading_ratio:
                # Leading too large, can increase font size
                if font_size < 12.0:
                    font_size = min(12.0, row_height / (1 + max_leading_ratio))
                    leading = row_height - font_size
    # Final validation: ensure row_height is set to fill body_height
    final_total_height = row_height * num_rows
    if abs(final_total_height - body_height) > 0.5 and num_rows > 0:
        # Force row_height to exactly match body_height / num_rows
        row_height = body_height / num_rows
        leading = max(font_size * min_leading_ratio, row_height - font_size)

    # Set minimal cell padding to reduce spacing
    # Use very small padding (1-2pt) to maximize space for content
    cell_padding = max(1.0, min(2.0, font_size * 0.15))

    # Detect language for font selection using unified method
    sample_text = " ".join(" ".join(row) for row in norm_rows[:3])
    lang, font_name = _detect_and_get_font_for_text(sample_text, target_language)
    
    # Verify font is registered and use fallback if needed
    # ReportLab ParagraphStyle requires exact font name match (case-sensitive)
    # So we need to ensure the font_name is actually registered
    registered_fonts = FontUtils.get_registered_fonts()
    if font_name not in registered_fonts:
        # Try to find a registered font with similar name (case-insensitive)
        font_name_lower = font_name.lower()
        found_font = None
        for reg_font_name in registered_fonts.keys():
            if reg_font_name.lower() == font_name_lower:
                found_font = reg_font_name
                break
        if found_font:
            font_name = found_font
        else:
            # Use fallback: try to set font on canvas to get actual font name
            try:
                c.setFont(font_name, font_size)
                # Font works, keep it
            except Exception:
                # Font doesn't work, use fallback
                font_name = FontUtils.set_font_with_fallback(c, font_name, font_size, lang)

    # Use Paragraph objects for cells to ensure LEADING and ROWHEIGHTS are respected
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    
    # Iterative adjustment: create table, check height, adjust if needed (HTML/markdown mode only)
    max_iterations = 5
    iteration = 0
    current_font_size = font_size
    current_row_height = row_height
    current_cell_padding = max(1.0, min(2.0, font_size * 0.15))  # Initialize cell padding
    table = None
    wrapped_height = 0

    if not use_image_body:
        while iteration < max_iterations:
            # Calculate paragraph leading - this is line spacing, not total height
            para_leading = current_font_size * 1.2  # Standard line spacing (120% of font size)
            
            # Recalculate cell padding based on current font size
            current_cell_padding = max(1.0, min(2.0, current_font_size * 0.15))
            
            # Verify font is registered before creating ParagraphStyle
            # ReportLab ParagraphStyle requires exact font name match (case-sensitive)
            # Use pdfmetrics to verify font is actually available
            actual_font_name = font_name
            font_verified = False
            
            # First check our registry
            if actual_font_name in registered_fonts:
                # Verify with pdfmetrics that font is actually registered
                try:
                    font_obj = pdfmetrics.getFont(actual_font_name)
                    if font_obj is not None:
                        font_verified = True
                except Exception:
                    pass
            
            # If not verified, try case-insensitive match
            if not font_verified:
                font_name_lower = actual_font_name.lower()
                for reg_font_name in registered_fonts.keys():
                    if reg_font_name.lower() == font_name_lower:
                        try:
                            font_obj = pdfmetrics.getFont(reg_font_name)
                            if font_obj is not None:
                                actual_font_name = reg_font_name
                                font_verified = True
                                break
                        except Exception:
                            continue
            
            # If still not verified, try to set font on canvas to get actual font name
            if not font_verified:
                try:
                    c.setFont(actual_font_name, current_font_size)
                    # Font works on canvas, try to verify with pdfmetrics
                    try:
                        font_obj = pdfmetrics.getFont(actual_font_name)
                        if font_obj is not None:
                            font_verified = True
                    except Exception:
                        pass
                except Exception:
                    pass
            
            # If still not verified, use fallback
            if not font_verified:
                # Try Helvetica (always available)
                actual_font_name = "Helvetica"
                try:
                    font_obj = pdfmetrics.getFont(actual_font_name)
                    if font_obj is None:
                        # Last resort: use canvas to verify
                        c.setFont(actual_font_name, current_font_size)
                except Exception:
                    # Should not happen, but if it does, we'll let ParagraphStyle handle it
                    pass
            
            # Create paragraph style for table cells
            cell_style = ParagraphStyle(
                name=f'TableCell_Iter{iteration}',
                fontName=actual_font_name,  # Use verified font name
                fontSize=current_font_size,
                leading=para_leading,  # Line spacing for wrapped text
                alignment=TA_LEFT,
                spaceBefore=0,
                spaceAfter=0,
                leftIndent=0,
                rightIndent=0,
            )
            
            # Convert table data to Paragraph objects
            table_data_with_paragraphs = []
            for row in norm_rows:
                para_row = []
                for cell_text in row:
                    # Escape HTML special characters for Paragraph
                    escaped_text = cell_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    para = Paragraph(escaped_text, cell_style)
                    para_row.append(para)
                table_data_with_paragraphs.append(para_row)
    
            # Calculate column widths based on content length
            # Use current_font_size in iteration loop
            col_widths = _calculate_table_column_widths(norm_rows, body_width, current_font_size, font_name, c)
            
            # Create table with Paragraph objects and calculated column widths
            table = RLTable(table_data_with_paragraphs, colWidths=col_widths)
            
            # Build style commands with calculated dimensions
            style_commands = [
                ("GRID", (0, 0), (-1, -1), 0.5, black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), current_cell_padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), current_cell_padding),
                ("LEFTPADDING", (0, 0), (-1, -1), current_cell_padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), current_cell_padding),
            ]
            
            # Add SPAN commands for merged cells (rowspan/colspan from HTML)
            if table_spans:
                for row_start, col_start, row_end, col_end in table_spans:
                    # ReportLab SPAN command format: ('SPAN', (col_start, row_start), (col_end, row_end))
                    # Note: ReportLab uses (col, row) format, and both start and end are inclusive
                    style_commands.append(("SPAN", (col_start, row_start), (col_end, row_end)))
            
            # Set row heights to ensure table fits in body_bbox
            current_row_heights = [current_row_height] * num_rows
            style_commands.append(("ROWHEIGHTS", (0, 0), (-1, -1), current_row_heights))
            
            table.setStyle(RLTableStyle(style_commands))
            
            # Wrap the table to get actual height
            wrap_height = max(current_row_height * num_rows * 1.5, body_height * 1.5)
            try:
                wrapped_width, wrapped_height = table.wrapOn(c, body_width, wrap_height)
            except Exception as e:
                logger.error(LogModule.LAYOUT, f"[REPORTLAB] Table (index={block.index}) wrapOn failed at iteration {iteration}: {e}")
                return False
            
            # Check if table fits within bbox (allow 5% tolerance)
            height_ratio = wrapped_height / body_height if body_height > 0 else 1.0
            height_diff = wrapped_height - body_height
            
            # Check convergence: if height is within tolerance, break
            tolerance = body_height * 0.05  # 5% tolerance
            if abs(height_diff) <= tolerance:
                break
            
            # If table exceeds bbox, adjust font size and row height
            if wrapped_height > body_height * 1.05:  # Only adjust if exceeds by more than 5%
                # Calculate scale factor to fit bbox
                # Safety check: avoid division by zero
                if wrapped_height <= 0:
                    logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Table (index={block.index}) wrapped_height is zero or negative: {wrapped_height}")
                    wrapped_height = body_height if body_height > 0 else 1.0
                scale_factor = body_height / wrapped_height
                # Apply scale with a small buffer (95%) to ensure it fits
                scale_factor = scale_factor * 0.95
                
                # Scale down font size
                new_font_size = current_font_size * scale_factor
                new_font_size = max(6.0, new_font_size)  # Minimum 6pt for readability
                
                # Scale down row height proportionally
                new_row_height = current_row_height * scale_factor
                # Ensure row_height >= font_size + min_leading
                min_row_height = new_font_size * (1 + min_leading_ratio)
                if new_row_height < min_row_height:
                    new_row_height = min_row_height
                
                # If row_height would make total height exceed bbox, recalculate
                if new_row_height * num_rows > body_height:
                    new_row_height = body_height / num_rows
                    # Adjust font_size to fit within row_height
                    if new_row_height >= new_font_size * (1 + min_leading_ratio):
                        # Row height is sufficient, keep font size
                        pass
                    else:
                        # Row height too small, reduce font size
                        new_font_size = new_row_height / (1 + min_leading_ratio)
                        new_font_size = max(6.0, new_font_size)
                
                # Check if adjustment is significant enough to continue
                font_size_change = abs(new_font_size - current_font_size)
                row_height_change = abs(new_row_height - current_row_height)
                
                current_font_size = new_font_size
                current_row_height = new_row_height
                
                # Check if adjustment is too small (convergence check)
                if font_size_change < 0.1 and row_height_change < 0.1:
                    logger.warning(
                        f"[REPORTLAB] Table (index={block.index}) adjustment too small at iteration {iteration + 1}: "
                        f"font_size_change={font_size_change:.3f}pt, row_height_change={row_height_change:.3f}pt. "
                        f"May not converge properly."
                    )
            elif wrapped_height < body_height * 0.9:
                # Table is significantly smaller than bbox, try to scale up
                # Safety check: avoid division by zero
                if wrapped_height <= 0:
                    logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Table (index={block.index}) wrapped_height is zero or negative: {wrapped_height}")
                    wrapped_height = body_height if body_height > 0 else 1.0
                scale_factor = body_height / wrapped_height
                # Apply scale with a small buffer (98%) to avoid overshooting
                scale_factor = scale_factor * 0.98
                
                # Scale up font size (but don't exceed max)
                new_font_size = current_font_size * scale_factor
                new_font_size = min(12.0, new_font_size)  # Maximum 12pt
                
                # Scale up row height proportionally
                new_row_height = current_row_height * scale_factor
                # Ensure row_height >= font_size + min_leading
                min_row_height = new_font_size * (1 + min_leading_ratio)
                if new_row_height < min_row_height:
                    new_row_height = min_row_height
                
                # Check if adjustment is significant enough to continue
                font_size_change = abs(new_font_size - current_font_size)
                row_height_change = abs(new_row_height - current_row_height)
                
                if font_size_change > 0.1 or row_height_change > 0.1:
                    current_font_size = new_font_size
                    current_row_height = new_row_height
            
            iteration += 1
    
    # Update final values (for HTML/markdown mode; for image mode they will be used for caption/footnote only)
    font_size = current_font_size
    row_height = current_row_height
    cell_padding = current_cell_padding
    
    # Final check: if still exceeds, use last resort scaling
    # Only check if we actually have a wrapped_height (i.e., not using image body)
    if not use_image_body and wrapped_height > body_height * 1.05 and num_rows > 0:
        logger.warning(
            f"[REPORTLAB] Table (index={block.index}) still exceeds bbox after {max_iterations} iterations. "
            f"Applying final scaling: wrapped_height={wrapped_height:.2f}pt > bbox={body_height:.2f}pt"
        )
        # Force row_height to exactly match body_height / num_rows
        row_height = body_height / num_rows
        # Adjust font_size to fit
        if row_height >= font_size * (1 + min_leading_ratio):
            # Keep font_size, adjust leading
            leading = row_height - font_size
        else:
            # Reduce font_size
            font_size = row_height / (1 + min_leading_ratio)
            font_size = max(6.0, font_size)
            leading = row_height - font_size
        
        # Verify font before creating final ParagraphStyle (same logic as iteration loop)
        final_font_name = font_name
        font_verified = False
        
        # First check our registry
        if final_font_name in registered_fonts:
            try:
                font_obj = pdfmetrics.getFont(final_font_name)
                if font_obj is not None:
                    font_verified = True
            except Exception:
                pass
        
        # If not verified, try case-insensitive match
        if not font_verified:
            font_name_lower = final_font_name.lower()
            for reg_font_name in registered_fonts.keys():
                if reg_font_name.lower() == font_name_lower:
                    try:
                        font_obj = pdfmetrics.getFont(reg_font_name)
                        if font_obj is not None:
                            final_font_name = reg_font_name
                            font_verified = True
                            break
                    except Exception:
                        continue
        
        # If still not verified, try canvas test
        if not font_verified:
            try:
                c.setFont(final_font_name, font_size)
                try:
                    font_obj = pdfmetrics.getFont(final_font_name)
                    if font_obj is not None:
                        font_verified = True
                except Exception:
                    pass
            except Exception:
                pass
        
        # If still not verified, use Helvetica fallback
        if not font_verified:
            final_font_name = "Helvetica"
        
        # Recreate table with final dimensions
        para_leading = font_size * 1.2
        cell_style = ParagraphStyle(
            name='TableCell_Final',
            fontName=final_font_name,  # Use verified font name
            fontSize=font_size,
            leading=para_leading,
            alignment=TA_LEFT,
            spaceBefore=0,
            spaceAfter=0,
            leftIndent=0,
            rightIndent=0,
        )
        
        table_data_with_paragraphs = []
        for row in norm_rows:
            para_row = []
            for cell_text in row:
                escaped_text = cell_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                para = Paragraph(escaped_text, cell_style)
                para_row.append(para)
            table_data_with_paragraphs.append(para_row)
        
        # Calculate column widths based on content length
        col_widths = _calculate_table_column_widths(norm_rows, body_width, font_size, font_name, c)
        
        table = RLTable(table_data_with_paragraphs, colWidths=col_widths)
        style_commands = [
            ("GRID", (0, 0), (-1, -1), 0.5, black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), cell_padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), cell_padding),
            ("LEFTPADDING", (0, 0), (-1, -1), cell_padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), cell_padding),
            ("ROWHEIGHTS", (0, 0), (-1, -1), [row_height] * num_rows),
        ]
        
        # Add SPAN commands for merged cells (rowspan/colspan from HTML)
        if table_spans:
            for row_start, col_start, row_end, col_end in table_spans:
                # ReportLab SPAN command format: ('SPAN', (col_start, row_start), (col_end, row_end))
                # Note: ReportLab uses (col, row) format, and both start and end are inclusive
                style_commands.append(("SPAN", (col_start, row_start), (col_end, row_end)))
                            # (Info logging removed)
        
        table.setStyle(RLTableStyle(style_commands))
        
        # Re-wrap with final dimensions
        wrap_height = max(row_height * num_rows * 1.5, body_height * 1.5)
        wrapped_width, wrapped_height = table.wrapOn(c, body_width, wrap_height)
    
    # Render caption (above table body) - bold, same font size as table
    if caption_text and caption_bbox and isinstance(caption_bbox, list) and len(caption_bbox) == 4:
        try:
            cap_x0, cap_y0, cap_x1, cap_y1 = tuple(float(x) for x in caption_bbox)
            cap_width = max(cap_x1 - cap_x0, 10)
            cap_height = max(cap_y1 - cap_y0, 10)
            cap_pdf_y = _layout_to_pdf_y(page_height, cap_y1)
            
            # Calculate gap between caption bottom and table body top
            gap_between_caption_and_body = body_y0 - cap_y1 if body_y0 > cap_y1 else 0
            
            # Use unified caption baseline font size if available (from 15-iteration global baseline search)
            # This ensures image_caption and table_caption use the same font size
            if type_font_baselines and "caption" in type_font_baselines:
                caption_baseline = type_font_baselines["caption"]
                # Use caption baseline font size instead of table body font size
                caption_font_size = caption_baseline
            else:
                # Fallback to table body font size if baseline not available
                caption_font_size = font_size
            
            # Use bold variant for caption
            caption_font_name = font_name
            # Try bold variant (Helvetica-Bold, etc.)
            if font_name == "Helvetica":
                caption_font_name = "Helvetica-Bold"
            elif font_name in ("SimSun", "SimHei", "Microsoft YaHei"):
                # For Chinese fonts, bold may not be available, use same font
                caption_font_name = font_name
            
            # Set font with automatic fallback (using shared utility)
            caption_font_name = _set_font_safe(c, caption_font_name, caption_font_size, fallback=font_name)
            
            # Wrap caption text with caption baseline font size
            caption_lines = _wrap_text_to_width(caption_text, cap_width, caption_font_name, caption_font_size, canvas_obj=c)
            caption_line_height = caption_font_size * 1.2
            
            # Calculate actual caption height based on wrapped lines
            actual_caption_height = len(caption_lines) * caption_line_height if caption_lines else cap_height
            
            # Render caption from top to bottom within bbox
            # In PDF coords: caption bbox top is at page_height - cap_y1, bottom is at page_height - cap_y0
            # We want to render from top (cap_y1) downward
            # First line baseline should be at: (page_height - cap_y1) + caption_font_size (to align with bbox top)
            cap_top_pdf_y = _layout_to_pdf_y(page_height, cap_y1)  # Top of caption bbox in PDF coords
            current_cap_y = cap_top_pdf_y + caption_font_size  # First line baseline
            
            # Track actual rendered caption bottom for accurate gap calculation
            actual_caption_bottom_pdf_y = current_cap_y  # Will be updated after rendering
            
            for line in caption_lines:
                if current_cap_y < 0:
                    break
                
                # Check and fix line width if necessary (using shared utility)
                fixed_lines = _check_and_fix_line_width(line, caption_font_name, caption_font_size, cap_width, c)
                
                for fixed_line in fixed_lines:
                    if current_cap_y < 0:
                        break
                    c.drawString(cap_x0, current_cap_y, fixed_line)
                    # Bottom of current line (before moving to next)
                    actual_caption_bottom_pdf_y = current_cap_y - caption_line_height
                    current_cap_y -= caption_line_height
            
            # Calculate actual caption bottom in layout coordinates
            # The bottom of the last line is at: actual_caption_bottom_pdf_y
            # In layout coords: page_height - actual_caption_bottom_pdf_y
            # But we need to account for the line height to get the true bottom
            actual_caption_bottom_layout_y = page_height - (actual_caption_bottom_pdf_y + caption_line_height) if actual_caption_bottom_pdf_y > 0 else cap_y0
            
            # Adjust body_y0 based on actual caption bottom if it exceeds bbox
            # This prevents overlap when caption text extends beyond bbox
            if actual_caption_bottom_layout_y > cap_y1:
                # Caption extends beyond bbox, adjust body_y0
                caption_gap = 1.5
                body_y0 = actual_caption_bottom_layout_y + caption_gap
                # Recalculate body_height since body_y0 changed
                body_height = max(body_y1 - body_y0, 10)
        except Exception as e:
            pass

    # Convert to ReportLab coordinates for table body
    # Note: In ReportLab, drawOn's y coordinate is the BOTTOM of the table, not the top!
    # Strategy: Always align table TOP with body_y0 (or caption bottom + gap) for consistent spacing
    body_draw_y = _layout_to_pdf_y(page_height, body_y1)  # Initial: align table bottom with body_y1
    
    # Draw the table body: HTML/markdown table or image, depending on mode
    try:
        if not use_image_body:
            # HTML/markdown mode: draw ReportLab table
            # Final wrap to ensure correct dimensions
            wrap_height = max(row_height * num_rows * 1.5, body_height * 1.5)
            wrapped_width, final_wrapped_height = table.wrapOn(c, body_width, wrap_height)
            
            # Always align table TOP with body_y0 for consistent gap to caption
            # In PDF coordinates: table top should be at page_height - body_y0
            # So table bottom (draw_y) should be at: (page_height - body_y0) - final_wrapped_height
            body_draw_y = _layout_to_pdf_y(page_height, body_y0) - final_wrapped_height
            
            # Calculate actual table top position in layout coordinates
            table_top_pdf_y = body_draw_y + final_wrapped_height  # Top of table in PDF coords
            table_top_layout_y = page_height - table_top_pdf_y
            
            # Final validation
            height_diff = abs(final_wrapped_height - body_height)
            height_ratio = final_wrapped_height / body_height if body_height > 0 else 1.0
            
            if final_wrapped_height > body_height * 1.05:
                logger.warning(
                    f"[REPORTLAB] Table body (index={block.index}) final wrapped height ({final_wrapped_height:.1f}pt) "
                    f"still exceeds bbox height ({body_height:.1f}pt) by {height_diff:.1f}pt (ratio={height_ratio:.3f}). "
                    f"This may cause overflow."
                )
            
            table.drawOn(c, body_x0, body_draw_y)
        else:
            # Image mode: draw table body as image inside [body_x0, body_y0, body_x1, body_y1]
            # Note: final_wrapped_height should be the actual scaled image height, not body_height
            # This ensures footnote spacing is calculated correctly
            final_wrapped_height = body_height  # Default fallback
            # In image mode, table_top_layout_y will be calculated after we know the scaled image height
            # For now, use body_y0 as initial value (will be updated below)
            table_top_layout_y = body_y0
            
            if table_image_bytes:
                try:
                    img_reader = ImageReader(io.BytesIO(table_image_bytes))
                    img_width, img_height = img_reader.getSize()
                    
                    # Calculate scaling and position using shared utility (reduces code duplication)
                    scaled_width, scaled_height, img_x, img_y = _calculate_image_scale_and_position(
                        img_width=img_width,
                        img_height=img_height,
                        bbox_width=body_width,
                        bbox_height=body_height,
                        bbox_x0=body_x0,
                        bbox_y0=body_y0,
                        page_height=page_height,
                    )
                    
                    # Use actual scaled height for table bottom calculation
                    # This ensures footnote spacing is correct when image doesn't fill full bbox height
                    final_wrapped_height = scaled_height
                    
                    # Calculate actual image top position in layout coordinates
                    # Image is centered vertically, so actual top = body_y0 + vertical_offset
                    vertical_offset = (body_height - scaled_height) / 2
                    table_top_layout_y = body_y0 + vertical_offset
                    
                    # Calculate scale factor for logging
                    scale_factor = min(scaled_width / img_width if img_width > 0 else 1.0, 
                                     scaled_height / img_height if img_height > 0 else 1.0)
                    
                    unified_logger.info(
                        LogModule.RESTOR,
                        "[REPORTLAB] Table image (index={index}) position calculation: "
                        "body_y0={y0:.1f}pt, body_height={h:.1f}pt, scaled_height={sh:.1f}pt, "
                        "vertical_offset={vo:.1f}pt, table_top_layout_y={top:.1f}pt",
                        index=getattr(block, "index", None),
                        y0=body_y0,
                        h=body_height,
                        sh=scaled_height,
                        vo=vertical_offset,
                        top=table_top_layout_y,
                    )
                    
                    unified_logger.info(
                        LogModule.RESTOR,
                        "[REPORTLAB] Table image (index={index}) rendering: "
                        "img_size=({img_w:.1f}pt x {img_h:.1f}pt), "
                        "bbox_size=({body_w:.1f}pt x {body_h:.1f}pt), "
                        "scale={scale:.3f}, "
                        "scaled_size=({scaled_w:.1f}pt x {scaled_h:.1f}pt), "
                        "final_wrapped_height={final_h:.1f}pt",
                        index=getattr(block, "index", None),
                        img_w=img_width,
                        img_h=img_height,
                        body_w=body_width,
                        body_h=body_height,
                        scale=scale_factor,
                        scaled_w=scaled_width,
                        scaled_h=scaled_height,
                        final_h=final_wrapped_height,
                    )
                    
                    c.drawImage(
                        img_reader,
                        img_x,
                        img_y,
                        width=scaled_width,
                        height=scaled_height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception as e:
                    unified_logger.warning(
                        LogModule.RESTOR,
                        "[REPORTLAB] Failed to render table image body (index={index}, path={path}): {error}",
                        index=getattr(block, "index", None),
                        path=table_image_path,
                        error=str(e),
                    )
                    # Fallback: treat as HTML/markdown mode if possible
                    # We don't attempt to re-run the full table pipeline here; body will be effectively empty.
    except Exception as e:
        logger.error(LogModule.LAYOUT, f"[REPORTLAB] Failed to render table body (index={block.index}): {e}", exc_info=True)
        return False
    
    # Render footnotes (below table body) - smaller font size, one line each
    # Calculate table bottom position for gap calculation
    table_bottom_layout_y = table_top_layout_y + final_wrapped_height
    
    # Match translated footnotes with original footnotes
    if footnote_texts and block.index is not None and translated_text_by_block_index:
        block_translated_text = translated_text_by_block_index.get(block.index)
        if block_translated_text:
            translated_lines = [line.strip() for line in block_translated_text.split('\n') if line.strip()]
            # Footnotes are usually at the end (after table body and caption)
            # Match them in order: last N lines correspond to N footnotes
            num_footnotes = len(footnote_texts)
            if len(translated_lines) >= num_footnotes:
                # Use the last num_footnotes lines as footnotes
                footnote_translations = translated_lines[-num_footnotes:]
                # Update footnote texts with translations (preserve bbox and order)
                updated_footnote_texts = []
                for i, (fn_bbox_tuple, original_fn_text) in enumerate(footnote_texts):
                    if i < len(footnote_translations):
                        updated_footnote_texts.append((fn_bbox_tuple, footnote_translations[i]))
                    else:
                        updated_footnote_texts.append((fn_bbox_tuple, original_fn_text))
                footnote_texts = updated_footnote_texts
    
    # Sort footnotes by y-coordinate (top to bottom) for consistent rendering
    sorted_footnotes = sorted(footnote_texts, key=lambda x: x[0][1] if x[0] and len(x[0]) >= 2 else 0)
    
    # Calculate available space for footnotes
    if sorted_footnotes:
        first_footnote_bbox = sorted_footnotes[0][0]
        first_footnote_y0 = first_footnote_bbox[1] if first_footnote_bbox and len(first_footnote_bbox) >= 2 else table_bottom_layout_y
        available_footnote_height = first_footnote_y0 - table_bottom_layout_y
    else:
        available_footnote_height = 0
    
    footnote_font_size = font_size * 0.85  # 85% of table font size
    footnote_font_size = max(6.0, min(10.0, footnote_font_size))  # Clamp between 6-10pt
    
    # In image mode, if the image is taller than HTML table, adjust footnote font size
    # to ensure text fits in available space
    if use_image_body and available_footnote_height > 0:
        # Estimate required height for footnote text (assuming single line)
        estimated_footnote_height = footnote_font_size * 1.15  # font_size + line spacing
        if estimated_footnote_height > available_footnote_height * 0.9:
            # Reduce font size to fit available space
            max_footnote_font_size = (available_footnote_height * 0.9) / 1.15
            if max_footnote_font_size < footnote_font_size:
                original_footnote_font_size = footnote_font_size
                footnote_font_size = max(6.0, max_footnote_font_size)
                unified_logger.info(
                    LogModule.RESTOR,
                    "[REPORTLAB] Table (index={index}) adjusted footnote font size for image mode: "
                    "original={orig:.1f}pt, adjusted={adj:.1f}pt, "
                    "available_height={avail:.1f}pt, estimated_height={est:.1f}pt, "
                    "table_bottom={bottom:.1f}pt, first_footnote_y0={fn_y0:.1f}pt",
                    index=getattr(block, "index", None),
                    orig=original_footnote_font_size,
                    adj=footnote_font_size,
                    avail=available_footnote_height,
                    est=estimated_footnote_height,
                    bottom=table_bottom_layout_y,
                    fn_y0=first_footnote_y0 if sorted_footnotes else 0,
                )
    
    # Adjust footnote positions based on table bottom
    # First footnote should start at table_bottom + gap, subsequent footnotes maintain relative spacing
    footnote_gap = 1.5  # Fixed gap between table bottom and first footnote
    first_footnote_adjusted_y0 = table_bottom_layout_y + footnote_gap
    
    # Calculate offset needed for first footnote
    if sorted_footnotes:
        first_footnote_original_y0 = sorted_footnotes[0][0][1] if sorted_footnotes[0][0] and len(sorted_footnotes[0][0]) >= 2 else first_footnote_adjusted_y0
        footnote_y_offset = first_footnote_adjusted_y0 - first_footnote_original_y0
    else:
        footnote_y_offset = 0
    
    for fn_bbox_tuple, fn_text in sorted_footnotes:
        try:
            fn_x0, fn_y0, fn_x1, fn_y1 = fn_bbox_tuple
            fn_width = max(fn_x1 - fn_x0, 10)
            fn_height = max(fn_y1 - fn_y0, 1.0)
            
            # Adjust footnote y0 based on table bottom position
            adjusted_fn_y0 = fn_y0 + footnote_y_offset
            adjusted_fn_y1 = fn_y1 + footnote_y_offset
            
            # Calculate gap between table bottom and footnote top
            gap_table_to_footnote = adjusted_fn_y0 - table_bottom_layout_y if adjusted_fn_y0 > table_bottom_layout_y else 0
            
            # Use adjusted y1 for PDF coordinate calculation
            fn_pdf_y = _layout_to_pdf_y(page_height, adjusted_fn_y1)
            
            # Set footnote font (smaller, not bold) using safe font setter
            font_name = _set_font_safe(c, font_name, footnote_font_size)
            
            # Wrap footnote text (usually fits in one line, but handle wrapping)
            fn_lines = _wrap_text_to_width(fn_text, fn_width, font_name, footnote_font_size, canvas_obj=c)
            fn_line_height = footnote_font_size * 1.15
            # Start from footnote bbox top (adjusted_fn_y1 in layout coords)
            current_fn_y = fn_pdf_y + fn_height - footnote_font_size
            
            for line in fn_lines:
                if current_fn_y < 0:
                    break
                
                # Check and fix line width if necessary (using shared utility)
                fixed_lines = _check_and_fix_line_width(line, font_name, footnote_font_size, fn_width, c)
                
                for fixed_line in fixed_lines:
                    if current_fn_y < 0:
                        break
                    c.drawString(fn_x0, current_fn_y, fixed_line)
                    current_fn_y -= fn_line_height
        except Exception as e:
            pass
    
    return True


def _render_text_in_bbox_simple(
    c: canvas.Canvas,
    text: str,
    bbox: Tuple[float, float, float, float],
    page_height: float,
    target_language: Optional[str] = None,
    type_font_baselines: Optional[Dict[str, float]] = None,
) -> None:
    """
    Render a relatively short text (e.g. image caption) inside a given bbox.

    This is a lightweight renderer, separate from the full block text pipeline,
    intended for captions where we don't have a dedicated LayoutBlock.
    """
    if not text or not text.strip():
        return

    x0, y0, x1, y1 = bbox
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)

    # Convert to PDF coordinate system
    pdf_y0 = _layout_to_pdf_y(page_height, y1)

    # Choose font based on language using unified method
    lang, font_name = _detect_and_get_font_for_text(text, target_language)

    # Get baseline font size if available
    baseline_font_size = None
    if type_font_baselines and "caption" in type_font_baselines:
        baseline_font_size = type_font_baselines["caption"]

    # Calculate optimal font size using shared component (reduces code duplication)
    def set_font_wrapper(font_name: str, font_size: float) -> None:
        _set_font_safe(c, font_name, font_size)
    
    font_size, lines, font_name = FontSizeCalculator.calculate_font_size_for_bbox(
        text=text,
        bbox_width=width,
        bbox_height=height,
        baseline_font_size=baseline_font_size,
        min_font_size=6.0,
        max_font_size=12.0,
        line_height_ratio=1.15,
        wrap_text_func=_wrap_text_to_width,
        set_font_func=set_font_wrapper,
        initial_font_name=font_name,
    )
    
    if not lines:
        return
    
    # Set final font
    font_name = _set_font_safe(c, font_name, font_size)
    
    # Calculate line height for rendering
    line_height = font_size * 1.15
    
    # Start drawing from top of caption bbox
    current_y = pdf_y0 + height - font_size
    
    for line in lines:
        if current_y < 0:
            break
        
        # Check and fix line width if necessary (using shared utility)
        fixed_lines = _check_and_fix_line_width(line, font_name, font_size, width, c)
        
        for fixed_line in fixed_lines:
            if current_y < 0:
                break
            c.drawString(x0, current_y, fixed_line)
            current_y -= line_height
    

# ============================================================================
# Backward compatibility wrapper functions - delegate to new architecture
# ============================================================================

def _calculate_available_height_for_lines(
    bbox_height: float,
    line_count: int,
    font_size: float,
    line_spacing_ratio: float = 1.2
) -> float:
    """Delegate to LayoutCalculator."""
    return LayoutCalculator.calculate_available_height_for_lines(
        bbox_height=bbox_height,
        line_count=line_count,
        font_size=font_size,
        line_spacing_ratio=line_spacing_ratio
    )

def _detect_text_language(text: str) -> str:
    """Delegate to TextUtils."""
    return TextUtils.detect_language(text)

def _wrap_text_to_width(text: str, max_width: float, font_name: str = "Helvetica", font_size: float = 12, canvas_obj=None) -> List[str]:
    """Delegate to TextUtils."""
    return TextUtils.wrap_text_to_width(text, max_width, font_name, font_size, canvas_obj)

def _analyze_language_distribution(text: str) -> Dict[str, float]:
    """Delegate to TextUtils."""
    return TextUtils.analyze_language_distribution(text)

def _split_text_by_language_segments(text: str) -> List[Tuple[str, str]]:
    """Delegate to TextUtils."""
    return TextUtils.split_text_by_language_segments(text)

def _extract_text_from_raw_layout(block_raw: dict) -> Optional[str]:
    """Delegate to BlockProcessor."""
    return BlockProcessor.extract_text_from_raw_layout(block_raw)

def _extract_image_captions_from_raw(
    block_raw: dict,
    block_index: Optional[int] = None,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
) -> List[Tuple[Tuple[float, float, float, float], str]]:
    """Delegate to BlockProcessor."""
    return BlockProcessor.extract_image_captions_from_raw(
        block_raw, block_index, translated_text_by_block_index
    )

def _get_text_actual_width_from_layout(block_raw: dict) -> Optional[float]:
    """Delegate to BlockProcessor."""
    return BlockProcessor.get_text_actual_width_from_layout(block_raw)

def _extract_line_heights_from_layout(block_raw: dict) -> List[float]:
    """Delegate to BlockProcessor."""
    return BlockProcessor.extract_line_heights_from_layout(block_raw)

def _extract_original_line_structure_from_layout(block_raw: dict) -> Optional[List[str]]:
    """Delegate to BlockProcessor."""
    return BlockProcessor.extract_original_line_structure_from_layout(block_raw)

def _build_page_block_bbox_index(layout_doc: "LayoutDocument") -> List[List[Tuple[float, float, float, float, str, int, int]]]:
    """Delegate to LayoutCalculator."""
    return LayoutCalculator.build_page_block_bbox_index(layout_doc)

def _check_block_collision_with_page(
    page_blocks: List[Tuple[float, float, float, float, str, int, int]],
    page_idx: int,
    page_block_idx: int,
    x0: float,
    y0: float,
    x1: float,
    rendered_height: float,
    current_block_type: str,
) -> bool:
    """Delegate to LayoutCalculator."""
    return LayoutCalculator.check_block_collision_with_page(
        page_blocks, page_idx, page_block_idx, x0, y0, x1, rendered_height, current_block_type
    )

def _normalize_language_code(lang: str) -> str:
    """Delegate to FontUtils."""
    return FontUtils.normalize_language_code(lang)

def _get_font_name_for_language(lang: str, target_language: Optional[str] = None) -> str:
    """Delegate to FontUtils."""
    return FontUtils.get_font_name_for_language(lang, target_language)

def _detect_and_get_font_for_text(text: str, target_language: Optional[str] = None) -> Tuple[str, str]:
    """Delegate to FontUtils."""
    return FontUtils.detect_and_get_font_for_text(text, target_language)

def _set_font_with_fallback(canvas_obj, font_name: str, font_size: float, lang: str = None) -> str:
    """Delegate to FontUtils."""
    return FontUtils.set_font_with_fallback(canvas_obj, font_name, font_size, lang)

def _estimate_line_count_from_font_size(text: str, font_size: float, block_width: float, block_raw: Optional[dict] = None) -> int:
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.estimate_line_count_from_font_size(text, font_size, block_width, block_raw)

def _calculate_block_height_from_font_size(font_size: float, line_count: int) -> float:
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.calculate_block_height_from_font_size(font_size, line_count)

def _estimate_initial_font_size(block_height: float, text: str = "", block_width: float = 0.0, block_raw: Optional[dict] = None) -> float:
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.estimate_initial_font_size(block_height, text, block_width, block_raw)

def _quantize_font_size(font_size: float) -> float:
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.quantize_font_size(font_size)


def _calculate_type_font_baselines(
    layout_doc: LayoutDocument, 
    translated_text_by_block_index: Dict[int, str],
    frontend_style_overrides: Optional[Dict[int, object]] = None
) -> Dict[str, float]:
    """Delegate to FontSizeCalculator."""
    from layout.pdf_renderer.shared.block_classifier import FrontendStyleOverrides
    return FontSizeCalculator.calculate_type_font_baselines(
        layout_doc, 
        translated_text_by_block_index,
        frontend_style_overrides=frontend_style_overrides
    )





def _fine_tune_font_size_to_prevent_overflow(
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
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.fine_tune_font_size_to_prevent_overflow(
        canvas_obj=canvas_obj,
        text=text,
        font_name=font_name,
        font_size=font_size,
        text_lines=text_lines,
        text_width_for_wrapping=text_width_for_wrapping,
        height=height,
        block_type=block_type,
        page_idx=page_idx,
        block_idx=block_idx,
        original_font_size=original_font_size,
        line_height_ratio=line_height_ratio,
        font_ascent_ratio=font_ascent_ratio,
        overflow_tolerance=overflow_tolerance,
        increment_step=increment_step,
        max_iterations=max_iterations
    )

def _get_font_size_from_type_baseline(
    type_baselines: Dict[str, float], 
    block_type: str, 
    text: str = "",
    block: Optional[LayoutBlock] = None,
    canvas_obj=None,
    font_name: str = "Helvetica",
) -> float:
    """Delegate to FontSizeCalculator."""
    return FontSizeCalculator.get_font_size_from_type_baseline(
        type_baselines, 
        block_type, 
        text,
        block=block,
        canvas_obj=canvas_obj,
        font_name=font_name,
    )


def _detect_text_alignment_from_layout(block_raw: dict, block_bbox: tuple) -> str:
    """Delegate to TextUtils."""
    return TextUtils.detect_text_alignment_from_layout(block_raw, block_bbox)

def _detect_text_alignment(text: str, text_width: float, block_width: float, font_name: str, font_size: float, canvas_obj, block_raw: dict = None, block_bbox: tuple = None) -> str:
    """Delegate to TextUtils."""
    return TextUtils.detect_text_alignment(text, text_width, block_width, font_name, font_size, canvas_obj, block_raw, block_bbox)


# Global switch: enable / disable block collision check.
# When enabled, after font size and line heights are determined for a text block,
# we will check whether its rendered region would invade other blocks' bboxes on the same page.
# If invasion is detected, the font size will be reduced (down to at least 5pt) and text will be
# re-wrapped to avoid collisions as much as possible.
ENABLE_BLOCK_COLLISION_CHECK: bool = True


def render_layout_pdf_reportlab(
    layout_doc: LayoutDocument,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    zip_bytes: Optional[bytes] = None,
    output_path: Optional[Path] = None,
    table_body_format: str = "html",
    equation_format: str = "text",
    target_language: Optional[str] = None,
) -> bytes:
    """
    Render LayoutDocument directly to PDF using ReportLab.
    
    This approach avoids HTML → PDF conversion issues by directly
    using bbox coordinates to place text and images in the PDF.
    
    Args:
        layout_doc: LayoutDocument instance
        translated_text_by_block_index: Optional mapping from block index to translated text
        zip_bytes: Optional ZIP bytes for extracting images
        output_path: Optional path to save PDF file (for debugging)
        
    Returns:
        PDF file content as bytes
        
    Raises:
        ImportError: If ReportLab is not installed
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "ReportLab is required for direct PDF generation. "
            "Install with: pip install reportlab"
        )
    
    import time
    render_start_time = time.time()
    total_blocks = sum(1 for _ in layout_doc.iter_blocks())
    
    # Ensure layout_doc is from MinerU (required for layout-based rendering)
    if layout_doc.engine != "mineru":
        logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Layout engine is '{layout_doc.engine}', expected 'mineru'")
    
    if translated_text_by_block_index is None:
        translated_text_by_block_index = {}
    
    # Register fonts on-demand based on target language (lazy loading for faster startup)
    # Only register fonts for the target language and common fallback languages
    # If fonts are being registered in background, wait for them (with timeout)
    try:
        # First, ensure required fonts are registered (synchronously for this task)
        if target_language:
            # Register fonts for target language
            FontUtils.register_fonts_for_language(target_language)
            # Also register common fallback languages (en, zh) for mixed content
            if target_language not in ('en', 'zh'):
                FontUtils.register_fonts_for_language('en')
                if target_language in ('ja', 'ko'):
                    FontUtils.register_fonts_for_language('zh')
        else:
            # If no target language specified, register only common languages (faster)
            # Full registration will happen on-demand when needed
            priority_languages = ['en', 'zh', 'ja', 'ko']
            for lang in priority_languages:
                FontUtils.register_fonts_for_language(lang)
        
        # Optionally wait for background font registration to complete (with timeout)
        # This ensures all fonts are available, but doesn't block if they're not ready
        FontUtils.wait_for_font_registration(timeout=2.0)  # Wait max 2 seconds
    except Exception as e:
        logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Failed to register fonts: {e}")
    
    # Calculate type-specific font baselines (using new architecture)
    import time
    baseline_start_time = time.time()
    try:
        # Create a temporary FontSizeCalculator instance for baseline calculation
        # Note: This is a complex function that hasn't been fully migrated yet
        # For now, we still call the old implementation but it will use new architecture components internally
        type_font_baselines = _calculate_type_font_baselines(layout_doc, translated_text_by_block_index or {})
    except Exception as e:
        logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Failed to calculate type font baselines: {e}, using fallback", exc_info=True)
        type_font_baselines = {"unknown": 12.0}
    
    # Build per-page bbox index for collision checking
    page_block_bboxes: List[List[Tuple[float, float, float, float, str, int, int]]] = _build_page_block_bbox_index(layout_doc)
    
    # Extract images from MinerU ZIP if available (using shared component)
    image_data_map: Dict[str, bytes] = {}
    if zip_bytes:
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
            image_data_map = BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
            
            # Log extracted images for debugging
            for img_path, img_data in image_data_map.items():
                unified_logger.debug(
                    LogModule.RESTOR,
                    "[REPORTLAB] Extracted image: path={path}, size={size} bytes",
                    path=img_path,
                    size=len(img_data),
                )
            
            # Log warnings for missing images
            zip_file_list = zip_file.namelist()
            for block in layout_doc.iter_image_blocks():
                if block.image_path and block.image_path not in image_data_map:
                    possible_paths = [
                        block.image_path,
                        block.image_path.lstrip('/'),
                        f"images/{block.image_path}",
                        f"images/{block.image_path.lstrip('/')}",
                    ]
                    logger.warning(
                        f"[REPORTLAB] Image {block.image_path} not found in ZIP. "
                        f"Tried paths: {possible_paths}. "
                        f"Available files (first 20): {zip_file_list[:20]}"
                    )
        except Exception as e:
            logger.error(LogModule.LAYOUT, f"[REPORTLAB] Failed to extract images from ZIP: {e}", exc_info=True)
    
    # Create PDF buffer
    pdf_buffer = io.BytesIO()
    
    # Process each page
    total_blocks_processed = 0
    total_blocks_rendered = 0
    total_blocks_skipped = 0
    # Track rendered images to avoid duplicates
    rendered_image_keys = set()  # Set of (block.index, block.image_path) or (page_idx, image_path, bbox) tuples
    try:
        for page_idx, page in enumerate(layout_doc.pages):
            
            # Determine page size
            if page.width and page.height:
                page_width = float(page.width)
                page_height = float(page.height)
            else:
                # Calculate from blocks if not specified
                max_x = 0
                max_y = 0
                for block in page.blocks:
                    x0, y0, x1, y1 = block.bbox
                    max_x = max(max_x, x1)
                    max_y = max(max_y, y1)
                page_width = max_x if max_x > 0 else 595  # A4 width in points
                page_height = max_y if max_y > 0 else 842  # A4 height in points
            
            # Create canvas for this page (using MinerU layout page size)
            if page_idx == 0:
                c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
            else:
                c.showPage()  # Finish previous page before creating new one
                c.setPageSize((page_width, page_height))
            
            # Set background to white for this page
            c.setFillColor(white)
            c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
            c.setFillColor(black)
            
            # Render blocks in this page
            block_count = 0
            rendered_count = 0
            skipped_count = 0
            for block_idx, block in enumerate(page.blocks):
                try:
                    x0, y0, x1, y1 = block.bbox
                    width = x1 - x0
                    height = y1 - y0
                    
                    if width <= 0 or height <= 0:
                        skipped_count += 1
                        total_blocks_skipped += 1
                        continue
                    
                    block_count += 1
                    total_blocks_processed += 1
                except Exception as e:
                    logger.error(LogModule.LAYOUT, f"[REPORTLAB] Page {page_idx}, Block {block_idx}: Error processing block: {e}", exc_info=True)
                    skipped_count += 1
                    total_blocks_skipped += 1
                    continue
                
                # PDF coordinate system: origin at bottom-left, need to convert (using shared utility)
                pdf_y0 = _layout_to_pdf_y(page_height, y1)
                pdf_y1 = _layout_to_pdf_y(page_height, y0)
                
                if block.type == "image" and block.image_path:
                    # Create a unique key for this image block to avoid duplicates
                    # Use (block.index, image_path) if index is available, otherwise use (page_idx, image_path, bbox)
                    if block.index is not None:
                        image_key = (block.index, block.image_path)
                    else:
                        # Use bbox as part of key to distinguish same image at different positions
                        bbox_key = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
                        image_key = (page_idx, block.image_path, bbox_key)
                    
                    # Check if this image has already been rendered
                    if image_key in rendered_image_keys:
                        skipped_count += 1
                        total_blocks_skipped += 1
                        continue
                    
                    # Render image
                    image_data = image_data_map.get(block.image_path)
                    if image_data:
                        try:
                            img_reader = ImageReader(io.BytesIO(image_data))
                            img_width, img_height = img_reader.getSize()
                            
                            # Calculate scaling and position using shared utility (reduces code duplication)
                            scaled_width, scaled_height, img_x, img_y = _calculate_image_scale_and_position(
                                img_width=img_width,
                                img_height=img_height,
                                bbox_width=width,
                                bbox_height=height,
                                bbox_x0=x0,
                                bbox_y0=y0,
                                page_height=page_height,
                            )
                            
                            c.drawImage(
                                img_reader,
                                img_x,
                                img_y,
                                width=scaled_width,
                                height=scaled_height,
                                preserveAspectRatio=True,
                                mask='auto'
                            )
                            # Mark this image as rendered
                            rendered_image_keys.add(image_key)
                            rendered_count += 1
                            total_blocks_rendered += 1
                        except Exception as e:
                            logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Failed to render image {block.image_path}: {e}")
                            skipped_count += 1
                            total_blocks_skipped += 1
                    else:
                        skipped_count += 1
                        total_blocks_skipped += 1
                    
                    # After rendering the image, try to render any nested image captions
                    if block.raw:
                        caption_entries = _extract_image_captions_from_raw(
                            block.raw,
                            block_index=block.index,
                            translated_text_by_block_index=translated_text_by_block_index,
                        )
                        for caption_bbox, caption_text in caption_entries:
                            _render_text_in_bbox_simple(
                                c,
                                caption_text,
                                caption_bbox,
                                page_height,
                                target_language=target_language,
                                type_font_baselines=type_font_baselines,
                            )
                    
                    # Skip text rendering for image blocks to avoid rendering placeholder/base64 strings on top of images
                    continue
                
                # Equation blocks: when equation_format is "image", render as image instead of LaTeX string
                equation_format_normalized = (equation_format or "text").strip().lower()
                if block.type in ("interline_equation", "formula", "equation") and equation_format_normalized == "image":
                    eq_image_path = getattr(block, "image_path", None)
                    eq_image_bytes = None
                    if not eq_image_path and block.raw and isinstance(block.raw, dict):
                        for line in block.raw.get("lines", []) or []:
                            if not isinstance(line, dict):
                                continue
                            for span in line.get("spans", []) or []:
                                if isinstance(span, dict) and span.get("type") == "interline_equation":
                                    eq_image_path = span.get("image_path")
                                    if eq_image_path:
                                        break
                            if eq_image_path:
                                break
                    if eq_image_path and image_data_map:
                        eq_image_bytes = image_data_map.get(eq_image_path) or image_data_map.get(
                            eq_image_path.lstrip("./")
                        )
                        if not eq_image_bytes and eq_image_path:
                            import os as _os
                            base = _os.path.basename(eq_image_path)
                            for k, v in image_data_map.items():
                                if _os.path.basename(k) == base:
                                    eq_image_bytes = v
                                    break
                        if eq_image_bytes:
                            try:
                                img_reader = ImageReader(io.BytesIO(eq_image_bytes))
                                img_w, img_h = img_reader.getSize()
                                sw, sh, img_x, img_y = _calculate_image_scale_and_position(
                                    img_width=img_w, img_height=img_h,
                                    bbox_width=width, bbox_height=height,
                                    bbox_x0=x0, bbox_y0=y0, page_height=page_height,
                                )
                                c.drawImage(
                                    img_reader, img_x, img_y,
                                    width=sw, height=sh,
                                    preserveAspectRatio=True, mask='auto',
                                )
                                rendered_count += 1
                                total_blocks_rendered += 1
                            except Exception as e:
                                logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Equation image render failed: {e}")
                        else:
                            logger.warning(
                                LogModule.LAYOUT,
                                f"[REPORTLAB] Equation (index={getattr(block, 'index', None)}) image format requested but image not found: {eq_image_path}"
                            )
                    if eq_image_path and image_data_map and eq_image_bytes:
                        continue
                    # When image was requested but not found, skip drawing LaTeX string
                    if equation_format_normalized == "image":
                        continue
                
                # Render text block - check all possible text sources
                # Priority: map > block.text > block.raw
                text = ""
                text_source = "none"
                has_text_in_map = False
                
                if block.index is not None and translated_text_by_block_index and block.index in translated_text_by_block_index:
                    text = translated_text_by_block_index[block.index]
                    text_source = "map"
                    has_text_in_map = bool(text.strip())
                
                if not text.strip() and block.text:
                    text = block.text
                    text_source = "block.text"
                
                if not text.strip() and block.raw:
                    text = _extract_text_from_raw_layout(block.raw) or ""
                    if text:
                        text_source = "block.raw"
                
                # Render if we have text, or if it's a supported text type (might have text in raw)
                is_text_type = block.type in ("text", "title", "header", "footer", "page_number", LEGACY_FIGURE, "table", "formula", "equation", "interline_equation", "list")
                
                if text.strip() or is_text_type:
                    if not text.strip():
                        # Try one more time to extract from raw for text types
                        if block.raw:
                            text = _extract_text_from_raw_layout(block.raw) or ""
                            if text:
                                text_source = "block.raw (retry)"
                    
                    if not text.strip():
                        skipped_count += 1
                        total_blocks_skipped += 1
                        continue
                    
                    # Special handling for table blocks: interpret text as markdown-style/HTML/image table
                    if block.type == "table":
                        if _render_table_block(
                            c,
                            block,
                            text,
                            page_height,
                            table_body_format=table_body_format,
                            image_data_map=image_data_map,
                            translated_text_by_block_index=translated_text_by_block_index,
                            target_language=target_language,
                            type_font_baselines=type_font_baselines,
                        ):
                            rendered_count += 1
                            total_blocks_rendered += 1
                            continue
                        else:
                            logger.warning(
                                f"[REPORTLAB] Page {page_idx}, Block {block_idx} (index={block.index}, type=table): "
                                f"failed to render as table, falling back to plain text"
                            )

                    rendered_count += 1
                    total_blocks_rendered += 1
                    
                    # Detect language to choose appropriate font
                    try:
                        lang = _detect_text_language(text)
                        font_name = _get_font_name_for_language(lang)
                    except Exception as e:
                        logger.error(LogModule.LAYOUT, f"[REPORTLAB] Error preparing text for block {block_idx} on page {page_idx}: {e}", exc_info=True)
                        continue
                    
                    # Estimate number of lines for font size adjustment
                    estimated_lines = text.count('\n') + 1
                    if len(text) > 50 and width > 0:
                        # Rough estimate: if text is long, likely wraps
                        avg_chars_per_line = max(1, int(width / 6))  # Rough estimate
                        estimated_lines = max(estimated_lines, int(len(text) / avg_chars_per_line))
                    
                    # 计算字号：
                    # - 对于 text / title：直接基于各自 block 的 bbox + 文本估算字号，再合并成少数几个典型字号
                    #   （先用 _estimate_initial_font_size 按高度/宽度/行数估算，再用 _quantize_font_size 做离散化）
                    #   Title 使用更大的系数（1.0 或 1.05）使其字号更大
                    # Use new unified font size calculation:
                    # - For text and title: use adjustable font size (based on unified baseline with 1.0pt step)
                    # - For other types: use unified baseline directly (0.5pt step)
                    # The get_font_size_from_type_baseline method now handles text/title adjustment automatically
                    font_size = _get_font_size_from_type_baseline(
                        type_font_baselines,
                        block.type,
                        text,
                        block=block,
                        canvas_obj=c,
                        font_name=font_name,
                    )
                    
                    # Set font with fallback handling
                    font_name = _set_font_with_fallback(c, font_name, font_size, lang)
                    
                    # Try to get actual text width from layout data (more accurate than block bbox)
                    actual_text_width = None
                    if block.raw:
                        actual_text_width = _get_text_actual_width_from_layout(block.raw)
                    
                    # Extract original line structure and line heights from layout
                    original_lines = None
                    original_line_heights = []
                    if block.raw:
                        original_lines = _extract_original_line_structure_from_layout(block.raw)
                        original_line_heights = _extract_line_heights_from_layout(block.raw)
                    
                    # IMPORTANT: Always use block width for wrapping, not actual_text_width
                    # actual_text_width might be the width of original single-line text, which would prevent wrapping
                    # We want to wrap based on the available block width, not the original text width
                    text_width_for_wrapping = width  # Always use block width to ensure proper wrapping
                    
                    # Check if text contains explicit newlines first
                    if '\n' in text:
                        # Text has explicit line breaks, split by newlines and wrap each line
                        text_lines = []
                        for line in text.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            # Wrap each line individually
                            wrapped = _wrap_text_to_width(line, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                            text_lines.extend(wrapped)
                    else:
                        # No explicit newlines, wrap based on width
                        # Always wrap to ensure text fits within block width
                        text_lines = _wrap_text_to_width(text, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                    
                    # Ensure we have at least one line
                    if not text_lines and text.strip():
                        text_lines = [text.strip()]
                    
                    # 根据实际 wrap 出来的行数，迭代调整字号和重新换行，直到收敛
                    # This iterative process ensures font size and line count are consistent
                    original_font_size_before_adjustment = font_size
                    font_size_ratio = 1.0
                    max_font_size_iterations = 10  # Increased to 10 iterations for better convergence
                    font_size_converged = False
                    
                    for font_iter in range(max_font_size_iterations):
                        if len(text_lines) == 0 or height <= 0:
                            break
                        
                        old_font_size = font_size
                        old_line_count = len(text_lines)
                        
                        # Calculate estimated total height with current font size and line count
                        estimated_line_height = font_size * 1.2  # Standard line height
                        estimated_total_height = len(text_lines) * estimated_line_height
                        
                        # Calculate available height based on line count
                        # Single line bbox doesn't include line spacing, multi-line includes (n-1) spacings
                        available_height = _calculate_available_height_for_lines(
                            bbox_height=height,
                            line_count=len(text_lines),
                            font_size=font_size,
                            line_spacing_ratio=1.2
                        )
                        
                        # Check if this is ref_text or caption block (used in both if and else branches)
                        # caption includes both image_caption and table_caption (unified for consistent font sizing)
                        is_ref_text = block.type == "ref_text"
                        is_caption = block.type in (IMAGE_CAPTION, TABLE_CAPTION, CAPTION)
                        is_unified_baseline_block = is_ref_text or is_caption
                        
                        # Check if total height exceeds available space
                        # For ref_text and caption: skip font size reduction in main iteration loop to preserve unified baseline
                        # The global baseline search already ensures all ref_text and caption blocks can fit with the baseline
                        # Height tolerance: 5% of line height per line (not 5% of bbox height)
                        estimated_line_height = font_size * 1.2
                        tolerance_per_line = estimated_line_height * 0.05
                        max_allowed_height = available_height + len(text_lines) * tolerance_per_line
                        
                        if estimated_total_height > max_allowed_height:
                            if is_unified_baseline_block:
                                # For ref_text and caption, don't reduce font size here - keep the unified baseline
                                # If it overflows, it will be handled by Final adjustment (which we skip for these types)
                                # or we'll just log a warning
                                pass
                            else:
                                # Total height exceeds, need to reduce font size
                                # Calculate required font size to fit exactly
                                required_line_height = available_height / len(text_lines) if len(text_lines) > 0 else font_size * 1.2
                                # Line height = font_size * 1.2, so font_size = line_height / 1.2
                                required_font_size = required_line_height / 1.2
                                # Use 95% of required to add safety margin
                                font_size = max(7.0, required_font_size * 0.95)
                                font_size = round(font_size, 1)
                            
                        else:
                            # Height fits, check if we can optimize font size
                            # Calculate maximum font size that fits the current line count
                            # Use 0.90 instead of 0.85 to allow larger font sizes
                            # This accounts for line spacing (typically 1.15-1.2x font size)
                            max_font_from_height = (height / len(text_lines)) * 0.90
                            
                            # Special handling for ref_text and caption: optimize to reduce gaps while maintaining unified font size
                            # For ref_text, we want to fill the bbox better (reduce gap between references)
                            # For caption, we want consistent font size across all captions
                            # but still keep font size unified across all blocks of the same type
                            if is_unified_baseline_block:
                                # Calculate height utilization ratio
                                height_utilization = estimated_total_height / available_height if available_height > 0 else 0
                                
                                # If height utilization is too low (< 80%), try to increase font size to fill bbox better
                                # But ensure we don't exceed the baseline too much (max 10% increase from baseline)
                                if height_utilization < 0.80 and font_size < max_font_from_height:
                                    # Try to increase font size to improve height utilization
                                    # Target: use at least 85% of available height
                                    target_height_utilization = 0.85
                                    target_total_height = available_height * target_height_utilization
                                    target_line_height = target_total_height / len(text_lines) if len(text_lines) > 0 else font_size * 1.2
                                    target_font_size = target_line_height / 1.2
                                    
                                    # But limit increase: don't exceed baseline by more than 10%
                                    max_allowed_font_size = original_font_size_before_adjustment * 1.10
                                    target_font_size = min(target_font_size, max_font_from_height, max_allowed_font_size)
                                    
                                    if target_font_size > font_size:
                                        font_size = max(7.0, round(target_font_size, 1))
                                        # (Info logging removed - ref_text optimization)
                            
                            # Check if font size needs adjustment
                            # Height tolerance: 5% of line height per line (not 5% of bbox height)
                            estimated_line_height = font_size * 1.2
                            tolerance_per_line = estimated_line_height * 0.05
                            max_allowed_height = available_height + len(text_lines) * tolerance_per_line
                            
                            if abs(font_size - max_font_from_height) < 0.1:  # Converged (within 0.1pt)
                                # Verify total height still fits (with line-height-based tolerance)
                                if estimated_total_height <= max_allowed_height:
                                    font_size_converged = True
                                    break
                                else:
                                    # Still exceeds, reduce font size
                                    required_line_height = available_height / len(text_lines) if len(text_lines) > 0 else font_size * 1.2
                                    required_font_size = required_line_height / 1.2
                                    font_size = max(7.0, required_font_size * 0.95)
                                    font_size = round(font_size, 1)
                            elif font_size > max_font_from_height:
                                # Font size too large, reduce it
                                font_size = max(7.0, round(max_font_from_height, 1))
                            else:
                                # Font size fits, but check if we can increase it slightly
                                # For non-ref_text blocks, allow up to 2% larger if there's room
                                # For ref_text, we already handled optimization above
                                if not is_ref_text:
                                    optimal_font_size = max_font_from_height * 1.02
                                    if optimal_font_size > font_size:
                                        font_size = min(optimal_font_size, font_size * 1.02)
                                        font_size = max(7.0, round(font_size, 1))
                                    else:
                                        # Already optimal, check if height fits (with line-height-based tolerance)
                                        if estimated_total_height <= max_allowed_height:
                                            font_size_converged = True
                                            break
                                else:
                                    # For ref_text, check if we've optimized enough (with line-height-based tolerance)
                                    if estimated_total_height <= max_allowed_height:
                                        font_size_converged = True
                                        break
                        
                        # Apply new font size with fallback handling
                        font_name = _set_font_with_fallback(c, font_name, font_size, lang)
                        
                        # Re-wrap text with the new font size
                        if '\n' in text:
                            # Text has explicit line breaks, split by newlines and wrap each line
                            new_text_lines = []
                            for line in text.split('\n'):
                                line = line.strip()
                                if not line:
                                    continue
                                # Wrap each line individually with adjusted font size
                                wrapped = _wrap_text_to_width(line, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                                new_text_lines.extend(wrapped)
                        else:
                            # No explicit newlines, wrap based on width with adjusted font size
                            new_text_lines = _wrap_text_to_width(text, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                        
                        # Ensure we have at least one line
                        if not new_text_lines and text.strip():
                            new_text_lines = [text.strip()]
                        
                        # Check if line count changed significantly
                        line_count_change = abs(len(new_text_lines) - len(text_lines))
                        text_lines = new_text_lines
                        
                        # If line count didn't change and font size is stable, verify height fits
                        if line_count_change == 0 and abs(font_size - old_font_size) < 0.1:
                            # Recalculate with actual line count
                            estimated_line_height = font_size * 1.2
                            estimated_total_height = len(text_lines) * estimated_line_height
                            
                            # Improved available_height calculation to prevent it from becoming too small
                            if height < font_size * 1.5:
                                # For very small blocks, use 90% of height as available space
                                available_height = height * 0.9
                            else:
                                # For normal blocks, account for font metrics space
                                estimated_font_ascent = font_size * 0.75
                                font_metrics_space = estimated_font_ascent + font_size * 0.25
                                available_height = height - font_metrics_space
                            
                            # Ensure available_height is at least 30% of height (safety margin)
                            available_height = max(available_height, height * 0.3)
                            
                            # Height tolerance: 5% of line height per line (not 5% of bbox height)
                            tolerance_per_line = estimated_line_height * 0.05
                            max_allowed_height = available_height + len(text_lines) * tolerance_per_line
                            
                            if estimated_total_height <= max_allowed_height:
                                font_size_converged = True
                                break
                    
                    # Calculate final font size ratio
                    if original_font_size_before_adjustment > 0:
                        font_size_ratio = font_size / original_font_size_before_adjustment
                    else:
                        font_size_ratio = 1.0
                    
                    # Log final result
                    if not font_size_converged:
                        logger.warning(
                            f"[REPORTLAB] Page {page_idx}, Block {block_idx}: Font size adjustment did not fully converge "
                            f"after {max_font_size_iterations} iterations. "
                            f"Final: font_size={font_size:.1f}pt, lines={len(text_lines)}, height={height:.1f}pt"
                        )
                    
                    # Note: ref_text blocks now rely on the global baseline search in
                    # _compute_type_font_baselines for a unified font size. We no longer
                    # apply per-block fine-tuning here to keep all citations consistent.

                    # Calculate line height for this block
                    # Priority:
                    # 1) Use original layout line heights if available.
                    # 2) Otherwise, estimate from font_size and block height.
                    # Initialize line_heights to avoid UnboundLocalError
                    line_heights: List[float] = []
                    
                    # Fall back to layout-based heights
                    if original_line_heights and len(original_line_heights) > 0:
                        # Use actual line heights from original layout, but validate against block height
                        # Calculate if original line heights can fit in the block
                        # Improved available_height calculation to prevent it from becoming too small
                        if height < font_size * 1.5:
                            # For very small blocks, use 90% of height as available space
                            available_height = height * 0.9
                        else:
                            # For normal blocks, account for font metrics space
                            estimated_font_ascent = font_size * 0.75
                            font_metrics_space = estimated_font_ascent + font_size * 0.25
                            available_height = height - font_metrics_space
                        
                        # Ensure available_height is at least 30% of height (safety margin)
                        available_height = max(available_height, height * 0.3)
                        
                        # Define reasonable line height bounds to prevent excessive spacing
                        # line_height should be between font_size * 1.15 (tight) and font_size * 1.4 (loose)
                        # This ensures line spacing is reasonable (15-40% of font size)
                        min_line_height_reasonable = font_size * 1.15  # Minimum reasonable line height
                        max_line_height_reasonable = font_size * 1.4   # Maximum reasonable line height (prevents excessive spacing)
                        
                        if len(text_lines) == len(original_line_heights):
                                # Same number of lines: check if original heights fit
                                # Apply font size ratio to original line heights first
                                adjusted_original_heights = [h * font_size_ratio for h in original_line_heights]
                                
                                # Clamp adjusted heights to reasonable range to prevent excessive spacing
                                clamped_heights = [
                                    max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                    for h in adjusted_original_heights
                                ]
                                
                                total_original_height = sum(clamped_heights)
                                
                                if total_original_height <= available_height * 1.1:  # Allow 10% tolerance
                                    # Adjusted original heights fit, use clamped heights
                                    # CRITICAL: Ensure each line height is at least font_size (no negative spacing)
                                    line_heights = [max(font_size, h) for h in clamped_heights]
                                else:
                                    # Adjusted original heights still too large, scale them down proportionally
                                    scale_factor = available_height / total_original_height
                                    scaled_heights = [h * scale_factor for h in clamped_heights]
                                    
                                    # Clamp scaled heights to reasonable range
                                    scaled_heights = [
                                        max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                        for h in scaled_heights
                                    ]
                                    
                                    # Ensure total doesn't exceed available height
                                    total_scaled = sum(scaled_heights)
                                    if total_scaled > available_height:
                                        # Scale down further
                                        final_scale = available_height / total_scaled
                                        line_heights = [h * final_scale for h in scaled_heights]
                                        # Final clamp to ensure reasonable spacing
                                        line_heights = [
                                            max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                            for h in line_heights
                                        ]
                                    else:
                                        line_heights = scaled_heights
                                    
                                    # CRITICAL: Ensure each line height is at least font_size (no negative spacing)
                                    line_heights = [max(font_size, h) for h in line_heights]
                        elif len(text_lines) > 0:
                            # Different number of lines: calculate average and distribute
                            # Apply font size ratio to original line heights first
                            adjusted_original_heights = [h * font_size_ratio for h in original_line_heights]
                            
                            # Define reasonable bounds
                            min_line_height_reasonable = font_size * 1.15
                            max_line_height_reasonable = font_size * 1.4
                            
                            # Clamp adjusted heights to reasonable range
                            clamped_heights = [
                                max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                for h in adjusted_original_heights
                            ]
                            
                            avg_line_height = sum(clamped_heights) / len(clamped_heights)
                            # Calculate max per-line height based on available space
                            max_per_line = available_height / len(text_lines) if len(text_lines) > 0 else font_size * 1.2
                            # Use the smaller of: average adjusted original height or max that fits
                            line_height = min(avg_line_height, max_per_line)
                            # Clamp to reasonable range
                            # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                            line_height = max(min_line_height_reasonable, font_size, min(line_height, max_line_height_reasonable))
                            line_heights = [line_height] * len(text_lines)
                        else:
                            # Fallback: use average of original line heights, but validate
                            adjusted_original_heights = [h * font_size_ratio for h in original_line_heights]
                            
                            # Define reasonable bounds
                            min_line_height_reasonable = font_size * 1.15
                            max_line_height_reasonable = font_size * 1.4
                            
                            # Clamp adjusted heights to reasonable range
                            clamped_heights = [
                                max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                for h in adjusted_original_heights
                            ]
                            
                            avg_line_height = sum(clamped_heights) / len(clamped_heights)
                            max_per_line = available_height if available_height > 0 else font_size * 1.2
                            line_height = min(avg_line_height, max_per_line)
                            # Clamp to reasonable range
                            # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                            line_height = max(min_line_height_reasonable, font_size, min(line_height, max_line_height_reasonable))
                            line_heights = [line_height] if text_lines else []
                    elif len(text_lines) > 0:
                        # No original line heights available: calculate based on font size
                        # Use font_size * 1.2 as base line height (standard line spacing)
                        base_line_height = font_size * 1.2
                        
                        # Define reasonable line height bounds (15-40% spacing above font size)
                        min_line_height_reasonable = font_size * 1.15  # 15% spacing (tight)
                        max_line_height_reasonable = font_size * 1.4   # 40% spacing (loose, prevents excessive spacing)
                        
                        # Estimate font ascent (used for first line positioning)
                        # For most fonts, ascent is approximately 0.7-0.8 * font_size
                        estimated_font_ascent = font_size * 0.75
                        
                        # Calculate maximum line height that fits in block
                        # We need to fit all lines within the block height
                        # The first line's baseline is at (top - font_ascent), so we need:
                        # font_ascent + (n-1) * line_height + font_descent <= height
                        # For simplicity, we use: n * line_height <= height (conservative estimate)
                        # This ensures all lines fit, accounting for ascent/descent
                        if len(text_lines) == 1:
                            max_line_height_from_block = height
                        else:
                            # Distribute available height across all lines
                            # Use a more conservative calculation: account for font ascent/descent
                            # Improved available_height calculation to prevent it from becoming too small
                            if height < font_size * 1.5:
                                # For very small blocks, use 90% of height as available space
                                available_height = height * 0.9
                            else:
                                # For normal blocks, account for font metrics space
                                font_metrics_space = estimated_font_ascent + font_size * 0.25  # ascent + some descent
                                available_height = height - font_metrics_space
                            
                            # Ensure available_height is at least 30% of height (safety margin)
                            available_height = max(available_height, height * 0.3)
                            
                            # Divide by number of lines to get max per-line height
                            max_line_height_from_block = available_height / len(text_lines) if available_height > 0 and len(text_lines) > 0 else base_line_height
                        
                        # Use the smaller of: base_line_height or max_line_height_from_block
                        # But clamp to reasonable range to prevent excessive spacing
                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                        if max_line_height_from_block >= base_line_height:
                            # Block is tall enough for base line height
                            line_height = base_line_height
                        else:
                            # Block is too short, use max that fits but ensure minimum
                            # Ensure line_height is at least font_size (no negative spacing)
                            line_height = max(max_line_height_from_block, min_line_height_reasonable, font_size)
                        
                        # Clamp to reasonable range to prevent excessive spacing
                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                        line_height = max(min_line_height_reasonable, font_size, min(line_height, max_line_height_reasonable))
                        
                        line_heights = [line_height] * len(text_lines)
                    else:
                        # Fallback: use fixed multiplier
                        line_height = font_size * 1.2
                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                        line_height = max(font_size, line_height)
                        line_heights = [line_height] if text_lines else []
                    
                    # Ensure line_heights is properly initialized for all text_lines
                    if text_lines and not line_heights:
                        # If we have text_lines but line_heights is still empty, use default
                        line_height = font_size * 1.2
                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                        line_height = max(font_size, line_height)
                        line_heights = [line_height] * len(text_lines)
                    
                    # Final safety check: Ensure all line heights are at least font_size (no negative spacing)
                    if text_lines and line_heights:
                        for i, h in enumerate(line_heights):
                            if h < font_size:
                                logger.warning(
                                    f"[REPORTLAB] Page {page_idx}, Block {block_idx}: Line {i} height {h:.1f}pt < font_size {font_size:.1f}pt, "
                                    f"adjusting to {font_size:.1f}pt to prevent negative spacing"
                                )
                                line_heights[i] = font_size
                    
                    # Final validation & collision-aware adjustment:
                    # 1) ensure total rendered height is reasonable for this block
                    # 2) optionally check whether this block's rendered region invades other blocks on the same page
                    if text_lines and line_heights and height > 0:
                        # For ref_text and caption: skip Final adjustment to maintain unified font size from global baseline
                        # The global baseline search already ensures all ref_text and caption blocks can fit with the baseline
                        # caption includes both image_caption and table_caption (unified for consistent font sizing)
                        is_ref_text_block = block.type == "ref_text"
                        is_caption_block = block.type in (IMAGE_CAPTION, TABLE_CAPTION, CAPTION)
                        is_unified_baseline_block_final = is_ref_text_block or is_caption_block
                        if is_unified_baseline_block_final:
                            # Skip Final adjustment for ref_text to preserve unified font size
                            # Only check if it fits (with tolerance), but don't reduce font size
                            total_rendered_height = sum(line_heights)
                            
                            # Improved available_height calculation to prevent it from becoming too small
                            if height < font_size * 1.5:
                                # For very small blocks, use 90% of height as available space
                                available_height = height * 0.9
                            else:
                                # For normal blocks, account for font metrics space
                                estimated_font_ascent = font_size * 0.75
                                font_metrics_space = estimated_font_ascent + font_size * 0.25
                                available_height = height - font_metrics_space
                            
                            # Ensure available_height is at least 30% of height (safety margin)
                            available_height = max(available_height, height * 0.3)
                            
                            # Height tolerance: ref_text 8% per line to allow slight overflow; others 5%
                            estimated_line_height = font_size * 1.2
                            ref_tolerance_ratio = 0.08 if is_ref_text_block else 0.05
                            tolerance_per_line = estimated_line_height * ref_tolerance_ratio
                            max_allowed_height = available_height + len(text_lines) * tolerance_per_line
                            
                            if total_rendered_height > max_allowed_height:
                                logger.warning(
                                    f"[REPORTLAB] Page {page_idx}, Block {block_idx} (ref_text): "
                                    f"Rendered height ({total_rendered_height:.1f}pt) exceeds max allowed height ({max_allowed_height:.1f}pt, "
                                    f"available={available_height:.1f}pt + {len(text_lines)} lines * {tolerance_per_line:.2f}pt tolerance) "
                                    f"but keeping unified font_size={font_size:.2f}pt (baseline={type_font_baselines.get('ref_text', 'N/A')})",
                                    module=LogModule.RESTOR
                                )
                        else:
                            # Step 1: height-based adjustment inside this block's bbox (for non-ref_text blocks)
                            max_final_adjustment_iterations = 5  # Additional iterations for final adjustment
                            for final_iter in range(max_final_adjustment_iterations):
                                total_rendered_height = sum(line_heights)
                                
                                # Calculate available height based on line count
                                # Single line bbox doesn't include line spacing, multi-line includes (n-1) spacings
                                available_height = _calculate_available_height_for_lines(
                                    bbox_height=height,
                                    line_count=len(text_lines),
                                    font_size=font_size,
                                    line_spacing_ratio=1.2
                                )
                                
                                # Height tolerance: 5% of line height per line (not 5% of bbox height)
                                estimated_line_height = font_size * 1.2
                                tolerance_per_line = estimated_line_height * 0.05
                                max_allowed_height = available_height + len(text_lines) * tolerance_per_line
                                
                                if total_rendered_height <= max_allowed_height:
                                    # Height fits, we're done
                                    break
                                
                                # Total height exceeds available space, need to reduce font size
                                # Calculate required line height to fit exactly
                                if len(text_lines) > 0 and available_height > 0:
                                    required_line_height = available_height / len(text_lines)
                                    # Line height = font_size * 1.2, so font_size = line_height / 1.2
                                    required_font_size = required_line_height / 1.2
                                    # Use 95% of required to add safety margin, but never below 6pt
                                    old_font_size = font_size
                                    font_size = max(6.0, required_font_size * 0.95)
                                else:
                                    # Fallback: reduce font size by 5% per iteration
                                    old_font_size = font_size
                                    font_size = max(6.0, font_size * 0.95)
                                font_size = round(font_size, 1)
                                
                                logger.debug(
                                    f"[REPORTLAB] Page {page_idx}, Block {block_idx}, Final adjustment iteration {final_iter + 1}: "
                                    f"Total rendered height ({total_rendered_height:.1f}pt) exceeds available height ({available_height:.1f}pt). "
                                    f"Reducing font_size from {old_font_size:.1f}pt to {font_size:.1f}pt "
                                    f"(required_font_size={required_font_size:.1f}pt)"
                                )
                                
                                # Apply new font size
                                try:
                                    c.setFont(font_name, font_size)
                                except Exception as e:
                                    # (Debug logging removed)
                                    font_name = "Helvetica"
                                    c.setFont(font_name, font_size)
                                
                                # Re-wrap with final font size
                                if '\n' in text:
                                    text_lines = []
                                    for line in text.split('\n'):
                                        line = line.strip()
                                        if not line:
                                            continue
                                        wrapped = _wrap_text_to_width(line, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                                        text_lines.extend(wrapped)
                                else:
                                    text_lines = _wrap_text_to_width(text, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                                
                                if not text_lines and text.strip():
                                    text_lines = [text.strip()]
                                
                                # Recalculate line heights with new font size
                                font_size_ratio = font_size / old_font_size if old_font_size > 0 else 1.0
                                base_line_height = font_size * 1.2
                                min_line_height_reasonable = font_size * 1.15
                                max_line_height_reasonable = font_size * 1.4
                                
                                # Recalculate line heights
                                if original_line_heights and len(original_line_heights) > 0:
                                    adjusted_original_heights = [h * font_size_ratio for h in original_line_heights]
                                    clamped_heights = [
                                        max(min_line_height_reasonable, min(h, max_line_height_reasonable))
                                        for h in adjusted_original_heights
                                    ]
                                    if len(text_lines) == len(clamped_heights):
                                        # Ensure each line height is at least font_size (no negative spacing)
                                        line_heights = [max(font_size, h) for h in clamped_heights]
                                    else:
                                        avg_line_height = sum(clamped_heights) / len(clamped_heights) if clamped_heights else base_line_height
                                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                                        line_height = max(min_line_height_reasonable, font_size, min(avg_line_height, max_line_height_reasonable))
                                        line_heights = [line_height] * len(text_lines)
                                else:
                                    # Calculate based on available height
                                    if len(text_lines) > 1:
                                        # Improved available_height calculation to prevent it from becoming too small
                                        if height < font_size * 1.5:
                                            # For very small blocks, use 90% of height as available space
                                            available_height = height * 0.9
                                        else:
                                            # For normal blocks, account for font metrics space
                                            estimated_font_ascent = font_size * 0.75
                                            font_metrics_space = estimated_font_ascent + font_size * 0.25
                                            available_height = height - font_metrics_space
                                        
                                        # Ensure available_height is at least 30% of height (safety margin)
                                        available_height = max(available_height, height * 0.3)
                                        
                                        max_line_height_from_block = available_height / len(text_lines) if available_height > 0 and len(text_lines) > 0 else base_line_height
                                        line_height = max(min_line_height_reasonable, font_size, min(base_line_height, max_line_height_from_block))
                                        # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                                        line_height = max(min_line_height_reasonable, font_size, min(line_height, max_line_height_reasonable))
                                    else:
                                        line_height = base_line_height
                                    # CRITICAL: Ensure line_height >= font_size (no negative spacing)
                                    line_height = max(font_size, line_height)
                                    line_heights = [line_height] * len(text_lines)
                                
                                # Verify final height after this iteration
                                final_total_height = sum(line_heights)
                                if final_total_height <= available_height * 1.02:
                                    break
                        
                        # Step 2: optional collision-aware adjustment across blocks on the same page
                        # Skip collision check for ref_text to maintain unified font size
                        if ENABLE_BLOCK_COLLISION_CHECK and text_lines and line_heights and not is_ref_text_block:
                            page_blocks_info = page_block_bboxes[page_idx] if page_idx < len(page_block_bboxes) else None
                            if page_blocks_info:
                                max_collision_iterations = 5
                                for coll_iter in range(max_collision_iterations):
                                    rendered_height = sum(line_heights)
                                    
                                    # Quick check: if rendered height already fits inside this block's bbox,
                                    # collision with vertically non-overlapping blocks is unlikely.
                                    if rendered_height <= height:
                                        break
                                    
                                    has_collision = _check_block_collision_with_page(
                                        page_blocks_info,
                                        page_idx,
                                        block_idx,
                                        x0,
                                        y0,
                                        x1,
                                        rendered_height,
                                        block.type or "unknown",
                                    )
                                    
                                    if not has_collision:
                                        break
                                    
                                    if font_size <= 6.0:
                                        logger.warning(
                                            f"[REPORTLAB] Page {page_idx}, Block {block_idx}: Collision detected but font_size already at minimum 6.0pt. "
                                            f"Keeping current settings (rendered_height={rendered_height:.1f}pt, bbox_height={height:.1f}pt)"
                                        )
                                        break
                                    
                                    # Compute a target font size to better fit into this block's height
                                    # Assume rendered height roughly scales linearly with font size
                                    # Safety check: avoid division by zero
                                    if rendered_height <= 0:
                                        logger.warning(
                                            f"[REPORTLAB] Page {page_idx}, Block {block_idx}: rendered_height is zero or negative: {rendered_height}. "
                                            f"Using current font_size={font_size:.1f}pt"
                                        )
                                        target_font_size = font_size
                                    else:
                                        target_font_size = font_size * (height / rendered_height) * 0.95
                                    target_font_size = max(6.0, min(font_size, target_font_size))
                                    old_font_size = font_size
                                    font_size = round(target_font_size, 1)
                                    
                                    # Apply new font size
                                    try:
                                        c.setFont(font_name, font_size)
                                    except Exception as e:
                                        # (Debug logging removed)
                                        font_name = "Helvetica"
                                        c.setFont(font_name, font_size)
                                    
                                    # Re-wrap with new font size
                                    if '\n' in text:
                                        text_lines = []
                                        for line in text.split('\n'):
                                            line = line.strip()
                                            if not line:
                                                continue
                                            wrapped = _wrap_text_to_width(line, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                                            text_lines.extend(wrapped)
                                    else:
                                        text_lines = _wrap_text_to_width(text, text_width_for_wrapping, font_name=font_name, font_size=font_size, canvas_obj=c)
                                    
                                    if not text_lines and text.strip():
                                        text_lines = [text.strip()]
                                    
                                    # Recalculate line heights with new font size (simple block-based estimation)
                                    base_line_height = font_size * 1.2
                                    min_line_height_reasonable = font_size * 1.15
                                    max_line_height_reasonable = font_size * 1.4
                                    
                                    if len(text_lines) > 1:
                                        estimated_font_ascent = font_size * 0.75
                                        font_metrics_space = estimated_font_ascent + font_size * 0.25
                                        available_height_for_lines = height - font_metrics_space
                                        if available_height_for_lines > 0:
                                            max_line_height_from_block = available_height_for_lines / len(text_lines)
                                        else:
                                            max_line_height_from_block = base_line_height
                                        line_height = max(min_line_height_reasonable, min(base_line_height, max_line_height_from_block, max_line_height_reasonable))
                                    else:
                                        line_height = max(min_line_height_reasonable, min(base_line_height, height, max_line_height_reasonable))
                                    
                                    line_heights = [line_height] * len(text_lines)
                    
                    # Force left alignment for all text (user requirement)
                    # Previously detected alignment from layout, but now all text is left-aligned
                    alignment = 'left'
                    
                    # Calculate font ascent for accurate Y positioning
                    # drawString uses baseline, so we need to account for ascent
                    # Try to get actual ascent from ReportLab's font metrics
                    # If unavailable, fall back to estimated ratio (0.718 for Helvetica, ~0.7-0.8 for most fonts)
                    try:
                        font_ascent = pdfmetrics.getAscent(font_name, font_size)
                        # Verify the result is reasonable (should be positive and less than font_size)
                        if font_ascent <= 0 or font_ascent > font_size:
                            # Fall back to estimated ratio if getAscent returns invalid value
                            font_ascent = font_size * 0.718  # More accurate than 0.75 based on actual measurements
                    except (KeyError, AttributeError, TypeError):
                        # Font not registered or getAscent not available, use estimated ratio
                        # For most fonts, ascent is approximately 0.7-0.8 * font_size
                        # Using 0.718 which is the actual ratio for Helvetica (most common fallback font)
                        font_ascent = font_size * 0.718
                    
                    # Render text lines using textobject for better multi-line control
                    # textobject provides more precise control over line spacing and positioning
                    # Start from top of block, accounting for font ascent
                    # textobject uses baseline coordinates, so we position at (top - ascent)
                    start_y = pdf_y1 - font_ascent
                    
                    # Ensure line_heights is properly initialized
                    if len(text_lines) > 1 and not line_heights:
                        # Fallback: use default line height if not calculated
                        line_heights = [font_size * 1.2] * len(text_lines)
                    
                    # Use textobject for better multi-line text rendering
                    # This provides more precise control over line spacing
                    text_obj = c.beginText()
                    text_obj.setFont(font_name, font_size)
                    
                    # Set initial position based on alignment
                    # For left alignment, x is x0
                    # For center/right, we'll adjust per line
                    current_y = start_y
                    rendered_line_count = 0
                    
                    for line_idx, line in enumerate(text_lines):
                        # 只在接近页面底部时停止，忽略 block 的 bbox 限制，确保整段文本尽量完整输出
                        # 注意：current_y 是基线坐标，0 附近已经接近物理页面底边
                        if current_y < 0:
                            break  # 避免画到页面之外
                        
                        # Get line height for this line
                        if line_idx < len(line_heights):
                            line_height = line_heights[line_idx]
                        elif line_heights:
                            line_height = line_heights[-1]
                        else:
                            line_height = font_size * 1.2
                        
                        # Calculate text width for alignment (using block-level font)
                        # CRITICAL: Verify line width doesn't exceed bbox width
                        try:
                            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                        except Exception as e:
                            logger.error(LogModule.LAYOUT, f"[REPORTLAB] Error calculating line width for page {page_idx}, block {block_idx}, line {line_idx}: {e}", exc_info=True)
                            continue
                        
                        # CRITICAL: Strict width limit - line width MUST NOT exceed bbox width
                        # Check and fix line width if necessary (using shared utility)
                        fixed_lines = _check_and_fix_line_width(line, font_name, font_size, width, c)
                        if len(fixed_lines) > 1:
                            # Line was split, need to insert additional lines
                            logger.debug(
                                f"[REPORTLAB] Line {line_idx} in block {block_idx} on page {page_idx} "
                                f"exceeded bbox width and was split into {len(fixed_lines)} lines",
                                module=LogModule.RESTOR
                            )
                            # Replace current line with first fixed line, insert rest after
                            line = fixed_lines[0]
                            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                            # Insert remaining fixed lines after current position
                            text_lines[line_idx+1:line_idx+1] = fixed_lines[1:]
                            # Recalculate line_heights if needed
                            if len(text_lines) > len(line_heights):
                                additional_heights = [line_heights[-1] if line_heights else font_size * 1.2] * (len(text_lines) - len(line_heights))
                                line_heights.extend(additional_heights)
                        else:
                            # Line fits or was truncated (single line returned)
                            line = fixed_lines[0]
                            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                            if not line:
                                continue
                        
                        # Determine x position based on alignment
                        if alignment == 'center':
                            text_x = x0 + (width - line_width) / 2
                        elif alignment == 'right':
                            text_x = x0 + width - line_width
                        else:  # left (default)
                            text_x = x0
                        
                        # CRITICAL: Ensure text_x is within bbox bounds
                        if text_x < x0:
                            text_x = x0
                        elif text_x + line_width > x1:
                            # Text would extend beyond bbox right edge
                            text_x = x0  # Force left alignment to keep within bbox
                        
                        # Render this line with per-language font segments.
                        # We keep a single font_size for the entire block/line,
                        # but choose fonts per segment to avoid tofu while improving Latin appearance.
                        segments = _split_text_by_language_segments(line)
                        current_x = text_x
                        for seg_text, seg_lang in segments:
                            if not seg_text:
                                continue
                            _, seg_font_name = _detect_and_get_font_for_text(seg_text, target_language)
                            try:
                                text_obj.setFont(seg_font_name, font_size)
                            except Exception:
                                # Fallback to block-level font, then to Helvetica
                                try:
                                    text_obj.setFont(font_name, font_size)
                                    seg_font_name = font_name
                                except Exception:
                                    text_obj.setFont("Helvetica", font_size)
                                    seg_font_name = "Helvetica"

                            # Set origin for this segment and draw it
                            text_obj.setTextOrigin(current_x, current_y)
                            text_obj.textOut(seg_text)

                            # Advance x by segment width (using its own font)
                            try:
                                seg_width = pdfmetrics.stringWidth(seg_text, seg_font_name, font_size)
                            except Exception:
                                seg_width = 0
                            current_x += seg_width
                        
                        rendered_line_count += 1
                        
                        # Move to next line position
                        # After rendering segments, the conceptual end of the line is at (text_x + line_width, current_y)
                        # We need to move to the next line's starting position
                        if line_idx < len(text_lines) - 1:  # Not the last line
                            # Calculate next line's x position (may change if alignment is center/right)
                            next_line = text_lines[line_idx + 1]
                            try:
                                next_line_width = pdfmetrics.stringWidth(next_line, font_name, font_size)
                            except Exception:
                                next_line_width = 0
                            
                            if alignment == 'center':
                                next_text_x = x0 + (width - next_line_width) / 2
                            elif alignment == 'right':
                                next_text_x = x0 + width - next_line_width
                            else:
                                next_text_x = x0
                            
                            # Move cursor to next line position
                            # After textOut, cursor is at (text_x + line_width, current_y)
                            # We need to move to (next_text_x, current_y - line_height)
                            # Calculate relative movement
                            current_cursor_x = text_x + line_width
                            dx = next_text_x - current_cursor_x
                            dy = -line_height
                            text_obj.moveCursor(dx, dy)
                            current_y -= line_height
                    
                    # Draw all text lines at once
                    try:
                        c.drawText(text_obj)
                        
                        # Log ref_text font size for diagnosis
                        if block.type == "ref_text":
                            total_rendered_height = sum(line_heights) if line_heights else len(text_lines) * font_size * 1.2
                            logger.debug(
                                f"[REPORTLAB] ref_text rendered: Page {page_idx}, Block {block_idx} (index={block.index}): "
                                f"font_size={font_size:.2f}pt, lines={len(text_lines)}, "
                                f"bbox_height={height:.2f}pt, rendered_height={total_rendered_height:.2f}pt, "
                                f"baseline_from_type={type_font_baselines.get('ref_text', 'N/A')}, "
                                f"original_baseline={original_font_size_before_adjustment:.2f}pt",
                                module=LogModule.RESTOR
                            )
                    except Exception as draw_error:
                        logger.error(LogModule.LAYOUT, f"[REPORTLAB] Error drawing textobject on page {page_idx}, block {block_idx}: {draw_error}", exc_info=True)
                        # Fallback: try creating a new textobject if the first one failed
                        try:
                            # Create a new textobject and try again
                            fallback_text_obj = c.beginText()
                            fallback_text_obj.setFont(font_name, font_size)
                            current_y = start_y
                            
                            for line_idx, line in enumerate(text_lines):
                                # 同样仅在接近页面底部时停止，忽略 bbox 限制
                                if current_y < 0:
                                    break
                                if line_idx < len(line_heights):
                                    line_height = line_heights[line_idx]
                                elif line_heights:
                                    line_height = line_heights[-1]
                                else:
                                    line_height = font_size * 1.2
                                
                                try:
                                    # Calculate line width for alignment with block-level font
                                    line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                                    if alignment == 'center':
                                        text_x = x0 + (width - line_width) / 2
                                    elif alignment == 'right':
                                        text_x = x0 + width - line_width
                                    else:
                                        text_x = x0

                                    # Render this line with per-language font segments (fallback path)
                                    segments = _split_text_by_language_segments(line)
                                    current_x = text_x
                                    for seg_text, seg_lang in segments:
                                        if not seg_text:
                                            continue
                                        _, seg_font_name = _detect_and_get_font_for_text(seg_text, target_language)
                                        try:
                                            fallback_text_obj.setFont(seg_font_name, font_size)
                                        except Exception:
                                            try:
                                                fallback_text_obj.setFont(font_name, font_size)
                                                seg_font_name = font_name
                                            except Exception:
                                                fallback_text_obj.setFont("Helvetica", font_size)
                                                seg_font_name = "Helvetica"

                                        fallback_text_obj.setTextOrigin(current_x, current_y)
                                        fallback_text_obj.textOut(seg_text)

                                        try:
                                            seg_width = pdfmetrics.stringWidth(seg_text, seg_font_name, font_size)
                                        except Exception:
                                            seg_width = 0
                                        current_x += seg_width

                                    if line_idx < len(text_lines) - 1:
                                        next_line = text_lines[line_idx + 1]
                                        try:
                                            next_line_width = pdfmetrics.stringWidth(next_line, font_name, font_size)
                                        except Exception:
                                            next_line_width = 0
                                        
                                        if alignment == 'center':
                                            next_text_x = x0 + (width - next_line_width) / 2
                                        elif alignment == 'right':
                                            next_text_x = x0 + width - next_line_width
                                        else:
                                            next_text_x = x0
                                        
                                        # After rendering segments, conceptual end of line is at (text_x + line_width, current_y)
                                        # Move to (next_text_x, current_y - line_height)
                                        current_cursor_x = text_x + line_width
                                        dx = next_text_x - current_cursor_x
                                        dy = -line_height
                                        fallback_text_obj.moveCursor(dx, dy)
                                        current_y -= line_height
                                except Exception as line_error:
                                    logger.error(LogModule.LAYOUT, f"[REPORTLAB] Error in fallback textobject line {line_idx}: {line_error}")
                                    continue
                            
                            c.drawText(fallback_text_obj)
                            
                            # Log ref_text font size for diagnosis (fallback path)
                            if block.type == "ref_text":
                                total_rendered_height = sum(line_heights) if line_heights else len(text_lines) * font_size * 1.2
                                logger.debug(
                                    f"[REPORTLAB] ref_text rendered (fallback): Page {page_idx}, Block {block_idx} (index={block.index}): "
                                    f"font_size={font_size:.2f}pt, lines={len(text_lines)}, "
                                    f"bbox_height={height:.2f}pt, rendered_height={total_rendered_height:.2f}pt, "
                                    f"baseline_from_type={type_font_baselines.get('ref_text', 'N/A')}, "
                                    f"original_baseline={original_font_size_before_adjustment:.2f}pt"
                                )
                        except Exception as fallback_error:
                                    logger.error(LogModule.LAYOUT, f"[REPORTLAB] Fallback textobject also failed for page {page_idx}, block {block_idx}: {fallback_error}", exc_info=True)
                else:
                    # Block type not handled and no text available
                    skipped_count += 1
                    total_blocks_skipped += 1
            
            # Finish page (showPage is called at the start of next page, or after last page)
            if page_idx < len(layout_doc.pages) - 1:
                # Not the last page, showPage will be called at start of next iteration
                pass
            else:
                # Last page, need to finish it
                try:
                    c.showPage()
                except Exception as e:
                    logger.error(LogModule.LAYOUT, f"[REPORTLAB] Failed to show last page {page_idx}: {e}", exc_info=True)
                    raise
    except Exception as e:
        logger.error(LogModule.LAYOUT, f"[REPORTLAB] Error processing pages: {e}", exc_info=True)
        raise
    
    # Save PDF
    try:
        c.save()
        pdf_bytes = pdf_buffer.getvalue()
    except Exception as e:
        logger.error(LogModule.LAYOUT, f"[REPORTLAB] Failed to save PDF: {e}", exc_info=True)
        raise
    
    # Save to file if output_path is provided (for debugging)
    if output_path:
        try:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.warning(LogModule.LAYOUT, f"[REPORTLAB] Failed to save PDF to {output_path}: {e}")
    
    total_blocks_in_layout = sum(1 for _ in layout_doc.iter_blocks())
    if total_blocks_rendered < total_blocks_in_layout:
        missing_count = total_blocks_in_layout - total_blocks_rendered
        logger.warning(
            f"[REPORTLAB] Only rendered {total_blocks_rendered}/{total_blocks_in_layout} blocks "
            f"({100*total_blocks_rendered/total_blocks_in_layout:.1f}%). "
            f"Missing {missing_count} blocks. Check logs above for skip reasons."
        )
        # Log summary of skip reasons
        # (Info logging removed)
    
    return pdf_bytes

