# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Direct segment-index -> layout block mapping for raster overlay export."""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from layout.base import LayoutDocument
from layout.block_types import IMAGE, TABLE, CHART, LIST, SKIP_OVERLAY_BLOCK_TYPES, TABLE_BODY, LEGACY_FIGURE
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    normalize_user_font_size_pt,
    normalize_user_font_weight,
    resolve_segment_layout_block_indices,
    segment_has_user_font_size_override,
    segment_has_user_font_weight_override,
)
from layout.renderable_block_indices import expand_renderable_block_indices
from layout.layout_group_pair_utils import is_layout_companion_block
from logger.logger import LogModule, unified_logger

_LOCAL_SKIP_OVERLAY_BLOCK_TYPES = frozenset({IMAGE, LEGACY_FIGURE, LIST, TABLE})
_IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)", re.DOTALL)
_MARKDOWN_IMAGE_PATH_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)", re.DOTALL)
_DETAILS_WRAPPER_RE = re.compile(r"<details\b", re.IGNORECASE)
_DETAILS_CLOSING_RE = re.compile(r"</details>", re.IGNORECASE)
_SUMMARY_TAG_RE = re.compile(r"<summary\b", re.IGNORECASE)
_MINERU_DETAILS_IMAGE_SUMMARY_RE = re.compile(
    r"<summary\b[^>]*>\s*(text_image|natural_image)\s*</summary>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TABLE_RE = re.compile(r"^<table\b", re.IGNORECASE | re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"^<ph-[a-zA-Z0-9]+>\s*$")
_HTML_TABLE_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class ImageOverlayBlockMapResult:
    """Block text map plus per-block segment provenance for overlay debug."""

    block_text_map: Dict[int, str] = field(default_factory=dict)
    block_segment_meta: Dict[int, Dict[str, Any]] = field(default_factory=dict)


def _segment_export_text(segment: Dict[str, Any], text_field: str) -> str:
    if text_field == "source_text":
        return segment.get("source_text") or ""
    return segment.get("modified_text") or segment.get("target_text") or ""


def _contains_overlay_skip_markup(text: str) -> bool:
    """Detect markdown/HTML fragments that must never be painted on layout blocks."""
    normalized = (text or "").strip()
    if not normalized:
        return False
    if _PLACEHOLDER_RE.match(normalized):
        return True
    if _IMAGE_MARKDOWN_RE.search(normalized):
        return True
    if _DETAILS_WRAPPER_RE.search(normalized):
        return True
    if _DETAILS_CLOSING_RE.search(normalized):
        return True
    if _SUMMARY_TAG_RE.search(normalized):
        return True
    if _HTML_TABLE_RE.match(normalized):
        return True
    if "images/" in normalized and ("![" in normalized or "<" in normalized):
        return True
    return False


def _is_non_overlay_segment_text(text: str, segment: Dict[str, Any]) -> bool:
    """Return True when segment text should not be painted on text layout blocks."""
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        segment_skips_overlay,
    )

    if segment.get("is_image"):
        return True
    if segment_skips_overlay(segment, "target_text"):
        return True
    normalized = (text or "").strip()
    if not normalized:
        return True
    if _contains_overlay_skip_markup(normalized):
        return True
    return False


def _is_mineru_details_image_segment(text: str) -> bool:
    """True for MinerU <details><summary>text_image|natural_image</summary> segments."""
    normalized = (text or "").strip()
    if not normalized:
        return False
    if _DETAILS_WRAPPER_RE.search(normalized) and _MINERU_DETAILS_IMAGE_SUMMARY_RE.search(normalized):
        return True
    return _is_mineru_details_image_fragment(text)


def _is_mineru_details_image_fragment(text: str) -> bool:
    """True for full or split MinerU text_image/natural_image markdown fragments."""
    normalized = (text or "").strip()
    if not normalized:
        return False
    if _MINERU_DETAILS_IMAGE_SUMMARY_RE.search(normalized):
        return True
    if _DETAILS_CLOSING_RE.search(normalized) and not _DETAILS_WRAPPER_RE.search(normalized):
        body = _extract_closing_details_body_text(normalized)
        return bool(body)
    return False


def _extract_closing_details_body_text(text: str) -> str:
    """Body from a split closing half, e.g. 'DAYONE\\n</details>'."""
    normalized = (text or "").replace("\r", "").strip()
    if not normalized:
        return ""
    return re.sub(r"</details>\s*", "", normalized, flags=re.IGNORECASE).strip()


