# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Source PDF cleanup for Typst overlay rendering.

Removes original text from the source PDF using PyMuPDF redaction,
then fills cleared areas with white rectangles. This produces a
clean background onto which the Typst overlay can be merged.
"""

import io
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logger.logger import unified_logger, LogModule
from layout.base import LayoutDocument
from layout.block_types import CHART_BODY, TABLE_BODY
from layout.layout_group_pair_utils import is_layout_companion_block
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    _layout_block_is_empty_ocr_text,
    collect_empty_text_block_protected_rects,
    empty_ocr_block_overlaps_overlay_block_region,
)
from layout.pdf_renderer.typst_overlay.visual_images import (
    block_preserves_source_pdf_visual,
    chart_block_has_replaceable_html_body,
    extract_nested_sub_bbox,
    protected_bbox_for_layout_block,
)

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
    bbox_override_by_block_index: Optional[Dict[int, tuple]] = None,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    segment_bbox_only_block_indices: Optional[set] = None,
    overlay_erase_block_indices: Optional[set] = None,
    partial_overlay_block_indices: Optional[set] = None,
) -> Tuple[
    Dict[int, List[Tuple[float, float, float, float]]],
    Dict[int, List[Tuple[float, float, float, float]]],
]:
    """
    Collect bounding boxes of translated text blocks as redaction targets.

    Also collects:
      - Cross-page lines whose bboxes fall on the *next* page.
      - merge_prev blocks whose text was merged into a previous paragraph.
      - Override bbox areas from bbox_override_by_block_index.

    Returns a (redaction_map, override_original_map) tuple:

    * redaction_map — page-indexed redaction rects for all text blocks.
      These are subject to _clip_rects_against_skipped_blocks.
    * override_original_map — page-indexed ORIGINAL bboxes of blocks that
      have a bbox override.  These are ADDED AFTER clipping so that other
      blocks (images, empty text blocks) cannot protect the original area
      and prevent its erasure.  The user has explicitly opted into erasing
      both the original and the override areas.

    Args:
        layout_doc: LayoutDocument with all layout blocks.
        margin_pt: Extra margin (in points) to expand each redaction rect.
        skip_block_indices: Set of block indices for which neither redaction
            nor overlay placement should happen.
        bbox_override_by_block_index: Optional mapping from block index to
            [x0, y0, x1, y1] override.  The override area is also redacted.
    """
    skip_set = skip_block_indices or set()
    segment_bbox_only = segment_bbox_only_block_indices or set()
    overlay_erase = overlay_erase_block_indices or set()
    partial_overlay = partial_overlay_block_indices or set()
    bbox_overrides = bbox_override_by_block_index or {}
    redaction_map: Dict[int, List[Tuple[float, float, float, float]]] = {}
    # Original bboxes of blocks that have overrides.  These are added
    # AFTER _clip_rects_against_skipped_blocks so that no other block
    # (image, empty text, etc.) can protect the original area.
    override_original_map: Dict[int, List[Tuple[float, float, float, float]]] = {}
    image_block_count = 0
    cross_page_rect_count = 0
    merge_prev_rect_count = 0
    skipped_by_skip_set = 0
    skipped_no_text = 0
    skipped_empty_recognized = 0
    skipped_chart = 0
    skipped_chart_no_html_body = 0
    skipped_table = 0
    skipped_equation_image = 0
    chart_html_redacted = 0
    equation_text_redacted = 0
    override_rect_count = 0
    redacted_blocks: list[tuple] = []  # (page, idx, type, bbox)
    chart_fmt = (chart_body_format or "image").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()

    def _expand_bbox(bbox: tuple) -> Tuple[float, float, float, float]:
        x0, y0, x1, y1 = bbox
        return (
            max(0, x0 - margin_pt),
            max(0, y0 - margin_pt),
            x1 + margin_pt,
            y1 + margin_pt,
        )

    for page in layout_doc.pages:
        rects: List[Tuple[float, float, float, float]] = []
        text_block_count = 0

        # -- Primary pass: redact all text blocks and cross-page paired blocks --
        for block in page.blocks:
            block_index = getattr(block, "index", None)

            # Skip blocks that are in the skip set — don't erase their
            # original text and don't place overlay text on top of them.
            # LaTeX equations are always re-rendered via mitex overlay.
            if block_index is not None and block_index in skip_set:
                if not (block.is_equation() and eq_fmt == "text"):
                    skipped_by_skip_set += 1
                    continue

            if block_index is not None and block_index in segment_bbox_only:
                continue

            raw = getattr(block, "raw", None) or {}
            is_layout_companion = is_layout_companion_block(raw)

            if block.type == "chart":
                if chart_fmt == "image":
                    skipped_chart += 1
                    continue
                if not chart_block_has_replaceable_html_body(block):
                    skipped_chart += 1
                    skipped_chart_no_html_body += 1
                    continue
                body_bbox = extract_nested_sub_bbox(block, CHART_BODY) or tuple(block.bbox)
                rects.append(_expand_bbox(body_bbox))
                chart_html_redacted += 1
                redacted_blocks.append(
                    (page.page_index, block_index, block.type, body_bbox),
                )
                if block_index is not None and block_index in bbox_overrides:
                    override_original_map.setdefault(page.page_index, []).append(
                        _expand_bbox(body_bbox),
                    )
                    override_bbox = bbox_overrides[block_index]
                    if isinstance(override_bbox, (tuple, list)) and len(override_bbox) == 4:
                        try:
                            ox0, oy0, ox1, oy1 = (
                                float(override_bbox[0]), float(override_bbox[1]),
                                float(override_bbox[2]), float(override_bbox[3]),
                            )
                            rects.append(_expand_bbox((ox0, oy0, ox1, oy1)))
                            override_rect_count += 1
                        except (TypeError, ValueError):
                            pass
                continue

            if block.is_equation():
                if eq_fmt == "image":
                    skipped_equation_image += 1
                    continue
                rects.append(_expand_bbox(tuple(block.bbox)))
                equation_text_redacted += 1
                redacted_blocks.append(
                    (page.page_index, block_index, block.type, block.bbox),
                )
                if block_index is not None and block_index in bbox_overrides:
                    override_original_map.setdefault(page.page_index, []).append(
                        _expand_bbox(tuple(block.bbox)),
                    )
                    override_bbox = bbox_overrides[block_index]
                    if isinstance(override_bbox, (tuple, list)) and len(override_bbox) == 4:
                        try:
                            ox0, oy0, ox1, oy1 = (
                                float(override_bbox[0]), float(override_bbox[1]),
                                float(override_bbox[2]), float(override_bbox[3]),
                            )
                            rects.append(_expand_bbox((ox0, oy0, ox1, oy1)))
                            override_rect_count += 1
                        except (TypeError, ValueError):
                            pass
                continue

            if block.type == "table":
                if table_fmt == "image":
                    skipped_table += 1
                    continue
                body_bbox = extract_nested_sub_bbox(block, TABLE_BODY) or tuple(block.bbox)
                rects.append(_expand_bbox(body_bbox))
                redacted_blocks.append(
                    (page.page_index, block_index, block.type, body_bbox),
                )
                if block_index is not None and block_index in bbox_overrides:
                    override_original_map.setdefault(page.page_index, []).append(
                        _expand_bbox(body_bbox),
                    )
                    override_bbox = bbox_overrides[block_index]
                    if isinstance(override_bbox, (tuple, list)) and len(override_bbox) == 4:
                        try:
                            ox0, oy0, ox1, oy1 = (
                                float(override_bbox[0]), float(override_bbox[1]),
                                float(override_bbox[2]), float(override_bbox[3]),
                            )
                            rects.append(_expand_bbox((ox0, oy0, ox1, oy1)))
                            override_rect_count += 1
                        except (TypeError, ValueError):
                            pass
                continue

            # Empty OCR text regions may still contain background graphics in the PDF.
            if _layout_block_is_empty_ocr_text(block) and not is_layout_companion:
                if block_index is None or block_index not in overlay_erase:
                    skipped_empty_recognized += 1
                    continue

            rects.append(_expand_bbox(tuple(block.bbox)))
            text_block_count += 1
            redacted_blocks.append((page.page_index, block_index, block.type, block.bbox))

            # Also redact user-overridden bbox area so that any original PDF
            # text in the expanded/moved region is erased.  This is a
            # safety measure — the original bbox (above) is always redacted
            # regardless of whether an override exists.
            # Record the ORIGINAL bbox separately so it can be added AFTER
            # _clip_rects_against_skipped_blocks.  This ensures other blocks
            # (images, empty text blocks) cannot protect the original area
            # and prevent its erasure.
            if block_index is not None and block_index in bbox_overrides:
                preserve_pixels = block_preserves_source_pdf_visual(
                    block,
                    equation_format=eq_fmt,
                    chart_body_format=chart_fmt,
                    table_body_format=table_fmt,
                )
                if not preserve_pixels:
                    override_original_map.setdefault(page.page_index, []).append(
                        _expand_bbox(tuple(block.bbox)),
                    )
                    override_bbox = bbox_overrides[block_index]
                    if isinstance(override_bbox, (tuple, list)) and len(override_bbox) == 4:
                        try:
                            ox0, oy0, ox1, oy1 = (
                                float(override_bbox[0]), float(override_bbox[1]),
                                float(override_bbox[2]), float(override_bbox[3]),
                            )
                            expanded_override = _expand_bbox((ox0, oy0, ox1, oy1))
                            rects.append(expanded_override)
                            override_original_map.setdefault(page.page_index, []).append(
                                expanded_override,
                            )
                            override_rect_count += 1
                        except (TypeError, ValueError):
                            pass

            # Detect cross-page lines inside this block's raw data.
            # MinerU marks cross-page spans (not lines) with "cross_page": true.
            # If any span in a line has cross_page, the whole line belongs to
            # the *next* page (page_index + 1).
            # (Skip this for paired blocks; their bbox already covers the target area.)
            if not is_layout_companion:
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
        visual_blocks_excluded += sum(
            1
            for block in page.blocks
            if block_preserves_source_pdf_visual(
                block,
                equation_format=eq_fmt,
                chart_body_format=chart_fmt,
                table_body_format=table_fmt,
            )
        )
        
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
        f"override_rects={override_rect_count}, "
        f"override_original_pages={sorted(override_original_map.keys())}, "
        f"override_original_rects={sum(len(v) for v in override_original_map.values())}, "
        f"skip_set_size={len(skip_set)}, "
        f"skip_set={sorted(skip_set) if skip_set else '[]'}, "
        f"skipped_by_set={skipped_by_skip_set}, "
        f"skipped_no_text={skipped_no_text}, "
        f"skipped_empty_recognized={skipped_empty_recognized}, "
        f"skipped_chart={skipped_chart}, "
        f"skipped_chart_no_html_body={skipped_chart_no_html_body}, "
        f"skipped_table={skipped_table}, "
        f"skipped_equation_image={skipped_equation_image}, "
        f"chart_html_redacted={chart_html_redacted}, "
        f"equation_text_redacted={equation_text_redacted}, "
        f"chart_fmt={chart_fmt}, eq_fmt={eq_fmt}, table_fmt={table_fmt}"
    )
    if skipped_chart_no_html_body:
        unified_logger.info(
            LogModule.RESTOR,
            f"[SOURCE_CLEANUP] {skipped_chart_no_html_body} chart block(s) kept "
            "source PDF pixels (html format selected but no replaceable "
            "HTML/markdown table body in layout)",
        )
    if override_original_map:
        for p_idx, orects in sorted(override_original_map.items()):
            unified_logger.debug(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] override_original_map page={p_idx}: "
                f"{len(orects)} rect(s)",
            )
    if redacted_blocks and unified_logger.isEnabledFor(10):  # DEBUG level
        for page_idx, blk_idx, blk_type, blk_bbox in redacted_blocks:
            unified_logger.debug(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] REDACT page={page_idx} block_idx={blk_idx} "
                f"type={blk_type} bbox=({blk_bbox[0]:.1f},{blk_bbox[1]:.1f},"
                f"{blk_bbox[2]:.1f},{blk_bbox[3]:.1f})",
            )

    # Overlay-erase blocks deferred to per-segment redaction still need their
    # full layout bbox erased after clipping (unless mixed skip+overlay on same block).
    overlay_erase_original_count = 0
    for page in layout_doc.pages:
        for block in page.blocks:
            block_index = getattr(block, "index", None)
            if block_index is None:
                continue
            if block_index in skip_set:
                continue
            if block_index not in overlay_erase:
                continue
            if block_index not in segment_bbox_only:
                continue
            if block_index in partial_overlay:
                continue
            if block_preserves_source_pdf_visual(
                block,
                equation_format=eq_fmt,
                chart_body_format=chart_fmt,
                table_body_format=table_fmt,
            ):
                continue
            override_original_map.setdefault(page.page_index, []).append(
                _expand_bbox(tuple(block.bbox)),
            )
            override_bbox = bbox_overrides.get(block_index)
            if isinstance(override_bbox, (tuple, list)) and len(override_bbox) == 4:
                try:
                    ox0, oy0, ox1, oy1 = (
                        float(override_bbox[0]), float(override_bbox[1]),
                        float(override_bbox[2]), float(override_bbox[3]),
                    )
                    override_original_map.setdefault(page.page_index, []).append(
                        _expand_bbox((ox0, oy0, ox1, oy1)),
                    )
                except (TypeError, ValueError):
                    pass
            overlay_erase_original_count += 1
    if overlay_erase_original_count:
        unified_logger.info(
            LogModule.RESTOR,
            f"[SOURCE_CLEANUP] Queued {overlay_erase_original_count} overlay-erase "
            "block bbox(es) for post-clip redaction",
        )

    return redaction_map, override_original_map


def _merge_overlapping_rects(
    rects: List[Tuple[float, float, float, float]],
    *,
    gap_pt: float = 3.0,
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
        if rect[0] <= last[2] + gap_pt and rect[1] <= last[3] + gap_pt:
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


def _merge_overlapping_rects_until_stable(
    rects: List[Tuple[float, float, float, float]],
    *,
    gap_pt: float = 3.0,
    max_passes: int = 8,
) -> List[Tuple[float, float, float, float]]:
    """Repeatedly merge rects until count stabilizes (post-clip fragment coalescing)."""
    current = list(rects)
    if len(current) <= 1:
        return current
    for _ in range(max_passes):
        merged = _merge_overlapping_rects(current, gap_pt=gap_pt)
        if len(merged) >= len(current):
            return merged
        current = merged
    return current


def _filter_degenerate_rects(
    rects: List[Tuple[float, float, float, float]],
    *,
    min_size_pt: float = 0.5,
) -> List[Tuple[float, float, float, float]]:
    """Drop zero-area or sub-pixel slivers produced by clipping."""
    kept: List[Tuple[float, float, float, float]] = []
    for x0, y0, x1, y1 in rects:
        if x1 - x0 < min_size_pt or y1 - y0 < min_size_pt:
            continue
        kept.append((x0, y0, x1, y1))
    return kept


def _compact_page_redaction_rects(
    rects: List[Tuple[float, float, float, float]],
    *,
    merge: bool = True,
) -> List[Tuple[float, float, float, float]]:
    """Normalize clipped redaction rects before PyMuPDF annotation creation."""
    compact = _filter_degenerate_rects(rects)
    if merge and len(compact) > 1:
        compact = _merge_overlapping_rects_until_stable(compact)
    return compact


def _compact_page_redaction_rects_preserving(
    rects: List[Tuple[float, float, float, float]],
    protected_rects: Optional[List[Tuple[float, float, float, float]]],
    *,
    merge: bool = True,
    max_passes: int = 4,
) -> List[Tuple[float, float, float, float]]:
    """Compact rects, then re-clip so AABB merges cannot refill protected holes.

    Greedy union of L-shaped fragments around a protected chart/image can produce
    a single bounding box that covers the protected region again. Always clip
    after compaction (and iterate a few times until stable).
    """
    current = _filter_degenerate_rects(rects)
    protected = list(protected_rects or [])
    if not current:
        return current
    for _ in range(max_passes):
        compact = _compact_page_redaction_rects(current, merge=merge)
        if protected:
            compact = _clip_rects_against_protected_rects(compact, protected)
            compact = _filter_degenerate_rects(compact)
        if compact == current:
            return compact
        current = compact
    return current


def _rect_mostly_covered_by(
    rect: Tuple[float, float, float, float],
    existing: List[Tuple[float, float, float, float]],
    *,
    tolerance_pt: float = 0.5,
) -> bool:
    """True when *rect* is already contained in one of *existing* rects."""
    rx0, ry0, rx1, ry1 = rect
    for ex0, ey0, ex1, ey1 in existing:
        if (
            ex0 <= rx0 + tolerance_pt
            and ey0 <= ry0 + tolerance_pt
            and ex1 >= rx1 - tolerance_pt
            and ey1 >= ry1 - tolerance_pt
        ):
            return True
    return False


def _dedupe_rects_not_covered(
    new_rects: List[Tuple[float, float, float, float]],
    existing: List[Tuple[float, float, float, float]],
) -> List[Tuple[float, float, float, float]]:
    """Drop override rects that duplicate an area already scheduled for redaction."""
    if not new_rects or not existing:
        return new_rects
    return [
        rect
        for rect in new_rects
        if not _rect_mostly_covered_by(rect, existing)
    ]


def _page_needs_pixel_redaction(
    page: "fitz.Page",
    rects: List[Tuple[float, float, float, float]],
) -> bool:
    """Use image-pixel redaction only when redaction rects overlap embedded images."""
    if not rects or not PYMUPDF_AVAILABLE:
        return False
    try:
        image_infos = page.get_image_info()
    except Exception:
        return False
    if not image_infos:
        return False
    for rx0, ry0, rx1, ry1 in rects:
        redact_rect = fitz.Rect(rx0, ry0, rx1, ry1)
        for info in image_infos:
            bbox = info.get("bbox")
            if bbox is None or len(bbox) != 4:
                continue
            if redact_rect.intersects(fitz.Rect(bbox)):
                return True
    return False


def _combine_protected_rect_lists(
    *rect_lists: Optional[List[Tuple[float, float, float, float]]],
) -> Optional[List[Tuple[float, float, float, float]]]:
    """Merge multiple protected-rect lists (skip None/empty)."""
    combined: List[Tuple[float, float, float, float]] = []
    for rect_list in rect_lists:
        if rect_list:
            combined.extend(rect_list)
    return combined or None


def _clip_rects_against_protected_rects(
    rects: List[Tuple[float, float, float, float]],
    protected_rects: List[Tuple[float, float, float, float]],
) -> List[Tuple[float, float, float, float]]:
    """Remove portions of redaction rects that overlap protected areas."""
    if not protected_rects:
        return rects

    clipped: List[Tuple[float, float, float, float]] = []
    for rx0, ry0, rx1, ry1 in rects:
        fragments = [(rx0, ry0, rx1, ry1)]
        for px0, py0, px1, py1 in protected_rects:
            next_fragments: List[Tuple[float, float, float, float]] = []
            for fx0, fy0, fx1, fy1 in fragments:
                if fx0 >= px1 or fx1 <= px0 or fy0 >= py1 or fy1 <= py0:
                    next_fragments.append((fx0, fy0, fx1, fy1))
                    continue
                if fx0 < px0:
                    next_fragments.append((fx0, fy0, px0, fy1))
                if fx1 > px1:
                    next_fragments.append((px1, fy0, fx1, fy1))
                clip_x0 = max(fx0, px0)
                clip_x1 = min(fx1, px1)
                if fy0 < py0:
                    next_fragments.append((clip_x0, fy0, clip_x1, py0))
                if fy1 > py1:
                    next_fragments.append((clip_x0, py1, clip_x1, fy1))
            fragments = next_fragments
        clipped.extend(fragments)
    return clipped


def _collect_page_protected_rects(
    layout_doc: LayoutDocument,
    page_index: int,
    skip_block_indices: set,
    *,
    override_block_indices: Optional[set] = None,
    unprotect_block_indices: Optional[set] = None,
    extra_protected_rects: Optional[List[Tuple[float, float, float, float]]] = None,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    overlay_erase_block_indices: Optional[set] = None,
) -> List[Tuple[float, float, float, float]]:
    """Collect layout regions that must survive redaction on one page."""
    override_ids = override_block_indices or set()
    unprotect_ids = unprotect_block_indices or set()
    overlay_erase = overlay_erase_block_indices or set()
    chart_fmt = (chart_body_format or "image").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    protected_rects: List[Tuple[float, float, float, float]] = []
    for page in layout_doc.pages:
        if page.page_index != page_index:
            continue
        for block in page.blocks:
            blk_idx = getattr(block, "index", None)
            # Blocks with a bbox override should NOT protect their
            # original area — unless the block must preserve source PDF pixels.
            preserve_pixels = block_preserves_source_pdf_visual(
                block,
                equation_format=eq_fmt,
                chart_body_format=chart_fmt,
                table_body_format=table_fmt,
            )
            if blk_idx is not None and blk_idx in override_ids and not preserve_pixels:
                continue
            if blk_idx is not None and blk_idx in unprotect_ids:
                continue
            if blk_idx is not None and blk_idx in skip_block_indices:
                if block.is_equation() and eq_fmt == "text":
                    pass
                elif preserve_pixels:
                    protected_rects.append(
                        protected_bbox_for_layout_block(
                            block,
                            equation_format=eq_fmt,
                            chart_body_format=chart_fmt,
                            table_body_format=table_fmt,
                        )
                    )
                else:
                    protected_rects.append(block.bbox)
            elif preserve_pixels:
                protected_rects.append(
                    protected_bbox_for_layout_block(
                        block,
                        equation_format=eq_fmt,
                        chart_body_format=chart_fmt,
                        table_body_format=table_fmt,
                    )
                )
            elif _layout_block_is_empty_ocr_text(block):
                if blk_idx is not None and blk_idx in overlay_erase:
                    continue
                if empty_ocr_block_overlaps_overlay_block_region(
                    block, layout_doc, overlay_erase,
                ):
                    continue
                protected_rects.append(block.bbox)

    if extra_protected_rects:
        protected_rects.extend(extra_protected_rects)
    return protected_rects


def _clip_rects_against_skipped_blocks(
    rects: List[Tuple[float, float, float, float]],
    layout_doc: LayoutDocument,
    page_index: int,
    skip_block_indices: set,
    *,
    override_block_indices: Optional[set] = None,
    unprotect_block_indices: Optional[set] = None,
    extra_protected_rects: Optional[List[Tuple[float, float, float, float]]] = None,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    overlay_erase_block_indices: Optional[set] = None,
) -> List[Tuple[float, float, float, float]]:
    """Clip redaction rects to exclude areas belonging to non-redacted blocks.

    Protects every block on the page whose content must NOT be erased:
      - Blocks in skip_block_indices (translation unchanged / failed)
      - Blocks with no recognized text (has_recognized_text()=False) — may
        still contain background graphics in the PDF
      - Chart / table / image blocks

    Blocks listed in unprotect_block_indices are NOT protected (e.g. layout
    images that will be re-embedded in the overlay PDF). Text redaction may
    erase original PDF pixels in those regions so overlay text can sit on the
    re-drawn image.

    Blocks in override_block_indices are NEVER protected, because the
    user has explicitly opted into erasing both the original and the
    override bbox areas.

    When a redaction rect overlaps with a protected block's bbox, the
    overlapping portion is split away so the original content survives.
    """
    protected_rects = _collect_page_protected_rects(
        layout_doc,
        page_index,
        skip_block_indices,
        override_block_indices=override_block_indices,
        unprotect_block_indices=unprotect_block_indices,
        extra_protected_rects=extra_protected_rects,
        equation_format=equation_format,
        chart_body_format=chart_body_format,
        table_body_format=table_body_format,
        overlay_erase_block_indices=overlay_erase_block_indices,
    )

    if not protected_rects:
        return rects

    clipped = _clip_rects_against_protected_rects(rects, protected_rects)
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
    save_garbage_level: int = 1,
    extra_redaction_rects: Optional[Dict[int, List[Tuple[float, float, float, float]]]] = None,
    skip_block_indices: Optional[set] = None,
    bbox_override_by_block_index: Optional[Dict[int, tuple]] = None,
    unprotect_block_indices: Optional[set] = None,
    protected_segment_rects: Optional[Dict[int, List[Tuple[float, float, float, float]]]] = None,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    segment_bbox_only_block_indices: Optional[set] = None,
    overlay_erase_block_indices: Optional[set] = None,
    partial_overlay_block_indices: Optional[set] = None,
    segment_redaction_rects: Optional[Dict[int, List[Tuple[float, float, float, float]]]] = None,
    redact_image_pixels: Optional[bool] = None,
    overlay_segments: Optional[List[Dict]] = None,
    overlay_task_state: Optional[Dict] = None,
    overlay_text_block_indices: Optional[set] = None,
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
        bbox_override_by_block_index: Optional mapping from block index
            to user-specified bbox override.  When provided, both the
            original block bbox and the overridden bbox are redacted
            so that any original PDF text in the expanded/moved region
            is erased.
        unprotect_block_indices: Block indices whose bboxes must NOT be
            protected from text redaction (re-embedded overlay images).

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
        f"skip_block_indices={sorted(skip_block_indices) if skip_block_indices else 'None/empty'}, "
        f"unprotect_block_indices="
        f"{sorted(unprotect_block_indices) if unprotect_block_indices else 'None/empty'}"
    )

    cleanup_started = time.perf_counter()
    phase_timings: Dict[str, float] = {}

    empty_ocr_protected = collect_empty_text_block_protected_rects(
        layout_doc,
        overlay_erase_block_indices=overlay_erase_block_indices,
        overlay_text_block_indices=overlay_text_block_indices,
        segments=overlay_segments,
        task_state=overlay_task_state,
    )
    phase_timings["collect_protected"] = time.perf_counter() - cleanup_started

    # Open the source PDF
    open_started = time.perf_counter()
    doc = fitz.open(source_pdf_path)
    phase_timings["open_pdf"] = time.perf_counter() - open_started
    try:
        collect_started = time.perf_counter()
        # Collect redaction rects from layout blocks.
        # override_original_map holds the original bboxes of blocks that
        # have overrides — these are applied AFTER clipping so that no
        # other block can protect the original text area from erasure.
        redaction_map, override_original_map = _collect_redaction_rects(
            layout_doc,
            skip_block_indices=skip_block_indices,
            bbox_override_by_block_index=bbox_override_by_block_index,
            equation_format=equation_format,
            chart_body_format=chart_body_format,
            table_body_format=table_body_format,
            segment_bbox_only_block_indices=segment_bbox_only_block_indices,
            overlay_erase_block_indices=overlay_erase_block_indices,
            partial_overlay_block_indices=partial_overlay_block_indices,
        )
        phase_timings["collect_rects"] = time.perf_counter() - collect_started

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

        if segment_redaction_rects:
            unified_logger.info(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] Segment redaction rects (applied after clip): "
                f"{sum(len(v) for v in segment_redaction_rects.values())}",
            )

        redacted_page_count = 0
        total_rect_count = 0
        raw_rect_count = 0
        redact_started = time.perf_counter()

        for page_idx in range(len(doc)):
            has_segment_rects = bool(
                segment_redaction_rects and segment_redaction_rects.get(page_idx),
            )
            if page_idx not in redaction_map and not has_segment_rects:
                continue

            page = doc[page_idx]
            rects = list(redaction_map.get(page_idx, []))
            raw_rect_count += len(rects)

            if merge_rects:
                rects = _merge_overlapping_rects(rects)

            # Protect skipped blocks: clip redaction rects so they do not
            # erase original content of excluded / translation-failed segments.
            # Blocks with bbox overrides are NEVER protected — the user
            # has explicitly opted into erasing both areas.
            override_block_indices: Optional[set] = None
            if bbox_override_by_block_index:
                override_block_indices = set(bbox_override_by_block_index.keys())
            page_extra_protected = None
            if protected_segment_rects and page_idx in protected_segment_rects:
                page_extra_protected = protected_segment_rects[page_idx]
            clip_kwargs = dict(
                override_block_indices=override_block_indices,
                unprotect_block_indices=unprotect_block_indices,
                extra_protected_rects=page_extra_protected,
                equation_format=equation_format,
                chart_body_format=chart_body_format,
                table_body_format=table_body_format,
                overlay_erase_block_indices=overlay_erase_block_indices,
            )
            page_protected = _collect_page_protected_rects(
                layout_doc,
                page_idx,
                skip_block_indices or set(),
                **clip_kwargs,
            )
            rects = _clip_rects_against_protected_rects(rects, page_protected) \
                if page_protected else rects
            if page_protected and rects:
                unified_logger.info(
                    LogModule.RESTOR,
                    f"[SOURCE_CLEANUP] Page {page_idx}: clipped redaction against "
                    f"{len(page_protected)} protected region(s) "
                    f"(after={len(rects)})",
                )
            if merge_rects:
                rects = _compact_page_redaction_rects_preserving(
                    rects, page_protected, merge=True,
                )

            # Add original bboxes of override blocks AFTER clipping so
            # they bypass protected-block exclusion entirely.  The user
            # has explicitly opted into erasing both the original and
            # override bbox areas.
            if page_idx in override_original_map:
                orig_rects = list(override_original_map[page_idx])
                if merge_rects:
                    orig_rects = _merge_overlapping_rects(orig_rects)
                post_clip_protected = _combine_protected_rect_lists(
                    page_extra_protected,
                    empty_ocr_protected.get(page_idx),
                )
                if post_clip_protected:
                    orig_rects = _clip_rects_against_protected_rects(
                        orig_rects, post_clip_protected,
                    )
                orig_rects = _dedupe_rects_not_covered(orig_rects, rects)
                if orig_rects:
                    rects.extend(orig_rects)
                if unified_logger.isEnabledFor(10):  # DEBUG
                    unified_logger.debug(
                        LogModule.RESTOR,
                        f"[SOURCE_CLEANUP] Page {page_idx}: added "
                        f"{len(orig_rects)} override-original rect(s) AFTER clipping "
                        f"(total={len(rects)})",
                    )

            if segment_redaction_rects and page_idx in segment_redaction_rects:
                seg_rects = list(segment_redaction_rects[page_idx])
                if merge_rects:
                    seg_rects = _merge_overlapping_rects(seg_rects)
                post_clip_protected = _combine_protected_rect_lists(
                    page_extra_protected,
                    empty_ocr_protected.get(page_idx),
                )
                if post_clip_protected:
                    seg_rects = _clip_rects_against_protected_rects(
                        seg_rects, post_clip_protected,
                    )
                if seg_rects:
                    rects.extend(seg_rects)

            # Final compact must preserve protected holes (charts/images).
            rects = _compact_page_redaction_rects_preserving(
                rects, page_protected, merge=merge_rects,
            )

            if not rects:
                continue

            for rx0, ry0, rx1, ry1 in rects:
                rect = fitz.Rect(rx0, ry0, rx1, ry1)
                # Add redaction annotation
                page.add_redact_annot(rect, fill=fill_color)
                total_rect_count += 1

            # Erase raster pixels only when redaction rects overlap embedded images.
            # Vector-text PDFs are much faster with PDF_REDACT_IMAGE_NONE.
            if redact_image_pixels is True:
                use_pixel_redaction = True
            elif redact_image_pixels is False:
                use_pixel_redaction = False
            else:
                use_pixel_redaction = _page_needs_pixel_redaction(page, rects)
            redact_images = (
                getattr(fitz, "PDF_REDACT_IMAGE_PIXELS", 2)
                if use_pixel_redaction
                else getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0)
            )
            page.apply_redactions(images=redact_images)
            redacted_page_count += 1

        phase_timings["redact"] = time.perf_counter() - redact_started

        unified_logger.info(
            LogModule.RESTOR,
            f"[SOURCE_CLEANUP] Redacted {total_rect_count} rects "
            f"across {redacted_page_count} pages "
            f"(raw_rects={raw_rect_count}, compacted={total_rect_count})"
        )

        # Layout/MinerU bboxes and Typst overlay pages use rotation=0 coordinates.
        # Normalize rotated source pages so overlay merge aligns with layout space.
        rotate_started = time.perf_counter()
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            rotation = page.rotation
            if rotation == 0:
                continue
            page.remove_rotation()
            unified_logger.info(
                LogModule.RESTOR,
                f"[SOURCE_CLEANUP] Page {page_idx}: normalized rotation "
                f"{rotation}° → 0 for layout-aligned overlay merge",
            )
        phase_timings["normalize_rotation"] = time.perf_counter() - rotate_started

        # Save to bytes
        save_started = time.perf_counter()
        save_kwargs = {"garbage": int(save_garbage_level), "deflate": True}
        if output_path:
            doc.save(output_path, **save_kwargs)
            phase_timings["save"] = time.perf_counter() - save_started
            phase_timings["total"] = time.perf_counter() - cleanup_started
            unified_logger.info(
                LogModule.RESTOR,
                "[SOURCE_CLEANUP] Timing breakdown: "
                + ", ".join(
                    f"{name}={elapsed:.2f}s"
                    for name, elapsed in phase_timings.items()
                ),
            )
            return output_path.read_bytes()
        else:
            pdf_buffer = io.BytesIO()
            doc.save(pdf_buffer, **save_kwargs)
            phase_timings["save"] = time.perf_counter() - save_started
            phase_timings["total"] = time.perf_counter() - cleanup_started
            unified_logger.info(
                LogModule.RESTOR,
                "[SOURCE_CLEANUP] Timing breakdown: "
                + ", ".join(
                    f"{name}={elapsed:.2f}s"
                    for name, elapsed in phase_timings.items()
                ),
            )
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
