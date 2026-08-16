# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Dry-run PDF overlay font size (matches Typst pdftr_fit_* render path)."""

from __future__ import annotations

import math
from typing import Any, Callable, Optional

from layout.base import LayoutBlock
from layout.pdf_renderer.typst_overlay.font_fit import (
    REF_TEXT_LINE_METRICS_EM,
    FontFitCalculator,
    LATIN_CHAR_WIDTH_RATIO,
    estimate_horizontal_text_width_pt,
)
from layout.pdf_renderer.typst_overlay.formula_safety import formula_safety_insets_pt
from layout.pdf_renderer.typst_overlay.models import RenderBlock, layout_block_to_render_block
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    FONT_SIZE_PT_MIN,
    apply_user_font_override,
)
from layout.pdf_renderer.typst_overlay.text_metrics import (
    count_visual_lines_from_content,
    estimate_typographic_units,
)

FIT_SIZE_EPS_PT = 0.08
FIT_LEADING_EPS_EM = 0.01
MIN_CONTENT_HEIGHT_PT = 8.0
# Keep in sync with emitter.PLAIN_LINE_FIT_MAX_CHARS (short plain → Typst scaled-font).
PLAIN_LINE_FIT_MAX_CHARS = 40
PRESERVED_LINE_FONT_HEIGHT_RATIO = 0.86


def _first_line_indent_pt(rb: RenderBlock, font_size_pt: float) -> float:
    indent_em = float(getattr(rb, "first_line_indent_em", 0.0) or 0.0)
    indent_pt = float(getattr(rb, "first_line_indent_pt", 0.0) or 0.0)
    if indent_em > 0:
        return max(indent_pt, indent_em * font_size_pt)
    return max(0.0, indent_pt)


def _short_plain_scaled_font_pt(
    rb: RenderBlock,
    text: str,
    layout_width_pt: float,
) -> float:
    """Mirror emitter short-plain Typst scaled-font width shrink."""
    base = float(rb.font_size_pt)
    if base <= 0:
        return base
    measured = estimate_horizontal_text_width_pt(text, base)
    measured += _first_line_indent_pt(rb, base)
    if measured > layout_width_pt and measured > 0:
        base = base * (layout_width_pt / measured)
    return max(1.0, base)


def _preserved_line_effective_font_pt(rb: RenderBlock) -> float:
    """Mirror emitter unlocked per-line clamp: min(font, line_height * 0.86)."""
    boxes = getattr(rb, "preserved_line_boxes", None) or []
    base = float(rb.font_size_pt)
    if not boxes:
        return base
    effective = base
    for line in boxes:
        bbox = getattr(line, "bbox", None)
        if not bbox or len(bbox) < 4:
            continue
        try:
            lh = max(1.0, float(bbox[3]) - float(bbox[1]))
        except (TypeError, ValueError):
            continue
        effective = min(effective, lh * PRESERVED_LINE_FONT_HEIGHT_RATIO)
    return max(1.0, effective)


def _binary_search_max(
    lo: float,
    hi: float,
    eps: float,
    fits: Callable[[float], bool],
) -> float:
    """Largest value in [lo, hi] where fits(value) is True (Typst pdftr_fit_size)."""
    while hi - lo > eps:
        mid = lo + (hi - lo) / 2.0
        if fits(mid):
            lo = mid
        else:
            hi = mid
    return lo


def _wrap_line_count(text: str, width_pt: float, font_size_pt: float, layout_raw: Any) -> float:
    typo_units = estimate_typographic_units(text, layout_raw)
    chars_per_line = width_pt / max(font_size_pt * LATIN_CHAR_WIDTH_RATIO, 0.1)
    wrap_lines = max(1.0, math.ceil(typo_units / max(chars_per_line, 1.0)))
    embedded_lines = float(count_visual_lines_from_content(text, layout_raw))
    return max(wrap_lines, embedded_lines)


def _par_block_height_pt(
    text: str,
    width_pt: float,
    font_size_pt: float,
    leading_em: float,
    layout_raw: Any,
) -> float:
    line_count = _wrap_line_count(text, width_pt, font_size_pt, layout_raw)
    body_em = REF_TEXT_LINE_METRICS_EM
    if line_count <= 1.0:
        return font_size_pt * body_em
    return font_size_pt * (line_count * body_em + (line_count - 1.0) * leading_em)