def _extract_details_body_text(text: str) -> str:
    """Text inside <details> excluding the <summary> line."""
    normalized = (text or "").replace("\r", "")
    if not normalized:
        return ""
    if (
        _DETAILS_CLOSING_RE.search(normalized)
        and not _DETAILS_WRAPPER_RE.search(normalized)
    ):
        return _extract_closing_details_body_text(normalized)
    inner = re.sub(r"<details\b[^>]*>", "", normalized, count=1, flags=re.IGNORECASE)
    inner = re.sub(r"</details>", "", inner, count=1, flags=re.IGNORECASE)
    inner = re.sub(
        r"<summary\b[^>]*>.*?</summary>",
        "",
        inner,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return inner.strip()


def _match_image_block_by_ocr(
    norm_body: str,
    layout_doc: LayoutDocument,
    *,
    want_sub_type: Optional[str] = None,
) -> Optional[int]:
    """Find layout image block whose OCR span content matches norm_body."""
    from layout.mineru_layout_model import extract_mineru_image_span_content

    best_idx: Optional[int] = None
    best_score = -1
    for block in layout_doc.iter_blocks():
        if block.type != "image" or block.index is None:
            continue
        raw = getattr(block, "raw", None) or {}
        if not isinstance(raw, dict):
            continue
        sub_type = str(raw.get("sub_type") or "").lower()
        ocr = (block.text or "").strip() or (extract_mineru_image_span_content(raw) or "")
        norm_ocr = _normalize_text_for_matching(ocr)

        score = 0
        if want_sub_type and sub_type == want_sub_type:
            score += 10
        if norm_body and norm_ocr:
            if norm_body == norm_ocr:
                score += 100
            elif norm_body in norm_ocr or norm_ocr in norm_body:
                score += 50

        if score > best_score:
            best_score = score
            best_idx = int(block.index)

    return best_idx if best_score > 0 else None


def _mineru_details_image_sub_type(source_text: str) -> Optional[str]:
    match = _MINERU_DETAILS_IMAGE_SUMMARY_RE.search(source_text or "")
    if not match:
        return None
    return str(match.group(1)).lower()


def _resolve_mineru_details_image_block_index(
    segment: Dict[str, Any],
    layout_doc: LayoutDocument,
) -> Optional[int]:
    """Map MinerU text_image/natural_image markdown to its layout image block bbox."""
    source = _segment_source_text(segment)
    if not _is_mineru_details_image_fragment(source):
        return None

    body = _extract_details_body_text(source)
    norm_body = _normalize_text_for_matching(body)
    want_sub_type = _mineru_details_image_sub_type(source)

    if norm_body:
        matched = _match_image_block_by_ocr(
            norm_body,
            layout_doc,
            want_sub_type=want_sub_type,
        )
        if matched is not None:
            return matched

    if want_sub_type:
        for block in layout_doc.iter_blocks():
            if block.type != "image" or block.index is None:
                continue
            raw = getattr(block, "raw", None) or {}
            if isinstance(raw, dict) and str(raw.get("sub_type") or "").lower() == want_sub_type:
                return int(block.index)

    return None


def _normalize_asset_basename(path: str) -> str:
    normalized = (path or "").replace("\\", "/").strip().lower()
    if not normalized:
        return ""
    return normalized.split("/")[-1]


def _extract_markdown_image_path(text: str) -> Optional[str]:
    match = _MARKDOWN_IMAGE_PATH_RE.search(text or "")
    if not match:
        return None
    return match.group(1).strip().strip("\"'")


def _layout_block_image_basename(block: Any) -> str:
    path = getattr(block, "image_path", None) or ""
    if not path:
        raw = getattr(block, "raw", None)
        if isinstance(raw, dict):
            from layout.mineru_layout_model import _extract_image_path_from_layout_block

            path = _extract_image_path_from_layout_block(raw) or ""
    return _normalize_asset_basename(path)


def _iter_layout_block_indices_by_type(
    layout_doc: LayoutDocument,
    block_type: str,
) -> List[int]:
    indices: List[int] = []
    for block in layout_doc.iter_blocks():
        if block.type != block_type or block.index is None:
            continue
        indices.append(int(block.index))
    return sorted(indices)


def _resolve_markdown_image_block_index(
    segment: Dict[str, Any],
    layout_doc: LayoutDocument,
    *,
    claimed_blocks: Optional[set[int]] = None,
) -> Optional[int]:
    """Map ![](images/...) markdown segments to layout image blocks for bbox highlight."""
    source = _segment_source_text(segment)
    export = _segment_export_text(segment, "target_text")
    path = _extract_markdown_image_path(source) or _extract_markdown_image_path(export)
    if not path:
        return None

    norm_path = _normalize_asset_basename(path)
    for block in layout_doc.iter_blocks():
        if block.type != "image" or block.index is None:
            continue
        block_idx = int(block.index)
        basename = _layout_block_image_basename(block)
        if not basename:
            continue
        if basename == norm_path or basename in norm_path or norm_path in basename:
            return block_idx

    return None


def _is_table_highlight_segment(segment: Dict[str, Any], text: str) -> bool:
    normalized = (text or "").strip()
    block_type = str(segment.get("block_type") or "").lower()
    if block_type in {TABLE, TABLE_BODY}:
        return True
    if segment.get("is_table"):
        return True
    if _HTML_TABLE_RE.match(normalized):
        return True
    try:
        from utils.translation_segments import _is_table_segment

        return _is_table_segment(normalized)
    except Exception:
        return False


def _resolve_table_block_index(
    layout_doc: LayoutDocument,
    *,
    claimed_blocks: set[int],
) -> Optional[int]:
    table_blocks = _iter_layout_block_indices_by_type(layout_doc, "table")
    if not table_blocks:
        return None
    for block_idx in table_blocks:
        if block_idx not in claimed_blocks:
            return block_idx
    return table_blocks[0]


def _plain_text_weight_for_bbox(text: str) -> int:
    """Character count after stripping HTML for proportional table bbox splits."""
    normalized = html.unescape((text or "").strip())
    if not normalized:
        return 0
    plain = _HTML_TAG_RE.sub("", normalized)
    plain = re.sub(r"\s+", " ", plain).strip()
    return max(len(plain), 1)


def _is_decomposed_table_region_segment(segment: Dict[str, Any], text: str) -> bool:
    """True when a segment is a deep-split fragment inside a single layout table block."""
    if _is_table_highlight_segment(segment, text):
        return True
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    if "<td" in normalized or "</td>" in normalized or "<tr" in normalized:
        return True
    if segment.get("layout_block_indices_resolution") == "layout_table":
        return True
    return False


def _find_fragment_offset(
    table_html: str,
    fragment: str,
    start_cursor: int = 0,
) -> Optional[tuple[int, int]]:
    """Return (html_start, html_end) for fragment inside table HTML."""
    needle = (fragment or "").strip()
    if not needle or not table_html:
        return None
    pos = table_html.find(needle, start_cursor)
    if pos >= 0:
        return (pos, pos + len(needle))
    short = needle[: min(32, len(needle))]
    if len(short) >= 4:
        pos = table_html.find(short, start_cursor)
        if pos >= 0:
            return (pos, pos + len(short))
    return None


def _table_row_layout_weight(row_html: str) -> float:
    """Weight a table row for vertical band allocation (empty rows stay minimal)."""
    plain = _HTML_TAG_RE.sub("", row_html or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    if not plain:
        return 0.05
    line_count = max(1, plain.count("\n") + 1)
    return max(float(len(plain)), float(line_count) * 12.0)


def _build_table_row_y_spans(
    table_html: str,
    y0: float,
    y1: float,
) -> List[tuple[int, int, float, float]]:
    """Map each HTML table row to a vertical band inside the table bbox."""
    rows = list(_HTML_TABLE_ROW_RE.finditer(table_html))
    if not rows:
        return []
    table_h = max(1.0, float(y1) - float(y0))
    weights = [_table_row_layout_weight(match.group(0)) for match in rows]
    total_weight = sum(weights) or float(len(rows))
    spans: List[tuple[int, int, float, float]] = []
    cursor_y = float(y0)
    for idx, match in enumerate(rows):
        share = table_h * weights[idx] / total_weight
        top = cursor_y
        bottom = float(y1) if idx == len(rows) - 1 else cursor_y + share
        spans.append((match.start(), match.end(), top, bottom))
        cursor_y = bottom
    return spans


def _bbox_vertical_overlap(
    bbox_a: Sequence[float],
    bbox_b: Sequence[float],
) -> float:
    top = max(float(bbox_a[1]), float(bbox_b[1]))
    bottom = min(float(bbox_a[3]), float(bbox_b[3]))
    return max(0.0, bottom - top)


def _bbox_intersection_area(
    bbox_a: Sequence[float],
    bbox_b: Sequence[float],
) -> float:
    left = max(float(bbox_a[0]), float(bbox_b[0]))
    top = max(float(bbox_a[1]), float(bbox_b[1]))
    right = min(float(bbox_a[2]), float(bbox_b[2]))
    bottom = min(float(bbox_a[3]), float(bbox_b[3]))
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def _iter_paddle_det_layout_blocks(layout_doc: LayoutDocument) -> List[LayoutBlock]:
    """Collect supplemental Paddle det blocks from layout pages or stored metadata."""
    from layout.base import LayoutBlock
    from layout.ocr_provider.paddle.block_labels import map_paddle_label
    from layout.ocr_provider.paddle.paddle_det_supplements import (
        paddle_det_boxes_from_layout_doc,
    )

    blocks: List[LayoutBlock] = []
    for block in layout_doc.iter_blocks():
        if "paddle_det" in (block.tags or []):
            blocks.append(block)
    if blocks:
        return blocks

    det_entries = paddle_det_boxes_from_layout_doc(layout_doc)
    if not det_entries:
        return blocks

    page = layout_doc.pages[0] if layout_doc.pages else None
    page_index = int(page.page_index) if page is not None else 0
    for entry in det_entries:
        label = str(entry.get("label") or entry.get("block_label") or "").lower()
        bbox_raw = entry.get("bbox") or entry.get("coordinate") or entry.get("block_bbox") or []
        if len(bbox_raw) < 4:
            continue
        try:
            bbox_tuple = tuple(float(v) for v in bbox_raw[:4])
        except (TypeError, ValueError):
            continue
        block_type, sub_type, tags, should_translate = map_paddle_label(label)
        if block_type in (TABLE, IMAGE, LEGACY_FIGURE, CHART):
            continue
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
                index=None,
                text=det_text,
                tags=[*list(tags), "paddle_det"],
                should_translate=should_translate,
                raw={"paddle_det_supplement": True, **entry},
            )
        )
    return blocks


