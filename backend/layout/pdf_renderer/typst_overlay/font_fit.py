# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Font fitting utilities for Typst overlay rendering.

Calculates optimal font sizes, line heights (leading), and font weights
based on the bounding box dimensions of each layout block.
"""

import math
import statistics
from typing import Any, List, Optional, Tuple

from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.text_metrics import (
    block_needs_math_fit,
    count_non_cross_page_lines,
    estimate_typographic_units,
    estimate_visual_line_count,
    is_single_line_bbox,
    SINGLE_LINE_BBOX_HEIGHT_PT,
)


# ---- Constants ----

# Typical CJK character width-to-font-size ratio (approximately)
CJK_CHAR_WIDTH_RATIO = 1.0
# Typical Latin character width-to-font-size ratio (approximately 0.5 for mixed text)
LATIN_CHAR_WIDTH_RATIO = 0.52

# Margin inside the bbox to leave around text (as fraction of bbox height)
BBOX_VERTICAL_MARGIN_RATIO = 0.15
BBOX_HORIZONTAL_MARGIN_PT = 4.0

# Font size ranges
MIN_FONT_SIZE_PT = 6.0
MAX_FONT_SIZE_PT = 24.0
DEFAULT_FONT_SIZE_PT = 10.0
DEFAULT_LEADING_EM = 1.25

# MinerU ref_text lines (~21pt bbox) typically use ~9pt body; cap estimate as fraction of height.
REF_TEXT_FONT_HEIGHT_RATIO = 0.48
# Unified bibliography font is floored to this step (10.1 -> 10.0, 10.6 -> 10.5).
REF_TEXT_FONT_QUANTIZE_STEP_PT = 0.5
# Applied after median + quantize (10.0 -> 9.5).
REF_TEXT_UNIFIED_FONT_OFFSET_PT = -0.5
# Per-line glyph box height as em of font size (Typst par leading is extra gap).
REF_TEXT_LINE_METRICS_EM = 0.88
# Target render height as a fraction of ref_text bbox height.
REF_TEXT_FIT_HEIGHT_RATIO = 0.90
REF_TEXT_MIN_LEADING_EM = 0.48
REF_TEXT_MAX_LEADING_EM = 0.72
REF_TEXT_LEADING_QUANTIZE_STEP_EM = 0.05
# Trigger fit_to_box when estimated line box exceeds this fraction of bbox height.
SHORT_BBOX_HEIGHT_OVERFLOW_RATIO = 0.85

# Title blocks: MinerU marks type "title" but often omits span size; bbox height is reliable.
TITLE_SINGLE_LINE_FONT_HEIGHT_RATIO = 0.86
TITLE_TYPICAL_LINE_HEIGHT_PT = 18.0
TITLE_LEADING_EM = 1.12
TITLE_MIN_FONT_SIZE_PT = 10.0


def _layout_block_type(layout_raw: Any) -> str:
    if isinstance(layout_raw, dict):
        return str(layout_raw.get("type") or "")
    return ""


def is_ref_text_layout(layout_raw: Any, block_type: str = "") -> bool:
    """True when MinerU marks this block as bibliography / reference text."""
    if block_type == "ref_text":
        return True
    return _layout_block_type(layout_raw) == "ref_text"


def is_title_layout(layout_raw: Any, block_type: str = "", heading_level: int = 0) -> bool:
    """True when MinerU or heading metadata marks this block as a title / heading."""
    if block_type in ("title", "header"):
        return True
    if heading_level >= 1:
        return True
    return _layout_block_type(layout_raw) in ("title", "header")


def estimate_title_font_size_pt(
    bbox_height: float,
    layout_raw: Any = None,
    *,
    min_size_pt: float = TITLE_MIN_FONT_SIZE_PT,
    max_size_pt: float = MAX_FONT_SIZE_PT,
) -> float:
    """
    Estimate title font size from bbox height and MinerU line structure.

    Section headings often have a tight single-line bbox (~11pt) where body-style
    line-count heuristics shrink the font below the original. Document titles use
    a taller bbox with one logical ``lines[]`` entry but multiple visual lines;
    prefer bbox-based visual line count over body line height (14pt).
    """
    if bbox_height <= 0:
        return DEFAULT_FONT_SIZE_PT

    raw_line_count = max(1, count_non_cross_page_lines(layout_raw))
    available_h = bbox_height * (1.0 - BBOX_VERTICAL_MARGIN_RATIO)

    if (
        bbox_height <= SINGLE_LINE_BBOX_HEIGHT_PT
        and raw_line_count == 1
    ):
        estimated = bbox_height * TITLE_SINGLE_LINE_FONT_HEIGHT_RATIO
    else:
        visual_lines = max(
            float(raw_line_count),
            bbox_height / TITLE_TYPICAL_LINE_HEIGHT_PT,
        )
        estimated = available_h / (visual_lines * TITLE_LEADING_EM)

    clamped = max(min_size_pt, min(max_size_pt, estimated))
    return round(clamped, 1)


def quantize_ref_font_size_pt(
    size_pt: float,
    *,
    step: float = REF_TEXT_FONT_QUANTIZE_STEP_PT,
    min_size_pt: float = MIN_FONT_SIZE_PT,
    max_size_pt: float = MAX_FONT_SIZE_PT,
) -> float:
    """Floor bibliography font size to the nearest 0.5pt step."""
    clamped = max(min_size_pt, min(max_size_pt, size_pt))
    if step <= 0:
        return round(clamped, 1)
    quantized = math.floor(clamped / step + 1e-9) * step
    return round(max(min_size_pt, min(max_size_pt, quantized)), 1)


def quantize_ref_leading_em(
    leading_em: float,
    *,
    step: float = REF_TEXT_LEADING_QUANTIZE_STEP_EM,
    min_leading_em: float = REF_TEXT_MIN_LEADING_EM,
    max_leading_em: float = REF_TEXT_MAX_LEADING_EM,
) -> float:
    """Floor bibliography leading to the nearest 0.05em step."""
    clamped = max(min_leading_em, min(max_leading_em, leading_em))
    if step <= 0:
        return round(clamped, 2)
    quantized = math.floor(clamped / step + 1e-9) * step
    return round(max(min_leading_em, min(max_leading_em, quantized)), 2)


def _estimate_line_count(
    bbox_height: float,
    typo_units: float,
    chars_per_line: float,
    layout_raw: Any,
) -> float:
    """Combine visual, width-wrap, and block-type signals for line count."""
    wrap_lines = typo_units / max(chars_per_line, 1.0)
    visual_lines = estimate_visual_line_count(bbox_height, layout_raw)
    block_type = _layout_block_type(layout_raw)

    if is_single_line_bbox(bbox_height, layout_raw):
        # Short boxes (bibliography lines): do not treat the full bbox as one
        # body paragraph line — prefer width-based wrap for long citations.
        if block_type == "ref_text" or wrap_lines > 1.05:
            return max(1.0, wrap_lines)
        return max(1.0, visual_lines, wrap_lines)

    return max(1.0, visual_lines, wrap_lines)


class FontFitCalculator:
    """Calculates font metrics based on bounding box dimensions."""

    def __init__(self,
                 default_size_pt: float = DEFAULT_FONT_SIZE_PT,
                 min_size_pt: float = MIN_FONT_SIZE_PT,
                 max_size_pt: float = MAX_FONT_SIZE_PT,
                 default_leading_em: float = DEFAULT_LEADING_EM):
        self.default_size_pt = default_size_pt
        self.min_size_pt = min_size_pt
        self.max_size_pt = max_size_pt
        self.default_leading_em = default_leading_em

    def estimate_font_size(
        self,
        block: RenderBlock,
        layout_raw: Any = None,
    ) -> float:
        """
        Estimate an appropriate font size for a render block.

        Uses typographic units and visual line count from bbox height so MinerU
        single-line entries that wrap across many visual lines are handled.
        """
        if block.font_size_pt > 0.0 and block.font_size_pt != DEFAULT_FONT_SIZE_PT:
            return block.font_size_pt

        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)

        block_type = _layout_block_type(layout_raw)
        if is_title_layout(layout_raw, block_type=block_type):
            return estimate_title_font_size_pt(
                bbox_height,
                layout_raw,
                min_size_pt=max(self.min_size_pt, TITLE_MIN_FONT_SIZE_PT),
                max_size_pt=self.max_size_pt,
            )

        available_h = bbox_height * (1.0 - BBOX_VERTICAL_MARGIN_RATIO)

        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text, layout_raw)
        if typo_units <= 0:
            return self.default_size_pt

        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        chars_per_line = max(
            1.0,
            bbox_width / (self.default_size_pt * LATIN_CHAR_WIDTH_RATIO),
        )
        line_count = _estimate_line_count(
            bbox_height, typo_units, chars_per_line, layout_raw,
        )

        estimated = available_h / (line_count * self.default_leading_em)

        block_type = _layout_block_type(layout_raw)
        if block_type == "ref_text":
            estimated = min(estimated, bbox_height * REF_TEXT_FONT_HEIGHT_RATIO)
        elif is_single_line_bbox(bbox_height, layout_raw):
            # Generic short single-line boxes: never exceed what fits one em line.
            estimated = min(estimated, available_h / 1.05)

        return round(max(self.min_size_pt, min(self.max_size_pt, estimated)), 1)

    def compute_unified_ref_font_size(
        self,
        candidates: List[float],
    ) -> Optional[float]:
        """
        Derive one bibliography font size from per-block estimates.

        Uses the median so more ref_text bboxes stabilize the result and
        outliers (very short/long entries) have limited influence.
        """
        valid = [
            c for c in candidates
            if c > 0 and self.min_size_pt <= c <= self.max_size_pt
        ]
        if not valid:
            return None
        median = statistics.median(valid)
        quantized = quantize_ref_font_size_pt(
            median,
            min_size_pt=self.min_size_pt,
            max_size_pt=self.max_size_pt,
        )
        adjusted = quantized + REF_TEXT_UNIFIED_FONT_OFFSET_PT
        return round(
            max(self.min_size_pt, min(self.max_size_pt, adjusted)),
            1,
        )

    def estimate_ref_text_leading_em(
        self,
        block: RenderBlock,
        font_size_pt: float,
        layout_raw: Any = None,
    ) -> float:
        """
        Estimate Typst par(leading) for a bibliography block at a fixed font size.

        Solves from bbox height and wrapped line count so the stack fits inside
        the MinerU ref_text bbox without overlapping adjacent entries.
        """
        if font_size_pt <= 0:
            return REF_TEXT_MIN_LEADING_EM

        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        fit_height = bbox_height * REF_TEXT_FIT_HEIGHT_RATIO
        body_per_line = font_size_pt * REF_TEXT_LINE_METRICS_EM

        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text, layout_raw)
        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        chars_per_line = max(
            1.0,
            bbox_width / max(font_size_pt * LATIN_CHAR_WIDTH_RATIO, 0.1),
        )
        line_count = _estimate_line_count(
            bbox_height, typo_units, chars_per_line, layout_raw,
        )
        line_count = max(1.0, line_count)
        visual_lines = max(1, int(math.ceil(line_count - 1e-6)))

        if visual_lines <= 1:
            remaining = fit_height - body_per_line
            leading = (
                remaining / max(font_size_pt, 0.1)
                if remaining > 0
                else REF_TEXT_MIN_LEADING_EM
            )
        else:
            bodies = visual_lines * body_per_line
            gaps = max(visual_lines - 1, 1)
            leading = (fit_height - bodies) / (gaps * max(font_size_pt, 0.1))

        leading = max(0.20, min(REF_TEXT_MAX_LEADING_EM, leading))
        return quantize_ref_leading_em(leading)

    def compute_unified_ref_leading_em(
        self,
        candidates: List[float],
    ) -> Optional[float]:
        """Derive one bibliography leading from per-block bbox-fit estimates."""
        valid = [
            c for c in candidates
            if c > 0 and REF_TEXT_MIN_LEADING_EM <= c <= REF_TEXT_MAX_LEADING_EM
        ]
        if not valid:
            return None
        median = statistics.median(valid)
        return quantize_ref_leading_em(median)

    def estimate_leading(self, font_size_pt: float) -> float:
        """Estimate line-height (in em) for a given font size."""
        if font_size_pt <= 8.0:
            return 1.15
        elif font_size_pt <= 12.0:
            return 1.25
        elif font_size_pt <= 16.0:
            return 1.3
        else:
            return 1.35

    def estimate_font_weight(self, block: RenderBlock) -> str:
        """Determine font weight based on block type hints."""
        if block.font_weight and block.font_weight != "regular":
            return block.font_weight
        return "regular"

    def calculate_fit_params(
        self,
        block: RenderBlock,
        *,
        preserve_font_size: bool = False,
        layout_raw: Optional[Any] = None,
        ref_unified_font_pt: Optional[float] = None,
        ref_unified_leading_em: Optional[float] = None,
    ) -> RenderBlock:
        """
        Fill in any missing fit-to-box parameters on the block.

        Args:
            block: The render block to compute parameters for.
            preserve_font_size: If True, keep the existing font_size_pt and
                leading_em values instead of re-estimating them.
            layout_raw: Optional MinerU raw block dict for inline_equation spans.

        Returns:
            A new RenderBlock with complete font/fit parameters.
        """
        block_type = _layout_block_type(layout_raw)
        is_ref_text = is_ref_text_layout(layout_raw, block_type=block_type)
        is_title = is_title_layout(layout_raw, block_type=block_type)
        use_unified_ref = (
            is_ref_text
            and ref_unified_font_pt is not None
            and ref_unified_font_pt > 0
        )

        font_size = block.font_size_pt
        if use_unified_ref:
            font_size = ref_unified_font_pt
        elif not preserve_font_size and (
            font_size <= 0 or font_size == DEFAULT_FONT_SIZE_PT
        ):
            font_size = self.estimate_font_size(block, layout_raw=layout_raw)

        leading = block.leading_em
        if use_unified_ref:
            if ref_unified_leading_em is not None and ref_unified_leading_em > 0:
                leading = ref_unified_leading_em
            else:
                leading = self.estimate_ref_text_leading_em(
                    block, font_size, layout_raw=layout_raw,
                )
        elif not preserve_font_size and (
            leading <= 0 or leading == DEFAULT_LEADING_EM
        ):
            leading = self.estimate_leading(font_size)

        _, _, x1, _ = block.inner_bbox
        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)

        if use_unified_ref:
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading,
                    "fit_to_box": False,
                    "fit_single_line": False,
                    "fit_min_font_size_pt": font_size,
                    "fit_max_font_size_pt": font_size,
                    "fit_min_leading_em": leading,
                    "fit_max_height_pt": bbox_height * 0.9,
                }
            )

        if is_title:
            title_leading = leading if leading > 0 and leading != DEFAULT_LEADING_EM else TITLE_LEADING_EM
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": title_leading,
                    "fit_to_box": False,
                    "fit_single_line": False,
                    "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.85),
                    "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.05),
                    "fit_min_leading_em": max(0.9, title_leading * 0.9),
                    "fit_max_height_pt": bbox_height * 0.9,
                }
            )

        bbox_width = max(1.0, x1 - block.inner_bbox[0])
        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text, layout_raw)
        has_math = block_needs_math_fit(text, layout_raw)
        short_single_line = is_single_line_bbox(bbox_height, layout_raw)
        wrap_ratio = typo_units / max(
            1.0, bbox_width / max(font_size * LATIN_CHAR_WIDTH_RATIO, 0.1),
        )
        height_overflow = (
            short_single_line
            and font_size * leading > bbox_height * SHORT_BBOX_HEIGHT_OVERFLOW_RATIO
            and (is_ref_text or wrap_ratio >= 0.35)
        )

        needs_fit = typo_units > 0 and (
            typo_units * font_size * LATIN_CHAR_WIDTH_RATIO > bbox_width * 1.2
            or has_math
            or height_overflow
            or (is_ref_text and short_single_line)
        )
        fit_single_line = (
            needs_fit
            and has_math
            and is_single_line_bbox(bbox_height, layout_raw)
        )

        return RenderBlock(
            **{
                **block.__dict__,
                "font_size_pt": font_size,
                "leading_em": leading,
                "fit_to_box": needs_fit,
                "fit_single_line": fit_single_line,
                "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.5),
                "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.2),
                "fit_min_leading_em": max(0.8, leading * 0.7),
                "fit_max_height_pt": bbox_height * 0.9,
            }
        )


# ---- Module-level convenience functions ----

_default_calc = FontFitCalculator()


def estimate_font_size_from_bbox(
    bbox: Tuple[float, float, float, float],
    text: str,
    font_size_hint: float = DEFAULT_FONT_SIZE_PT,
) -> float:
    """Estimate font size purely from bbox and text."""
    temp_block = RenderBlock(
        block_id="_temp",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        font_size_pt=font_size_hint,
    )
    return _default_calc.estimate_font_size(temp_block)


def estimate_leading_from_bbox(
    bbox: Tuple[float, float, float, float],
    text: str,
) -> float:
    """Estimate line height purely from bbox and text."""
    fs = estimate_font_size_from_bbox(bbox, text)
    return _default_calc.estimate_leading(fs)
