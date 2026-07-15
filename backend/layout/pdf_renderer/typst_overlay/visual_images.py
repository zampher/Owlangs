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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AbstractSet, Dict, List, Optional, Tuple

from layout.base import LayoutDocument
from layout.ocr_provider.paddle.layout_parser import _PADDLE_IMAGE_PATH_SENTINEL
from logger.logger import LogModule, unified_logger

PADDLE_SOURCE_PDF_IMAGE_SENTINEL = _PADDLE_IMAGE_PATH_SENTINEL
EQUATION_SOURCE_PDF_FALLBACK_SENTINEL = "__equation_source_pdf__"


@dataclass(frozen=True)
class VisualImagePlacement:
    """A chart/table body region to render as an embedded image."""

    page_index: int
    block_index: int
    inner_bbox: Tuple[float, float, float, float]
    image_path: str
    block_type: str  # "chart" | "table" | "equation" | "image"


from layout.block_types import (
    CHART_BODY,
    EQUATION_BLOCK_TYPES,
    IMAGE,
    LEGACY_FIGURE,
    TABLE_BODY,
    VISUAL_BLOCK_TYPES,
)


def chart_block_has_replaceable_html_body(block) -> bool:
    """True when the chart exposes markdown-table/HTML content for overlay re-render."""
    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return False
    for sub in raw.get("blocks") or []:
        if not isinstance(sub, dict):
            continue
        if str(sub.get("type", "")) != CHART_BODY:
            continue
        for line in sub.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                if span.get("type") != "chart":
                    continue
                content = span.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                text = content.strip()
                lowered = text.lower()
                if (
                    text.startswith("|")
                    or "<table" in lowered
                    or text.startswith("<div")
                    or text.startswith("<svg")
                    or text.startswith("<img")
                ):
                    return True
                # Markdown table separator heuristic
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if "|" in text and any(
                    "|" in ln and all(c in " -:|" for c in ln.replace("|", "").strip())
                    for ln in lines
                ):
                    return True
    return False


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
        # Image mode always keeps source pixels. HTML mode only erases when a
        # replaceable HTML/markdown body exists; otherwise keep the chart.
        if chart_fmt == "image":
            return True
        return not chart_block_has_replaceable_html_body(block)
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
    if isinstance(raw, dict):
        paddle_content = raw.get("block_content")
        if isinstance(paddle_content, str) and paddle_content.strip():
            return paddle_content.strip()
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


# Regex to detect existing TeX math delimiters.
_EQUATION_DELIMITED_RE = re.compile(
    r"^(\$\$.*\$\$|\$.*\$|\\\[.*\\\]|\\\(.*\\\))$",
    re.DOTALL,
)


def normalize_equation_content_for_typst(content: Optional[str]) -> Optional[str]:
    r"""Ensure extracted equation LaTeX has math delimiters for Typst rendering.

    MinerU may return bare LaTeX source (e.g. ``x = 1``) without ``$...$`` or
    ``\(...\)`` delimiters. When such content is passed to cmarker it is
    rendered as plain text, so the formula source becomes visible in the PDF.
    This helper wraps bare LaTeX in ``$$...$$`` (display math) while keeping
    existing delimiters untouched so downstream sanitization can normalize
    them.
    """
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    if _EQUATION_DELIMITED_RE.match(text):
        return text
    return f"$${text}$$"


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


def is_paddle_source_pdf_image_path(image_path: Optional[str]) -> bool:
    """Return True when layout image pixels exist only on the source PDF."""
    return isinstance(image_path, str) and image_path.strip() == PADDLE_SOURCE_PDF_IMAGE_SENTINEL


def is_equation_source_pdf_fallback_path(image_path: Optional[str]) -> bool:
    """Return True when equation pixels must be cropped from the source PDF."""
    return (
        isinstance(image_path, str)
        and image_path.strip() == EQUATION_SOURCE_PDF_FALLBACK_SENTINEL
    )


