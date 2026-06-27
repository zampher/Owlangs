# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Supplemental LayoutBlocks from Paddle detection boxes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from layout.base import LayoutBlock
from layout.ocr_provider.paddle.block_labels import map_paddle_label

_PADDLE_IMAGE_PATH_SENTINEL = "__paddle_image__"


def _bbox_covers_page(
    bbox: Sequence[float],
    page_w: float,
    page_h: float,
    *,
    ratio: float = 0.85,
) -> bool:
    if page_w <= 0 or page_h <= 0:
        return False
    x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    bw = abs(x1 - x0)
    bh = abs(y1 - y0)
    return bw >= page_w * ratio and bh >= page_h * ratio


def _scale_bbox(
    bbox: Sequence[float],
    scale_x: float,
    scale_y: float,
) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    if scale_x != 1.0 or scale_y != 1.0:
        return (
            round(x0 * scale_x, 3),
            round(y0 * scale_y, 3),
            round(x1 * scale_x, 3),
            round(y1 * scale_y, 3),
        )
    return (x0, y0, x1, y1)


def extract_paddle_det_boxes_from_pruned(pruned: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Read detection boxes from Paddle ``prunedResult`` payload."""
    if not isinstance(pruned, dict):
        return []
    for key in ("layout_det_res", "layout_det_result", "det_res"):
        raw = pruned.get(key)
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        if isinstance(raw, dict):
            nested = raw.get("boxes") or raw.get("det_boxes") or raw.get("results")
            if isinstance(nested, list):
                return [entry for entry in nested if isinstance(entry, dict)]
    return []


def append_paddle_det_supplement_blocks(
    blocks: List[LayoutBlock],
    det_boxes: Sequence[Dict[str, Any]],
    *,
    page_index: int,
    next_block_index: int,
    page_w: float,
    page_h: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> int:
    """Append non-table ``layout_det_res`` boxes as supplemental layout blocks."""
    existing_det = any("paddle_det" in (block.tags or []) for block in blocks)
    if existing_det:
        return next_block_index

    block_index = next_block_index
    for entry in det_boxes:
        label = str(entry.get("label") or entry.get("block_label") or "").lower()
        bbox_raw = entry.get("bbox") or entry.get("coordinate") or entry.get("block_bbox") or []
        if len(bbox_raw) < 4:
            continue
        try:
            bbox_tuple = _scale_bbox(bbox_raw[:4], scale_x, scale_y)
        except (TypeError, ValueError):
            continue
        if label == "table" and _bbox_covers_page(bbox_tuple, page_w, page_h):
            continue

        block_type, sub_type, tags, should_translate = map_paddle_label(label)
        image_path: Optional[str] = None
        if block_type == "image":
            image_path = _PADDLE_IMAGE_PATH_SENTINEL
        det_text = str(
            entry.get("text")
            or entry.get("block_content")
            or entry.get("content")
            or ""
        ).strip() or None

        blocks.append(
            LayoutBlock(
                page_index=page_index,
                bbox=bbox_tuple,
                type=block_type,
                sub_type=sub_type,
                index=block_index,
                text=det_text,
                tags=[*list(tags), "paddle_det"],
                should_translate=should_translate,
                image_path=image_path,
                raw={"paddle_det_supplement": True, **entry},
            )
        )
        block_index += 1
    return block_index


def paddle_det_boxes_from_layout_doc(layout_doc: Any) -> List[Dict[str, Any]]:
    """Read stored Paddle det boxes from layout document metadata."""
    metadata = getattr(layout_doc, "metadata", None) or {}
    if not isinstance(metadata, dict):
        return []
    boxes = metadata.get("paddle_det_boxes") or []
    return [entry for entry in boxes if isinstance(entry, dict)]
