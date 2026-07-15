# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Content-hash cache helpers for Typst overlay PDF preview."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def _segment_fingerprint_fields(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment_index": segment.get("segment_index"),
        "modified_text": segment.get("modified_text"),
        "target_text": segment.get("target_text"),
        # Exclusion reason affects overlay vs source-PDF preserve (e.g. formula→image).
        "is_excluded": bool(segment.get("is_excluded")),
        "exclusion_reason": segment.get("exclusion_reason"),
        "font_size_pt": segment.get("font_size_pt"),
        "font_weight": segment.get("font_weight"),
        "font_style": segment.get("font_style"),
        "leading_em": segment.get("leading_em"),
        "rotation": segment.get("rotation", 0),
        "table_stroke_pt": segment.get("table_stroke_pt", 0.5),
        "table_border_style": segment.get("table_border_style", "booktabs"),
    }


def compute_typst_overlay_content_fingerprint(
    segments: List[Dict[str, Any]],
    *,
    equation_format: str,
    table_body_format: str,
    chart_body_format: str,
    font_size_by_block_index: Optional[Dict[int, float]] = None,
    font_weight_by_block_index: Optional[Dict[int, str]] = None,
    font_style_by_block_index: Optional[Dict[int, str]] = None,
    leading_em_by_block_index: Optional[Dict[int, float]] = None,
    rotation_by_block_index: Optional[Dict[int, int]] = None,
    table_stroke_pt_by_block_index: Optional[Dict[int, float]] = None,
    table_border_style_by_block_index: Optional[Dict[int, str]] = None,
    bbox_override_by_block_index: Optional[Dict[int, tuple]] = None,
    auto_rotation_enabled: bool = False,
    auto_rotation_aspect_ratio: Optional[float] = None,
    auto_rotation_degrees: Optional[int] = None,
) -> str:
    """Stable hash of all inputs that affect Typst overlay PDF output."""
    payload: Dict[str, Any] = {
        "equation_format": equation_format,
        "table_body_format": table_body_format,
        "chart_body_format": chart_body_format,
        "auto_rotation_enabled": bool(auto_rotation_enabled),
        "auto_rotation_aspect_ratio": (
            float(auto_rotation_aspect_ratio)
            if auto_rotation_enabled and auto_rotation_aspect_ratio is not None
            else None
        ),
        "auto_rotation_degrees": (
            int(auto_rotation_degrees)
            if auto_rotation_enabled and auto_rotation_degrees is not None
            else None
        ),
        "segments": [
            _segment_fingerprint_fields(seg)
            for seg in sorted(
                (s for s in segments if isinstance(s, dict)),
                key=lambda s: int(s.get("segment_index") or 0),
            )
        ],
        "font_size_by_block_index": _sorted_int_key_map(font_size_by_block_index),
        "font_weight_by_block_index": _sorted_int_key_map(font_weight_by_block_index),
        "font_style_by_block_index": _sorted_int_key_map(font_style_by_block_index),
        "leading_em_by_block_index": _sorted_int_key_map(leading_em_by_block_index),
        "rotation_by_block_index": _sorted_int_key_map(rotation_by_block_index),
        "table_stroke_pt_by_block_index": _sorted_int_key_map(
            table_stroke_pt_by_block_index,
        ),
        "table_border_style_by_block_index": _sorted_int_key_map(
            table_border_style_by_block_index,
        ),
        "bbox_override_by_block_index": _sorted_int_key_map(
            bbox_override_by_block_index,
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_typst_cleanup_fingerprint(
    *,
    skip_overlay_block_indices: Optional[Set[int]] = None,
    bbox_override_by_block_index: Optional[Dict[int, tuple]] = None,
    segment_bbox_overlay_block_indices: Optional[Set[int]] = None,
    image_exclusion_block_indices: Optional[Set[int]] = None,
    equation_format: str,
    table_body_format: str,
    chart_body_format: str,
    layout_page_count: int,
) -> str:
    """Stable hash of inputs that affect source PDF redaction/cleanup only."""
    payload: Dict[str, Any] = {
        "equation_format": equation_format,
        "table_body_format": table_body_format,
        "chart_body_format": chart_body_format,
        "layout_page_count": int(layout_page_count),
        "skip_overlay_block_indices": sorted(skip_overlay_block_indices or []),
        "bbox_override_by_block_index": _sorted_int_key_map(
            bbox_override_by_block_index,
        ),
        "segment_bbox_overlay_block_indices": sorted(
            segment_bbox_overlay_block_indices or [],
        ),
        # Per-segment image exclusion changes protected rects even when the
        # parent layout block still overlays other segments (skip set unchanged).
        "image_exclusion_block_indices": sorted(
            image_exclusion_block_indices or [],
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sorted_int_key_map(values: Optional[Dict[int, Any]]) -> Dict[str, Any]:
    if not values:
        return {}
    return {str(k): values[k] for k in sorted(values.keys())}


def get_pdf_preview_cache(task_state: Dict[str, Any]) -> Dict[str, Any]:
    cache = task_state.get("_pdf_preview_cache")
    return cache if isinstance(cache, dict) else {}


def store_pdf_preview_cache(
    task_state: Dict[str, Any],
    *,
    content_hash: str,
    pdf_path: Path,
    cleaned_source_path: Optional[Path] = None,
    partial_render: bool = False,
    cleanup_hash: Optional[str] = None,
    has_full_render: Optional[bool] = None,
) -> None:
    prev = get_pdf_preview_cache(task_state)
    resolved_full_render = (
        bool(has_full_render)
        if has_full_render is not None
        else (bool(prev.get("has_full_render")) or not partial_render)
    )
    entry: Dict[str, Any] = {
        "content_hash": content_hash,
        "pdf_path": str(pdf_path),
        "cleaned_source_path": (
            str(cleaned_source_path) if cleaned_source_path is not None else None
        ),
        "has_full_render": resolved_full_render,
    }
    if cleanup_hash:
        entry["cleanup_hash"] = cleanup_hash
    elif prev.get("cleanup_hash"):
        entry["cleanup_hash"] = prev.get("cleanup_hash")
    task_state["_pdf_preview_cache"] = entry


def read_cached_pdf_path(task_state: Dict[str, Any]) -> Optional[Path]:
    cache = get_pdf_preview_cache(task_state)
    raw = cache.get("pdf_path")
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.is_file() else None


def read_cached_cleaned_source_path(task_state: Dict[str, Any]) -> Optional[Path]:
    cache = get_pdf_preview_cache(task_state)
    raw = cache.get("cleaned_source_path")
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.is_file() else None