def is_source_pdf_crop_image_path(image_path: Optional[str]) -> bool:
    """Return True when image bytes should be extracted from the source PDF region."""
    return is_paddle_source_pdf_image_path(image_path) or is_equation_source_pdf_fallback_path(
        image_path
    )


def extract_image_bytes_from_pdf_region(
    source_pdf_path: Path,
    page_index: int,
    bbox: Tuple[float, float, float, float],
    *,
    dpi: int = 150,
) -> Optional[bytes]:
    """Crop a PDF page region to PNG bytes (Paddle OCR image blocks)."""
    try:
        import fitz
    except ImportError:
        unified_logger.warning(
            LogModule.RESTOR,
            "[TYPST_OVERLAY] PyMuPDF unavailable; cannot extract paddle PDF images",
        )
        return None

    try:
        doc = fitz.open(source_pdf_path)
    except Exception as exc:
        unified_logger.warning(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Failed to open source PDF for image extract: {exc}",
        )
        return None

    try:
        if page_index < 0 or page_index >= len(doc):
            return None
        page = doc[page_index]
        rect = fitz.Rect(*bbox) & page.rect
        if rect.is_empty:
            return None
        pix = page.get_pixmap(clip=rect, dpi=dpi)
        return pix.tobytes("png")
    except Exception as exc:
        unified_logger.warning(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Failed to extract PDF image on page {page_index + 1}: {exc}",
        )
        return None
    finally:
        doc.close()


def collect_paddle_source_pdf_image_placements(
    layout_doc: LayoutDocument,
) -> List[VisualImagePlacement]:
    """Collect image blocks whose raster lives only on the source PDF layer."""
    placements: List[VisualImagePlacement] = []
    for page in layout_doc.pages:
        for block in page.blocks:
            if block.type not in (IMAGE, LEGACY_FIGURE):
                continue
            image_path = getattr(block, "image_path", None)
            if not is_paddle_source_pdf_image_path(image_path):
                continue
            block_index = getattr(block, "index", None)
            if block_index is None:
                continue
            body_bbox = _parse_bbox(getattr(block, "bbox", None))
            if body_bbox is None:
                continue
            placements.append(VisualImagePlacement(
                page_index=page.page_index,
                block_index=block_index,
                inner_bbox=body_bbox,
                image_path=PADDLE_SOURCE_PDF_IMAGE_SENTINEL,
                block_type="image",
            ))
    if placements:
        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Collected {len(placements)} paddle source-PDF "
            "image placement(s)",
        )
    return placements


def collect_latex_overlay_equation_block_indices(layout_doc: LayoutDocument) -> set[int]:
    """Return layout block indices for equation blocks (LaTeX overlay targets)."""
    indices: set[int] = set()
    for page in layout_doc.pages:
        for block in page.blocks:
            if not block.is_equation():
                continue
            block_index = getattr(block, "index", None)
            if block_index is None:
                continue
            try:
                indices.add(int(block_index))
            except (TypeError, ValueError):
                continue
    return indices


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
    equation_image_fallback_block_indices: Optional[AbstractSet[int]] = None,
) -> List[VisualImagePlacement]:
    """Collect chart/table/equation regions that should be embedded as images."""
    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    fallback_eq_blocks = equation_image_fallback_block_indices or set()
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

            elif block.is_equation() and (
                eq_fmt == "image"
                or block_index in fallback_eq_blocks
            ):
                image_path = extract_equation_image_path(block)
                body_bbox = _parse_bbox(getattr(block, "bbox", None))
                if not body_bbox:
                    continue
                if image_path and lookup_image_bytes(image_data_map, image_path):
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=image_path,
                        block_type="equation",
                    ))
                elif block_index in fallback_eq_blocks:
                    placements.append(VisualImagePlacement(
                        page_index=page.page_index,
                        block_index=block_index,
                        inner_bbox=body_bbox,
                        image_path=EQUATION_SOURCE_PDF_FALLBACK_SENTINEL,
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