def _refine_bbox_with_paddle_det_layout_blocks(
    source_text: str,
    layout_doc: LayoutDocument,
    bbox: List[float],
) -> List[float]:
    """Snap subdivided table bbox to Paddle det boxes (text match or spatial overlap)."""
    det_blocks = _iter_paddle_det_layout_blocks(layout_doc)
    if not det_blocks:
        return bbox

    norm_source = _normalize_text_for_matching(source_text)
    best_block = None
    best_score = 0
    for block in det_blocks:
        layout_text = (block.text or "").strip()
        if layout_text:
            norm_layout = _normalize_text_for_matching(layout_text)
            if not norm_layout:
                continue
            if norm_source == norm_layout:
                score = 1000 + len(norm_layout)
            elif norm_source in norm_layout or norm_layout in norm_source:
                score = min(len(norm_source), len(norm_layout))
            else:
                continue
            if score > best_score:
                best_score = score
                best_block = block

    if best_block is not None and best_score >= 1000:
        det_x0, det_y0, det_x1, det_y1 = best_block.bbox
        return [float(det_x0), float(det_y0), float(det_x1), float(det_y1)]

    plain_source = _HTML_TAG_RE.sub("", source_text or "")
    plain_source = re.sub(r"\s+", " ", plain_source).strip()
    overlapping = [
        block
        for block in det_blocks
        if _bbox_vertical_overlap(bbox, block.bbox) > 0.0
        or _bbox_intersection_area(bbox, block.bbox) > 0.0
    ]
    if plain_source and "<" not in source_text and ">" not in source_text:
        if overlapping:
            best_overlap = max(
                overlapping,
                key=lambda block: _bbox_intersection_area(bbox, block.bbox),
            )
            area = _bbox_intersection_area(bbox, best_overlap.bbox)
            if area > 0.0 or _bbox_vertical_overlap(bbox, best_overlap.bbox) > 0.0:
                det_x0, det_y0, det_x1, det_y1 = best_overlap.bbox
                return [float(det_x0), float(det_y0), float(det_x1), float(det_y1)]

    if best_block is not None and best_score > 0:
        det_x0, det_y0, det_x1, det_y1 = best_block.bbox
        return [
            max(bbox[0], float(det_x0)),
            max(bbox[1], float(det_y0)),
            min(bbox[2], float(det_x1)),
            min(bbox[3], float(det_y1)),
        ]

    if overlapping and plain_source:
        ox0 = min(float(block.bbox[0]) for block in overlapping)
        oy0 = min(float(block.bbox[1]) for block in overlapping)
        ox1 = max(float(block.bbox[2]) for block in overlapping)
        oy1 = max(float(block.bbox[3]) for block in overlapping)
        return [
            max(bbox[0], ox0),
            max(bbox[1], oy0),
            min(bbox[2], ox1),
            min(bbox[3], oy1),
        ]
    return bbox


def _strip_html_keep_newlines(text: str) -> str:
    """Remove HTML tags but preserve newline structure for intra-row bbox splits."""
    stripped = _HTML_TAG_RE.sub("", text or "")
    return html_module.unescape(stripped)


