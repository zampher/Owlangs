# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Segment-level raster overlay for single-table image workflows (Paddle / MinerU)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from layout.base import LayoutDocument
from layout.block_types import TABLE


@dataclass(frozen=True)
class SegmentOverlayDrawItem:
    """One translated segment painted directly at its layout bbox."""

    segment_index: int
    text: str
    layout_bbox: Tuple[float, float, float, float]
    user_font_size_pt: Optional[float] = None
    font_weight: str = "regular"


def is_single_table_image_layout(layout_doc: Any) -> bool:
    """True when the page was merged into one table block (PNG/JPG title blocks)."""
    if layout_doc is None:
        return False
    table_blocks = [
        block
        for block in layout_doc.iter_blocks()
        if block.type == TABLE and block.index is not None
    ]
    return len(table_blocks) == 1


def is_paddle_single_table_image_layout(layout_doc: Any) -> bool:
    """Backward-compatible alias; prefer [is_single_table_image_layout]."""
    if layout_doc is None:
        return False
    if str(getattr(layout_doc, "engine", "") or "").lower() != "paddle":
        return False
    return is_single_table_image_layout(layout_doc)


def should_use_segment_direct_overlay(layout_doc: Any) -> bool:
    """True when overlay must paint per-segment bboxes instead of layout text blocks."""
    if layout_doc is None:
        return False
    from layout.image_overlay.block_text_map import _LOCAL_SKIP_OVERLAY_BLOCK_TYPES

    if is_single_table_image_layout(layout_doc):
        return True
    engine = str(getattr(layout_doc, "engine", "") or "").lower()
    if engine != "paddle":
        return False
    from layout.image_overlay.coordinate_space import layout_uses_image_pixel_coordinates

    if not layout_uses_image_pixel_coordinates(layout_doc):
        return False
    overlayable_blocks = [
        block
        for block in layout_doc.iter_blocks()
        if block.index is not None
        and block.type not in _LOCAL_SKIP_OVERLAY_BLOCK_TYPES
    ]
    return len(overlayable_blocks) == 0


def _segment_sort_key(segment: Dict[str, Any]) -> int:
    try:
        return int(segment.get("segment_index", 0))
    except (TypeError, ValueError):
        return 0


def _read_segment_layout_bbox(segment: Dict[str, Any]) -> Optional[List[float]]:
    override = segment.get("layout_block_bbox_override")
    if isinstance(override, (list, tuple)) and len(override) >= 4:
        try:
            return [float(v) for v in override[:4]]
        except (TypeError, ValueError):
            pass
    raw = segment.get("layout_block_bbox")
    if not isinstance(raw, list) or not raw:
        return None
    first = raw[0]
    if not isinstance(first, (list, tuple)) or len(first) < 4:
        return None
    try:
        return [float(v) for v in first[:4]]
    except (TypeError, ValueError):
        return None


def build_segment_overlay_draw_items(
    segments: Sequence[Dict[str, Any]],
    layout_doc: LayoutDocument,
    *,
    text_field: str = "target_text",
    task_state: Optional[Dict[str, Any]] = None,
    image_size: Optional[Tuple[int, int]] = None,
) -> List[SegmentOverlayDrawItem]:
    """Build per-segment overlay placements using stored segment bboxes."""
    from layout.image_overlay.block_text_map import (
        _is_non_overlay_segment_text,
        _segment_export_text,
        ensure_image_overlay_segment_bboxes,
    )

    if not should_use_segment_direct_overlay(layout_doc):
        return []

    segment_list = [seg for seg in segments if isinstance(seg, dict)]
    if not segment_list:
        return []

    ensure_image_overlay_segment_bboxes(
        segment_list,
        layout_doc,
        task_state=task_state,
    )

    items: List[SegmentOverlayDrawItem] = []
    for segment in sorted(segment_list, key=_segment_sort_key):
        text = _segment_export_text(segment, text_field)
        if _is_non_overlay_segment_text(text, segment):
            continue
        # Keep layout_bbox in layout coordinates; renderer scales once to image px.
        bbox = _read_segment_layout_bbox(segment)
        if bbox is None:
            continue
        user_pt = segment.get("font_size_pt")
        try:
            user_font_pt = float(user_pt) if user_pt is not None else None
        except (TypeError, ValueError):
            user_font_pt = None
        font_weight = str(segment.get("font_weight") or "regular")
        items.append(
            SegmentOverlayDrawItem(
                segment_index=_segment_sort_key(segment),
                text=text,
                layout_bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                user_font_size_pt=user_font_pt,
                font_weight=font_weight,
            )
        )
    return items
