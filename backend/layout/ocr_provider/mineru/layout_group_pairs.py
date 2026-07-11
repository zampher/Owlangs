# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Pair MinerU column-flow blocks; allow same-row pairing only for empty companions."""

from __future__ import annotations

from typing import List, Optional

from layout.base import LayoutBlock, LayoutDocument
from layout.layout_group_pair_utils import (
    CROSS_PAGE_PAIR_OF_KEY,
    LAYOUT_GROUP_PAIR_OF_KEY,
    bbox_overlap_over_min_area,
    is_block_claimed_for_layout_group_pairing,
    is_bottom_left_to_right_top_wrap_pair,
    is_cross_page_companion_block,
    is_flow_column_continuation_bbox,
    is_left_column_bbox,
    is_right_column_bbox,
    is_same_row_parallel_column_pair,
    layout_group_ids_compatible,
    paddle_group_cross_column_pair,
)
from layout.ocr_provider.paddle.layout_group_pairs import (
    _attach_layout_group_pair,
    _effective_page_dims,
    _has_recognized_text,
)
from logger import unified_logger as logger
from logger.logger import LogModule


def _is_mineru_text_block(block: LayoutBlock) -> bool:
    return block.type == "text"


def _already_paired(block: LayoutBlock) -> bool:
    raw = block.raw if isinstance(block.raw, dict) else {}
    return (
        raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is not None
        or raw.get(CROSS_PAGE_PAIR_OF_KEY) is not None
    )


def _mineru_column_flow_accepts(
    primary: LayoutBlock,
    companion: LayoutBlock,
    *,
    page_height: float,
    page_width: float,
) -> bool:
    if primary.bbox is None or companion.bbox is None:
        return False
    if len(primary.bbox) != 4 or len(companion.bbox) != 4:
        return False
    if not _has_recognized_text(companion):
        if is_bottom_left_to_right_top_wrap_pair(
            primary.bbox,
            companion.bbox,
            page_height=page_height,
            page_width=page_width,
        ):
            return True
    if is_same_row_parallel_column_pair(
        primary.bbox,
        companion.bbox,
        page_width=page_width,
    ):
        # MinerU often keeps right-column OCR in the left block but leaves an empty
        # lines_deleted bbox for the right column — pair for multi-bbox overlay split.
        if not _has_recognized_text(companion):
            return paddle_group_cross_column_pair(
                primary.bbox,
                companion.bbox,
                page_width=page_width,
            )
        return False
    return is_flow_column_continuation_bbox(
        primary.bbox,
        companion.bbox,
        page_height=page_height,
        page_width=page_width,
    )


def _is_right_column_topmost_empty(
    empty: LayoutBlock,
    text_blocks: List[LayoutBlock],
    *,
    page_width: float,
    y_tol: float = 20.0,
) -> bool:
    """True when empty sits at the top of the right column on its page."""
    if empty.bbox is None or len(empty.bbox) != 4:
        return False
    if not is_right_column_bbox(empty.bbox, page_width=page_width):
        return False
    try:
        ey0 = float(empty.bbox[1])
    except (TypeError, ValueError):
        return False
    right_y0_values: List[float] = []
    for block in text_blocks:
        if block.page_index != empty.page_index:
            continue
        if block.bbox is None or len(block.bbox) != 4:
            continue
        if not is_right_column_bbox(block.bbox, page_width=page_width):
            continue
        try:
            right_y0_values.append(float(block.bbox[1]))
        except (TypeError, ValueError):
            continue
    if not right_y0_values:
        return False
    return ey0 <= min(right_y0_values) + y_tol


def _bottommost_left_column_text_block(
    text_blocks: List[LayoutBlock],
    *,
    page_index: int,
    page_width: float,
) -> Optional[LayoutBlock]:
    """Return the left-column text block with the lowest bottom edge on the page."""
    best: Optional[LayoutBlock] = None
    best_y1 = -1.0
    for block in text_blocks:
        if not _has_recognized_text(block):
            continue
        if block.page_index != page_index:
            continue
        if block.bbox is None or len(block.bbox) != 4:
            continue
        if not is_left_column_bbox(block.bbox, page_width=page_width):
            continue
        try:
            y1 = float(block.bbox[3])
        except (TypeError, ValueError):
            continue
        if y1 > best_y1:
            best_y1 = y1
            best = block
    return best