def _subdivide_row_band_for_fragment(
    row_html: str,
    fragment: str,
    row_top: float,
    row_bottom: float,
) -> tuple[float, float]:
    """Assign a vertical sub-band inside one table row for a deep-split fragment."""
    row_h = max(1e-6, float(row_bottom) - float(row_top))
    plain_row = _strip_html_keep_newlines(row_html)
    frag_plain = _strip_html_keep_newlines(fragment).strip()
    if not frag_plain:
        return (row_top, row_bottom)

    lines = [line.strip() for line in plain_row.split("\n") if line.strip()]
    if len(lines) > 1:
        norm_frag = _normalize_text_for_matching(frag_plain)
        for idx, line in enumerate(lines):
            norm_line = _normalize_text_for_matching(line)
            if not norm_line:
                continue
            if (
                norm_frag == norm_line
                or norm_frag in norm_line
                or norm_line in norm_frag
            ):
                line_h = row_h / len(lines)
                top = row_top + idx * line_h
                bottom = row_top + (idx + 1) * line_h
                return (top, bottom)

    if plain_row.strip():
        pos = plain_row.find(frag_plain)
        end = pos + len(frag_plain)
        if pos < 0:
            short = frag_plain[: min(24, len(frag_plain))]
            if len(short) >= 4:
                pos = plain_row.find(short)
                end = pos + len(short) if pos >= 0 else pos
        if pos >= 0:
            row_len = max(1, len(plain_row))
            top = row_top + row_h * (pos / row_len)
            bottom = row_top + row_h * (min(row_len, end) / row_len)
            min_h = max(row_h * 0.05, 1.0)
            if bottom - top < min_h:
                mid = (top + bottom) / 2.0
                half = min_h / 2.0
                top = max(row_top, mid - half)
                bottom = min(row_bottom, mid + half)
            return (top, bottom)

    return (row_top, row_bottom)


def _html_range_to_layout_y(
    html_start: int,
    html_end: int,
    row_spans: List[tuple[int, int, float, float]],
    *,
    table_html: str = "",
    fragment: str = "",
) -> tuple[float, float]:
    """Convert an HTML character range to layout Y bounds inside table row band(s)."""
    if not row_spans:
        return (0.0, 0.0)

    overlapping = [
        span
        for span in row_spans
        if html_start < span[1] and html_end > span[0]
    ]
    if not overlapping:
        mid = (html_start + html_end) / 2.0
        for span in row_spans:
            if span[0] <= mid <= span[1]:
                overlapping = [span]
                break
        if not overlapping:
            return (row_spans[0][2], row_spans[-1][3])

    if len(overlapping) == 1:
        row_html_start, row_html_end, row_top, row_bottom = overlapping[0]
        row_html = table_html[row_html_start:row_html_end] if table_html else ""
        if row_html and fragment:
            return _subdivide_row_band_for_fragment(
                row_html,
                fragment,
                row_top,
                row_bottom,
            )
        row_h = max(1e-6, float(row_bottom) - float(row_top))
        row_len = max(1, row_html_end - row_html_start)
        rel_start = max(0, min(row_len, html_start - row_html_start))
        rel_end = max(rel_start + 1, min(row_len, html_end - row_html_start))
        sub_top = row_top + row_h * (rel_start / row_len)
        sub_bottom = row_top + row_h * (rel_end / row_len)
        return (sub_top, sub_bottom)

    first = overlapping[0]
    last = overlapping[-1]
    first_len = max(1, first[1] - first[0])
    last_len = max(1, last[1] - last[0])
    first_h = max(1e-6, float(first[3]) - float(first[2]))
    last_h = max(1e-6, float(last[3]) - float(last[2]))
    top = first[2] + first_h * max(0, min(1, (html_start - first[0]) / first_len))
    bottom = last[2] + last_h * max(0, min(1, (html_end - last[0]) / last_len))
    if bottom <= top:
        bottom = min(float(last[3]), top + max(first_h * 0.05, 1.0))
    return (top, bottom)


def _resolve_table_block_html(table_block: LayoutBlock) -> str:
    """Return table HTML for bbox subdivision (MinerU stores HTML on nested spans)."""
    text = (table_block.text or "").strip()
    if text:
        return text
    raw = getattr(table_block, "raw", None)
    if isinstance(raw, dict):
        from layout.mineru_layout_model import _extract_text_from_layout_block

        extracted = (_extract_text_from_layout_block(raw) or "").strip()
        if extracted:
            return extracted
    return ""


