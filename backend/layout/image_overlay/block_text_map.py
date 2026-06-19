# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Direct segment-index -> layout block mapping for raster overlay export."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from layout.base import LayoutDocument
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    normalize_user_font_size_pt,
    normalize_user_font_weight,
    resolve_segment_layout_block_indices,
    segment_has_user_font_size_override,
    segment_has_user_font_weight_override,
)
from layout.renderable_block_indices import expand_renderable_block_indices
from logger.logger import LogModule, unified_logger

_SKIP_OVERLAY_BLOCK_TYPES = frozenset({"image", "figure", "list", "table"})
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
    normalized = (text or "").strip()
    if not normalized:
        return True
    if segment.get("is_excluded"):
        return True
    if segment.get("is_image"):
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
    if block_type in {"table", "table_body"}:
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
    seg.pop("layout_block_bbox_space", None)
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
        if block_index_to_type.get(idx, "text") in _SKIP_OVERLAY_BLOCK_TYPES:
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
            if isinstance(raw, dict) and raw.get("_cross_page_pair_of") is not None:
                continue
            if block_type in _SKIP_OVERLAY_BLOCK_TYPES:
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
        if block_type in _SKIP_OVERLAY_BLOCK_TYPES:
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
                seg.pop("layout_block_bbox_space", None)
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

        # Table segments: skip raster overlay text but keep table block bbox.
        if _is_table_highlight_segment(seg, _segment_source_text(seg)):
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
                seg.pop("layout_block_bbox_space", None)
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
            if block_index_to_type.get(block_index_int, "text") in _SKIP_OVERLAY_BLOCK_TYPES:
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
            seg.pop("layout_block_bbox_space", None)
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
                seg.pop("layout_block_bbox_space", None)
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