def apply_mineru_merge_prev_layout_group_pairs(
    blocks: List[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> int:
    """Pair MinerU merge_prev / lines_deleted blocks when column-flow geometry matches."""
    text_blocks = [b for b in blocks if _is_mineru_text_block(b)]
    if len(text_blocks) < 2:
        return 0

    page_h, page_w = _effective_page_dims(
        blocks,
        page_height=page_height,
        page_width=page_width,
    )

    paired = 0
    for idx, companion in enumerate(text_blocks):
        raw = companion.raw if isinstance(companion.raw, dict) else {}
        if not (raw.get("merge_prev") or raw.get("lines_deleted")):
            continue
        if _already_paired(companion) or companion.index is None:
            continue
        companion_raw = companion.raw if isinstance(companion.raw, dict) else {}
        if is_block_claimed_for_layout_group_pairing(companion_raw):
            continue

        primary: Optional[LayoutBlock] = None
        for prev in reversed(text_blocks[:idx]):
            if prev.page_index != companion.page_index:
                break
            if prev.index is None or _already_paired(prev):
                continue
            prev_raw = prev.raw if isinstance(prev.raw, dict) else {}
            if is_cross_page_companion_block(prev_raw):
                continue
            if not _has_recognized_text(prev) and not (prev.text or "").strip():
                continue
            primary = prev
            break
        if primary is None or primary.index is None:
            continue
        if not _mineru_column_flow_accepts(
            primary,
            companion,
            page_height=page_h,
            page_width=page_w,
        ):
            continue

        _attach_layout_group_pair(primary, companion)
        paired += 1

    return paired


def apply_mineru_spatial_layout_group_pairs(
    blocks: List[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> int:
    """Pair empty column companions only (Paddle-style), rejecting same-row multi-column rows."""
    text_blocks = [b for b in blocks if _is_mineru_text_block(b)]
    if len(text_blocks) < 2:
        return 0

    page_h, page_w = _effective_page_dims(
        blocks,
        page_height=page_height,
        page_width=page_width,
    )

    paired = 0
    paired_primary_indices = {
        int(p.get("index"))
        for b in text_blocks
        for p in ((b.raw or {}).get("_layout_group_pairs") or [])
        if isinstance(p, dict) and p.get("index") is not None
    }

    for empty in text_blocks:
        if _has_recognized_text(empty):
            continue
        empty_raw = empty.raw if isinstance(empty.raw, dict) else {}
        if empty_raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is not None:
            continue
        if is_block_claimed_for_layout_group_pairing(empty_raw):
            continue
        if empty.index is None:
            continue
        if int(empty.index) in paired_primary_indices:
            continue
        if empty.bbox is None or len(empty.bbox) != 4:
            continue

        overlaps_existing_block = False
        for other in text_blocks:
            if other.index is not None and other.index == empty.index:
                continue
            if other.bbox is None or len(other.bbox) != 4:
                continue
            if bbox_overlap_over_min_area(other.bbox, empty.bbox) >= 0.85:
                overlaps_existing_block = True
                break
        if overlaps_existing_block:
            continue

        if _is_right_column_topmost_empty(empty, text_blocks, page_width=page_w):
            bottom_primary = _bottommost_left_column_text_block(
                text_blocks,
                page_index=empty.page_index,
                page_width=page_w,
            )
            if (
                bottom_primary is not None
                and bottom_primary.index is not None
                and bottom_primary.index != empty.index
                and bottom_primary.bbox is not None
                and is_bottom_left_to_right_top_wrap_pair(
                    bottom_primary.bbox,
                    empty.bbox,
                    page_height=page_h,
                    page_width=page_w,
                )
            ):
                bottom_raw = (
                    bottom_primary.raw if isinstance(bottom_primary.raw, dict) else {}
                )
                if not is_cross_page_companion_block(bottom_raw):
                    _attach_layout_group_pair(bottom_primary, empty)
                    paired += 1
                    continue

        empty_gid = empty_raw.get("group_id")
        best_primary: Optional[LayoutBlock] = None
        best_order = -1
        for primary in text_blocks:
            if not _has_recognized_text(primary):
                continue
            if primary.index is None or primary.index == empty.index:
                continue
            if primary.page_index != empty.page_index:
                continue
            primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
            if is_cross_page_companion_block(primary_raw):
                continue
            if not layout_group_ids_compatible(
                primary_raw.get("group_id"),
                empty_gid,
            ):
                continue
            if not _mineru_column_flow_accepts(
                primary,
                empty,
                page_height=page_h,
                page_width=page_w,
            ):
                continue
            try:
                order = int(primary.index)
            except (TypeError, ValueError):
                order = -1
            if order > best_order:
                best_order = order
                best_primary = primary

        if best_primary is None:
            continue
        _attach_layout_group_pair(best_primary, empty)
        paired += 1

    if paired:
        logger.info(
            LogModule.LAYOUT,
            f"[MINERU_GROUP] Spatially paired {paired} empty column companion block(s) on page",
        )
    return paired


def apply_mineru_layout_group_pairs_on_document(doc: LayoutDocument) -> None:
    """Run MinerU merge_prev pairing; empty companions are handled in enrich."""
    merge_prev_total = 0
    for page in doc.pages:
        page_height = float(page.height) if page.height else None
        page_width = float(page.width) if page.width else None
        merge_prev_total += apply_mineru_merge_prev_layout_group_pairs(
            page.blocks,
            page_height=page_height,
            page_width=page_width,
        )

    if merge_prev_total:
        logger.info(
            LogModule.LAYOUT,
            f"[MINERU_GROUP] Paired merge_prev layout group blocks: count={merge_prev_total}",
        )
