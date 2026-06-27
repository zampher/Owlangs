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


from layout.block_types import (
    CHART_BODY,
    EQUATION_BLOCK_TYPES,
    IMAGE,
    LEGACY_FIGURE,
    TABLE_BODY,
    VISUAL_BLOCK_TYPES,
)


def block_preserves_source_pdf_visual(
    block,
    *,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
) -> bool:
    """Return True when original PDF pixels for this block must not be redacted."""
    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    if block.type == "chart":
        return chart_fmt == "image"
    if block.type == "table":
        return table_fmt == "image"
    is_equation = getattr(block, "is_equation", None)
    if callable(is_equation) and is_equation():
        return eq_fmt == "image"
    if block.type in (IMAGE, LEGACY_FIGURE):
        return True
    return False


def protected_bbox_for_layout_block(
    block,
    *,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
) -> Tuple[float, float, float, float]:
    """Bbox region that must survive redaction for a preserve-pixels layout block."""
    if block.type == "chart":
        nested = extract_nested_sub_bbox(block, CHART_BODY)
        return nested or tuple(block.bbox)
    if block.type == "table":
        nested = extract_nested_sub_bbox(block, TABLE_BODY)
        return nested or tuple(block.bbox)
    return tuple(block.bbox)


def extract_equation_content(block) -> Optional[str]:
    """Return LaTeX/text content from an interline_equation block."""
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
            content = span.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    text = getattr(block, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def collect_preserved_visual_protected_rects(
    layout_doc: LayoutDocument,
    *,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    margin_pt: float = 2.0,
) -> Dict[int, List[Tuple[float, float, float, float]]]:
    """Per-page rects that must survive text redaction (image-format visual blocks)."""
    by_page: Dict[int, List[Tuple[float, float, float, float]]] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            if not block_preserves_source_pdf_visual(
                block,
                equation_format=equation_format,
                chart_body_format=chart_body_format,
                table_body_format=table_body_format,
            ):
                continue
            if block.type == "chart":
                bbox = extract_nested_sub_bbox(block, CHART_BODY) or tuple(block.bbox)
            elif block.type == "table":
                bbox = extract_nested_sub_bbox(block, TABLE_BODY) or tuple(block.bbox)
            else:
                bbox = tuple(block.bbox)
            x0, y0, x1, y1 = bbox
            by_page.setdefault(page.page_index, []).append((
                max(0.0, x0 - margin_pt),
                max(0.0, y0 - margin_pt),
                x1 + margin_pt,
                y1 + margin_pt,
            ))
    return by_page


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


def extract_nested_sub_bbox(
    block,
    body_sub_type: str,
) -> Optional[Tuple[float, float, float, float]]:
    """Return bbox of a nested sub-block (e.g. table_body) when present."""
    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return None
    for sub in raw.get("blocks") or []:
        if not isinstance(sub, dict):
            continue
        if str(sub.get("type", "")) != body_sub_type:
            continue
        bbox = _parse_bbox(sub.get("bbox"))
        if bbox is not None:
            return bbox
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
                    block, CHART_BODY, "chart",
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
                    block, TABLE_BODY, "table",
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

            elif block.is_equation() and eq_fmt == "image":
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

            elif block.type in (IMAGE, LEGACY_FIGURE):
                image_path = getattr(block, "image_path", None)
                if isinstance(image_path, str) and image_path.strip():
                    image_path = image_path.strip()
                else:
                    image_path = None
                body_bbox = _parse_bbox(getattr(block, "bbox", None))
                if body_bbox and image_path and lookup_image_bytes(image_data_map, image_path):
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=image_path,
                        block_type="image",
                    ))

    if placements:
        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Collected {len(placements)} visual image placement(s) "
            f"(chart_fmt={chart_fmt}, table_fmt={table_fmt}, eq_fmt={eq_fmt})",
        )
    return placements
