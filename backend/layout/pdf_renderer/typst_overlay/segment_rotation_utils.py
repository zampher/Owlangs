# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Infer sideways text rotation from layout block bbox geometry."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.logger.logger import LogModule, unified_logger

DEFAULT_AUTO_ROTATION_ASPECT_RATIO = 20.0
DEFAULT_AUTO_ROTATION_DEGREES = 270
VALID_AUTO_ROTATION_DEGREES = {90, 180, 270}

_Bbox = Tuple[float, float, float, float]


def _bbox_dimensions(bbox: _Bbox) -> Tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0), max(0.0, y1 - y0)


def infer_sideways_rotation_from_bbox(
    bbox: _Bbox,
    *,
    aspect_ratio_threshold: float = DEFAULT_AUTO_ROTATION_ASPECT_RATIO,
    page_width_pt: Optional[float] = None,
    rotation_degrees: int = DEFAULT_AUTO_ROTATION_DEGREES,
) -> int:
    """Return configured degrees when bbox is a tall narrow strip; otherwise 0.

    Height/width must exceed *aspect_ratio_threshold* (default 20).
    Manual segment rotation always takes precedence over this heuristic.
    """
    del page_width_pt  # reserved for future margin-specific angles
    width, height = _bbox_dimensions(bbox)
    if width <= 0 or height <= 0:
        return 0
    if aspect_ratio_threshold <= 0:
        return 0
    if height / width < aspect_ratio_threshold:
        return 0
    if rotation_degrees not in VALID_AUTO_ROTATION_DEGREES:
        rotation_degrees = DEFAULT_AUTO_ROTATION_DEGREES
    return rotation_degrees


def _resolve_page_width_pt(layout_doc: Any) -> Optional[float]:
    pages = getattr(layout_doc, "pages", None) or []
    if not pages:
        return None
    first = pages[0]
    width = getattr(first, "width", None)
    try:
        return float(width) if width is not None and float(width) > 0 else None
    except (TypeError, ValueError):
        return None


def _segment_block_bboxes(
    segment: Dict[str, Any],
    layout_doc: Any,
) -> List[Tuple[int, _Bbox]]:
    indices_raw = segment.get("layout_block_indices") or []
    indices: List[int] = []
    for raw in indices_raw:
        try:
            indices.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not indices:
        return []

    bboxes_raw = segment.get("layout_block_bbox")
    parsed_bboxes: List[_Bbox] = []
    if isinstance(bboxes_raw, list):
        for entry in bboxes_raw:
            if not isinstance(entry, (list, tuple)) or len(entry) < 4:
                continue
            try:
                parsed_bboxes.append(
                    tuple(float(v) for v in entry[:4]),
                )
            except (TypeError, ValueError):
                continue

    pairs: List[Tuple[int, _Bbox]] = []
    for i, block_index in enumerate(indices):
        bbox: Optional[_Bbox] = None
        if i < len(parsed_bboxes):
            bbox = parsed_bboxes[i]
        if bbox is None and layout_doc is not None:
            from utils.format_convert_utils import get_layout_block_bbox

            looked_up = get_layout_block_bbox(layout_doc).get(block_index)
            if looked_up is not None:
                bbox = looked_up
        if bbox is not None:
            pairs.append((block_index, bbox))
    return pairs


def build_rotation_by_block_index(
    segments: List[Dict[str, Any]],
    task_state: Dict[str, Any],
    *,
    layout_doc: Any = None,
    auto_rotation_enabled: bool = False,
    auto_rotation_aspect_ratio: float = DEFAULT_AUTO_ROTATION_ASPECT_RATIO,
    auto_rotation_degrees: int = DEFAULT_AUTO_ROTATION_DEGREES,
) -> Dict[int, int]:
    """Merge manual segment rotation with optional bbox-based auto rotation."""
    rotation_map: Dict[int, int] = {}
    manual_block_indices: set[int] = set()

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        rotation = seg.get("rotation", 0)
        try:
            rotation_int = int(rotation) if rotation else 0
        except (TypeError, ValueError):
            rotation_int = 0
        if not rotation_int:
            continue
        block_indices = seg.get("layout_block_indices") or []
        for bi in block_indices:
            try:
                block_index = int(bi)
            except (TypeError, ValueError):
                continue
            if block_index < 0:
                continue
            rotation_map[block_index] = rotation_int
            manual_block_indices.add(block_index)

    if not auto_rotation_enabled:
        return rotation_map

    page_width_pt = _resolve_page_width_pt(layout_doc)
    threshold = (
        auto_rotation_aspect_ratio
        if auto_rotation_aspect_ratio > 0
        else DEFAULT_AUTO_ROTATION_ASPECT_RATIO
    )
    rotation_degrees = (
        auto_rotation_degrees
        if auto_rotation_degrees in VALID_AUTO_ROTATION_DEGREES
        else DEFAULT_AUTO_ROTATION_DEGREES
    )
    auto_applied: List[Tuple[int, int, float]] = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if seg.get("rotation"):
            continue
        for block_index, bbox in _segment_block_bboxes(seg, layout_doc):
            if block_index in manual_block_indices:
                continue
            if block_index in rotation_map:
                continue
            inferred = infer_sideways_rotation_from_bbox(
                bbox,
                aspect_ratio_threshold=threshold,
                page_width_pt=page_width_pt,
                rotation_degrees=rotation_degrees,
            )
            if not inferred:
                continue
            rotation_map[block_index] = inferred
            width, height = _bbox_dimensions(bbox)
            auto_applied.append((block_index, inferred, height / max(width, 1e-6)))

    if auto_applied:
        unified_logger.info(
            LogModule.RESTOR,
            "[TYPST_OVERLAY] Auto rotation from bbox aspect ratio "
            f"(threshold={threshold}, blocks={auto_applied[:8]})",
        )

    return rotation_map
