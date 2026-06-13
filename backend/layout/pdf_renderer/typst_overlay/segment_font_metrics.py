# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Per-segment font size helpers for PDF Typst overlay rendering."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layout.base import LayoutBlock, LayoutDocument
from layout.pdf_renderer.typst_overlay.font_fit import (
    DEFAULT_LEADING_EM,
    FontFitCalculator,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock, layout_block_to_render_block

FONT_SIZE_PT_MIN = 5.0
FONT_SIZE_PT_MAX = 72.0
FONT_SIZE_PT_STEP = 0.1

LEADING_EM_MIN = 0.35
LEADING_EM_MAX = 3.0
LEADING_EM_STEP = 0.05
LEADING_EM_DEFAULT = DEFAULT_LEADING_EM

VALID_FONT_WEIGHTS = frozenset({"regular", "bold"})
VALID_FONT_STYLES = frozenset({"normal", "italic"})

_NON_TEXT_BLOCK_TYPES = frozenset({
    "image",
    "figure",
    "table",
    "chart",
    "list",
})


def clamp_font_size_pt(value: float) -> float:
    """Clamp user/computed font size to supported PDF range."""
    clamped = max(FONT_SIZE_PT_MIN, min(FONT_SIZE_PT_MAX, float(value)))
    steps = round(clamped / FONT_SIZE_PT_STEP)
    return round(steps * FONT_SIZE_PT_STEP, 1)


def normalize_user_font_size_pt(value: Any) -> Optional[float]:
    """Parse and validate a user font size; return None when invalid."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < FONT_SIZE_PT_MIN or parsed > FONT_SIZE_PT_MAX:
        return None
    return clamp_font_size_pt(parsed)


def segment_font_size_source(segment: Dict[str, Any]) -> str:
    """Return ``user`` when segment has a persisted override, else ``auto``."""
    if normalize_user_font_size_pt(segment.get("font_size_pt")) is not None:
        return "user"
    return "auto"


def normalize_user_font_weight(value: Any) -> Optional[str]:
    """Parse and validate a user font weight; return None when invalid."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("bold", "700", "semibold", "600"):
        return "bold"
    if text in ("regular", "normal", "400"):
        return "regular"
    return None


def normalize_user_font_style(value: Any) -> Optional[str]:
    """Parse and validate a user font style; return None when invalid."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "italic" if value else "normal"
    text = str(value).strip().lower()
    if text in ("italic", "oblique"):
        return "italic"
    if text in ("normal", "regular", "roman"):
        return "normal"
    return None


def segment_font_weight_source(segment: Dict[str, Any]) -> str:
    if normalize_user_font_weight(segment.get("font_weight")) is not None:
        return "user"
    return "auto"


def segment_font_style_source(segment: Dict[str, Any]) -> str:
    if normalize_user_font_style(segment.get("font_style")) is not None:
        return "user"
    return "auto"


def clamp_leading_em(value: float) -> float:
    """Clamp user/computed line spacing to supported PDF range."""
    clamped = max(LEADING_EM_MIN, min(LEADING_EM_MAX, float(value)))
    steps = round(clamped / LEADING_EM_STEP)
    return round(steps * LEADING_EM_STEP, 2)


def normalize_user_leading_em(value: Any) -> Optional[float]:
    """Parse and validate a user line spacing (em); return None when invalid."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < LEADING_EM_MIN or parsed > LEADING_EM_MAX:
        return None
    return clamp_leading_em(parsed)


def segment_leading_em_source(segment: Dict[str, Any]) -> str:
    if normalize_user_leading_em(segment.get("leading_em")) is not None:
        return "user"
    return "auto"


def compute_block_font_weight_from_layout(block: LayoutBlock) -> str:
    """Infer font weight from MinerU layout metadata."""
    raw = getattr(block, "raw", None) or {}
    if isinstance(raw, dict):
        weight = normalize_user_font_weight(
            raw.get("font_weight") or raw.get("weight"),
        )
        if weight is not None:
            return weight
    return "regular"


def compute_block_font_style_from_layout(block: LayoutBlock) -> str:
    """Infer font style from MinerU layout metadata."""
    raw = getattr(block, "raw", None) or {}
    if isinstance(raw, dict):
        style = normalize_user_font_style(
            raw.get("font_style") or raw.get("style") or raw.get("italic"),
        )
        if style is not None:
            return style
    return "normal"


def is_font_size_editable_block_type(block_type: str) -> bool:
    return (block_type or "text") not in _NON_TEXT_BLOCK_TYPES


def primary_layout_block_index(
    segment: Dict[str, Any],
    block_index_to_type: Optional[Dict[int, str]] = None,
    task_state: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Pick the main text block for font metrics within a segment."""
    indices = resolve_segment_layout_block_indices(segment, task_state)
    if not indices:
        return None

    type_map = block_index_to_type or {}
    for idx in indices:
        if is_font_size_editable_block_type(type_map.get(idx, "text")):
            return idx
    return indices[0]


def compute_block_render_font_size_pt(
    block: LayoutBlock,
    text: str,
    *,
    calculator: Optional[FontFitCalculator] = None,
) -> Optional[float]:
    """Dry-run Typst font fit for one layout block."""
    metrics = compute_block_render_fit_metrics(
        block, text, calculator=calculator,
    )
    return metrics[0] if metrics else None


def compute_block_render_fit_metrics(
    block: LayoutBlock,
    text: str,
    *,
    calculator: Optional[FontFitCalculator] = None,
) -> Optional[tuple[float, float]]:
    """Dry-run Typst font fit; return (font_size_pt, leading_em)."""
    if not text or not text.strip():
        return None
    if not is_font_size_editable_block_type(getattr(block, "type", "") or "text"):
        return None

    calc = calculator or FontFitCalculator()
    layout_raw = getattr(block, "raw", None) or {}
    rb = layout_block_to_render_block(
        block,
        page_index=getattr(block, "page_index", 0) or 0,
        translated_text=text,
    )
    fitted = calc.calculate_fit_params(rb, layout_raw=layout_raw)
    return (
        round(float(fitted.font_size_pt), 1),
        round(float(fitted.leading_em), 2),
    )


def enrich_segment_font_fields(
    segment: Dict[str, Any],
    layout_doc: Optional[LayoutDocument],
    *,
    text: Optional[str] = None,
    calculator: Optional[FontFitCalculator] = None,
    task_state: Optional[Dict[str, Any]] = None,
) -> None:
    """Add computed font fields to a segment dict (mutates in place)."""
    segment["font_size_source"] = segment_font_size_source(segment)
    segment["font_weight_source"] = segment_font_weight_source(segment)
    segment["font_style_source"] = segment_font_style_source(segment)
    segment["leading_em_source"] = segment_leading_em_source(segment)

    if layout_doc is None:
        segment.pop("computed_font_size_pt", None)
        segment.pop("computed_font_weight", None)
        segment.pop("computed_font_style", None)
        segment.pop("computed_leading_em", None)
        segment.pop("pdf_page_number", None)
        return

    block_map: Dict[int, LayoutBlock] = {}
    type_map: Dict[int, str] = {}
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_map[int(block.index)] = block
        type_map[int(block.index)] = getattr(block, "type", "") or "text"

    block_idx = primary_layout_block_index(segment, type_map, task_state)
    if block_idx is None or block_idx not in block_map:
        segment.pop("computed_font_size_pt", None)
        segment.pop("computed_font_weight", None)
        segment.pop("computed_font_style", None)
        segment.pop("computed_leading_em", None)
        segment.pop("pdf_page_number", None)
        return

    block = block_map[block_idx]
    page_index = getattr(block, "page_index", None)
    if page_index is not None:
        try:
            segment["pdf_page_number"] = int(page_index) + 1
        except (TypeError, ValueError):
            segment.pop("pdf_page_number", None)
    else:
        segment.pop("pdf_page_number", None)

    if not is_font_size_editable_block_type(type_map.get(block_idx, "text")):
        segment.pop("computed_font_size_pt", None)
        segment.pop("computed_font_weight", None)
        segment.pop("computed_font_style", None)
        segment.pop("computed_leading_em", None)
        return

    segment["computed_font_weight"] = compute_block_font_weight_from_layout(block)
    segment["computed_font_style"] = compute_block_font_style_from_layout(block)

    content = text
    if content is None:
        content = (
            segment.get("modified_text")
            or segment.get("target_text")
            or segment.get("text")
            or segment.get("source_text")
            or ""
        )
    computed = compute_block_render_fit_metrics(
        block,
        str(content),
        calculator=calculator,
    )
    if computed is not None:
        segment["computed_font_size_pt"] = computed[0]
        segment["computed_leading_em"] = computed[1]
    else:
        segment.pop("computed_font_size_pt", None)
        segment.pop("computed_leading_em", None)


def enrich_segments_font_fields(
    layout_doc: Optional[LayoutDocument],
    segments: List[Dict[str, Any]],
    *,
    text_field: str = "target_text",
    task_state: Optional[Dict[str, Any]] = None,
) -> None:
    """Enrich all segments with computed font metadata."""
    if not segments:
        return
    calc = FontFitCalculator()
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        text = seg.get(text_field) or seg.get("modified_text") or seg.get("target_text")
        if not text:
            text = seg.get("text") or seg.get("source_text")
        enrich_segment_font_fields(
            seg,
            layout_doc,
            text=str(text or ""),
            calculator=calc,
            task_state=task_state,
        )


def resolve_segment_layout_block_indices(
    segment: Dict[str, Any],
    task_state: Optional[Dict[str, Any]] = None,
) -> List[int]:
    """Resolve layout block indices for a segment from stored fields or task maps."""
    indices: List[int] = []
    seen: set[int] = set()
    for raw in segment.get("layout_block_indices") or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value not in seen:
            seen.add(value)
            indices.append(value)
    if indices:
        return indices

    seg_idx = segment.get("segment_index")
    if task_state is not None and seg_idx is not None:
        try:
            seg_idx_int = int(seg_idx)
        except (TypeError, ValueError):
            seg_idx_int = None
        if seg_idx_int is not None:
            seg_map = task_state.get("segment_layout_block_map")
            if isinstance(seg_map, list) and 0 <= seg_idx_int < len(seg_map):
                for raw in seg_map[seg_idx_int] or []:
                    try:
                        value = int(raw)
                    except (TypeError, ValueError):
                        continue
                    if value not in seen:
                        seen.add(value)
                        indices.append(value)
            if not indices:
                chunk_map = task_state.get("layout_chunk_block_map")
                if isinstance(chunk_map, list) and 0 <= seg_idx_int < len(chunk_map):
                    for raw in chunk_map[seg_idx_int] or []:
                        try:
                            value = int(raw)
                        except (TypeError, ValueError):
                            continue
                        if value not in seen:
                            seen.add(value)
                            indices.append(value)

    if not indices and segment.get("block_index") is not None:
        try:
            indices = [int(segment["block_index"])]
        except (TypeError, ValueError):
            indices = []
    return indices


def build_block_font_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, float]:
    """Expand segment-level user font overrides to layout block indices."""
    block_map: Dict[int, float] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        font_pt = normalize_user_font_size_pt(seg.get("font_size_pt"))
        if font_pt is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = font_pt
    return block_map


def build_block_font_weight_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, str]:
    """Expand segment-level user font weight overrides to layout block indices."""
    block_map: Dict[int, str] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        weight = normalize_user_font_weight(seg.get("font_weight"))
        if weight is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = weight
    return block_map


def build_block_font_style_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, str]:
    """Expand segment-level user font style overrides to layout block indices."""
    block_map: Dict[int, str] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        style = normalize_user_font_style(seg.get("font_style"))
        if style is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = style
    return block_map


def build_block_leading_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, float]:
    """Expand segment-level user leading overrides to layout block indices."""
    block_map: Dict[int, float] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        leading = normalize_user_leading_em(seg.get("leading_em"))
        if leading is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = leading
    return block_map


def segments_have_user_font_overrides(
    segments: List[Dict[str, Any]],
) -> bool:
    """Return True when any segment has a persisted user typography override."""
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if normalize_user_font_size_pt(seg.get("font_size_pt")) is not None:
            return True
        if normalize_user_font_weight(seg.get("font_weight")) is not None:
            return True
        if normalize_user_font_style(seg.get("font_style")) is not None:
            return True
        if normalize_user_leading_em(seg.get("leading_em")) is not None:
            return True
    return False


def invalidate_pdf_export_cache(task_state: Dict[str, Any]) -> None:
    """Drop cached PDF export so the next download regenerates with latest segments."""
    files = task_state.get("downloadable_files")
    if isinstance(files, dict):
        files.pop("pdf", None)


def apply_user_font_override(
    rb: RenderBlock,
    font_size_pt: float,
    *,
    calculator: Optional[FontFitCalculator] = None,
) -> RenderBlock:
    """Lock render block to a user-specified font size."""
    calc = calculator or FontFitCalculator()
    pt = clamp_font_size_pt(font_size_pt)
    leading = rb.leading_em
    if leading <= 0:
        leading = calc.estimate_leading(pt)
    return RenderBlock(
        **{
            **rb.__dict__,
            "font_size_pt": pt,
            "leading_em": leading,
            "fit_to_box": False,
            "fit_single_line": False,
            "fit_min_font_size_pt": pt,
            "fit_max_font_size_pt": pt,
            "fit_min_leading_em": leading,
            "font_size_locked": True,
        }
    )


def apply_user_typography_override(
    rb: RenderBlock,
    *,
    font_weight: Optional[str] = None,
    font_style: Optional[str] = None,
    leading_em: Optional[float] = None,
) -> RenderBlock:
    """Apply user font weight/style/leading to a render block."""
    updates: Dict[str, Any] = {}
    normalized_weight = normalize_user_font_weight(font_weight)
    normalized_style = normalize_user_font_style(font_style)
    normalized_leading = normalize_user_leading_em(leading_em)
    if normalized_weight is not None:
        updates["font_weight"] = normalized_weight
    if normalized_style is not None:
        updates["font_style"] = normalized_style
    if normalized_leading is not None:
        updates["leading_em"] = normalized_leading
        updates["fit_min_leading_em"] = normalized_leading
        # Lock user leading during fit-to-box; font size may still shrink to fit bbox.
        updates["leading_em_locked"] = True
    if not updates:
        return rb
    return RenderBlock(**{**rb.__dict__, **updates})