def _content_fit_height_pt(block: RenderBlock, text: str, box_height_pt: float) -> float:
    insets = formula_safety_insets_pt(
        text,
        block.math_map,
        font_size_pt=block.font_size_pt,
        box_height_pt=box_height_pt,
    )
    return max(MIN_CONTENT_HEIGHT_PT, box_height_pt - insets.total_pt)


def _dry_run_single_line_fit(
    rb: RenderBlock,
    text: str,
    layout_raw: Any,
    fit_width_pt: float,
    fit_height_pt: float,
) -> float:
    max_font = max(rb.font_size_pt, rb.fit_max_font_size_pt or rb.font_size_pt)
    min_font = max(1.0, min(rb.fit_min_font_size_pt or rb.font_size_pt, rb.font_size_pt))

    def fits(size_pt: float) -> bool:
        width = estimate_horizontal_text_width_pt(text, size_pt)
        height = size_pt * 1.0
        return width <= fit_width_pt + 0.5 and height <= fit_height_pt + 0.1

    if fits(max_font):
        return round(max_font, 1)
    chosen = _binary_search_max(min_font, max_font, FIT_SIZE_EPS_PT, fits)
    return round(max(chosen, min_font), 1)


def _dry_run_markdown_fit_fixed_leading(
    rb: RenderBlock,
    text: str,
    layout_raw: Any,
    width_pt: float,
    fit_height_pt: float,
) -> float:
    max_font = rb.font_size_pt
    if rb.fit_max_font_size_pt and rb.fit_max_font_size_pt > 0:
        max_font = min(max_font, rb.fit_max_font_size_pt)
    min_font = rb.fit_min_font_size_pt
    if not min_font or min_font <= 0:
        min_font = max(1.0, max_font * 0.5)
    leading = rb.leading_em

    def fits(size_pt: float) -> bool:
        return _par_block_height_pt(text, width_pt, size_pt, leading, layout_raw) <= fit_height_pt + 0.1

    if fits(max_font):
        return round(max_font, 1)

    fallback_min = min_font
    emergency_min = max(4.2, min_font * 0.65)
    if not fits(fallback_min):
        if not fits(emergency_min):
            return round(emergency_min, 1)
        chosen = _binary_search_max(emergency_min, fallback_min, FIT_SIZE_EPS_PT, fits)
    else:
        chosen = _binary_search_max(fallback_min, max_font, FIT_SIZE_EPS_PT, fits)
    return round(chosen, 1)


def _dry_run_markdown_fit(
    rb: RenderBlock,
    text: str,
    layout_raw: Any,
    width_pt: float,
    fit_height_pt: float,
) -> float:
    max_size = rb.font_size_pt
    min_size = rb.fit_min_font_size_pt or max(1.0, max_size * 0.5)
    max_leading = rb.leading_em
    min_leading = rb.fit_min_leading_em or max(0.8, max_leading * 0.7)

    def fits(size_pt: float, leading_em: float) -> bool:
        return _par_block_height_pt(text, width_pt, size_pt, leading_em, layout_raw) <= fit_height_pt + 0.1

    if fits(max_size, max_leading):
        return round(max_size, 1)

    fallback_min_size = min_size
    fallback_min_leading = min_leading
    emergency_min_size = max(4.2, min_size * 0.65)
    emergency_min_leading = max(0.20, min_leading * 0.75)
    chosen_leading = max_leading if fits(min_size, max_leading) else min_leading

    if not fits(min_size, chosen_leading):
        if not fits(fallback_min_size, fallback_min_leading):
            chosen_size = _binary_search_max(
                emergency_min_size,
                fallback_min_size,
                FIT_SIZE_EPS_PT,
                lambda s: fits(s, emergency_min_leading),
            )
        else:
            chosen_size = _binary_search_max(
                fallback_min_size,
                min_size,
                FIT_SIZE_EPS_PT,
                lambda s: fits(s, fallback_min_leading),
            )
    else:
        chosen_size = _binary_search_max(
            min_size,
            max_size,
            FIT_SIZE_EPS_PT,
            lambda s: fits(s, chosen_leading),
        )

    leading_floor = (
        min_leading
        if fits(chosen_size, min_leading)
        else emergency_min_leading
        if fits(chosen_size, emergency_min_leading)
        else emergency_min_leading
    )
    leading_cap = max_leading if fits(chosen_size, max_leading) else chosen_leading
    if not fits(chosen_size, leading_cap):
        _binary_search_max(
            leading_floor,
            leading_cap,
            FIT_LEADING_EPS_EM,
            lambda leading: fits(chosen_size, leading),
        )

    return round(chosen_size, 1)