def assign_proportional_bboxes_for_single_table_layout(
    segments: List[Dict[str, Any]],
    layout_doc: LayoutDocument,
    task_state: Optional[Dict[str, Any]] = None,
) -> int:
    """Subdivide a full-page Paddle table block bbox across deep-split table segments."""
    from layout.image_overlay.coordinate_space import layout_coordinate_space

    table_blocks = [
        block
        for block in layout_doc.iter_blocks()
        if block.type == TABLE and block.index is not None
    ]
    if len(table_blocks) != 1:
        return 0

    table_block = table_blocks[0]
    table_idx = int(table_block.index)
    x0, y0, x1, y1 = table_block.bbox
    table_html = _resolve_table_block_html(table_block)
    if not table_html:
        return 0

    page = None
    if layout_doc.pages and 0 <= table_block.page_index < len(layout_doc.pages):
        page = layout_doc.pages[table_block.page_index]
    page_h = float(page.height) if page and page.height else max(float(y1), 1.0)
    table_h = max(1.0, float(y1) - float(y0))
    if table_h < page_h * 0.5:
        return 0

    row_spans = _build_table_row_y_spans(table_html, float(y0), float(y1))
    def _segment_sort_key(seg: Dict[str, Any]) -> int:
        try:
            return int(seg.get("segment_index", 0))
        except (TypeError, ValueError):
            return 0

    ordered_segments = sorted(
        (seg for seg in segments if isinstance(seg, dict)),
        key=_segment_sort_key,
    )
    if len(ordered_segments) < 2:
        return 0

    table_segment_indexes: set[int] = set()
    for seg in ordered_segments:
        source_text = _segment_source_text(seg)
        seg_index = _segment_sort_key(seg)
        if table_idx in (seg.get("layout_block_indices") or []):
            table_segment_indexes.add(seg_index)
        elif _is_decomposed_table_region_segment(seg, source_text):
            table_segment_indexes.add(seg_index)

    if len(table_segment_indexes) < 2:
        indexed_blocks = [
            block
            for block in layout_doc.iter_blocks()
            if block.index is not None
        ]
        if len(indexed_blocks) == 1 and len(ordered_segments) >= 2:
            for seg in ordered_segments:
                seg_index = _segment_sort_key(seg)
                source_text = _segment_source_text(seg)
                if _is_mineru_details_image_segment(source_text):
                    continue
                table_segment_indexes.add(seg_index)

    if len(table_segment_indexes) < 2:
        return 0

    min_index = min(table_segment_indexes)
    max_index = max(table_segment_indexes)
    updated = 0
    html_cursor = 0

    for seg in ordered_segments:
        seg_index = _segment_sort_key(seg)
        if seg_index < min_index or seg_index > max_index:
            continue
        source_text = _segment_source_text(seg)
        if _is_mineru_details_image_segment(source_text):
            continue

        if row_spans:
            fragment_offset = _find_fragment_offset(table_html, source_text, html_cursor)
            if fragment_offset is None:
                continue
            html_start, html_end = fragment_offset
            html_cursor = html_end
            sub_top, sub_bottom = _html_range_to_layout_y(
                html_start,
                html_end,
                row_spans,
                table_html=table_html,
                fragment=source_text,
            )
        else:
            # Weight-based fallback when table HTML has no <tr> rows.
            region_segments = [
                s for s in ordered_segments
                if min_index <= _segment_sort_key(s) <= max_index
            ]
            weights = [
                _plain_text_weight_for_bbox(_segment_source_text(s))
                for s in region_segments
            ]
            total_weight = sum(weights) or len(weights)
            cursor_y = float(y0)
            sub_top = float(y0)
            sub_bottom = float(y1)
            for idx, candidate in enumerate(region_segments):
                share = table_h * weights[idx] / total_weight
                band_top = cursor_y
                band_bottom = float(y1) if idx == len(region_segments) - 1 else cursor_y + share
                if _segment_sort_key(candidate) == seg_index:
                    sub_top, sub_bottom = band_top, band_bottom
                    break
                cursor_y = band_bottom

        refined = _refine_bbox_with_paddle_det_layout_blocks(
            source_text,
            layout_doc,
            [float(x0), sub_top, float(x1), sub_bottom],
        )
        seg["layout_block_bbox"] = [refined]
        from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

        clear_segment_bbox_image_mapping(seg)
        if not seg.get("layout_block_indices"):
            seg["layout_block_indices"] = [table_idx]
            seg["layout_block_indices_resolution"] = "single_table_subdivide"
        updated += 1

    if updated > 0:
        unified_logger.info(
            LogModule.EXPORT,
            "[IMAGE_OVERLAY] Subdivided single-table layout bbox for "
            f"{updated} segment(s) (table block {table_idx}, "
            f"rows={len(row_spans)}, "
            f"coordinate_space={layout_coordinate_space(layout_doc)})",
        )
    return updated


def ensure_image_overlay_segment_bboxes(
    segments: List[Dict[str, Any]],
    layout_doc: LayoutDocument,
    *,
    task_state: Optional[Dict[str, Any]] = None,
) -> int:
    """Single entry for Paddle raster overlay per-segment bbox subdivision."""
    return assign_proportional_bboxes_for_single_table_layout(
        segments,
        layout_doc,
        task_state=task_state,
    )


def _assign_segment_highlight_block(
    seg: Dict[str, Any],
    block_idx: int,
    resolution: str,
) -> bool:
    new_indices = [block_idx]
    if seg.get("layout_block_indices") == new_indices:
        return False
    seg["layout_block_indices"] = new_indices
    seg["layout_block_indices_resolution"] = resolution
    seg.pop("layout_block_bbox", None)
    from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

    clear_segment_bbox_image_mapping(seg)
    return True


def _split_by_newlines(text: str, expected: int) -> Optional[List[str]]:
    text = (text or "").replace("\r", "")
    parts = [part.strip() for part in text.split("\n") if part.strip()]
    return parts if len(parts) == expected else None


def _nearest_whitespace_boundary(text: str, target: int) -> int:
    text_len = len(text)
    if target >= text_len:
        return text_len
    if text[target : target + 1].isspace():
        return target
    window = 20
    forward = next(
        (
            target + offset
            for offset in range(1, window)
            if target + offset < text_len and text[target + offset].isspace()
        ),
        None,
    )
    backward = next(
        (
            target - offset
            for offset in range(1, window)
            if target - offset > 0 and text[target - offset].isspace()
        ),
        None,
    )
    candidates = [pos for pos in [backward, forward] if pos is not None]
    if not candidates:
        return target
    return min(candidates, key=lambda pos: abs(pos - target))


def _split_by_weights(text: str, weights: List[int]) -> List[str]:
    if not weights:
        return []
    normalized_text = text.strip()
    if not normalized_text:
        return [""] * len(weights)
    total_weight = sum(weights) or len(weights)
    text_len = len(normalized_text)
    result: List[str] = []
    cursor = 0
    for idx, weight in enumerate(weights):
        if idx == len(weights) - 1:
            result.append(normalized_text[cursor:].strip())
            break
        share = max(1, round(text_len * weight / total_weight))
        tentative_end = min(text_len, cursor + share)
        boundary = _nearest_whitespace_boundary(normalized_text, tentative_end)
        end_pos = max(boundary, cursor + 1)
        result.append(normalized_text[cursor:end_pos].strip())
        cursor = end_pos
    if len(result) < len(weights):
        result.extend([""] * (len(weights) - len(result)))
    elif len(result) > len(weights):
        extra = result[len(weights) - 1 :]
        merged = " ".join(piece for piece in extra if piece)
        result = result[: len(weights) - 1] + [merged]
    return result


def _distribute_text_to_blocks(text: str, block_hints: List[str]) -> List[str]:
    expected = len(block_hints)
    if expected == 0:
        return []
    normalized_text = (text or "").strip()
    if not normalized_text:
        return [""] * expected
    newline_split = _split_by_newlines(normalized_text, expected)
    if newline_split:
        return newline_split
    weights = [max(len((hint or "").strip()), 1) for hint in block_hints]
    return _split_by_weights(normalized_text, weights)


