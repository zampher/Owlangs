# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Per-segment font size helpers for PDF Typst overlay rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.block_types import NON_TEXT_BLOCK_TYPES as _NON_TEXT_BLOCK_TYPES
from layout.layout_group_pair_utils import is_layout_companion_block
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
    size = read_overlay_source_image_size(image_path)
    if size is not None:
        task_state["overlay_source_image_size"] = [size[0], size[1]]


def read_overlay_source_image_size(image_path: str) -> Optional[Tuple[int, int]]:
    """Read overlay raster dimensions with EXIF orientation applied (matches renderer)."""
    from utils.mineru_layout_utils import is_mineru_layout_image

    if not is_mineru_layout_image(image_path):
        return None
    try:
        from PIL import Image, ImageOps

        with Image.open(image_path) as opened:
            oriented = ImageOps.exif_transpose(opened)
            return int(oriented.width), int(oriented.height)
    except OSError:
        return None


def read_oriented_overlay_source_image_bytes(
    image_path: str,
) -> Optional[Tuple[bytes, str]]:
    """Encode source raster with EXIF orientation applied for browser preview."""
    from utils.mineru_layout_utils import is_mineru_layout_image

    if not is_mineru_layout_image(image_path):
        return None
    try:
        import io

        from PIL import Image, ImageOps

        path = Path(image_path)
        with Image.open(path) as opened:
            oriented = ImageOps.exif_transpose(opened)
            ext = path.suffix.lower()
            buf = io.BytesIO()
            if ext in (".jpg", ".jpeg"):
                rgb = oriented.convert("RGB")
                rgb.save(buf, format="JPEG", quality=95)
                return buf.getvalue(), "image/jpeg"
            if ext == ".png":
                oriented.save(buf, format="PNG")
                return buf.getvalue(), "image/png"
            if ext == ".webp":
                oriented.save(buf, format="WEBP", quality=95)
                return buf.getvalue(), "image/webp"
            rgb = oriented.convert("RGB")
            rgb.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    except OSError:
        return None


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
    size = read_overlay_source_image_size(raw_path)
    if size is not None:
        task_state["overlay_source_image_size"] = [size[0], size[1]]
        return size
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
    from layout.pdf_renderer.typst_overlay.text_metrics import outer_bbox_content_height_pt

    if line_count <= 1:
        bbox_cap_pt = bbox_h
        layout_line_pt = bbox_h * 0.88
    else:
        content_h = outer_bbox_content_height_pt(bbox_h, float(line_count))
        bbox_cap_pt = content_h
        layout_line_pt = (content_h / line_count) * 0.88

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


def build_layout_block_maps(
    layout_doc: LayoutDocument,
) -> tuple[Dict[int, LayoutBlock], Dict[int, str]]:
    """Build block index maps once for batch segment typography enrichment."""
    block_map: Dict[int, LayoutBlock] = {}
    type_map: Dict[int, str] = {}
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_map[int(block.index)] = block
        type_map[int(block.index)] = getattr(block, "type", "") or "text"
    return block_map, type_map


