# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Per-segment font size helpers for PDF Typst overlay rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.block_types import NON_TEXT_BLOCK_TYPES as _NON_TEXT_BLOCK_TYPES
from layout.pdf_renderer.typst_overlay.font_fit import (
    DEFAULT_LEADING_EM,
    FontFitCalculator,
    USER_FONT_SIZE_PT_MIN,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock, layout_block_to_render_block

FONT_SIZE_PT_MIN = USER_FONT_SIZE_PT_MIN
FONT_SIZE_PT_MAX = 72.0
FONT_SIZE_PT_STEP = 0.1

LEADING_EM_MIN = 0.35
LEADING_EM_MAX = 3.0

DEFAULT_TABLE_STROKE_PT = 0.5
LEADING_EM_STEP = 0.05
LEADING_EM_DEFAULT = DEFAULT_LEADING_EM

VALID_FONT_WEIGHTS = frozenset({"regular", "bold"})
VALID_FONT_STYLES = frozenset({"normal", "italic"})

_IMAGE_OVERLAY_EXTENSIONS = frozenset({
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
})


def is_image_overlay_task(task_state: Optional[Dict[str, Any]]) -> bool:
    """True when task renders translated text via raster image overlay."""
    if not task_state:
        return False
    if task_state.get("layout_document") is None:
        return False
    raw_path = task_state.get("original_file_path")
    if not raw_path or not isinstance(raw_path, str):
        return False
    suffix = Path(raw_path).suffix.lower()
    return suffix in _IMAGE_OVERLAY_EXTENSIONS and Path(raw_path).is_file()


def cache_overlay_source_image_size(
    task_state: Dict[str, Any],
    image_path: str,
) -> None:
    """Persist raster dimensions on task_state for overlay typography dry-run."""
    from utils.mineru_layout_utils import is_mineru_layout_image

    if not is_mineru_layout_image(image_path):
        return
    try:
        from PIL import Image, ImageOps

        with Image.open(image_path) as opened:
            oriented = ImageOps.exif_transpose(opened)
            task_state["overlay_source_image_size"] = [
                int(oriented.width),
                int(oriented.height),
            ]
    except OSError:
        return


def resolve_overlay_font_family(task_state: Optional[Dict[str, Any]]) -> str:
    """Match production image overlay font selection (target language)."""
    to_lang: Any = None
    if task_state:
        to_lang = task_state.get("to_lang") or task_state.get("target_language")
        if not to_lang:
            payload = task_state.get("payload")
            if isinstance(payload, dict):
                to_lang = payload.get("to_lang") or payload.get("target_language")
            elif payload is not None:
                to_lang = getattr(payload, "to_lang", None) or getattr(
                    payload, "target_language", None,
                )
    lang = str(to_lang or "en").strip().lower()
    try:
        from translator.ai_translator.docx_translator import get_font_for_language

        return get_font_for_language(lang)
    except Exception:
        if lang.startswith(("zh", "ja", "ko")):
            from utils.format_convert_utils import _cjk_mainfont_fallback

            return _cjk_mainfont_fallback(lang)
        return "Calibri"


def resolve_image_overlay_image_size(
    task_state: Optional[Dict[str, Any]],
    *,
    layout_doc: Optional[LayoutDocument] = None,
) -> Optional[Tuple[int, int]]:
    """Read source raster dimensions for overlay dry-run font metrics."""
    if task_state:
        cached = task_state.get("overlay_source_image_size")
        if isinstance(cached, (list, tuple)) and len(cached) == 2:
            try:
                return int(cached[0]), int(cached[1])
            except (TypeError, ValueError):
                pass
    if not is_layout_image_typography_task(task_state, layout_doc=layout_doc):
        return None
    if not task_state:
        return None
    raw_path = task_state.get("original_file_path")
    if not raw_path or not isinstance(raw_path, str):
        return None
    if not Path(raw_path).is_file():
        return None
    try:
        from PIL import Image, ImageOps

        with Image.open(raw_path) as opened:
            oriented = ImageOps.exif_transpose(opened)
            size = (int(oriented.width), int(oriented.height))
            task_state["overlay_source_image_size"] = list(size)
            return size
    except OSError:
        return None


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
    if segment_has_user_font_size_override(segment):
        return "user"
    return "auto"


def segment_has_user_font_size_override(segment: Dict[str, Any]) -> bool:
    """True when segment stores an explicit user font size override."""
    source = segment.get("font_size_source")
    if source is not None and str(source).strip().lower() == "auto":
        return False
    return normalize_user_font_size_pt(segment.get("font_size_pt")) is not None


def is_layout_image_typography_task(
    task_state: Optional[Dict[str, Any]],
    *,
    layout_doc: Optional[LayoutDocument] = None,
) -> bool:
    """True for MinerU layout image workflows that use raster overlay typography."""
    if not task_state:
        return False
    has_layout = (
        layout_doc is not None or task_state.get("layout_document") is not None
    )
    if not has_layout:
        return False
    from utils.mineru_layout_utils import is_mineru_layout_image

    return is_mineru_layout_image(str(task_state.get("original_filename") or ""))


def effective_segment_font_size_pt_for_ui(segment: Dict[str, Any]) -> float:
    """
    Resolved font size for batch ± steps (matches frontend effectivePdfSegmentFontSizePt).
    """
    font_size_source = segment.get("font_size_source")
    font_size_pt = segment.get("font_size_pt")
    overlay_render = segment.get("overlay_render_font_size_pt")
    computed_font_size_pt = segment.get("computed_font_size_pt")

    if font_size_source == "user" and font_size_pt is not None:
        normalized = normalize_user_font_size_pt(font_size_pt)
        if normalized is not None:
            return normalized

    if overlay_render is not None:
        try:
            return clamp_font_size_pt(float(overlay_render))
        except (TypeError, ValueError):
            pass

    if computed_font_size_pt is not None:
        try:
            return clamp_font_size_pt(float(computed_font_size_pt))
        except (TypeError, ValueError):
            pass

    if font_size_pt is not None:
        normalized = normalize_user_font_size_pt(font_size_pt)
        if normalized is not None:
            return normalized

    return FONT_SIZE_PT_MIN


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
    if segment_has_user_font_weight_override(segment):
        return "user"
    return "auto"


def segment_has_user_font_weight_override(segment: Dict[str, Any]) -> bool:
    source = segment.get("font_weight_source")
    if source is not None and str(source).strip().lower() == "auto":
        return False
    return normalize_user_font_weight(segment.get("font_weight")) is not None


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


def compute_image_overlay_font_size_pt(
    block: LayoutBlock,
    text: str,
    *,
    calculator: Optional[FontFitCalculator] = None,
) -> Optional[float]:
    """Typst dry-run estimate for overlay text (before bbox cap)."""
    if not text or not text.strip():
        return None
    calc = calculator or FontFitCalculator(min_size_pt=FONT_SIZE_PT_MIN)
    layout_raw = getattr(block, "raw", None) or {}
    if not isinstance(layout_raw, dict):
        layout_raw = {}
    rb = layout_block_to_render_block(
        block,
        page_index=getattr(block, "page_index", 0) or 0,
        translated_text=text,
    )
    try:
        fitted = calc.calculate_fit_params(rb, layout_raw=layout_raw)
        if fitted.font_size_pt > 0:
            return round(float(fitted.font_size_pt), 1)
    except Exception:
        pass
    try:
        estimated = float(calc.estimate_font_size(rb, layout_raw=layout_raw))
        if estimated > 0:
            return round(estimated, 1)
    except Exception:
        pass
    return None


def compute_image_overlay_effective_font_size_pt(
    block: LayoutBlock,
    text: str,
    *,
    calculator: Optional[FontFitCalculator] = None,
) -> Optional[float]:
    """Effective auto overlay font size (matches renderer min-candidate logic in pt)."""
    if not text or not text.strip():
        return None
    from layout.image_overlay.renderer import (
        _estimate_overlay_font_size_pt,
        _mineru_layout_font_size_pt,
        _overlay_line_count,
    )

    line_count = _overlay_line_count(text)
    _, y0, _, y1 = block.bbox
    bbox_h = max(0.1, float(y1) - float(y0))
    bbox_cap_pt = (bbox_h / line_count) * 0.90
    layout_line_pt = (bbox_h / line_count) * 0.88

    candidates: List[float] = [bbox_cap_pt, layout_line_pt]
    layout_pt = _mineru_layout_font_size_pt(block)
    if layout_pt is not None and layout_pt > 0:
        candidates.append(float(layout_pt))
    estimated_pt = _estimate_overlay_font_size_pt(block, text)
    if estimated_pt is not None and estimated_pt > 0:
        candidates.append(float(estimated_pt))

    effective = max(FONT_SIZE_PT_MIN, min(FONT_SIZE_PT_MAX, min(candidates)))
    return round(effective, 1)


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

    calc = calculator or FontFitCalculator(min_size_pt=FONT_SIZE_PT_MIN)
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


def _overlay_dry_run_render_pt(
    block: LayoutBlock,
    text: str,
    overlay_page: Optional[LayoutPage],
    overlay_image_size: Tuple[int, int],
    task_state: Optional[Dict[str, Any]],
    *,
    user_pt: Optional[float] = None,
    font_weight: str = "regular",
) -> Optional[float]:
    """Dry-run overlay render pt using the same font family as production render."""
    from layout.image_overlay.renderer import dry_run_overlay_font_size_pt

    return dry_run_overlay_font_size_pt(
        block,
        text,
        overlay_page,
        overlay_image_size,
        user_pt=user_pt,
        font_family=resolve_overlay_font_family(task_state),
        bold=font_weight == "bold",
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

    block_idx: Optional[int] = None
    if task_state is not None and is_layout_image_typography_task(
        task_state, layout_doc=layout_doc,
    ):
        from layout.image_overlay.block_text_map import (
            resolve_overlay_primary_text_block_index,
        )

        block_idx = resolve_overlay_primary_text_block_index(
            segment,
            layout_doc,
            task_state,
        )
    if block_idx is None:
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

    content = text
    if content is None:
        content = (
            segment.get("modified_text")
            or segment.get("target_text")
            or segment.get("text")
            or segment.get("source_text")
            or ""
        )

    block_type = type_map.get(block_idx, "text")
    overlay_image_size = None
    layout_image_typography = (
        task_state is not None
        and is_layout_image_typography_task(task_state, layout_doc=layout_doc)
    )
    if layout_image_typography:
        overlay_image_size = resolve_image_overlay_image_size(
            task_state, layout_doc=layout_doc,
        )
    overlay_page = layout_doc.get_page(getattr(block, "page_index", 0) or 0)
    block_font_weight = compute_block_font_weight_from_layout(block)

    if not is_font_size_editable_block_type(block_type):
        if block_type == "image" and str(content).strip():
            overlay_pt: Optional[float] = None
            if overlay_image_size is not None:
                overlay_pt = _overlay_dry_run_render_pt(
                    block,
                    str(content),
                    overlay_page,
                    overlay_image_size,
                    task_state,
                    font_weight=block_font_weight,
                )
            if overlay_pt is None:
                overlay_pt = compute_image_overlay_effective_font_size_pt(
                    block,
                    str(content),
                    calculator=calculator,
                )
            if overlay_pt is not None:
                segment["computed_font_size_pt"] = overlay_pt
                segment["computed_leading_em"] = DEFAULT_LEADING_EM
            else:
                segment.pop("computed_font_size_pt", None)
                segment.pop("computed_leading_em", None)
        else:
            segment.pop("computed_font_size_pt", None)
            segment.pop("computed_leading_em", None)
        segment.pop("computed_font_weight", None)
        segment.pop("computed_font_style", None)
        return

    segment["computed_font_weight"] = compute_block_font_weight_from_layout(block)
    segment["computed_font_style"] = compute_block_font_style_from_layout(block)

    computed: Optional[tuple[float, float]] = None
    if overlay_image_size is not None and str(content).strip():
        user_pt: Optional[float] = None
        if segment_has_user_font_size_override(segment):
            user_pt = normalize_user_font_size_pt(segment.get("font_size_pt"))
        render_pt = _overlay_dry_run_render_pt(
            block,
            str(content),
            overlay_page,
            overlay_image_size,
            task_state,
            user_pt=user_pt,
            font_weight=block_font_weight,
        )
        if render_pt is not None:
            computed = (render_pt, DEFAULT_LEADING_EM)
            segment["overlay_render_font_size_pt"] = render_pt
            try:
                from layout.image_overlay.renderer import _estimate_overlay_font_size_pt

                estimated_pt = _estimate_overlay_font_size_pt(block, str(content))
                if estimated_pt is not None:
                    segment["overlay_estimated_font_size_pt"] = round(
                        float(estimated_pt), 1,
                    )
            except Exception:
                segment.pop("overlay_estimated_font_size_pt", None)

    if computed is None and not layout_image_typography:
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
        segment.pop("overlay_render_font_size_pt", None)
        segment.pop("overlay_estimated_font_size_pt", None)

    _reconcile_pdf_render_font_size_pt(
        segment,
        block,
        str(content),
        layout_doc,
        calculator=calculator,
        task_state=task_state,
        font_weight=block_font_weight,
    )

    _reconcile_overlay_user_font_size_pt(
        segment,
        block,
        str(content),
        layout_doc,
        overlay_page,
        overlay_image_size,
        task_state=task_state,
        font_weight=block_font_weight,
    )


def _reconcile_pdf_render_font_size_pt(
    segment: Dict[str, Any],
    block: LayoutBlock,
    text: str,
    layout_doc: LayoutDocument,
    *,
    calculator: Optional[FontFitCalculator] = None,
    task_state: Optional[Dict[str, Any]] = None,
    font_weight: str = "regular",
) -> None:
    """Attach PDF dry-run render pt to segment metadata (WYSIWYG UI labels)."""
    if not text.strip():
        return
    if task_state is not None and is_layout_image_typography_task(
        task_state, layout_doc=layout_doc,
    ):
        return

    from layout.pdf_renderer.typst_overlay.pdf_font_dry_run import dry_run_pdf_font_size_pt

    layout_raw = getattr(block, "raw", None) or {}
    page_index = getattr(block, "page_index", 0) or 0
    overlay_page = layout_doc.get_page(page_index)
    page_width_pt: Optional[float] = None
    if overlay_page is not None:
        width = getattr(overlay_page, "width", None)
        if width is not None:
            try:
                page_width_pt = float(width)
            except (TypeError, ValueError):
                page_width_pt = None

    requested = normalize_user_font_size_pt(segment.get("font_size_pt"))
    user_pt = requested if segment_has_user_font_size_override(segment) else None

    render_pt = dry_run_pdf_font_size_pt(
        block,
        text,
        layout_raw=layout_raw,
        page_width_pt=page_width_pt,
        user_pt=user_pt,
        font_weight=font_weight,
        calculator=calculator,
    )
    if render_pt is not None:
        segment["computed_font_size_pt"] = render_pt
        segment["overlay_render_font_size_pt"] = render_pt


def _reconcile_overlay_user_font_size_pt(
    segment: Dict[str, Any],
    block: LayoutBlock,
    text: str,
    layout_doc: LayoutDocument,
    overlay_page: Optional[LayoutPage],
    overlay_image_size: Optional[Tuple[int, int]],
    *,
    task_state: Optional[Dict[str, Any]] = None,
    font_weight: str = "regular",
) -> None:
    """Attach overlay render pt to computed fields; keep user request in font_size_pt."""
    if overlay_image_size is None or not text.strip():
        return
    requested = normalize_user_font_size_pt(segment.get("font_size_pt"))
    user_pt = requested if segment_has_user_font_size_override(segment) else None

    effective = _overlay_dry_run_render_pt(
        block,
        text,
        overlay_page,
        overlay_image_size,
        task_state,
        user_pt=user_pt,
        font_weight=font_weight,
    )
    if effective is not None:
        segment["computed_font_size_pt"] = effective
        segment["overlay_render_font_size_pt"] = effective


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
    calc = FontFitCalculator(min_size_pt=FONT_SIZE_PT_MIN)
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
        if not segment_has_user_font_size_override(seg):
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
        if not segment_has_user_font_weight_override(seg):
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


def normalize_table_stroke_pt(value: Any) -> Optional[float]:
    """Normalize user table grid stroke width in pt (0 = hidden)."""
    if value is None:
        return None
    try:
        stroke_pt = float(value)
    except (TypeError, ValueError):
        return None
    if stroke_pt < 0 or stroke_pt > 3.0:
        return None
    return round(stroke_pt, 2)


def build_block_table_stroke_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, float]:
    """Expand segment-level table stroke overrides to layout block indices."""
    block_map: Dict[int, float] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if "table_stroke_pt" not in seg:
            continue
        stroke_pt = normalize_table_stroke_pt(seg.get("table_stroke_pt"))
        if stroke_pt is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = stroke_pt
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
        if segment_has_user_font_size_override(seg):
            return True
        if segment_has_user_font_weight_override(seg):
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


def invalidate_pdf_preview_cache(task_state: Dict[str, Any]) -> None:
    """Drop in-memory PDF preview cache after typography or segment edits."""
    task_state.pop("_pdf_preview_cache", None)


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
        # Keep font size fixed for leading-only edits so line spacing changes are visible.
        # Auto fit-to-box often already uses ~0.875em leading; shrinking font there can
        # mask a user change to 0.9em when only max font was capped before.
        if rb.font_size_pt > 0 and not rb.font_size_locked:
            pt = rb.font_size_pt
            updates["fit_max_font_size_pt"] = pt
            # When tightening line spacing, keep font size fixed so the change is visible.
            if normalized_leading < rb.leading_em:
                updates["fit_min_font_size_pt"] = pt
    if not updates:
        return rb
    return RenderBlock(**{**rb.__dict__, **updates})
