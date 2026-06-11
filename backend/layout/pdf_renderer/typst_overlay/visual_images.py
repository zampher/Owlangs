# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Visual image placement helpers for Typst overlay PDF rendering.

When chart_body_format, table_body_format, or equation_format is "image",
those regions must be embedded from MinerU ZIP assets instead of relying on
the source PDF layer (which may be erased during text redaction).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from layout.base import LayoutDocument
from logger.logger import LogModule, unified_logger


@dataclass(frozen=True)
class VisualImagePlacement:
    """A chart/table body region to render as an embedded image."""

    page_index: int
    block_index: int
    inner_bbox: Tuple[float, float, float, float]
    image_path: str
    block_type: str  # "chart" | "table" | "equation"


EQUATION_BLOCK_TYPES = frozenset({"interline_equation", "formula", "equation"})


def extract_equation_image_path(block) -> Optional[str]:
    """Return MinerU-rendered equation image path for an equation block."""
    image_path = getattr(block, "image_path", None)
    if isinstance(image_path, str) and image_path.strip():
        return image_path.strip()

    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return None

    for line in raw.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans") or []:
            if not isinstance(span, dict):
                continue
            if span.get("type") != "interline_equation":
                continue
            candidate = span.get("image_path")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _parse_bbox(raw_bbox) -> Optional[Tuple[float, float, float, float]]:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    try:
        return tuple(float(v) for v in raw_bbox)
    except (TypeError, ValueError):
        return None


def _extract_body_image_from_nested(
    block,
    body_sub_type: str,
    span_type: str,
) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[str]]:
    """Return (body_bbox, image_path) from nested chart_body/table_body sub-block."""
    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return None, None

    nested_blocks = raw.get("blocks") or []
    for sub in nested_blocks:
        if not isinstance(sub, dict):
            continue
        if str(sub.get("type", "")) != body_sub_type:
            continue

        body_bbox = _parse_bbox(sub.get("bbox"))
        image_path = None
        for line in sub.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                if span.get("type") != span_type:
                    continue
                candidate = span.get("image_path")
                if isinstance(candidate, str) and candidate.strip():
                    image_path = candidate.strip()
                    break
            if image_path:
                break
        if body_bbox or image_path:
            return body_bbox, image_path

    return None, None


def lookup_image_bytes(image_data_map: Dict[str, bytes], image_path: str) -> Optional[bytes]:
    """Resolve image bytes by full path or basename."""
    if not image_path or not image_data_map:
        return None

    data = image_data_map.get(image_path)
    if data:
        return data

    stripped = image_path.lstrip("./")
    data = image_data_map.get(stripped)
    if data:
        return data

    filename = os.path.basename(image_path)
    for key, value in image_data_map.items():
        if os.path.basename(key) == filename:
            return value
    return None


def collect_visual_image_placements(
    layout_doc: LayoutDocument,
    *,
    chart_body_format: str,
    table_body_format: str,
    equation_format: str = "text",
    image_data_map: Dict[str, bytes],
) -> List[VisualImagePlacement]:
    """Collect chart/table/equation regions that should be embedded as images."""
    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    placements: List[VisualImagePlacement] = []

    for page in layout_doc.pages:
        for block in page.blocks:
            block_index = getattr(block, "index", None)
            if block_index is None:
                continue

            if block.type == "chart" and chart_fmt == "image":
                body_bbox, image_path = _extract_body_image_from_nested(
                    block, "chart_body", "chart",
                )
                if not image_path and getattr(block, "image_path", None):
                    image_path = str(block.image_path)
                if not body_bbox:
                    body_bbox = _parse_bbox(getattr(block, "bbox", None))
                if body_bbox and image_path and lookup_image_bytes(image_data_map, image_path):
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=image_path,
                        block_type="chart",
                    ))

            elif block.type == "table" and table_fmt == "image":
                body_bbox, image_path = _extract_body_image_from_nested(
                    block, "table_body", "table",
                )
                if not body_bbox:
                    body_bbox = _parse_bbox(getattr(block, "bbox", None))
                if body_bbox and image_path and lookup_image_bytes(image_data_map, image_path):
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=image_path,
                        block_type="table",
                    ))

            elif block.type in EQUATION_BLOCK_TYPES and eq_fmt == "image":
                image_path = extract_equation_image_path(block)
                body_bbox = _parse_bbox(getattr(block, "bbox", None))
                if body_bbox and image_path and lookup_image_bytes(image_data_map, image_path):
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=image_path,
                        block_type="equation",
                    ))

    if placements:
        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Collected {len(placements)} visual image placement(s) "
            f"(chart_fmt={chart_fmt}, table_fmt={table_fmt}, eq_fmt={eq_fmt})",
        )
    return placements