def _segment_source_text(segment: Dict[str, Any]) -> str:
    return (segment.get("source_text") or segment.get("text") or "").strip()


def _normalize_text_for_matching(text: str) -> str:
    """Normalize text for matching segment source to layout block OCR text."""
    if not text:
        return ""
    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    normalized = re.sub(r"^#+\s*", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"\*\*([^*]+)\*\*", r"\1", normalized)
    normalized = re.sub(r"\*([^*]+)\*", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"\$([^$]+)\$", r"\1", normalized)
    normalized = re.sub(r"\\\(([^)]+)\\\)", r"\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _match_source_text_to_layout_blocks(
    source: str,
    layout_block_original_texts: Dict[int, str],
    block_index_to_type: Dict[int, str],
) -> List[int]:
    """Map segment source text to layout blocks by normalized content matching."""
    source_stripped = (source or "").strip()
    if not source_stripped or _contains_overlay_skip_markup(source_stripped):
        return []

    norm_source = _normalize_text_for_matching(source_stripped)
    if not norm_source:
        return []

    best_indices: List[int] = []
    best_score = -1
    for idx, layout_text in layout_block_original_texts.items():
        if block_index_to_type.get(idx, "text") in _LOCAL_SKIP_OVERLAY_BLOCK_TYPES:
            continue
        norm_layout = _normalize_text_for_matching(layout_text)
        if not norm_layout:
            continue
        if norm_source == norm_layout:
            return [idx]
        if norm_source in norm_layout or norm_layout in norm_source:
            score = min(len(norm_source), len(norm_layout))
            if score > best_score and score >= 3:
                best_score = score
                best_indices = [idx]

    if best_indices:
        return best_indices

    lines = [
        line.strip()
        for line in source_stripped.replace("\r", "").split("\n")
        if line.strip()
    ]
    if len(lines) > 1:
        matched: List[int] = []
        for line in lines:
            if _contains_overlay_skip_markup(line):
                continue
            line_blocks = _match_source_text_to_layout_blocks(
                line,
                layout_block_original_texts,
                block_index_to_type,
            )
            for block_idx in line_blocks:
                if block_idx not in matched:
                    matched.append(block_idx)
        return matched

    return []


def _resolve_overlay_layout_block_indices(
    segment: Dict[str, Any],
    layout_block_original_texts: Dict[int, str],
    block_index_to_type: Dict[int, str],
    task_state: Dict[str, Any],
    *,
    allow_segment_map_fallback: bool = True,
) -> tuple[List[int], str]:
    """
    Resolve layout block indices for overlay export.

    MinerU JPG/PNG uses markdown segments (full.md) whose segment_index does not
    align 1:1 with layout block indices when <details>/image segments are present.
    Prefer matching segment source_text to layout block OCR text.
    """
    source = _segment_source_text(segment)
    matched = _match_source_text_to_layout_blocks(
        source,
        layout_block_original_texts,
        block_index_to_type,
    )
    if matched:
        return matched, "source_text_match"

    if allow_segment_map_fallback:
        indices = resolve_segment_layout_block_indices(segment, task_state)
        if indices:
            return indices, "segment_map_fallback"

    return [], "unmapped"


def build_image_overlay_block_text_map(
    layout_doc: LayoutDocument,
    segments: List[Dict[str, Any]],
    *,
    text_field: str = "target_text",
    task_state: Optional[Dict[str, Any]] = None,
) -> ImageOverlayBlockMapResult:
    """
    Map translated segment text to layout blocks for image overlay.

    Unlike PDF export mapping, this path:
    - never enables deep_split cross-segment merging
    - never assigns text to image/figure/list/table blocks
    - skips image/details/markdown placeholder segments
    - resolves layout blocks by matching segment source_text to layout OCR text
    """
    task_state = task_state or {}
    result = ImageOverlayBlockMapResult()
    block_text_map = result.block_text_map
    block_segment_meta = result.block_segment_meta
    layout_block_original_texts: Dict[int, str] = {}
    block_index_to_type: Dict[int, str] = {}
    block_index_to_bbox: Dict[int, tuple] = {}
    block_index_to_raw: Dict[int, Dict[str, Any]] = {}

    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_index_to_type[int(block.index)] = block.type
        block_index_to_bbox[int(block.index)] = block.bbox
        block_index_to_raw[int(block.index)] = getattr(block, "raw", None) or {}
        layout_block_original_texts[int(block.index)] = (block.text or "").strip()

    def _segment_sort_key(seg: Dict[str, Any]) -> int:
        try:
            return int(seg.get("segment_index", 0))
        except (TypeError, ValueError):
            return 0

    ordered_segments = sorted(
        (seg for seg in segments if isinstance(seg, dict)),
        key=_segment_sort_key,
    )

    skipped_image_segments = 0
    assigned_blocks = 0
    source_match_count = 0
    fallback_map_count = 0

    for seg in ordered_segments:
        text = _segment_export_text(seg, text_field)
        if _is_non_overlay_segment_text(text, seg):
            skipped_image_segments += 1
            continue

        indices, resolution_method = _resolve_overlay_layout_block_indices(
            seg,
            layout_block_original_texts,
            block_index_to_type,
            task_state,
        )
        if not indices:
            continue
        if resolution_method == "source_text_match":
            source_match_count += 1
        else:
            fallback_map_count += 1

        expanded = expand_renderable_block_indices(
            indices,
            layout_doc,
            block_index_to_type,
            block_index_to_bbox,
        )

        text_block_indices: List[int] = []
        for idx in expanded:
            try:
                block_index_int = int(idx)
            except (TypeError, ValueError):
                continue
            block_type = block_index_to_type.get(block_index_int, "text")
            raw = block_index_to_raw.get(block_index_int, {})
            if is_layout_companion_block(raw):
                continue
            if block_type in _LOCAL_SKIP_OVERLAY_BLOCK_TYPES:
                continue
            text_block_indices.append(block_index_int)

        if not text_block_indices:
            skipped_image_segments += 1
            continue

        if len(text_block_indices) == 1:
            per_block_texts = [text]
        else:
            block_hints = [
                layout_block_original_texts.get(idx, "") for idx in text_block_indices
            ]
            per_block_texts = _distribute_text_to_blocks(text, block_hints)

        for block_index_int, block_text in zip(text_block_indices, per_block_texts):
            overlay_text = block_text or ""
            if not overlay_text.strip():
                continue
            if _contains_overlay_skip_markup(overlay_text):
                continue
            if block_index_int in block_text_map:
                unified_logger.warning(
                    LogModule.EXPORT,
                    "[IMAGE_OVERLAY] Block "
                    f"{block_index_int} remapped by segment "
                    f"{seg.get('segment_index')}: replacing prior overlay text",
                )
            block_text_map[block_index_int] = overlay_text
            block_segment_meta[block_index_int] = {
                "source_segment_index": seg.get("segment_index"),
                "layout_block_indices": list(indices),
                "text_block_indices": list(text_block_indices),
                "resolution_method": resolution_method,
                "matched_source_text": _segment_source_text(seg)[:120],
            }
            assigned_blocks += 1

    unified_logger.info(
        LogModule.EXPORT,
        "[IMAGE_OVERLAY] Direct block map: "
        f"segments={len(ordered_segments)}, blocks={len(block_text_map)}, "
        f"assignments={assigned_blocks}, skipped_image_segments={skipped_image_segments}, "
        f"source_text_match={source_match_count}, segment_map_fallback={fallback_map_count}",
    )
    return result