def enrich_segment_font_fields(
    segment: Dict[str, Any],
    layout_doc: Optional[LayoutDocument],
    *,
    text: Optional[str] = None,
    calculator: Optional[FontFitCalculator] = None,
    task_state: Optional[Dict[str, Any]] = None,
    block_map: Optional[Dict[int, LayoutBlock]] = None,
    type_map: Optional[Dict[int, str]] = None,
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

    if block_map is None or type_map is None:
        block_map, type_map = build_layout_block_maps(layout_doc)

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
    block_map: Optional[Dict[int, LayoutBlock]] = None
    type_map: Optional[Dict[int, str]] = None
    if layout_doc is not None:
        block_map, type_map = build_layout_block_maps(layout_doc)
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
            block_map=block_map,
            type_map=type_map,
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


def segment_overlay_export_text(
    segment: Dict[str, Any],
    text_field: str = "target_text",
) -> str:
    """Resolve overlay export text with LaTeX normalization for Typst rendering."""
    from utils.segment_latex_flags import prepare_segment_export_text
    return prepare_segment_export_text(segment, text_field=text_field, for_typst=True)


_IDENTIFIER_OVERLAY_EXCLUSION_REASONS = frozenset({
    "identifier",
    "numeric",
    "number",
})

_NON_TEXT_OVERLAY_EXCLUSION_REASONS = frozenset({
    "formula",
    "image",
    "table",
    "reference",
    "user_selected",
})


def segment_exclusion_reason_tokens(segment: Dict[str, Any]) -> set[str]:
    """Normalized exclusion reason tokens from segment metadata."""
    tokens: set[str] = set()
    for key in ("exclusion_reason", "detected_exclusion_reason"):
        raw = (segment.get(key) or "").strip().lower()
        if raw:
            tokens.add(raw)
    return tokens


def segment_exclusion_prefers_source_image(segment: Dict[str, Any]) -> bool:
    """True when the user marked this segment as image exclusion.

    Image exclusion means: keep source-PDF pixels and do not Typst-overlay text/LaTeX,
    even for mixed prose+$math$ that would otherwise force latex overlay when excluded
    as ``formula``.
    """
    reason = (segment.get("exclusion_reason") or "").strip().lower()
    return reason == "image"


def collect_image_exclusion_layout_block_indices(
    segments: Optional[List[Dict[str, Any]]],
    task_state: Optional[Dict[str, Any]] = None,
) -> set[int]:
    """Layout block indices mapped from segments with exclusion_reason=image."""
    indices: set[int] = set()
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        if not segment_exclusion_prefers_source_image(seg):
            continue
        for raw_idx in resolve_segment_layout_block_indices(seg, task_state):
            try:
                indices.add(int(raw_idx))
            except (TypeError, ValueError):
                continue
    return indices


def segment_is_excluded_identifier_overlay(segment: Dict[str, Any]) -> bool:
    """True when an excluded identifier-like segment must render via Typst overlay."""
    if not bool(segment.get("is_excluded")):
        return False

    reason_tokens = segment_exclusion_reason_tokens(segment)
    if reason_tokens & _NON_TEXT_OVERLAY_EXCLUSION_REASONS:
        return False
    if not (reason_tokens & _IDENTIFIER_OVERLAY_EXCLUSION_REASONS):
        return False

    chunk = (segment.get("chunk_type") or "").strip().lower()
    if chunk in (
        "interline_equation",
        "inline_equation",
        "formula",
        "equation",
        "image",
        "chart_body",
        "table_body",
    ):
        return False
    if bool(segment.get("is_image")):
        return False

    source_text = (segment.get("source_text") or "").strip()
    target_text = (segment.get("target_text") or "").strip()
    return bool(source_text or target_text)


def collect_layout_block_indices_with_overlay_text(
    segments: Optional[List[Dict[str, Any]]],
    task_state: Optional[Dict[str, Any]] = None,
    block_text_map: Optional[Dict[int, str]] = None,
) -> set[int]:
    """Layout block indices that receive non-empty overlay text from segments."""
    indices: set[int] = set()
    if block_text_map:
        for raw_idx, text in block_text_map.items():
            if not (text or "").strip():
                continue
            try:
                indices.add(int(raw_idx))
            except (TypeError, ValueError):
                continue
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        if segment_skips_overlay(seg):
            continue
        if not segment_overlay_export_text(seg):
            continue
        for raw_idx in resolve_segment_layout_block_indices(seg, task_state):
            try:
                indices.add(int(raw_idx))
            except (TypeError, ValueError):
                continue
    return indices


def collect_overlay_erase_block_indices(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
    *,
    skip_block_indices: Optional[set] = None,
    block_text_map: Optional[Dict[int, str]] = None,
    layout_doc: Any = None,
) -> set[int]:
    """Layout block indices that receive translated overlay and must be erased."""
    skip = skip_block_indices or set()
    erase: set[int] = set()
    block_by_index: Dict[int, Any] = {}
    if layout_doc is not None:
        for page in layout_doc.pages:
            for block in page.blocks:
                idx = getattr(block, "index", None)
                if idx is not None:
                    block_by_index[int(idx)] = block

    def _block_eligible_for_erase(idx: int, *, has_overlay_text: bool) -> bool:
        if idx in skip:
            return False
        blk = block_by_index.get(idx)
        if blk is not None and _layout_block_is_empty_ocr_text(blk):
            # Empty OCR layout text: erase only when segment supplies overlay text.
            return has_overlay_text
        return True

    if block_text_map:
        for raw_idx, text in block_text_map.items():
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if not (text or "").strip():
                continue
            if _block_eligible_for_erase(idx, has_overlay_text=True):
                erase.add(idx)
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        if segment_skips_overlay(seg):
            continue
        if not segment_overlay_export_text(seg):
            continue
        for raw_idx in resolve_segment_layout_block_indices(seg, task_state):
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if _block_eligible_for_erase(idx, has_overlay_text=True):
                erase.add(idx)
    return erase


def segment_skips_overlay(
    segment: Dict[str, Any],
    text_field: str = "target_text",
) -> bool:
    """True when overlay/redaction should preserve original PDF content for this segment.

    Mixed prose+LaTeX (latex_flags.present) must overlay even when excluded as
    ``formula``: otherwise preserve is False (needs Typst math) while skip is True
    and the redacted region becomes a blank hole.

    Exception: ``exclusion_reason=image`` always preserves source PDF (user chose
    per-segment image rendering for that formula/mixed region).
    """
    if segment_exclusion_prefers_source_image(segment):
        return True

    if segment_is_excluded_identifier_overlay(segment):
        return False

    from utils.segment_latex_flags import segment_requires_typst_latex_overlay

    # Must run before is_excluded: formula-excluded mixed text still needs Typst.
    if segment_requires_typst_latex_overlay(segment, text_field):
        return False

    if bool(segment.get("is_excluded")):
        return True

    export_text = segment_overlay_export_text(segment, text_field)
    source_text = (segment.get("source_text") or "").strip()
    modified_text = (segment.get("modified_text") or "").strip()
    target_text = (segment.get("target_text") or "").strip()

    status = str(segment.get("translation_status") or "").strip().lower()
    is_failed = bool(segment.get("is_failed")) or status in (
        "failed",
        "error",
        "failure",
    )

    # Failed segments with renderable text (e.g. English bibliography entries returned
    # unchanged) must still be overlaid. Image-based PDF cleanup can erase neighboring
    # regions; skip_overlay alone leaves blank holes when no overlay text is placed.
    if is_failed:
        return not bool(export_text)

    if bool(segment.get("needs_retry")) and not export_text:
        return True
    if (
        text_field != "source_text"
        and source_text
        and source_text == target_text
        and not modified_text
    ):
        return True
    if text_field != "source_text" and not export_text and source_text:
        return True
    return False


def segment_preserves_source_pdf_pixels(
    segment: Dict[str, Any],
    *,
    chart_body_format: str = "image",
    table_body_format: str = "html",
    equation_format: str = "text",
    text_field: str = "target_text",
) -> bool:
    """True when segment region must keep original PDF pixels (failed/excluded/image-format)."""
    if segment_exclusion_prefers_source_image(segment):
        return True
    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    chunk = (segment.get("chunk_type") or "").strip().lower()
    if chunk in ("interline_equation", "formula", "equation") and eq_fmt == "text":
        return False
    from utils.segment_latex_flags import segment_requires_typst_latex_overlay

    if segment_requires_typst_latex_overlay(segment, text_field):
        return False
    if segment_skips_overlay(segment, text_field):
        return True
    if chunk == "chart_body" and chart_fmt == "image":
        return True
    if chunk == "table_body" and table_fmt == "image":
        return True
    if chunk in ("interline_equation", "formula", "equation") and eq_fmt == "image":
        return True
    if bool(segment.get("is_image")):
        if chunk == "chart_body" and chart_fmt == "image":
            return True
        if chunk == "table_body" and table_fmt == "image":
            return True
    return False


def segment_skips_redaction(
    segment: Dict[str, Any],
    *,
    chart_body_format: str = "image",
    table_body_format: str = "html",
    equation_format: str = "text",
    text_field: str = "target_text",
) -> bool:
    """True when this segment must not be a redaction target."""
    return segment_preserves_source_pdf_pixels(
        segment,
        chart_body_format=chart_body_format,
        table_body_format=table_body_format,
        equation_format=equation_format,
        text_field=text_field,
    )


def resolve_segment_protected_bbox(
    segment: Dict[str, Any],
    layout_doc: Any,
    task_state: Optional[Dict[str, Any]] = None,
    *,
    chart_body_format: str = "image",
    table_body_format: str = "html",
    equation_format: str = "text",
    segment_bbox_overlay_blocks: Optional[set] = None,
) -> Optional[tuple[float, float, float, float]]:
    """Best bbox to protect for a preserve-pixels segment."""
    from layout.block_types import CHART_BODY, TABLE_BODY
    from layout.pdf_renderer.typst_overlay.visual_images import (
        block_preserves_source_pdf_visual,
        extract_nested_sub_bbox,
    )

    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    overlay_blocks = segment_bbox_overlay_blocks or set()
    block_by_index: Dict[int, Any] = {}
    block_bbox_by_index = _layout_block_bbox_by_index(layout_doc)
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is not None:
                block_by_index[int(idx)] = block

    bbox = _read_segment_layout_bbox(segment, task_state, layout_doc)
    indices = resolve_segment_layout_block_indices(segment, task_state)
    for raw_idx in indices:
        try:
            blk = block_by_index.get(int(raw_idx))
        except (TypeError, ValueError):
            blk = None
        if blk is None:
            continue
        if blk.type == "chart" and chart_fmt == "image":
            nested = extract_nested_sub_bbox(blk, CHART_BODY)
            return nested or tuple(blk.bbox)
        if blk.type == "table" and table_fmt == "image":
            nested = extract_nested_sub_bbox(blk, TABLE_BODY)
            return nested or tuple(blk.bbox)
        if block_preserves_source_pdf_visual(
            blk,
            equation_format=eq_fmt,
            chart_body_format=chart_fmt,
            table_body_format=table_fmt,
        ):
            if blk.type == "chart":
                nested = extract_nested_sub_bbox(blk, CHART_BODY)
                return nested or tuple(blk.bbox)
            if blk.type == "table":
                nested = extract_nested_sub_bbox(blk, TABLE_BODY)
                return nested or tuple(blk.bbox)
            return tuple(blk.bbox)
    if bbox is not None:
        return bbox
    for raw_idx in indices:
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            idx = None
        if idx is not None and idx in overlay_blocks:
            continue
        try:
            fallback = block_bbox_by_index.get(int(raw_idx))
        except (TypeError, ValueError):
            fallback = None
        if fallback is not None:
            return fallback
    return None


def _block_has_recognized_text(block: Any) -> bool:
    """Safe wrapper for LayoutBlock.has_recognized_text()."""
    checker = getattr(block, "has_recognized_text", None)
    if callable(checker):
        return bool(checker())
    has_text_fn = getattr(block, "has_text", None)
    if callable(has_text_fn):
        return bool(has_text_fn())
    text = getattr(block, "text", None)
    return bool(text and str(text).strip())


def _layout_block_is_empty_ocr_text(block: Any) -> bool:
    """True for text-like layout blocks whose OCR/content string is empty."""
    if block is None:
        return False
    is_visual = getattr(block, "is_visual", None)
    if callable(is_visual) and is_visual():
        return False
    is_equation = getattr(block, "is_equation", None)
    if callable(is_equation) and is_equation():
        return False
    blk_type = (getattr(block, "type", None) or "").strip().lower()
    if blk_type in (
        "table",
        "chart",
        "image",
        "interline_equation",
        "inline_equation",
    ):
        return False
    return not _block_has_recognized_text(block)


def _overlay_block_bboxes_by_page(
    layout_doc: Any,
    block_indices: set[int],
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Per-page bboxes for layout blocks scheduled for overlay erase or text."""
    by_page: Dict[int, List[tuple[float, float, float, float]]] = {}
    if layout_doc is None or not block_indices:
        return by_page
    active = {int(i) for i in block_indices}
    for page in layout_doc.pages:
        page_idx = int(page.page_index)
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is None or int(idx) not in active:
                continue
            try:
                bbox = tuple(float(v) for v in block.bbox[:4])
            except (TypeError, ValueError, IndexError):
                continue
            by_page.setdefault(page_idx, []).append(bbox)
    return by_page


def _bbox_overlaps_any(
    bbox: tuple[float, float, float, float],
    candidates: List[tuple[float, float, float, float]],
) -> bool:
    from layout.pdf_renderer.typst_overlay.layer_order import bboxes_overlap

    for other in candidates:
        if bboxes_overlap(bbox, other):
            return True
    return False


def empty_ocr_block_overlaps_overlay_block_region(
    block: Any,
    layout_doc: Any,
    overlay_block_indices: set[int],
) -> bool:
    """True when an empty OCR block shares area with an overlay-erase block bbox.

    Paddle det supplements can duplicate the same physical region as a primary
    OCR block (empty duplicate + text block). Protecting the empty duplicate
    clips redaction rects and leaves original PDF text under Typst overlay.
    """
    if layout_doc is None or not overlay_block_indices or block is None:
        return False
    page_idx = getattr(block, "page_index", None)
    if page_idx is None:
        return False
    overlay_bboxes = _overlay_block_bboxes_by_page(layout_doc, overlay_block_indices)
    candidates = overlay_bboxes.get(int(page_idx), [])
    if not candidates:
        return False
    try:
        bbox = tuple(float(v) for v in block.bbox[:4])
    except (TypeError, ValueError, IndexError):
        return False
    return _bbox_overlaps_any(bbox, candidates)


def collect_partial_overlay_block_indices(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> set[int]:
    """Block indices with both skip-overlay and overlay segments (mixed deep-split blocks)."""
    has_skip: Dict[int, bool] = {}
    has_overlay: Dict[int, bool] = {}
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        indices = resolve_segment_layout_block_indices(seg, task_state)
        try:
            idx_set = {int(i) for i in indices if i is not None}
        except (TypeError, ValueError):
            continue
        for idx in idx_set:
            if segment_skips_overlay(seg):
                has_skip[idx] = True
            elif segment_overlay_export_text(seg):
                has_overlay[idx] = True
    return {idx for idx in has_skip if has_skip[idx] and has_overlay.get(idx, False)}


def _layout_block_bbox_by_index(layout_doc: Any) -> Dict[int, tuple[float, float, float, float]]:
    block_map: Dict[int, tuple[float, float, float, float]] = {}
    if layout_doc is None:
        return block_map
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is None:
                continue
            try:
                bbox = tuple(float(v) for v in block.bbox)
            except (TypeError, ValueError):
                continue
            if len(bbox) == 4:
                block_map[int(idx)] = bbox
    return block_map


def _read_segment_layout_bbox_for_block(
    segment: Dict[str, Any],
    block_key: int,
    task_state: Optional[Dict[str, Any]] = None,
    layout_doc: Any = None,
) -> Optional[tuple[float, float, float, float]]:
    """Return layout bbox for a specific block within a multi-block segment."""
    indices = resolve_segment_layout_block_indices(segment, task_state)
    is_primary_block = True
    if indices:
        try:
            is_primary_block = int(block_key) == int(indices[0])
        except (TypeError, ValueError):
            is_primary_block = True

    from layout.layout_group_pair_utils import (
        LAYOUT_BLOCK_BBOX_OVERRIDES_KEY,
        parse_layout_block_bbox_overrides,
    )

    per_block_overrides = parse_layout_block_bbox_overrides(
        segment.get(LAYOUT_BLOCK_BBOX_OVERRIDES_KEY),
    )
    if per_block_overrides:
        try:
            block_override = per_block_overrides.get(int(block_key))
        except (TypeError, ValueError):
            block_override = None
        if block_override is not None:
            return block_override

    override = segment.get("layout_block_bbox_override")
    if is_primary_block and isinstance(override, (tuple, list)) and len(override) >= 4:
        try:
            return tuple(float(v) for v in override[:4])
        except (TypeError, ValueError):
            pass

    raw = segment.get("layout_block_bbox")
    nested_bboxes: List[tuple[float, float, float, float]] = []
    if isinstance(raw, list) and raw:
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                try:
                    nested_bboxes.append(tuple(float(v) for v in item[:4]))
                except (TypeError, ValueError):
                    continue
            elif len(raw) >= 4 and not isinstance(item, (list, tuple)):
                try:
                    return tuple(float(v) for v in raw[:4])
                except (TypeError, ValueError):
                    break

    if nested_bboxes and indices:
        try:
            normalized_indices = [int(i) for i in indices]
            pos = normalized_indices.index(int(block_key))
            if pos < len(nested_bboxes):
                return nested_bboxes[pos]
        except (TypeError, ValueError):
            pass
        if len(nested_bboxes) == 1:
            return nested_bboxes[0]

    if task_state is not None or layout_doc is not None:
        from utils.format_convert_utils import bboxes_for_layout_block_indices

        bboxes = bboxes_for_layout_block_indices(
            [block_key],
            task_state.get("layout_block_bbox") if task_state else None,
            layout_document=layout_doc,
        )
        if len(bboxes) == 1:
            try:
                return tuple(float(v) for v in bboxes[0][:4])
            except (TypeError, ValueError):
                pass
    return None


def _read_segment_layout_bbox(
    segment: Dict[str, Any],
    task_state: Optional[Dict[str, Any]] = None,
    layout_doc: Any = None,
    *,
    block_key: Optional[int] = None,
) -> Optional[tuple[float, float, float, float]]:
    """Return layout bbox from segment override or computed layout_block_bbox."""
    if block_key is not None:
        resolved = _read_segment_layout_bbox_for_block(
            segment,
            block_key,
            task_state,
            layout_doc,
        )
        if resolved is not None:
            return resolved

    override = segment.get("layout_block_bbox_override")
    if isinstance(override, (tuple, list)) and len(override) >= 4:
        try:
            return tuple(float(v) for v in override[:4])
        except (TypeError, ValueError):
            pass
    raw = segment.get("layout_block_bbox")
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, (list, tuple)) and len(first) >= 4:
            try:
                return tuple(float(v) for v in first[:4])
            except (TypeError, ValueError):
                pass
        elif len(raw) >= 4 and not isinstance(first, (list, tuple)):
            try:
                return tuple(float(v) for v in raw[:4])
            except (TypeError, ValueError):
                pass
    if task_state is not None or layout_doc is not None:
        from utils.format_convert_utils import bboxes_for_layout_block_indices

        indices = resolve_segment_layout_block_indices(segment, task_state)
        bboxes = bboxes_for_layout_block_indices(
            indices,
            task_state.get("layout_block_bbox") if task_state else None,
            layout_document=layout_doc,
        )
        if len(bboxes) == 1:
            try:
                return tuple(float(v) for v in bboxes[0][:4])
            except (TypeError, ValueError):
                pass
    return None


def _bbox_differs_from_block(
    segment_bbox: tuple[float, float, float, float],
    block_bbox: tuple[float, float, float, float],
    tolerance: float = 1.0,
) -> bool:
    try:
        for a, b in zip(segment_bbox, block_bbox):
            if abs(float(a) - float(b)) > tolerance:
                return True
        return False
    except (TypeError, ValueError):
        return True


def _infer_page_index_for_bbox(
    bbox: tuple[float, float, float, float],
    layout_doc: Any,
) -> Optional[int]:
    """Find page index whose block bbox contains the segment bbox center."""
    if layout_doc is None:
        return None
    try:
        cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        cy = (float(bbox[1]) + float(bbox[3])) / 2.0
    except (TypeError, ValueError):
        return None
    for page in layout_doc.pages:
        for block in page.blocks:
            try:
                bx0, by0, bx1, by1 = (
                    float(block.bbox[0]),
                    float(block.bbox[1]),
                    float(block.bbox[2]),
                    float(block.bbox[3]),
                )
            except (TypeError, ValueError, IndexError):
                continue
            if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                return int(page.page_index)
    return None


def collect_segment_bbox_overlay_block_indices(
    segments: List[Dict[str, Any]],
    layout_doc: Any,
    task_state: Optional[Dict[str, Any]] = None,
) -> set[int]:
    """Layout blocks that need per-segment bbox overlay/erase instead of full block."""
    result = collect_partial_overlay_block_indices(segments, task_state)
    overlay_count: Dict[int, int] = {}
    block_bbox_by_index = _layout_block_bbox_by_index(layout_doc)
    block_by_index: Dict[int, Any] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is not None:
                block_by_index[int(idx)] = block

    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        if segment_skips_overlay(seg):
            continue
        if not segment_overlay_export_text(seg):
            continue
        indices = resolve_segment_layout_block_indices(seg, task_state)
        seg_bbox = _read_segment_layout_bbox(seg, task_state, layout_doc)
        for raw_idx in indices:
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            blk = block_by_index.get(idx)
            if blk is not None and _layout_block_is_empty_ocr_text(blk):
                continue
            overlay_count[idx] = overlay_count.get(idx, 0) + 1
            if seg_bbox is not None:
                block_bbox = block_bbox_by_index.get(idx)
                if block_bbox is not None and _bbox_differs_from_block(seg_bbox, block_bbox):
                    result.add(idx)

    for idx, count in overlay_count.items():
        if count > 1:
            result.add(idx)
    return result


def collect_segment_layout_bbox_redaction_rects(
    segments: List[Dict[str, Any]],
    layout_doc: Any,
    task_state: Optional[Dict[str, Any]] = None,
    *,
    skip_block_indices: Optional[set] = None,
    margin_pt: float = 2.0,
    equation_format: str = "text",
    chart_body_format: str = "image",
    table_body_format: str = "html",
    bbox_override_by_block_index: Optional[Dict[int, tuple]] = None,
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Collect per-page redaction rects from segment layout bboxes (deep-split erase)."""
    if not segments or layout_doc is None:
        return {}

    from layout.pdf_renderer.typst_overlay.visual_images import block_preserves_source_pdf_visual

    skip = skip_block_indices or set()
    block_page: Dict[int, int] = {}
    block_by_index: Dict[int, Any] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is not None:
                block_by_index[int(idx)] = block
                block_page[int(idx)] = int(page.page_index)

    by_page: Dict[int, List[tuple[float, float, float, float]]] = {}
    preserve_empty_by_page = collect_empty_text_block_protected_rects(
        layout_doc,
        margin_pt=margin_pt,
        overlay_text_block_indices=collect_layout_block_indices_with_overlay_text(
            segments,
            task_state,
        ),
    )

    def _append_rect(
        page_idx: int,
        rect_bbox: tuple[float, float, float, float],
    ) -> None:
        x0, y0, x1, y1 = rect_bbox
        expanded = (
            max(0.0, x0 - margin_pt),
            max(0.0, y0 - margin_pt),
            x1 + margin_pt,
            y1 + margin_pt,
        )
        preserve_on_page = preserve_empty_by_page.get(page_idx, [])
        if preserve_on_page:
            from layout.pdf_renderer.typst_overlay.source_cleanup import (
                _clip_rects_against_protected_rects,
            )

            clipped = _clip_rects_against_protected_rects([expanded], preserve_on_page)
            for rect in clipped:
                by_page.setdefault(page_idx, []).append(rect)
        else:
            by_page.setdefault(page_idx, []).append(expanded)

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if segment_skips_redaction(
            seg,
            chart_body_format=chart_body_format,
            table_body_format=table_body_format,
            equation_format=equation_format,
        ):
            continue
        bbox = _read_segment_layout_bbox(seg, task_state, layout_doc)
        indices = resolve_segment_layout_block_indices(seg, task_state)
        redaction_targets: List[tuple[int, tuple[float, float, float, float]]] = []
        if indices:
            for raw_idx in indices:
                try:
                    idx = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                per_block_bbox = _read_segment_layout_bbox_for_block(
                    seg,
                    idx,
                    task_state,
                    layout_doc,
                )
                if per_block_bbox is None:
                    blk = block_by_index.get(idx)
                    if blk is not None and getattr(blk, "bbox", None):
                        try:
                            per_block_bbox = tuple(float(v) for v in blk.bbox[:4])
                        except (TypeError, ValueError):
                            per_block_bbox = None
                if per_block_bbox is None:
                    continue
                page_for_block = block_page.get(idx)
                if page_for_block is None:
                    page_for_block = _infer_page_index_for_bbox(per_block_bbox, layout_doc)
                if page_for_block is None:
                    continue
                redaction_targets.append((int(page_for_block), per_block_bbox))
        if not redaction_targets and bbox is not None:
            page_idx = None
            for raw_idx in indices or []:
                try:
                    page_idx = block_page.get(int(raw_idx))
                except (TypeError, ValueError):
                    continue
                if page_idx is not None:
                    break
            if page_idx is None:
                page_idx = _infer_page_index_for_bbox(bbox, layout_doc)
            if page_idx is not None:
                redaction_targets.append((int(page_idx), bbox))
        if not redaction_targets and bbox_override_by_block_index and indices:
            for raw_idx in indices:
                try:
                    idx = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                override_bbox = bbox_override_by_block_index.get(idx)
                if override_bbox is None:
                    continue
                try:
                    override_rect = tuple(float(v) for v in override_bbox[:4])
                    page_idx = block_page.get(idx)
                    if page_idx is not None:
                        redaction_targets.append((int(page_idx), override_rect))
                    break
                except (TypeError, ValueError):
                    continue
        if not redaction_targets:
            continue
        if indices and all(int(i) in skip for i in indices if i is not None):
            continue
        preserve_all = bool(indices)
        for raw_idx in indices:
            try:
                blk = block_by_index.get(int(raw_idx))
            except (TypeError, ValueError):
                blk = None
                preserve_all = False
                break
            if blk is None:
                preserve_all = False
                break
            if not block_preserves_source_pdf_visual(
                blk,
                equation_format=equation_format,
                chart_body_format=chart_body_format,
                table_body_format=table_body_format,
            ):
                preserve_all = False
                break
        if preserve_all:
            continue
        has_overlay_text = bool(segment_overlay_export_text(seg))
        if indices:
            all_empty_ocr_text = True
            for raw_idx in indices:
                try:
                    blk = block_by_index.get(int(raw_idx))
                except (TypeError, ValueError):
                    blk = None
                if blk is None or not _layout_block_is_empty_ocr_text(blk):
                    all_empty_ocr_text = False
                    break
            # Empty OCR blocks without segment overlay text keep PDF background pixels.
            if all_empty_ocr_text and not has_overlay_text:
                continue
        for page_idx, target_bbox in redaction_targets:
            _append_rect(page_idx, target_bbox)
    return by_page


def collect_empty_text_block_protected_rects(
    layout_doc: Any,
    *,
    margin_pt: float = 2.0,
    overlay_erase_block_indices: Optional[set] = None,
    overlay_text_block_indices: Optional[set] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    task_state: Optional[Dict[str, Any]] = None,
    block_text_map: Optional[Dict[int, str]] = None,
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Protect empty OCR layout blocks that have no segment overlay text."""
    if layout_doc is None:
        return {}

    overlay_erase = overlay_erase_block_indices or set()
    overlay_text = overlay_text_block_indices or set()
    if segments is not None or block_text_map is not None:
        overlay_text = overlay_text | collect_layout_block_indices_with_overlay_text(
            segments,
            task_state,
            block_text_map,
        )

    by_page: Dict[int, List[tuple[float, float, float, float]]] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            if not _layout_block_is_empty_ocr_text(block):
                continue
            idx = getattr(block, "index", None)
            if idx is not None and int(idx) in overlay_erase:
                continue
            if idx is not None and int(idx) in overlay_text:
                continue
            if empty_ocr_block_overlaps_overlay_block_region(
                block,
                layout_doc,
                overlay_erase | overlay_text,
            ):
                continue
            raw = getattr(block, "raw", None) or {}
            if is_layout_companion_block(raw):
                continue
            x0, y0, x1, y1 = block.bbox
            by_page.setdefault(page.page_index, []).append(
                (
                    max(0.0, x0 - margin_pt),
                    max(0.0, y0 - margin_pt),
                    x1 + margin_pt,
                    y1 + margin_pt,
                )
            )
    return by_page


def collect_excluded_segment_protected_rects(
    segments: List[Dict[str, Any]],
    layout_doc: Any,
    task_state: Optional[Dict[str, Any]] = None,
    *,
    margin_pt: float = 2.0,
    chart_body_format: str = "image",
    table_body_format: str = "html",
    equation_format: str = "text",
    segment_bbox_overlay_blocks: Optional[set] = None,
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Protected rects for segments that must keep original PDF pixels."""
    if not segments or layout_doc is None:
        return {}

    block_page: Dict[int, int] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is not None:
                block_page[int(idx)] = int(page.page_index)

    by_page: Dict[int, List[tuple[float, float, float, float]]] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if not segment_preserves_source_pdf_pixels(
            seg,
            chart_body_format=chart_body_format,
            table_body_format=table_body_format,
            equation_format=equation_format,
        ):
            continue
        bbox = resolve_segment_protected_bbox(
            seg,
            layout_doc,
            task_state,
            chart_body_format=chart_body_format,
            table_body_format=table_body_format,
            equation_format=equation_format,
            segment_bbox_overlay_blocks=segment_bbox_overlay_blocks,
        )
        if bbox is None:
            continue
        page_idx = None
        for raw_idx in resolve_segment_layout_block_indices(seg, task_state):
            try:
                page_idx = block_page.get(int(raw_idx))
            except (TypeError, ValueError):
                continue
            if page_idx is not None:
                break
        if page_idx is None:
            continue
        x0, y0, x1, y1 = bbox
        by_page.setdefault(page_idx, []).append(
            (
                max(0.0, x0 - margin_pt),
                max(0.0, y0 - margin_pt),
                x1 + margin_pt,
                y1 + margin_pt,
            )
        )
    return by_page


def build_block_bbox_override_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
    layout_doc: Any = None,
    *,
    chart_body_format: str = "image",
    table_body_format: str = "html",
    equation_format: str = "text",
) -> Dict[int, tuple]:
    """Build block_index -> bbox_override map from segments with overrides."""
    from layout.pdf_renderer.typst_overlay.visual_images import block_preserves_source_pdf_visual

    block_map: Dict[int, tuple] = {}
    chart_fmt = (chart_body_format or "image").strip().lower()
    table_fmt = (table_body_format or "html").strip().lower()
    eq_fmt = (equation_format or "text").strip().lower()
    block_by_index: Dict[int, Any] = {}
    if layout_doc is not None:
        for page in layout_doc.pages:
            for block in page.blocks:
                idx = getattr(block, "index", None)
                if idx is not None:
                    block_by_index[int(idx)] = block

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if segment_skips_redaction(
            seg,
            chart_body_format=chart_fmt,
            table_body_format=table_fmt,
            equation_format=eq_fmt,
        ):
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            try:
                idx_int = int(idx)
            except (TypeError, ValueError):
                continue
            per_block_bbox = _read_segment_layout_bbox_for_block(
                seg,
                idx_int,
                task_state,
                layout_doc,
            )
            if per_block_bbox is None:
                continue
            blk = block_by_index.get(idx_int)
            if blk is not None and block_preserves_source_pdf_visual(
                blk,
                equation_format=eq_fmt,
                chart_body_format=chart_fmt,
                table_body_format=table_fmt,
            ):
                continue
            block_map[idx_int] = per_block_bbox
    return block_map


def collect_bbox_override_redaction_rects(
    bbox_override_by_block_index: Optional[Dict[int, tuple]],
    layout_doc: Any,
    overlay_erase_block_indices: Optional[set],
    *,
    skip_block_indices: Optional[set] = None,
    margin_pt: float = 2.0,
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Redaction rects for user bbox overrides on overlay-erase layout blocks."""
    if not bbox_override_by_block_index or layout_doc is None:
        return {}

    overlay_erase = overlay_erase_block_indices or set()
    skip = skip_block_indices or set()
    block_page: Dict[int, int] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            idx = getattr(block, "index", None)
            if idx is not None:
                block_page[int(idx)] = int(page.page_index)

    by_page: Dict[int, List[tuple[float, float, float, float]]] = {}
    for raw_idx, override_bbox in bbox_override_by_block_index.items():
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if idx not in overlay_erase or idx in skip:
            continue
        if not isinstance(override_bbox, (tuple, list)) or len(override_bbox) < 4:
            continue
        try:
            x0, y0, x1, y1 = (
                float(override_bbox[0]),
                float(override_bbox[1]),
                float(override_bbox[2]),
                float(override_bbox[3]),
            )
        except (TypeError, ValueError):
            continue
        page_idx = block_page.get(idx)
        if page_idx is None:
            continue
        expanded = (
            max(0.0, x0 - margin_pt),
            max(0.0, y0 - margin_pt),
            x1 + margin_pt,
            y1 + margin_pt,
        )
        by_page.setdefault(page_idx, []).append(expanded)
    return by_page


def merge_redaction_rect_maps(
    base: Dict[int, List[tuple[float, float, float, float]]],
    extra: Dict[int, List[tuple[float, float, float, float]]],
) -> Dict[int, List[tuple[float, float, float, float]]]:
    """Merge per-page redaction rect lists."""
    if not extra:
        return base
    merged = dict(base)
    for page_idx, rects in extra.items():
        merged.setdefault(page_idx, []).extend(rects)
    return merged


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
