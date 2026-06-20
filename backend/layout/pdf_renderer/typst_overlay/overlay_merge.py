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

            src_w = float(source_page.rect.width)
            src_h = float(source_page.rect.height)
            ovl_w = float(overlay_page.rect.width)
            ovl_h = float(overlay_page.rect.height)
            if abs(src_w - ovl_w) > 0.05 or abs(src_h - ovl_h) > 0.05:
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[OVERLAY_MERGE] Page {page_idx + 1} dimension mismatch: "
                    f"source=({src_w:.2f}, {src_h:.2f}) "
                    f"overlay=({ovl_w:.2f}, {ovl_h:.2f}) "
                    f"delta=({ovl_w - src_w:+.4f}, {ovl_h - src_h:+.4f})"
                )

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


def _save_assembled_pdf(out_doc: "fitz.Document", *, compress: bool) -> bytes:
    """Save an assembled PDF without aggressive GC that can strip shared page assets."""
    buffer = io.BytesIO()
    if compress:
        out_doc.save(buffer, garbage=0, deflate=True)
    else:
        out_doc.save(buffer)
    return buffer.getvalue()


def _assemble_pdf_with_page_replacements(
    base_doc: "fitz.Document",
    replacement_docs: dict[int, "fitz.Document"],
) -> "fitz.Document":
    """Build a new PDF, copying untouched pages verbatim from base_doc."""
    out_doc = fitz.open()
    for page_num in range(len(base_doc)):
        replacement = replacement_docs.get(page_num)
        if replacement is not None and len(replacement) > 0:
            out_doc.insert_pdf(replacement, from_page=0, to_page=0)
        else:
            out_doc.insert_pdf(base_doc, from_page=page_num, to_page=page_num)
    return out_doc


def patch_merged_pdf_pages(
    merged_pdf_bytes: bytes,
    cleaned_source_bytes: bytes,
    overlay_pdf_path: Path,
    source_page_indices: list[int],
    *,
    compress: bool = True,
) -> bytes:
    """Replace selected pages in a merged PDF with freshly overlaid pages."""
    _check_pymupdf()

    if not source_page_indices:
        return merged_pdf_bytes

    merged_doc = fitz.open(stream=merged_pdf_bytes, filetype="pdf")
    cleaned_doc = fitz.open(stream=cleaned_source_bytes, filetype="pdf")
    overlay_doc = fitz.open(overlay_pdf_path)
    temp_doc = fitz.open()
    replacement_docs: dict[int, "fitz.Document"] = {}
    try:
        sorted_pages = sorted(set(source_page_indices))
        for ovl_idx, page_idx in enumerate(sorted_pages):
            if page_idx < 0 or page_idx >= len(merged_doc):
                continue
            if page_idx >= len(cleaned_doc) or ovl_idx >= len(overlay_doc):
                break

            temp_doc.select([])
            temp_doc.insert_pdf(cleaned_doc, from_page=page_idx, to_page=page_idx)
            temp_page = temp_doc[0]
            temp_page.show_pdf_page(
                temp_page.rect,
                overlay_doc,
                ovl_idx,
                overlay=True,
            )

            repl_doc = fitz.open()
            repl_doc.insert_pdf(temp_doc, from_page=0, to_page=0)
            replacement_docs[page_idx] = repl_doc

        if not replacement_docs:
            return merged_pdf_bytes

        out_doc = _assemble_pdf_with_page_replacements(merged_doc, replacement_docs)
        try:
            patched = _save_assembled_pdf(out_doc, compress=compress)
        finally:
            out_doc.close()

        unified_logger.info(
            LogModule.RESTOR,
            f"[OVERLAY_MERGE] Patched {len(replacement_docs)} page(s): {sorted_pages}",
        )
        return patched
    finally:
        for repl_doc in replacement_docs.values():
            repl_doc.close()
        temp_doc.close()
        overlay_doc.close()
        cleaned_doc.close()
        merged_doc.close()


def patch_merged_pdf_pages_from_rendered(
    merged_pdf_bytes: bytes,
    rendered_pdf_bytes: bytes,
    source_page_indices: list[int],
    *,
    compress: bool = True,
) -> bytes:
    """Replace selected pages using fully rendered page PDF bytes (background-embed)."""
    _check_pymupdf()

    if not source_page_indices:
        return merged_pdf_bytes

    merged_doc = fitz.open(stream=merged_pdf_bytes, filetype="pdf")
    rendered_doc = fitz.open(stream=rendered_pdf_bytes, filetype="pdf")
    replacement_docs: dict[int, "fitz.Document"] = {}
    try:
        sorted_pages = sorted(set(source_page_indices))
        for ovl_idx, page_idx in enumerate(sorted_pages):
            if page_idx < 0 or page_idx >= len(merged_doc):
                continue
            if ovl_idx >= len(rendered_doc):
                break
            repl_doc = fitz.open()
            repl_doc.insert_pdf(rendered_doc, from_page=ovl_idx, to_page=ovl_idx)
            replacement_docs[page_idx] = repl_doc

        if not replacement_docs:
            return merged_pdf_bytes

        out_doc = _assemble_pdf_with_page_replacements(merged_doc, replacement_docs)
        try:
            patched = _save_assembled_pdf(out_doc, compress=compress)
        finally:
            out_doc.close()

        unified_logger.info(
            LogModule.RESTOR,
            f"[OVERLAY_MERGE] Patched {len(replacement_docs)} background-embed page(s): "
            f"{sorted_pages}",
        )
        return patched
    finally:
        for repl_doc in replacement_docs.values():
            repl_doc.close()
        rendered_doc.close()
        merged_doc.close()


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
