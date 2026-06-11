# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Overlay merge utilities.

Merges Typst-compiled overlay PDF pages onto a source PDF document
using PyMuPDF's show_pdf_page() overlay feature.

Two modes are supported:
  1. Overlay mode: Places translucent translated text on top of source pages
  2. Background mode: Embeds source page as background, places text on top
"""

import io
from pathlib import Path
from typing import Optional

from logger.logger import unified_logger, LogModule

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def _check_pymupdf():
    """Raise ImportError if PyMuPDF is not available."""
    if not PYMUPDF_AVAILABLE:
        raise ImportError(
            "PyMuPDF (fitz) is required for PDF overlay operations. "
            "Install with: pip install PyMuPDF"
        )


def merge_overlay_pdf(
    source_pdf_bytes: bytes,
    overlay_pdf_path: Path,
    output_path: Optional[Path] = None,
    *,
    compress: bool = True,
    check_page_count: bool = True,
) -> bytes:
    """
    Merge a Typst overlay PDF onto a source PDF.

    Each page of the overlay is placed on top of the corresponding source
    page using PyMuPDF's transparent overlay feature. This preserves all
    original PDF content while adding translated text.

    Args:
        source_pdf_bytes: The source PDF (cleaned or original) as bytes
        overlay_pdf_path: Path to the Typst-compiled overlay PDF
        output_path: Optional path to save the merged PDF
        compress: Whether to apply garbage collection and compression
        check_page_count: if True, verify page counts match

    Returns:
        Merged PDF content as bytes

    Raises:
        ImportError: If PyMuPDF is not installed
        ValueError: If page counts don't match
    """
    _check_pymupdf()

    source_doc = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    overlay_doc = fitz.open(overlay_pdf_path)
    try:
        if check_page_count:
            src_pages = len(source_doc)
            ovl_pages = len(overlay_doc)
            if src_pages != ovl_pages:
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[OVERLAY_MERGE] Page count mismatch: source={src_pages} "
                    f"overlay={ovl_pages}. Merging min({src_pages}, {ovl_pages}) pages."
                )

        merged_page_count = 0
        for page_idx in range(min(len(source_doc), len(overlay_doc))):
            source_page = source_doc[page_idx]
            overlay_page = overlay_doc[page_idx]

            # Show overlay PDF page on top of source page
            source_page.show_pdf_page(
                source_page.rect,
                overlay_doc,
                page_idx,
                overlay=True,
            )
            merged_page_count += 1

        unified_logger.info(
            LogModule.RESTOR,
            f"[OVERLAY_MERGE] Merged {merged_page_count} overlay pages"
        )

        if output_path:
            if compress:
                source_doc.save(output_path, garbage=4, deflate=True)
            else:
                source_doc.save(output_path)
            return output_path.read_bytes()
        else:
            buffer = io.BytesIO()
            if compress:
                source_doc.save(buffer, garbage=4, deflate=True)
            else:
                source_doc.save(buffer)
            return buffer.getvalue()

    finally:
        source_doc.close()
        overlay_doc.close()


def merge_overlay_pdf_to_file(
    source_pdf_bytes: bytes,
    overlay_pdf_path: Path,
    output_path: Path,
    **kwargs,
) -> Path:
    """Merge overlay and save to file. Returns output path."""
    merge_overlay_pdf(source_pdf_bytes, overlay_pdf_path,
                      output_path=output_path, **kwargs)
    return output_path


def apply_source_overlay(
    source_page: "fitz.Page",
    translated_blocks,
    *,
    cover_only: bool = False,
    fill_color: tuple = (1.0, 1.0, 1.0),
) -> int:
    """
    Draw white cover rectangles directly on a source page.

    This is a fast-path alternative to full Typst overlay rendering.
    It simply draws white rectangles over the areas where original text
    was located, providing a clean background for later Typst text placement.

    Args:
        source_page: PyMuPDF page object
        translated_blocks: List of RenderBlock or dict with bbox info
        cover_only: If True, don't try to place text, just draw covers
        fill_color: RGB fill color for cover rects

    Returns:
        Number of cover rects drawn
    """
    _check_pymupdf()

    rect_count = 0
    for block_data in translated_blocks:
        bbox = None
        if hasattr(block_data, 'inner_bbox'):
            bbox = block_data.inner_bbox
        elif isinstance(block_data, dict):
            bbox = block_data.get('bbox') or block_data.get('inner_bbox')
            if bbox is None:
                continue
        else:
            continue

        if len(bbox) != 4:
            continue

        x0, y0, x1, y1 = bbox
        rect = fitz.Rect(x0, y0, x1, y1)

        # Draw white rectangle to cover original content
        shape = source_page.new_shape()
        shape.draw_rect(rect)
        r, g, b = [int(max(0, min(1, c)) * 255) for c in fill_color]
        shape.finish(
            fill=(r / 255, g / 255, b / 255),
            color=None,
            width=0,
        )
        shape.commit()
        rect_count += 1

    return rect_count
