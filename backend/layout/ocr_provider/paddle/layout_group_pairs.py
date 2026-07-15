# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Pair Paddle empty column companion blocks with their primary text blocks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from layout.base import LayoutBlock
from layout.layout_group_pair_utils import (
    LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP,
    LAYOUT_GROUP_PAIR_KIND_KEY,
    LAYOUT_GROUP_PAIR_OF_KEY,
    LAYOUT_GROUP_PAIRS_KEY,
    bbox_overlap_over_min_area,
    bbox_y_overlap_ratio,
    has_inset_image_for_figure_left_strip,
    has_inset_image_for_figure_wrap,
    is_block_claimed_for_layout_group_pairing,
    is_column_continuation_bbox,
    is_column_wrap_continuation_bbox,
    is_figure_wrap_inset_left_strip_bbox,
    is_figure_wrap_text_continuation_bbox,
    layout_group_ids_compatible,
    paddle_group_cross_column_pair,
)
from logger import unified_logger as logger
from logger.logger import LogModule


def _block_order(block: LayoutBlock) -> int:
    raw = block.raw if isinstance(block.raw, dict) else {}
    try:
        return int(raw.get("block_order"))
    except (TypeError, ValueError):
        pass
    if block.index is not None:
        return int(block.index)
    return 999_999


def _group_id(block: LayoutBlock) -> Optional[Any]:
    raw = block.raw if isinstance(block.raw, dict) else {}
    return raw.get("group_id")


def _is_parsing_res_text_block(block: LayoutBlock) -> bool:
    if block.type != "text":
        return False
    if "paddle_det" in (block.tags or []):
        return False
    return True


def _has_recognized_text(block: LayoutBlock) -> bool:
    return bool((block.text or "").strip())


def _primary_text_block_for_group(
    text_blocks: List[LayoutBlock],
    group_id: Any,
) -> Optional[LayoutBlock]:
    candidates = [
        b
        for b in text_blocks
        if _has_recognized_text(b) and _group_id(b) == group_id
    ]
    if not candidates:
        return None
    return min(candidates, key=_block_order)