def resolve_overlay_primary_text_block_index(
    segment: Dict[str, Any],
    layout_doc: LayoutDocument,
    task_state: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Primary editable text block for overlay typography (matches export mapping)."""
    task_state = task_state or {}
    layout_block_original_texts: Dict[int, str] = {}
    block_index_to_type: Dict[int, str] = {}
    block_index_to_bbox: Dict[int, tuple] = {}

    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_index_to_type[int(block.index)] = block.type
        block_index_to_bbox[int(block.index)] = block.bbox
        layout_block_original_texts[int(block.index)] = (block.text or "").strip()

    indices, _ = _resolve_overlay_layout_block_indices(
        segment,
        layout_block_original_texts,
        block_index_to_type,
        task_state,
    )
    if not indices:
        return None

    expanded = expand_renderable_block_indices(
        indices,
        layout_doc,
        block_index_to_type,
        block_index_to_bbox,
    )
    for idx in expanded:
        try:
            block_index_int = int(idx)
        except (TypeError, ValueError):
            continue
        block_type = block_index_to_type.get(block_index_int, "text")
        if block_type in _LOCAL_SKIP_OVERLAY_BLOCK_TYPES:
            continue
        return block_index_int
    return None


def assign_overlay_layout_block_indices_for_segments(
    segments: List[Dict[str, Any]],
    layout_doc: LayoutDocument,
    task_state: Optional[Dict[str, Any]] = None,
    *,
    claim_blocks: bool = True,
) -> int:
    """Assign one primary layout block per overlay segment for bbox highlight.

    MinerU JPG/PNG markdown segments often misalign with ``segment_layout_block_map``
    when image/details fragments are present. Re-resolve blocks via source_text_match
    (same path as overlay export) and optionally claim blocks in segment order so
    consecutive segments do not reuse the same bbox.
    """
    task_state = task_state or {}
    layout_block_original_texts: Dict[int, str] = {}
    block_index_to_type: Dict[int, str] = {}
    block_index_to_bbox: Dict[int, tuple] = {}

    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_index_int = int(block.index)
        block_index_to_type[block_index_int] = block.type
        block_index_to_bbox[block_index_int] = block.bbox
        layout_block_original_texts[block_index_int] = (block.text or "").strip()

    def _segment_sort_key(seg: Dict[str, Any]) -> int:
        try:
            return int(seg.get("segment_index", 0))
        except (TypeError, ValueError):
            return 0

    ordered_segments = sorted(
        (seg for seg in segments if isinstance(seg, dict)),
        key=_segment_sort_key,
    )

    claimed_blocks: set[int] = set()
    updated = 0
    duplicate_warnings: List[str] = []

    for seg in ordered_segments:
        seg_idx = seg.get("segment_index", "?")
        export_text = _segment_export_text(seg, "target_text")

        # MinerU text_image / natural_image: OCR lives on the image block; bbox = image bbox.
        image_block_idx = _resolve_mineru_details_image_block_index(seg, layout_doc)
        if image_block_idx is not None:
            new_indices = [image_block_idx]
            if seg.get("layout_block_indices") != new_indices:
                seg["layout_block_indices"] = new_indices
                seg["layout_block_indices_resolution"] = "mineru_text_image"
                seg.pop("layout_block_bbox", None)
                from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

                clear_segment_bbox_image_mapping(seg)
                updated += 1
                unified_logger.debug(
                    LogModule.EXPORT,
                    "[IMAGE_OVERLAY] Segment "
                    f"{seg_idx}: text_image -> image block {image_block_idx}",
                )
            if claim_blocks:
                claimed_blocks.add(image_block_idx)
            continue

        # Markdown image segments: skip raster overlay text but keep image block bbox.
        md_image_idx = _resolve_markdown_image_block_index(
            seg,
            layout_doc,
            claimed_blocks=claimed_blocks,
        )
        if md_image_idx is not None:
            if _assign_segment_highlight_block(seg, md_image_idx, "markdown_image"):
                updated += 1
                unified_logger.debug(
                    LogModule.EXPORT,
                    "[IMAGE_OVERLAY] Segment "
                    f"{seg_idx}: markdown image -> image block {md_image_idx}",
                )
            if claim_blocks:
                claimed_blocks.add(md_image_idx)
            continue

        # Full-table HTML wrapper only; decomposed cell fragments use text/det match.
        source_stripped = _segment_source_text(seg)
        if _HTML_TABLE_RE.match(source_stripped):
            table_idx = _resolve_table_block_index(
                layout_doc,
                claimed_blocks=claimed_blocks,
            )
            if table_idx is not None:
                if _assign_segment_highlight_block(seg, table_idx, "layout_table"):
                    updated += 1
                    unified_logger.debug(
                        LogModule.EXPORT,
                        "[IMAGE_OVERLAY] Segment "
                        f"{seg_idx}: table -> table block {table_idx}",
                    )
                if claim_blocks:
                    claimed_blocks.add(table_idx)
                continue

        if _is_non_overlay_segment_text(export_text, seg):
            if seg.get("layout_block_indices"):
                seg.pop("layout_block_indices", None)
                seg.pop("layout_block_bbox", None)
                from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

                clear_segment_bbox_image_mapping(seg)
                updated += 1
            continue

        indices, resolution_method = _resolve_overlay_layout_block_indices(
            seg,
            layout_block_original_texts,
            block_index_to_type,
            task_state,
            allow_segment_map_fallback=False,
        )
        if not indices:
            continue

        expanded = expand_renderable_block_indices(
            indices,
            layout_doc,
            block_index_to_type,
            block_index_to_bbox,
        )
        text_block_indices: List[int] = []
        for idx in expanded:
            try:
                block_index_int = int(idx)
            except (TypeError, ValueError):
                continue
            if block_index_to_type.get(block_index_int, "text") in _LOCAL_SKIP_OVERLAY_BLOCK_TYPES:
                continue
            text_block_indices.append(block_index_int)

        if not text_block_indices:
            continue

        primary: Optional[int] = None
        for block_index_int in text_block_indices:
            if claim_blocks and block_index_int in claimed_blocks:
                continue
            primary = block_index_int
            break
        if primary is None:
            primary = text_block_indices[0]
            if claim_blocks and primary in claimed_blocks:
                duplicate_warnings.append(
                    f"segment={seg_idx} block={primary} "
                    f"(all candidates claimed, candidates={text_block_indices})"
                )

        new_indices = [primary]
        old_indices = seg.get("layout_block_indices")
        if old_indices != new_indices:
            seg["layout_block_indices"] = new_indices
            seg["layout_block_indices_resolution"] = resolution_method
            seg.pop("layout_block_bbox", None)
            from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

            clear_segment_bbox_image_mapping(seg)
            updated += 1
            if old_indices and old_indices != new_indices:
                unified_logger.debug(
                    LogModule.EXPORT,
                    "[IMAGE_OVERLAY] Segment "
                    f"{seg_idx}: layout_block_indices {old_indices} -> "
                    f"{new_indices} ({resolution_method})",
                )

        if claim_blocks and primary is not None:
            claimed_blocks.add(primary)

    # Sequential content match for text segments still unmapped (never use segment_map).
    unmapped = [
        seg
        for seg in ordered_segments
        if isinstance(seg, dict)
        and not seg.get("layout_block_indices")
        and not _is_non_overlay_segment_text(_segment_export_text(seg, "target_text"), seg)
        and _resolve_mineru_details_image_block_index(seg, layout_doc) is None
    ]
    if unmapped:
        try:
            from utils import translation_segments as ts_mod

            source_chunks = [_segment_source_text(seg) for seg in unmapped]
            ts_mod._map_segments_to_layout_blocks(
                unmapped,
                source_chunks,
                layout_doc,
                unified_logger,
            )
            for seg in unmapped:
                bidxs = seg.get("layout_block_indices") or []
                if not bidxs:
                    continue
                primary = int(bidxs[0])
                seg["layout_block_indices"] = [primary]
                seg["layout_block_indices_resolution"] = "sequential_content_match"
                seg.pop("layout_block_bbox", None)
                from layout.image_overlay.coordinate_space import clear_segment_bbox_image_mapping

                clear_segment_bbox_image_mapping(seg)
                updated += 1
                if claim_blocks:
                    claimed_blocks.add(primary)
        except Exception as seq_err:
            unified_logger.debug(
                LogModule.EXPORT,
                f"[IMAGE_OVERLAY] Sequential block mapping fallback failed: {seq_err}",
            )

    if duplicate_warnings:
        preview = "; ".join(duplicate_warnings[:6])
        if len(duplicate_warnings) > 6:
            preview += f"; ... +{len(duplicate_warnings) - 6} more"
        unified_logger.warning(
            LogModule.EXPORT,
            "[IMAGE_OVERLAY] Duplicate layout block assignment after reassignment: "
            f"{preview}",
        )

    if updated > 0:
        unified_logger.info(
            LogModule.EXPORT,
            "[IMAGE_OVERLAY] Reassigned layout_block_indices for "
            f"{updated} segment(s) via overlay source_text_match",
        )
    return updated


def build_block_typography_maps_from_overlay_meta(
    segments: Sequence[Dict[str, Any]],
    block_segment_meta: Dict[int, Dict[str, Any]],
) -> Tuple[Dict[int, float], Dict[int, str]]:
    """Map user typography to layout blocks using overlay text provenance.

    Font overrides must follow the same block assignment as overlay text. Using
    ``layout_block_indices`` alone can shift user font size to the next block when
    ``source_text_match`` resolved a different block for rendering.
    """
    font_size_by_block: Dict[int, float] = {}
    font_weight_by_block: Dict[int, str] = {}
    if not segments or not block_segment_meta:
        return font_size_by_block, font_weight_by_block

    segment_by_index: Dict[int, Dict[str, Any]] = {}
    for list_idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        seg_key = seg.get("segment_index")
        if seg_key is not None:
            try:
                segment_by_index[int(seg_key)] = seg
                continue
            except (TypeError, ValueError):
                pass
        segment_by_index[list_idx] = seg

    for block_index, meta in block_segment_meta.items():
        if not isinstance(meta, dict):
            continue
        source_segment_index = meta.get("source_segment_index")
        if source_segment_index is None:
            continue
        try:
            seg_idx = int(source_segment_index)
        except (TypeError, ValueError):
            continue
        seg = segment_by_index.get(seg_idx)
        if seg is None:
            continue

        try:
            block_idx = int(block_index)
        except (TypeError, ValueError):
            continue

        if segment_has_user_font_size_override(seg):
            font_size = normalize_user_font_size_pt(seg.get("font_size_pt"))
            if font_size is not None and font_size > 0:
                font_size_by_block[block_idx] = float(font_size)

        if segment_has_user_font_weight_override(seg):
            font_weight = normalize_user_font_weight(seg.get("font_weight"))
            if font_weight is not None:
                font_weight_by_block[block_idx] = font_weight

    return font_size_by_block, font_weight_by_block
