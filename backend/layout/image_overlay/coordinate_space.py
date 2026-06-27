# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Layout coordinate space helpers for raster overlay vs PDF workflows."""

from __future__ import annotations

from typing import Any, Optional

COORDINATE_SPACE_IMAGE_PX = "image_px"
COORDINATE_SPACE_PDF_PT = "pdf_pt"


def layout_coordinate_space(layout_doc: Any) -> str:
    """Return layout bbox coordinate space: ``image_px``, ``pdf_pt``, or ``layout_pt``."""
    if layout_doc is None:
        return "layout_pt"
    metadata = getattr(layout_doc, "metadata", None)
    if isinstance(metadata, dict):
        space = metadata.get("coordinate_space")
        if isinstance(space, str) and space.strip():
            return space.strip()
    engine = str(getattr(layout_doc, "engine", "") or "").lower()
    if engine == "paddle":
        return COORDINATE_SPACE_IMAGE_PX
    return "layout_pt"


def layout_uses_image_pixel_coordinates(layout_doc: Any) -> bool:
    """True when layout block bboxes are already in source raster pixel space."""
    return layout_coordinate_space(layout_doc) == COORDINATE_SPACE_IMAGE_PX


def segment_bbox_mapped_to_image_size(
    segment: dict,
    image_size: tuple[int, int],
) -> bool:
    """True when segment bbox was already scaled to the given source raster size."""
    stored = segment.get("layout_block_bbox_image_size")
    if not isinstance(stored, (list, tuple)) or len(stored) != 2:
        return False
    try:
        return (
            int(stored[0]) == int(image_size[0])
            and int(stored[1]) == int(image_size[1])
        )
    except (TypeError, ValueError):
        return False


def segment_bbox_max_extent(segment: dict) -> tuple[float, float]:
    """Return max (x1, y1) across all layout_block_bbox entries in a segment."""
    raw = segment.get("layout_block_bbox")
    if not isinstance(raw, list):
        return 0.0, 0.0
    max_x = 0.0
    max_y = 0.0
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) < 4:
            continue
        try:
            x0, y0, x1, y1 = (
                float(entry[0]),
                float(entry[1]),
                float(entry[2]),
                float(entry[3]),
            )
        except (TypeError, ValueError):
            continue
        max_x = max(max_x, x0, x1)
        max_y = max(max_y, y0, y1)
    return max_x, max_y


def segment_bbox_exceeds_image_size(
    segment: dict,
    image_size: tuple[int, int],
    *,
    tolerance: float = 1.02,
) -> bool:
    """True when stored bbox extents exceed the reference raster (unit mismatch)."""
    img_w, img_h = image_size
    if img_w <= 0 or img_h <= 0:
        return False
    max_x, max_y = segment_bbox_max_extent(segment)
    if max_x <= 0 or max_y <= 0:
        return False
    return max_x > float(img_w) * tolerance or max_y > float(img_h) * tolerance


def clear_segment_bbox_image_mapping(segment: dict) -> None:
    """Drop cached raster-space bbox metadata so bbox can be remapped."""
    segment.pop("layout_block_bbox_space", None)
    segment.pop("layout_block_bbox_image_size", None)


def layout_canvas_dimensions(
    layout_doc: Any,
    page: Any = None,
) -> tuple[Optional[float], Optional[float]]:
    """Return Paddle/layout canvas size used for bbox coordinates."""
    metadata = getattr(layout_doc, "metadata", None)
    if isinstance(metadata, dict):
        canvas = metadata.get("paddle_layout_canvas_size")
        if isinstance(canvas, (list, tuple)) and len(canvas) >= 2:
            try:
                w = float(canvas[0])
                h = float(canvas[1])
                if w > 0 and h > 0:
                    return w, h
            except (TypeError, ValueError):
                pass
    if page is not None:
        page_w = getattr(page, "width", None)
        page_h = getattr(page, "height", None)
        if page_w and page_h and float(page_w) > 0 and float(page_h) > 0:
            return float(page_w), float(page_h)
    return None, None


def clamp_bbox_to_image_pixels(
    bbox: Any,
    image_size: tuple[int, int],
) -> Optional[list[float]]:
    """Clamp ``[x0,y0,x1,y1]`` to image bounds without layout-to-pixel scaling."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return None
    img_w, img_h = image_size
    left = max(0.0, min(min(x0, x1), float(img_w - 1)))
    top = max(0.0, min(min(y0, y1), float(img_h - 1)))
    right = max(left + 1.0, min(float(img_w), max(x0, x1)))
    bottom = max(top + 1.0, min(float(img_h), max(y0, y1)))
    return [left, top, right, bottom]
