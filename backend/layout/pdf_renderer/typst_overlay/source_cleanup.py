# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Source PDF cleanup for Typst overlay rendering.

Removes original text from the source PDF using PyMuPDF redaction,
then fills cleared areas with white rectangles. This produces a
clean background onto which the Typst overlay can be merged.
"""

import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logger.logger import unified_logger, LogModule
from layout.base import LayoutDocument

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def _collect_redaction_rects(
    layout_doc: LayoutDocument,
    margin_pt: float = 2.0,
    *,
    skip_block_indices: Optional[set] = None,
) -> Dict[int, List[Tuple[float, float, float, float]]]:
    """
    Collect bounding boxes of all translated text blocks as redaction targets.

    Also collects:
      - Cross-page lines (lines with ``cross_page: true`` in raw data)
        whose bboxes fall on the *next* page.
      - ``merge_prev`` blocks (blocks whose text was merged into the
        previous page's paragraph).  These carry ``merge_prev: true`` and
        ``lines_deleted: true`` in their raw data, have empty ``lines``,
        and their bbox must still be redacted so that the original text
        on the source PDF is cleared.

    Args:
        layout_doc: LayoutDocument with all layout blocks.
        margin_pt: Extra margin (in points) to expand each redaction rect.
        skip_block_indices: Set of block indices for which neither redaction
            nor overlay placement should happen (excluded or translation-
            failed segments).

    Returns:
        Dict mapping page_index -> list of (x0, y0, x1, y1) rects to redact.
    """
    skip_set = skip_block_indices or set()
    redaction_map: Dict[int, List[Tuple[float, float, float, float]]] = {}
    image_block_count = 0
    cross_page_rect_count = 0
    merge_prev_rect_count = 0
    skipped_by_skip_set = 0
    skipped_no_text = 0
    skipped_chart = 0
    skipped_table = 0
    redacted_blocks: list[tuple] = []  # (page, idx, type, bbox)

    for page in layout_doc.pages:
        rects: List[Tuple[float, float, float, float]] = []
        text_block_count = 0

        # -- Primary pass: redact all text blocks and cross-page paired blocks --
        for block in page.blocks:
            block_index = getattr(block, "index", None)

            # Skip blocks that are in the skip set — don't erase their
            # original text and don't place overlay text on top of them.
            if block_index is not None and block_index in skip_set:
                skipped_by_skip_set += 1
                continue

            raw = getattr(block, "raw", None) or {}
            is_cross_page_pair = isinstance(raw, dict) and raw.get("_cross_page_pair_of") is not None

            # Skip chart and table blocks - they should always stay on original PDF
            # Chart and table visual content (images) must not be redacted
            if block.type in ("chart", "table"):
                if block.type == "chart":
                    skipped_chart += 1
                else:
                    skipped_table += 1
                continue

            # Skip blocks that are neither text blocks nor cross-page paired blocks
            if not block.has_text() and not is_cross_page_pair:
                skipped_no_text += 1
                continue

            x0, y0, x1, y1 = block.bbox
            # Expand rect slightly to ensure complete coverage
            rects.append((
                max(0, x0 - margin_pt),
                max(0, y0 - margin_pt),
                x1 + margin_pt,
                y1 + margin_pt,
            ))
            text_block_count += 1
            redacted_blocks.append((page.page_index, block_index, block.type, block.bbox))

            # Detect cross-page lines inside this block's raw data.
            # MinerU marks cross-page spans (not lines) with "cross_page": true.
            # If any span in a line has cross_page, the whole line belongs to
            # the *next* page (page_index + 1).
            # (Skip this for paired blocks; their bbox already covers the target area.)
            if not is_cross_page_pair:
                raw_lines = raw.get("lines") or []
                if raw_lines:
                    next_page_idx = page.page_index + 1
                    for line in raw_lines:
                        if not isinstance(line, dict):
                            continue
                        spans = line.get("spans") or []
                        if not any(isinstance(s, dict) and s.get("cross_page") for s in spans):
                            continue
                        line_bbox = line.get("bbox")
                        if not isinstance(line_bbox, list) or len(line_bbox) != 4:
                            continue
                        try:
                            lx0, ly0, lx1, ly1 = (
                                float(line_bbox[0]), float(line_bbox[1]),
                                float(line_bbox[2]), float(line_bbox[3]),
                            )
                        except (TypeError, ValueError):
                            continue
                        cross_page_rects = redaction_map.setdefault(
                            next_page_idx, [],
                        )
                        cross_page_rects.append((
                            max(0, lx0 - margin_pt),
                            max(0, ly0 - margin_pt),
                            lx1 + margin_pt,
                            ly1 + margin_pt,
                        ))
                        cross_page_rect_count += 1

        # -- Secondary pass: redact merge_prev blocks --
        # These blocks have merge_prev=true and lines_deleted=true,
        # meaning their text content was merged into a previous page's
        # paragraph block.  They have empty lines but their bbox covers
        # original text that must still be cleared on this page.
        for block in page.blocks:
            block_index = getattr(block, "index", None)
            if block_index is not None and block_index in skip_set:
                continue

            raw = getattr(block, "raw", None) or {}
            if not isinstance(raw, dict):
                continue
            if not (raw.get("merge_prev") and raw.get("lines_deleted")):
                continue
            if block.has_text():
                # Text block already handled above; skip.
                continue
            x0, y0, x1, y1 = block.bbox
            rects.append((
                max(0, x0 - margin_pt),
                max(0, y0 - margin_pt),
                x1 + margin_pt,
                y1 + margin_pt,
            ))
            merge_prev_rect_count += 1

        # Count image blocks, chart blocks, and table blocks on this page (should NOT be redacted)
        page_images = list(page.iter_image_blocks())
        visual_blocks_excluded = len(page_images)

        # Also count all chart and table blocks (they are all excluded from redaction)
        chart_table_count = sum(1 for block in page.blocks if block.type in ("chart", "table"))
        visual_blocks_excluded += chart_table_count
        
        if visual_blocks_excluded:
            image_block_count += visual_blocks_excluded
        if rects:
            # Merge with any cross-page rects that landed on this page
            if page.page_index in redaction_map:
                redaction_map[page.page_index] = (
                    rects + redaction_map[page.page_index]
                )
            else:
                redaction_map[page.page_index] = rects

    unified_logger.info(
        LogModule.RESTOR,
        f"[SOURCE_CLEANUP] Collected redaction rects from text blocks only: "
        f"text_blocks={sum(len(r) for r in redaction_map.values())}, "
        f"image_blocks_excluded={image_block_count}, "
        f"cross_page_rects={cross_page_rect_count}, "
        f"merge_prev_rects={merge_prev_rect_count}, "
        f"skip_set_size={len(skip_set)}, "
        f"skip_set={sorted(skip_set) if skip_set else '[]'}, "
        f"skipped_by_set={skipped_by_skip_set}, "
        f"skipped_no_text={skipped_no_text}, "
        f"skipped_chart={skipped_chart}, "
        f"skipped_table={skipped_table}"
    )
    if redacted_blocks and unified_logger.isEnabledFor(10):  # DEBUG level
        for page_idx, blk_idx, blk_type, blk_bbox in redacted_blocks:
            unified_logger.debug(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] REDACT page={page_idx} block_idx={blk_idx} "
                f"type={blk_type} bbox=({blk_bbox[0]:.1f},{blk_bbox[1]:.1f},"
                f"{blk_bbox[2]:.1f},{blk_bbox[3]:.1f})",
            )

    return redaction_map


def _merge_overlapping_rects(
    rects: List[Tuple[float, float, float, float]],
) -> List[Tuple[float, float, float, float]]:
    """
    Merge overlapping or adjacent rectangles to minimize redaction operations.

    Uses a simple greedy merge: sort by x0 then y0, merge if overlap.
    """
    if len(rects) <= 1:
        return rects

    sorted_rects = sorted(rects, key=lambda r: (r[0], r[1]))
    merged: List[Tuple[float, float, float, float]] = [sorted_rects[0]]

    for rect in sorted_rects[1:]:
        last = merged[-1]
        # Check if rects overlap or are very close
        if rect[0] <= last[2] + 3 and rect[1] <= last[3] + 3:
            # Merge
            merged[-1] = (
                last[0],
                min(last[1], rect[1]),
                max(last[2], rect[2]),
                max(last[3], rect[3]),
            )
        else:
            merged.append(rect)

    return merged


def _clip_rects_against_skipped_blocks(
    rects: List[Tuple[float, float, float, float]],
    layout_doc: LayoutDocument,
    page_index: int,
    skip_block_indices: set,
) -> List[Tuple[float, float, float, float]]:
    """Clip redaction rects to exclude areas belonging to non-redacted blocks.

    Protects every block on the page whose content must NOT be erased:
      - Blocks in skip_block_indices (translation unchanged / failed)
      - Blocks with no detected text (has_text()=False) — their bbox
        may still contain original PDF content
      - Chart / table / image blocks

    When a redaction rect overlaps with a protected block's bbox, the
    overlapping portion is split away so the original content survives.
    """
    protected_rects: List[Tuple[float, float, float, float]] = []
    for page in layout_doc.pages:
        if page.page_index != page_index:
            continue
        for block in page.blocks:
            blk_idx = getattr(block, "index", None)
            # Protect all blocks that _collect_redaction_rects would skip:
            #   1. skip_set blocks
            #   2. blocks without text (has_text()=False)
            #   3. chart / table blocks
            if blk_idx is not None and blk_idx in skip_block_indices:
                protected_rects.append(block.bbox)
            elif not block.has_text():
                protected_rects.append(block.bbox)
            elif block.type in ("chart", "table"):
                protected_rects.append(block.bbox)

    if not protected_rects:
        return rects

    clipped: List[Tuple[float, float, float, float]] = []
    for rx0, ry0, rx1, ry1 in rects:
        fragments = [(rx0, ry0, rx1, ry1)]
        for px0, py0, px1, py1 in protected_rects:
            next_fragments: List[Tuple[float, float, float, float]] = []
            for fx0, fy0, fx1, fy1 in fragments:
                # No overlap — keep fragment as-is
                if fx0 >= px1 or fx1 <= px0 or fy0 >= py1 or fy1 <= py0:
                    next_fragments.append((fx0, fy0, fx1, fy1))
                    continue
                # Split fragment around the protected rect (4 sub-rects)
                # Left of protected rect
                if fx0 < px0:
                    next_fragments.append((fx0, fy0, px0, fy1))
                # Right of protected rect
                if fx1 > px1:
                    next_fragments.append((px1, fy0, fx1, fy1))
                # Top of protected rect (between px0 and px1 in x)
                clip_x0 = max(fx0, px0)
                clip_x1 = min(fx1, px1)
                if fy0 < py0:
                    next_fragments.append((clip_x0, fy0, clip_x1, py0))
                # Bottom of protected rect
                if fy1 > py1:
                    next_fragments.append((clip_x0, py1, clip_x1, fy1))
            fragments = next_fragments
        clipped.extend(fragments)

    clipped_count = len(clipped) - len(rects)
    if clipped_count != 0:
        unified_logger.info(
            LogModule.RESTOR,
            f"[SOURCE_CLEANUP] Page {page_index}: split {clipped_count} "
            f"extra redaction fragment(s) to protect non-redacted blocks "
            f"(protected={len(protected_rects)}, before={len(rects)}, after={len(clipped)})",
        )

    return clipped


def clean_source_pdf(
    source_pdf_path: Path,
    layout_doc: LayoutDocument,
    output_path: Optional[Path] = None,
    *,
    merge_rects: bool = True,
    fill_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    extra_redaction_rects: Optional[Dict[int, List[Tuple[float, float, float, float]]]] = None,
    skip_block_indices: Optional[set] = None,
) -> bytes:
    """
    Clean original text from a source PDF and return the cleaned PDF bytes.

    Process:
      1. Collect all text block bboxes as redaction targets
      2. Optionally merge overlapping rects to reduce operations
      3. Apply PyMuPDF redaction on each page
      4. Fill redacted areas with white (or specified color)
      5. Return cleaned PDF as bytes

    Args:
        source_pdf_path: Path to the original PDF file
        layout_doc: LayoutDocument with all text block positions
        output_path: Optional path to save the cleaned PDF
        merge_rects: Whether to merge overlapping rects
        fill_color: RGB fill color for redacted areas (default white)
        skip_block_indices: Set of block indices to skip (excluded or
            translation-failed segments whose original text should not
            be erased)

    Returns:
        Cleaned PDF file content as bytes

    Raises:
        ImportError: If PyMuPDF is not installed
        FileNotFoundError: If source_pdf_path does not exist
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for source cleanup. "
                          "Install with: pip install PyMuPDF")

    unified_logger.info(
        LogModule.RESTOR,
        f"[SOURCE_CLEANUP] Cleaning source PDF: {source_pdf_path}, "
        f"skip_block_indices={sorted(skip_block_indices) if skip_block_indices else 'None/empty'}"
    )

    # Open the source PDF
    doc = fitz.open(source_pdf_path)
    try:
        # Collect redaction rects from layout blocks
        redaction_map = _collect_redaction_rects(
            layout_doc, skip_block_indices=skip_block_indices,
        )

        if extra_redaction_rects:
            for page_idx, extra_rects in extra_redaction_rects.items():
                if not extra_rects:
                    continue
                redaction_map.setdefault(page_idx, []).extend(extra_rects)
            unified_logger.info(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] Added {sum(len(v) for v in extra_redaction_rects.values())} "
                f"extra redaction rect(s) for embedded chart/table images",
            )

        redacted_page_count = 0
        total_rect_count = 0

        for page_idx in range(len(doc)):
            if page_idx not in redaction_map:
                continue

            page = doc[page_idx]
            rects = redaction_map[page_idx]

            if merge_rects:
                rects = _merge_overlapping_rects(rects)

            # Protect skipped blocks: clip redaction rects so they do not
            # erase original content of excluded / translation-failed segments.
            if skip_block_indices:
                rects = _clip_rects_against_skipped_blocks(
                    rects, layout_doc, page_idx, skip_block_indices,
                )

            for rx0, ry0, rx1, ry1 in rects:
                rect = fitz.Rect(rx0, ry0, rx1, ry1)
                # Add redaction annotation
                page.add_redact_annot(rect, fill=fill_color)
                total_rect_count += 1

            # Apply redaction (images=NONE is already the default, so
            # images that overlap with text block areas are preserved)
            page.apply_redactions()
            redacted_page_count += 1

        unified_logger.info(
            LogModule.RESTOR,
            f"[SOURCE_CLEANUP] Redacted {total_rect_count} rects "
            f"across {redacted_page_count} pages"
        )

        # Save to bytes
        if output_path:
            doc.save(output_path, garbage=4, deflate=True)
            return output_path.read_bytes()
        else:
            pdf_buffer = io.BytesIO()
            doc.save(pdf_buffer, garbage=4, deflate=True)
            return pdf_buffer.getvalue()

    finally:
        doc.close()


def clean_source_pdf_to_file(
    source_pdf_path: Path,
    layout_doc: LayoutDocument,
    output_path: Path,
    **kwargs,
) -> Path:
    """Clean source PDF and save to file. Returns the output path."""
    clean_source_pdf(source_pdf_path, layout_doc, output_path=output_path, **kwargs)
    return output_path
