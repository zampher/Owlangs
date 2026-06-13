# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Content-hash cache helpers for Typst overlay PDF preview."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _segment_fingerprint_fields(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment_index": segment.get("segment_index"),
        "modified_text": segment.get("modified_text"),
        "target_text": segment.get("target_text"),
        "font_size_pt": segment.get("font_size_pt"),
        "font_weight": segment.get("font_weight"),
        "font_style": segment.get("font_style"),
        "leading_em": segment.get("leading_em"),
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
) -> str:
    """Stable hash of all inputs that affect Typst overlay PDF output."""
    payload: Dict[str, Any] = {
        "equation_format": equation_format,
        "table_body_format": table_body_format,
        "chart_body_format": chart_body_format,
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
) -> None:
    prev = get_pdf_preview_cache(task_state)
    task_state["_pdf_preview_cache"] = {
        "content_hash": content_hash,
        "pdf_path": str(pdf_path),
        "cleaned_source_path": (
            str(cleaned_source_path) if cleaned_source_path is not None else None
        ),
        "has_full_render": bool(prev.get("has_full_render")) or not partial_render,
    }


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
