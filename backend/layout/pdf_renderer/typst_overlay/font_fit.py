# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Font fitting utilities for Typst overlay rendering.

Calculates optimal font sizes, line heights (leading), and font weights
based on the bounding box dimensions of each layout block.
"""

from typing import Any, Optional, Tuple

from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.text_metrics import (
    block_needs_math_fit,
    estimate_typographic_units,
    is_single_line_bbox,
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

    def estimate_font_size(self, block: RenderBlock) -> float:
        """
        Estimate an appropriate font size for a render block.

        Uses typographic units so inline math counts wider than plain chars.
        """
        if block.font_size_pt > 0.0 and block.font_size_pt != DEFAULT_FONT_SIZE_PT:
            return block.font_size_pt

        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        available_h = bbox_height * (1.0 - BBOX_VERTICAL_MARGIN_RATIO)

        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text)
        if typo_units <= 0:
            return self.default_size_pt

        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        chars_per_line = max(
            1.0,
            bbox_width / (self.default_size_pt * LATIN_CHAR_WIDTH_RATIO),
        )
        line_count = max(1.0, typo_units / chars_per_line)

        estimated = available_h / (line_count * self.default_leading_em)
        return round(max(self.min_size_pt, min(self.max_size_pt, estimated)), 1)

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
        font_size = block.font_size_pt
        if not preserve_font_size and (font_size <= 0 or font_size == DEFAULT_FONT_SIZE_PT):
            font_size = self.estimate_font_size(block)

        leading = block.leading_em
        if not preserve_font_size and (leading <= 0 or leading == DEFAULT_LEADING_EM):
            leading = self.estimate_leading(font_size)

        _, _, x1, _ = block.inner_bbox
        _, y0, _, y1 = block.inner_bbox
        bbox_width = max(1.0, x1 - block.inner_bbox[0])
        bbox_height = max(1.0, y1 - y0)
        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text)
        has_math = block_needs_math_fit(text, layout_raw)

        needs_fit = typo_units > 0 and (
            typo_units * font_size * LATIN_CHAR_WIDTH_RATIO > bbox_width * 1.2
            or has_math
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