def _page_height_for_block(block: LayoutBlock, page_height: Optional[float]) -> float:
    if page_height is not None and page_height > 0:
        return float(page_height)
    raw = block.raw if isinstance(block.raw, dict) else {}
    for key in ("page_height", "height"):
        try:
            value = float(raw.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 842.0


def _page_width_for_block(block: LayoutBlock, page_width: Optional[float]) -> float:
    if page_width is not None and page_width > 0:
        return float(page_width)
    raw = block.raw if isinstance(block.raw, dict) else {}
    for key in ("page_width", "width"):
        try:
            value = float(raw.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    if block.bbox is not None and len(block.bbox) == 4:
        try:
            return max(float(block.bbox[2]) * 2.05, 595.0)
        except (TypeError, ValueError):
            pass
    return 595.0


def _effective_page_dims(
    blocks: Sequence[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> Tuple[float, float]:
    """Align page dims with bbox coordinate space (PDF pt vs render px)."""
    max_x1 = 0.0
    max_y1 = 0.0
    for block in blocks:
        if block.bbox is None or len(block.bbox) != 4:
            continue
        try:
            max_x1 = max(max_x1, float(block.bbox[2]))
            max_y1 = max(max_y1, float(block.bbox[3]))
        except (TypeError, ValueError):
            continue

    eff_w = float(page_width) if page_width and page_width > 0 else max(max_x1, 595.0)
    eff_h = float(page_height) if page_height and page_height > 0 else max(max_y1, 842.0)

    if max_x1 > 0 and eff_w > max_x1 * 1.35:
        eff_w = max(max_x1 * 1.02, 1.0)
    if max_y1 > 0 and eff_h > max_y1 * 1.35:
        eff_h = max(max_y1 * 1.02, 1.0)
    return eff_h, eff_w


def _empty_pairs_with_primary(
    primary: LayoutBlock,
    empty: LayoutBlock,
    *,
    page_height: Optional[float] = None,
) -> bool:
    if primary.bbox is None or empty.bbox is None:
        return False
    if len(primary.bbox) != 4 or len(empty.bbox) != 4:
        return False
    page_h = _page_height_for_block(primary, page_height)
    if is_column_continuation_bbox(primary.bbox, empty.bbox, page_height=page_h):
        return True

    primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
    for pair in primary_raw.get(LAYOUT_GROUP_PAIRS_KEY) or []:
        if not isinstance(pair, dict):
            continue
        bbox = pair.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            if is_column_continuation_bbox(bbox, empty.bbox, page_height=page_h):
                return True
    return False


def _paddle_group_pair_accepts(
    primary: LayoutBlock,
    empty: LayoutBlock,
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> bool:
    """Return True when empty block may pair with primary via Paddle group_id."""
    if _empty_pairs_with_primary(primary, empty, page_height=page_height):
        return True
    if primary.page_index != empty.page_index:
        return False
    if primary.bbox is None or empty.bbox is None:
        return False
    page_w = _page_width_for_block(primary, page_width)
    if not paddle_group_cross_column_pair(
        primary.bbox,
        empty.bbox,
        page_width=page_w,
    ):
        return False
    # Paddle group_id already matched in caller; accept same-page cross-column empties.
    return True


def apply_paddle_layout_group_pairs(
    blocks: List[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> None:
    """Mark empty column companions and attach them to primary text blocks."""
    text_blocks = [b for b in blocks if _is_parsing_res_text_block(b)]
    if not text_blocks:
        return

    page_h, page_w = _effective_page_dims(
        blocks,
        page_height=page_height,
        page_width=page_width,
    )

    empties = [b for b in text_blocks if not _has_recognized_text(b)]
    if not empties:
        return

    paired = 0
    for empty in sorted(empties, key=_block_order):
        empty_raw = empty.raw if isinstance(empty.raw, dict) else {}
        if is_block_claimed_for_layout_group_pairing(empty_raw):
            continue
        gid = _group_id(empty)
        if gid is None:
            continue
        if empty.bbox is None or len(empty.bbox) != 4:
            continue
        if empty.index is None:
            continue

        empty_order = _block_order(empty)
        primary = _primary_text_block_for_group(text_blocks, gid)
        if primary is None or primary.index is None:
            continue
        if _block_order(primary) >= empty_order:
            continue
        if not _paddle_group_pair_accepts(
            primary,
            empty,
            page_height=page_h,
            page_width=page_w,
        ):
            continue

        _attach_layout_group_pair(primary, empty)
        paired += 1

    if paired:
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLE_GROUP] Paired {paired} empty column companion block(s) on page",
        )


def _attach_layout_group_pair(
    primary: LayoutBlock,
    empty: LayoutBlock,
    *,
    pair_kind: Optional[str] = None,
) -> None:
    """Link empty companion block to primary and append pair metadata."""
    if primary.index is None or empty.index is None:
        return
    if empty.bbox is None or len(empty.bbox) != 4:
        return

    empty_raw = empty.raw if isinstance(empty.raw, dict) else {}
    if is_block_claimed_for_layout_group_pairing(empty_raw):
        return

    empty.raw = dict(empty.raw or {})
    if empty.raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is not None:
        return
    empty.raw[LAYOUT_GROUP_PAIR_OF_KEY] = primary.index
    if pair_kind:
        empty.raw[LAYOUT_GROUP_PAIR_KIND_KEY] = pair_kind

    primary.raw = dict(primary.raw or {})
    pairs: List[Dict[str, Any]] = list(primary.raw.get(LAYOUT_GROUP_PAIRS_KEY) or [])
    pair_entry: Dict[str, Any] = {
        "index": empty.index,
        "bbox": [float(v) for v in empty.bbox[:4]],
        "page_index": empty.page_index,
    }
    if pair_kind:
        pair_entry[LAYOUT_GROUP_PAIR_KIND_KEY] = pair_kind
    if any(p.get("index") == empty.index for p in pairs):
        return
    pairs.append(pair_entry)
    pairs.sort(
        key=lambda p: (
            int(p.get("page_index") or 0),
            float((p.get("bbox") or [0, 0, 0, 0])[1]),
            float((p.get("bbox") or [0, 0, 0, 0])[0]),
        )
    )
    primary.raw[LAYOUT_GROUP_PAIRS_KEY] = pairs


def _merge_companion_text_into_primary(
    primary: LayoutBlock,
    companion: LayoutBlock,
) -> None:
    """Move companion OCR into primary so markdown keeps a single segment body."""
    primary_text = (primary.text or "").strip()
    companion_text = (companion.text or "").strip()
    if primary_text and companion_text:
        primary.text = f"{primary_text} {companion_text}"
    elif companion_text:
        primary.text = companion_text
    companion.text = ""


def _figure_wrap_match_kind(
    primary: LayoutBlock,
    companion: LayoutBlock,
    *,
    page_w: float,
    image_bboxes: Sequence[Sequence[float]],
) -> Optional[str]:
    """Return 'classic' or 'inset_left' when primary/companion form a figure-wrap pair."""
    if primary.bbox is None or companion.bbox is None:
        return None
    if len(primary.bbox) != 4 or len(companion.bbox) != 4:
        return None
    if is_figure_wrap_text_continuation_bbox(
        primary.bbox,
        companion.bbox,
        page_width=page_w,
    ) and has_inset_image_for_figure_wrap(
        primary.bbox,
        companion.bbox,
        image_bboxes,
    ):
        return "classic"
    if is_figure_wrap_inset_left_strip_bbox(
        primary.bbox,
        companion.bbox,
        page_width=page_w,
    ) and has_inset_image_for_figure_left_strip(
        primary.bbox,
        companion.bbox,
        image_bboxes,
    ):
        return "inset_left"
    return None


def apply_figure_wrap_layout_group_pairs(
    blocks: List[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> int:
    """Pair figure-wrapped text blocks when an inset image fills the notch.

    Two geometries (mutually exclusive):

    - classic: narrow left primary + full-width continuation below (companion has OCR)
    - inset_left: wide primary above + narrow left strip beside the figure (companion
      may be empty; translation is later split into the strip bbox by area)

    Without pairing, the strip/continuation becomes its own segment or is orphaned,
    so text beside the figure never gets a dedicated overlay bbox.
    """
    del page_height  # geometry is driven by bbox abutment / effective width
    text_blocks = [b for b in blocks if _is_parsing_res_text_block(b)]
    if len(text_blocks) < 2:
        return 0

    _, page_w = _effective_page_dims(
        blocks,
        page_height=None,
        page_width=page_width,
    )
    image_bboxes = [
        list(b.bbox)
        for b in blocks
        if b.type in ("image", "figure", "chart")
        and b.bbox is not None
        and len(b.bbox) == 4
    ]
    if not image_bboxes:
        return 0

    paired = 0
    claimed_primary = {
        int(p.get("index"))
        for b in text_blocks
        for p in ((b.raw or {}).get(LAYOUT_GROUP_PAIRS_KEY) or [])
        if isinstance(p, dict) and p.get("index") is not None
    }

    for companion in sorted(text_blocks, key=_block_order):
        companion_raw = companion.raw if isinstance(companion.raw, dict) else {}
        if is_block_claimed_for_layout_group_pairing(companion_raw):
            continue
        if companion.index is None or companion.bbox is None or len(companion.bbox) != 4:
            continue
        if int(companion.index) in claimed_primary:
            continue
        companion_has_text = _has_recognized_text(companion)

        best_primary: Optional[LayoutBlock] = None
        best_order = -1
        best_kind: Optional[str] = None
        for primary in text_blocks:
            if primary.index is None or primary.index == companion.index:
                continue
            if primary.page_index != companion.page_index:
                continue
            if not _has_recognized_text(primary):
                continue
            primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
            if is_block_claimed_for_layout_group_pairing(primary_raw):
                continue
            if primary.bbox is None or len(primary.bbox) != 4:
                continue
            if _block_order(primary) >= _block_order(companion):
                continue
            match_kind = _figure_wrap_match_kind(
                primary,
                companion,
                page_w=page_w,
                image_bboxes=image_bboxes,
            )
            if match_kind is None:
                continue
            # Classic wrap merges companion OCR into primary; requires companion text.
            if match_kind == "classic" and not companion_has_text:
                continue
            order = _block_order(primary)
            if order > best_order:
                best_order = order
                best_primary = primary
                best_kind = match_kind

        if best_primary is None or best_kind is None:
            continue

        if companion_has_text:
            _merge_companion_text_into_primary(best_primary, companion)
        _attach_layout_group_pair(
            best_primary,
            companion,
            pair_kind=LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP,
        )
        claimed_primary.add(int(companion.index))
        paired += 1

    if paired:
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLE_GROUP] Paired {paired} figure-wrap continuation block(s) on page",
        )
    return paired


def _spatial_pair_score(
    primary: LayoutBlock,
    empty: LayoutBlock,
    *,
    page_height: Optional[float] = None,
) -> float:
    """Higher score = better column companion match."""
    if primary.bbox is None or empty.bbox is None:
        return -1.0
    if len(primary.bbox) != 4 or len(empty.bbox) != 4:
        return -1.0
    page_h = _page_height_for_block(primary, page_height)
    if is_column_wrap_continuation_bbox(primary.bbox, empty.bbox, page_height=page_h):
        score = 0.28
        try:
            px0 = float(primary.bbox[0])
            py0 = float(primary.bbox[1])
            ex0 = float(empty.bbox[0])
        except (TypeError, ValueError):
            px0 = 0.0
            py0 = 0.0
            ex0 = 0.0
        if px0 < ex0:
            score += 0.12
        if py0 >= page_h * 0.55:
            score += 0.08
        score += min(0.25, max(0.0, py0 / page_h) * 0.25)
    elif is_column_continuation_bbox(primary.bbox, empty.bbox, page_height=page_h):
        score = bbox_y_overlap_ratio(primary.bbox, empty.bbox)
    else:
        return -1.0
    primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
    empty_raw = empty.raw if isinstance(empty.raw, dict) else {}
    primary_gid = primary_raw.get("group_id")
    empty_gid = empty_raw.get("group_id")
    if primary_gid is not None and primary_gid == empty_gid:
        score += 0.35

    primary_order = _block_order(primary)
    empty_order = _block_order(empty)
    if primary_order < empty_order:
        score += 0.15
    elif primary_order > empty_order:
        score -= 0.25
    return score


def apply_spatial_layout_group_pairs(
    blocks: List[LayoutBlock],
    *,
    page_height: Optional[float] = None,
    page_width: Optional[float] = None,
) -> None:
    """Pair unlinked empty column companions using bbox geometry only."""
    text_blocks = [b for b in blocks if _is_parsing_res_text_block(b)]
    if not text_blocks:
        return

    page_h, page_w = _effective_page_dims(
        blocks,
        page_height=page_height,
        page_width=page_width,
    )

    paired = 0
    paired_primary_indices = {
        int(p.get("index"))
        for b in text_blocks
        for p in ((b.raw or {}).get(LAYOUT_GROUP_PAIRS_KEY) or [])
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

        overlaps_text_primary = False
        for primary in text_blocks:
            if not _has_recognized_text(primary):
                continue
            if primary.bbox is None or len(primary.bbox) != 4:
                continue
            if bbox_overlap_over_min_area(primary.bbox, empty.bbox) >= 0.85:
                overlaps_text_primary = True
                break
        if overlaps_text_primary:
            continue

        empty_gid = empty_raw.get("group_id")
        best_primary: Optional[LayoutBlock] = None
        best_score = -1.0
        for primary in text_blocks:
            if not _has_recognized_text(primary):
                continue
            if primary.index is None or primary.index == empty.index:
                continue
            primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
            primary_gid = primary_raw.get("group_id")
            if not layout_group_ids_compatible(primary_gid, empty_gid):
                continue
            score = _spatial_pair_score(primary, empty, page_height=page_h)
            if score > best_score:
                best_score = score
                best_primary = primary

        if best_primary is None or best_score < 0.12:
            continue
        _attach_layout_group_pair(best_primary, empty)
        paired += 1

    if paired:
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLE_GROUP] Spatially paired {paired} empty column companion block(s) on page",
        )