def resolve_pdf_render_font_size_pt(
    rb: RenderBlock,
    text: str,
    *,
    layout_raw: Any = None,
) -> Optional[float]:
    """Resolve fitted font size pt from a prepared RenderBlock.

    Must stay aligned with emitter production paths (short scaled-font, fit_to_box,
    preserved-line height clamp). Otherwise Preview-revision UI labels show a larger
    auto size than the unlocked render, so locking that same number looks bigger.
    """
    plain = (text or "").strip()
    if not plain:
        return None
    if rb.font_size_locked:
        return round(float(rb.font_size_pt), 1)

    _, _, x1, y1 = rb.inner_bbox
    x0, y0, _, _ = rb.inner_bbox
    width_pt = max(1.0, x1 - x0)
    height_pt = max(1.0, y1 - y0)
    rotation = int(getattr(rb, "rotation", 0) or 0)
    if rotation in {90, 270}:
        layout_width_pt, layout_height_pt = height_pt, width_pt
    else:
        layout_width_pt, layout_height_pt = width_pt, height_pt
    content = _content_fit_height_pt(rb, plain, layout_height_pt)

    if rb.preserve_line_breaks and (getattr(rb, "preserved_line_boxes", None) or "\n" in plain):
        return round(_preserved_line_effective_font_pt(rb), 1)

    # emitter._render_plain_block: short text uses Typst scaled-font even when
    # fit_to_box is False (preferred pt is only an upper bound before width shrink).
    kind = (getattr(rb, "render_kind", None) or "").strip().lower()
    if (
        kind in ("plain", "plain_line")
        and len(plain) <= PLAIN_LINE_FIT_MAX_CHARS
        and "\n" not in plain
    ):
        return round(_short_plain_scaled_font_pt(rb, plain, layout_width_pt), 1)

    if not rb.fit_to_box:
        return round(float(rb.font_size_pt), 1)

    if rb.fit_single_line:
        fit_w = (
            max(layout_width_pt, rb.fit_target_width_pt)
            if rb.fit_target_width_pt > 0
            else layout_width_pt
        )
        fit_h = max(
            MIN_CONTENT_HEIGHT_PT,
            min(content, rb.fit_max_height_pt or content),
        )
        return _dry_run_single_line_fit(rb, plain, layout_raw, fit_w, fit_h)

    if getattr(rb, "leading_em_locked", False):
        return _dry_run_markdown_fit_fixed_leading(
            rb, plain, layout_raw, layout_width_pt, content,
        )
    return _dry_run_markdown_fit(rb, plain, layout_raw, layout_width_pt, content)


def dry_run_pdf_font_size_pt(
    block: LayoutBlock,
    text: str,
    *,
    layout_raw: Any = None,
    page_width_pt: Optional[float] = None,
    user_pt: Optional[float] = None,
    font_weight: str = "regular",
    calculator: Optional[FontFitCalculator] = None,
    ref_unified_font_pt: Optional[float] = None,
    ref_unified_leading_em: Optional[float] = None,
) -> Optional[float]:
    """Return PDF overlay render pt using the same fit path as Typst production."""
    plain = (text or "").strip()
    if not plain:
        return None

    calc = calculator or FontFitCalculator(min_size_pt=FONT_SIZE_PT_MIN)
    rb = layout_block_to_render_block(
        block,
        page_index=getattr(block, "page_index", 0) or 0,
        translated_text=plain,
    )
    raw = layout_raw if layout_raw is not None else getattr(block, "raw", None) or {}

    if user_pt is not None and user_pt > 0:
        rb = apply_user_font_override(rb, user_pt, calculator=calc)
    else:
        rb = calc.calculate_fit_params(
            rb,
            layout_raw=raw,
            ref_unified_font_pt=ref_unified_font_pt,
            ref_unified_leading_em=ref_unified_leading_em,
            page_width_pt=page_width_pt,
        )
    if font_weight == "bold":
        rb = RenderBlock(**{**rb.__dict__, "font_weight": "bold"})

    return resolve_pdf_render_font_size_pt(rb, plain, layout_raw=raw)
