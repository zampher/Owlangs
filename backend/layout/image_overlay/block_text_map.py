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
_DETAILS_WRAPPER_RE = re.compile(r"<details\b", re.IGNORECASE)
_DETAILS_CLOSING_RE = re.compile(r"</details>", re.IGNORECASE)
_SUMMARY_TAG_RE = re.compile(r"<summary\b", re.IGNORECASE)
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
