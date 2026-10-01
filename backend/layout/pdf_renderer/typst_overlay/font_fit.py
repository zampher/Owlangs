# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Font fitting utilities for Typst overlay rendering.

Calculates optimal font sizes, line heights (leading), and font weights
based on the bounding box dimensions of each layout block.
"""

import math
import re
import statistics
from dataclasses import replace
from typing import Any, Callable, List, Optional, Tuple

from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.text_metrics import (
    BBOX_VERTICAL_EDGE_INSET_MAX_PT,
    block_needs_math_fit,
    bbox_content_height_pt,
    count_embedded_newlines,
    count_non_cross_page_lines,
    count_visual_lines_from_content,
    estimate_text_width_pt,
    estimate_typographic_units,
    estimate_visual_line_count,
    estimate_wrap_line_count,
    estimate_wrap_ratio,
    is_single_line_at_font,
    is_single_line_bbox,
    line_count_for_vertical_edge_margin,
    resolve_embedded_newline_policy,
    shrink_inner_bbox_vertical,
    SINGLE_LINE_BBOX_HEIGHT_PT,
)


# ---- Constants ----

# Typical CJK character width-to-font-size ratio (approximately)
CJK_CHAR_WIDTH_RATIO = 1.0
# Typical Latin character width-to-font-size ratio (approximately 0.5 for mixed text)
LATIN_CHAR_WIDTH_RATIO = 0.52

BBOX_HORIZONTAL_MARGIN_PT = 4.0

# Font size ranges
MIN_FONT_SIZE_PT = 6.0
# User-adjustable / segment display floor (may be below PDF fit minimum)
USER_FONT_SIZE_PT_MIN = 0.5
MAX_FONT_SIZE_PT = 24.0
DEFAULT_FONT_SIZE_PT = 10.0
DEFAULT_LEADING_EM = 1.25
# Preserved-line Typst stack: one block per line (~1em tall) plus inter-line spacing.
PRESERVED_STACK_LINE_BODY_EM = 1.0

# MinerU ref_text lines (~21pt bbox) typically use ~9pt body; cap estimate as fraction of height.
REF_TEXT_FONT_HEIGHT_RATIO = 0.48
# Unified bibliography font is floored to this step (10.1 -> 10.0, 10.6 -> 10.5).
REF_TEXT_FONT_QUANTIZE_STEP_PT = 0.5
# Applied after median + quantize (10.0 -> 9.5).
REF_TEXT_UNIFIED_FONT_OFFSET_PT = -0.5
# Per-line glyph box height as em of font size (Typst par leading is extra gap).
REF_TEXT_LINE_METRICS_EM = 0.88
REF_TEXT_MIN_LEADING_EM = 0.48
REF_TEXT_MAX_LEADING_EM = 0.72
REF_TEXT_LEADING_QUANTIZE_STEP_EM = 0.05
# Body paragraphs: same height model as pdf_font_dry_run._par_block_height_pt.
BODY_LINE_METRICS_EM = REF_TEXT_LINE_METRICS_EM
BODY_LEADING_EM_MIN = 0.35
BODY_LEADING_EM_MAX = 1.50
BODY_LEADING_QUANTIZE_STEP_EM = 0.05
# Locked (extracted) multi-line font: if estimated height exceeds the bbox by
# more than this fraction of the font size (10pt → 1pt), treat the extracted
# size as unreliable (e.g. first-glyph only) and refit.
LOCKED_MULTILINE_HEIGHT_OVERFLOW_FONT_RATIO = 0.10
# Trigger fit_to_box when estimated line box exceeds this fraction of bbox height.
SHORT_BBOX_HEIGHT_OVERFLOW_RATIO = 0.85

# Title blocks: MinerU marks type "title" but often omits span size; bbox height is reliable.
TITLE_SINGLE_LINE_FONT_HEIGHT_RATIO = 0.86
TITLE_TYPICAL_LINE_HEIGHT_PT = 18.0
TITLE_LEADING_EM = 1.12
TITLE_MIN_FONT_SIZE_PT = 10.0
# Section headings are ~9–11pt bbox; taller single-line "title" tags are often mislabels.
TIGHT_TITLE_BBOX_HEIGHT_PT = 16.0
# Page headers (dates, patent numbers): one line inside a tight bbox (~9–15pt).
SHORT_HEADER_FONT_HEIGHT_RATIO = 0.68

# Title / header horizontal extension when translation is slightly wider than bbox.
TITLE_PAGE_RIGHT_MARGIN_PT = 24.0
TITLE_RIGHT_EDGE_TOLERANCE_PT = 18.0
# Prefer single-line extend (no wrap) when overflow tail is at most this many characters.
HORIZONTAL_EXTEND_MAX_CHARS = 4
# Back-compat alias used in tests/docs.
TITLE_HORIZONTAL_EXTEND_MAX_CHARS = HORIZONTAL_EXTEND_MAX_CHARS
# Typst/cmarker glyph width is often wider than the Python CJK/Latin estimate;
# pad single-line extend targets so redaction covers the painted overflow.
SINGLE_LINE_WIDTH_ESTIMATE_SLACK = 1.12


def _char_width_pt(ch: str, font_size_pt: float) -> float:
    if ch.isspace():
        return font_size_pt * 0.28
    if _is_cjk_char(ch):
        return font_size_pt * CJK_CHAR_WIDTH_RATIO
    return font_size_pt * LATIN_CHAR_WIDTH_RATIO


def _effective_font_size_hint(font_size_pt: float) -> Optional[float]:
    """
    Return a real font-size hint, or None when the value is unset.

    ``RenderBlock.font_size_pt`` defaults to ``DEFAULT_FONT_SIZE_PT`` (10pt).
    Passing that default into font-aware line-height heuristics treats every
    unset block as 10pt body text and over-counts visual lines → undersized
    fonts and chronically under-filled bboxes (especially EN→ZH).
    """
    if font_size_pt <= 0 or font_size_pt == DEFAULT_FONT_SIZE_PT:
        return None
    return font_size_pt


def overflow_tail_text(
    text: str,
    bbox_width: float,
    font_size_pt: float,
) -> str:
    """Return the suffix of *text* that exceeds *bbox_width* at *font_size_pt*."""
    if not text or font_size_pt <= 0:
        return ""
    width = 0.0
    for index, ch in enumerate(text):
        ch_w = _char_width_pt(ch, font_size_pt)
        if width + ch_w > bbox_width + 0.5:
            return text[index:]
        width += ch_w
    return ""


def overflow_tail_char_count(
    text: str,
    bbox_width: float,
    font_size_pt: float,
) -> int:
    """Character count of the horizontal overflow tail (includes CJK and ASCII)."""
    return len(overflow_tail_text(text, bbox_width, font_size_pt))


def _is_cjk_char(ch: str) -> bool:
    """True for CJK unified / extension / compatibility ideographs."""
    if not ch:
        return False
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0xF900 <= o <= 0xFAFF
    )


def estimate_horizontal_text_width_pt(text: str, font_size_pt: float) -> float:
    """Estimate rendered single-line text width in pt (CJK ≈ 1em, Latin ≈ 0.52em)."""
    return estimate_text_width_pt(text, font_size_pt)


def is_bbox_at_page_right_edge(
    x1: float,
    page_width_pt: float,
    *,
    margin_pt: float = TITLE_PAGE_RIGHT_MARGIN_PT,
    tolerance_pt: float = TITLE_RIGHT_EDGE_TOLERANCE_PT,
) -> bool:
    """True when the block bbox already sits at the page right margin."""
    if page_width_pt <= 0:
        return False
    return x1 >= page_width_pt - margin_pt - tolerance_pt


def title_wrap_would_exceed_bbox_height(
    text: str,
    bbox_width: float,
    bbox_height: float,
    font_size_pt: float,
    leading_em: float,
) -> bool:
    """True when width-wrap at *font_size_pt* needs more vertical space than *bbox_height*."""
    text_width = estimate_horizontal_text_width_pt(text, font_size_pt)
    wrap_lines = max(1, int(math.ceil(text_width / max(bbox_width, 1.0))))
    if wrap_lines <= 1:
        return False
    available_h = bbox_content_height_pt(
        bbox_height, float(wrap_lines), font_size_pt=font_size_pt,
    )
    needed_h = preserved_stack_render_height_pt(
        float(wrap_lines), font_size_pt, leading_em,
    )
    return needed_h > available_h + 0.5


def plan_title_horizontal_extension_pt(
    text: str,
    inner_bbox: Tuple[float, float, float, float],
    font_size_pt: float,
    leading_em: float,
    page_width_pt: Optional[float],
    *,
    max_overflow_chars: Optional[int] = HORIZONTAL_EXTEND_MAX_CHARS,
) -> Optional[float]:
    """
    Return a widened fit width (pt) for single-line text, or None.

    Prefer horizontal extension over wrapping when the overflow tail is within
    *max_overflow_chars* (``None`` = unlimited) and there is room toward the
    page right margin. When *page_width_pt* is unknown, extend to the natural
    text width (still no wrap).
    """
    del leading_em  # reserved for callers; char tail count is the gate.
    if font_size_pt <= 0:
        return None

    x0, _y0, x1, _y1 = inner_bbox
    bbox_width = max(1.0, x1 - x0)

    text_width = estimate_horizontal_text_width_pt(text, font_size_pt)
    text_width *= SINGLE_LINE_WIDTH_ESTIMATE_SLACK
    if text_width <= bbox_width + 0.5:
        return None

    tail_chars = overflow_tail_char_count(text, bbox_width, font_size_pt)
    if tail_chars <= 0:
        return None
    if max_overflow_chars is not None and tail_chars > max_overflow_chars:
        return None

    if page_width_pt and page_width_pt > 0:
        if is_bbox_at_page_right_edge(x1, page_width_pt):
            return None
        max_x1 = page_width_pt - TITLE_PAGE_RIGHT_MARGIN_PT
        extended_x1 = min(x0 + text_width, max_x1)
        extended_width = extended_x1 - x0
        if extended_width <= bbox_width + 0.5:
            return None
        # Title path (limited chars) refuses partial extend; body (unlimited)
        # still takes whatever room remains toward the margin.
        if (
            max_overflow_chars is not None
            and text_width > extended_width + 1.0
        ):
            return None
        return extended_width

    # No page width: still allow natural single-line width for no-wrap render.
    return text_width


plan_horizontal_extension_pt = plan_title_horizontal_extension_pt


def plan_body_single_line_extension_pt(
    text: str,
    inner_bbox: Tuple[float, float, float, float],
    font_size_pt: float,
    leading_em: float,
    page_width_pt: Optional[float],
) -> Optional[float]:
    """Widen single-line body text to natural width (no char-count cap)."""
    return plan_horizontal_extension_pt(
        text,
        inner_bbox,
        font_size_pt,
        leading_em,
        page_width_pt,
        max_overflow_chars=None,
    )


def _block_width_overflows(
    text: str,
    bbox_width: float,
    font_size_pt: float,
) -> bool:
    return estimate_horizontal_text_width_pt(text, font_size_pt) > bbox_width * 0.95


_title_width_overflows = _block_width_overflows


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


_PATENT_FIELD_LABEL_RE = re.compile(r"^\(\d{2}\)\s")


def _layout_text_content(text: str = "", layout_raw: Any = None) -> str:
    """Best-effort plain text from render text or MinerU raw spans."""
    if text and text.strip():
        return text.strip()
    if isinstance(layout_raw, dict):
        parts: List[str] = []
        for line in layout_raw.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                content = span.get("content")
                if content:
                    parts.append(str(content))
        if parts:
            return " ".join(parts).strip()
    return ""


def is_patent_field_label(text: str = "", layout_raw: Any = None) -> bool:
    """US patent form lines like ``(56) References Cited ...``."""
    content = _layout_text_content(text, layout_raw)
    return bool(_PATENT_FIELD_LABEL_RE.match(content))


def should_use_title_font_sizing(
    text: str,
    layout_raw: Any,
    bbox_height: float,
    *,
    block_type: str = "",
) -> bool:
    """
    Whether Typst should apply title-specific font sizing.

    Local MinerU (middle.json) often tags patent bibliography headers as
    ``type: "title"`` with a ~27pt bbox; treating them as section titles yields
    ~23pt font (bbox × 0.86). Route those through body-text fitting instead.

    ``type: header`` page labels (dates, patent numbers) use short-header fitting.
    """
    resolved_type = block_type or _layout_block_type(layout_raw)
    if resolved_type == "header":
        return False
    if is_patent_field_label(text, layout_raw):
        return False
    return True


def is_page_header_layout(layout_raw: Any, block_type: str = "") -> bool:
    """True for MinerU page margin headers (dates, patent ids), not section titles."""
    return (block_type or _layout_block_type(layout_raw)) == "header"


def estimate_short_header_font_size_pt(
    bbox_height: float,
    layout_raw: Any = None,
) -> float:
    """
    Estimate font size for a tight single-line page header bbox.

    Patent page headers (e.g. ``Mar. 18, 2014`` in a ~15pt-tall box) must stay
    near the original ~9–10pt size; title-style ``bbox × 0.86`` overshoots.
    """
    if bbox_height <= 0:
        return DEFAULT_FONT_SIZE_PT

    raw_line_count = max(1, count_non_cross_page_lines(layout_raw))
    available_h = bbox_content_height_pt(bbox_height, float(raw_line_count))
    if raw_line_count <= 1:
        estimated = min(
            bbox_height * SHORT_HEADER_FONT_HEIGHT_RATIO,
            available_h / 1.08,
        )
    else:
        estimated = available_h / (raw_line_count * DEFAULT_LEADING_EM)

    return round(max(MIN_FONT_SIZE_PT, min(MAX_FONT_SIZE_PT, estimated)), 1)


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

    if (
        bbox_height <= TIGHT_TITLE_BBOX_HEIGHT_PT
        and raw_line_count == 1
    ):
        visual_lines = 1.0
        estimated = bbox_height * TITLE_SINGLE_LINE_FONT_HEIGHT_RATIO
    elif (
        bbox_height <= SINGLE_LINE_BBOX_HEIGHT_PT
        and raw_line_count == 1
    ):
        visual_lines = max(
            2.0,
            bbox_height / TITLE_TYPICAL_LINE_HEIGHT_PT,
        )
        available_h = bbox_content_height_pt(bbox_height, visual_lines)
        estimated = available_h / (visual_lines * TITLE_LEADING_EM)
    else:
        visual_lines = max(
            float(raw_line_count),
            bbox_height / TITLE_TYPICAL_LINE_HEIGHT_PT,
        )
        available_h = bbox_content_height_pt(bbox_height, visual_lines)
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


def quantize_body_leading_em(
    leading_em: float,
    *,
    step: float = BODY_LEADING_QUANTIZE_STEP_EM,
    min_leading_em: float = BODY_LEADING_EM_MIN,
    max_leading_em: float = BODY_LEADING_EM_MAX,
) -> float:
    """Clamp body leading and round to the nearest step."""
    clamped = max(min_leading_em, min(max_leading_em, leading_em))
    if step <= 0:
        return round(clamped, 2)
    quantized = round(clamped / step) * step
    return round(max(min_leading_em, min(max_leading_em, quantized)), 2)


def body_visual_line_count(
    text: str,
    bbox_width_pt: float,
    font_size_pt: float,
    layout_raw: Any = None,
) -> int:
    """
    Visual line count for body height / leading estimates.

    Width-wrap alone under-counts markdown hard breaks and preserved ``\\n``
    lists (``\\n`` is treated as a thin space in the width heuristic). When
    embedded newlines remain in *text*, also count per-segment wrap lines.
    """
    wrap_lines = estimate_wrap_line_count(
        text or "", bbox_width_pt, font_size_pt, layout_raw,
    )
    visual_lines = max(1, int(math.ceil(float(wrap_lines) - 1e-6)))
    if count_embedded_newlines(text or "", layout_raw) > 0:
        hard_lines = estimate_preserved_stack_visual_lines(
            text or "", bbox_width_pt, font_size_pt,
        )
        visual_lines = max(
            visual_lines,
            int(math.ceil(float(hard_lines) - 1e-6)),
        )
    return visual_lines


def locked_multiline_height_limit_pt(
    bbox_height_pt: float,
    font_size_pt: float,
) -> float:
    """Bbox height plus an overflow allowance of 10% of the font size."""
    allowance = max(0.0, float(font_size_pt)) * LOCKED_MULTILINE_HEIGHT_OVERFLOW_FONT_RATIO
    return float(bbox_height_pt) + allowance


def estimate_body_content_height_pt(
    text: str,
    bbox_width_pt: float,
    font_size_pt: float,
    leading_em: float,
    layout_raw: Any = None,
) -> float:
    """
    Estimated rendered height (pt) for multi-line body text.

    Matches ``pdf_font_dry_run._par_block_height_pt`` /
    ``estimate_body_leading_em_at_font``::

        height ≈ font × (n × body_em + (n − 1) × leading)
    """
    if font_size_pt <= 0:
        return 0.0
    visual_lines = body_visual_line_count(
        text or "", bbox_width_pt, font_size_pt, layout_raw,
    )
    if visual_lines <= 1:
        return font_size_pt * BODY_LINE_METRICS_EM
    return font_size_pt * (
        visual_lines * BODY_LINE_METRICS_EM
        + (visual_lines - 1) * max(leading_em, 0.0)
    )


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


def preserved_stack_height_em(
    line_count: float,
    leading_em: float,
    *,
    body_em: float = PRESERVED_STACK_LINE_BODY_EM,
) -> float:
    """
    Vertical extent in em for Typst preserved-line stack rendering.

    Matches ``stack(dir: ttb, spacing: leading)`` with one single-line block per
    visual line — not ``line_count * leading`` (which double-counts line bodies).
    """
    n = max(1.0, line_count)
    if n <= 1.0:
        return body_em
    return n * body_em + (n - 1.0) * leading_em


def preserved_stack_render_height_pt(
    font_size_pt: float,
    line_count: float,
    leading_em: float,
    *,
    body_em: float = PRESERVED_STACK_LINE_BODY_EM,
) -> float:
    """Estimated rendered height (pt) for a preserved-line stack."""
    return font_size_pt * preserved_stack_height_em(
        line_count, leading_em, body_em=body_em,
    )


def estimate_preserved_stack_visual_lines(
    text: str,
    bbox_width: float,
    font_size_pt: float,
) -> float:
    """
    Visual line count for preserved-stack rendering.

    Each ``\\n`` segment is placed in a width-constrained block; long segments
    (e.g. USPC classification lists) may wrap to additional visual lines.
    """
    segments = [s.strip() for s in (text or "").splitlines() if s.strip()]
    if not segments:
        return 1.0
    chars_per_line = bbox_width / max(font_size_pt * LATIN_CHAR_WIDTH_RATIO, 0.1)
    total = 0.0
    for seg in segments:
        units = estimate_typographic_units(seg)
        total += max(1.0, math.ceil(units / max(chars_per_line, 1.0)))
    return max(1.0, total)


def fit_preserved_stack_leading_em(
    font_size_pt: float,
    visual_lines: float,
    available_height_pt: float,
    preferred_leading_em: float,
    *,
    body_em: float = PRESERVED_STACK_LINE_BODY_EM,
    min_leading_em: float = 0.35,
) -> float:
    """Tighten leading so a preserved stack fits inside *available_height_pt*."""
    if visual_lines <= 1.0 or font_size_pt <= 0:
        return preferred_leading_em
    gap_count = visual_lines - 1.0
    body_total = visual_lines * body_em
    needed_leading = (available_height_pt / font_size_pt - body_total) / gap_count
    if needed_leading >= preferred_leading_em:
        return preferred_leading_em
    return max(min_leading_em, needed_leading)


def _blend_height_and_wrap_line_count(visual_lines: float, wrap_lines: float) -> float:
    """
    Tall bbox font sizing: balance height-implied lines vs width-wrap lines.

    When EN→ZH (or similar) shortens text, width-wrap can be ~1–2 lines while the
    source bbox height still implies ~3 visual lines. Using ``max(visual, wrap)``
    alone then under-sizes the font. For near-single-line wrap, trade off toward
    a 2-line height budget; for longer wrap, allow at most ``wrap + 1``.

    Use ``wrap < 2.5`` (not ``<= 2.0``) so probe fonts near the 2-line boundary
    still get the single↔double tradeoff instead of oscillating to wrap+1.
    """
    visual = max(1.0, float(visual_lines))
    wrap = max(1.0, float(wrap_lines))
    if wrap + 0.15 >= visual:
        return max(visual, wrap)
    # Under-filled width relative to bbox height.
    # ~1–2 wrap lines → never size as if ≥3 visual lines.
    if wrap < 2.5:
        height_cap = 2.0
    else:
        height_cap = wrap + 1.0
    return max(wrap, min(visual, height_cap))


def _is_underfilled_tall_bbox(
    block: RenderBlock,
    layout_raw: Any,
    font_size_pt: float,
) -> bool:
    """
    True when width-wrap is clearly shorter than height-implied lines.

    Detects EN→ZH (etc.) cases where a source multi-line bbox holds much shorter
    translated text; layout-seeded fonts must be allowed to grow.
    """
    text = (block.plain_text or block.markdown_text or "").strip()
    if not text:
        return False
    x0, y0, x1, y1 = block.inner_bbox
    bbox_height = max(1.0, y1 - y0)
    if is_single_line_bbox(bbox_height, layout_raw):
        return False
    # Explicit multi-line structure: keep layout seed / full visual weight.
    if count_visual_lines_from_content(text, layout_raw) > 1:
        return False
    bbox_width = max(1.0, x1 - x0)
    probe = font_size_pt if font_size_pt > 0 else DEFAULT_FONT_SIZE_PT
    visual = estimate_visual_line_count(
        bbox_height, layout_raw, text=text, font_size_pt=probe,
    )
    wrap = estimate_wrap_line_count(text, bbox_width, probe, layout_raw)
    return wrap + 0.15 < visual


def _estimate_line_count(
    bbox_height: float,
    typo_units: float,
    chars_per_line: float,
    layout_raw: Any,
    text: str = "",
    *,
    font_size_pt: Optional[float] = None,
) -> float:
    """Combine visual, width-wrap, and block-type signals for line count."""
    wrap_lines = typo_units / max(chars_per_line, 1.0)
    visual_lines = estimate_visual_line_count(
        bbox_height, layout_raw, text=text, font_size_pt=font_size_pt,
    )
    embedded_lines = float(count_visual_lines_from_content(text, layout_raw))
    if embedded_lines > 1.0:
        visual_lines = max(visual_lines, embedded_lines)

    if is_single_line_bbox(bbox_height, layout_raw):
        # Short boxes: combine width-wrap with bbox-height / embedded-\\n visual lines.
        # Never return wrap_lines alone — patent headers with \\n or ~30pt bbox are
        # two visual lines even when translated text is shorter than the source.
        return max(1.0, visual_lines, wrap_lines)

    # Explicit structure (\\n / multi-line OCR content): keep full visual weight.
    if embedded_lines > 1.0:
        return max(1.0, visual_lines, wrap_lines)

    return _blend_height_and_wrap_line_count(visual_lines, wrap_lines)


def _is_true_single_visual_line(
    bbox_height: float,
    layout_raw: Any,
    text: str = "",
    *,
    font_size_pt: Optional[float] = None,
) -> bool:
    """True when the block bbox fits exactly one visual text line."""
    return estimate_visual_line_count(
        bbox_height, layout_raw, text=text, font_size_pt=font_size_pt,
    ) <= 1.05


def _visual_line_count_for_edge_margin(
    block: RenderBlock,
    layout_raw: Any,
    *,
    font_size_pt: float,
) -> float:
    """Line count used to decide multi-line inner_bbox vertical shrink."""
    text = block.plain_text or block.markdown_text or ""
    _, y0, _, y1 = block.inner_bbox
    bbox_height = max(1.0, y1 - y0)
    x0, _, x1, _ = block.inner_bbox
    bbox_width = max(1.0, x1 - x0)
    if block.preserve_line_breaks and count_embedded_newlines(text, layout_raw) > 0:
        return estimate_preserved_stack_visual_lines(
            text, bbox_width, font_size_pt,
        )
    return line_count_for_vertical_edge_margin(
        bbox_height,
        layout_raw,
        text=text,
        font_size_pt=font_size_pt,
        bbox_width_pt=bbox_width,
    )


def shrink_render_block_inner_bbox_for_edge_margin(
    block: RenderBlock,
    layout_raw: Any = None,
    *,
    estimate_font_size: Optional[
        Callable[[RenderBlock, Any], float]
    ] = None,
) -> RenderBlock:
    """Apply method-1 margin by shrinking inner_bbox (10% line height, max 1.5pt/edge)."""
    if block.skip_reason or block.render_kind in ("image", "table"):
        return block
    block_type = _layout_block_type(layout_raw)
    text = block.plain_text or block.markdown_text or ""
    if is_page_header_layout(layout_raw, block_type=block_type):
        return block
    if (
        is_title_layout(layout_raw, block_type=block_type)
        and should_use_title_font_sizing(
            text,
            layout_raw,
            max(1.0, block.inner_bbox[3] - block.inner_bbox[1]),
            block_type=block_type,
        )
    ):
        return block
    if not text.strip():
        return block

    font_size_pt = block.font_size_pt
    if (
        estimate_font_size is not None
        and (font_size_pt <= 0 or font_size_pt == DEFAULT_FONT_SIZE_PT)
    ):
        font_size_pt = estimate_font_size(block, layout_raw)

    line_count = _visual_line_count_for_edge_margin(
        block, layout_raw, font_size_pt=font_size_pt,
    )
    shrunk = shrink_inner_bbox_vertical(
        block.inner_bbox,
        line_count,
        font_size_pt=font_size_pt,
    )
    if shrunk == block.inner_bbox:
        return block
    return replace(block, inner_bbox=shrunk)


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
        *,
        inner_bbox_shrunk: bool = False,
    ) -> float:
        """
        Estimate an appropriate font size for a render block.

        Uses typographic units and visual line count from bbox height so MinerU
        single-line entries that wrap across many visual lines are handled.

        Layout-/MinerU-seeded sizes are kept unless the tall bbox is under-filled
        by short translated text (single↔double tradeoff should grow the font).
        """
        layout_seed = (
            block.font_size_pt
            if (
                block.font_size_pt > 0.0
                and block.font_size_pt != DEFAULT_FONT_SIZE_PT
            )
            else None
        )
        if layout_seed is not None and not _is_underfilled_tall_bbox(
            block, layout_raw, layout_seed,
        ):
            return layout_seed

        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)

        text = block.plain_text or block.markdown_text or ""
        block_type = _layout_block_type(layout_raw)
        if block_type == "header":
            return estimate_short_header_font_size_pt(bbox_height, layout_raw)
        if (
            is_title_layout(layout_raw, block_type=block_type)
            and should_use_title_font_sizing(
                text, layout_raw, bbox_height, block_type=block_type,
            )
        ):
            return estimate_title_font_size_pt(
                bbox_height,
                layout_raw,
                min_size_pt=max(self.min_size_pt, TITLE_MIN_FONT_SIZE_PT),
                max_size_pt=self.max_size_pt,
            )

        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        font_hint = _effective_font_size_hint(block.font_size_pt)
        probe_font = font_hint if font_hint is not None else self.default_size_pt
        text, preserve_breaks = resolve_embedded_newline_policy(
            text,
            layout_raw,
            bbox_width_pt=bbox_width,
            font_size_pt=probe_font,
        )
        # Soft body newlines: ignore OCR span ``\\n`` so reflow fit can fill.
        newline_raw = layout_raw if preserve_breaks else None

        typo_units = estimate_typographic_units(text, layout_raw)
        if typo_units <= 0:
            return self.default_size_pt

        if preserve_breaks and count_embedded_newlines(text, newline_raw) > 0:
            font_pt, _leading = self.estimate_preserved_stack_metrics(
                block, layout_raw=layout_raw,
            )
            return font_pt

        wrap_lines = estimate_wrap_line_count(
            text, bbox_width, probe_font, layout_raw,
        )
        chars_per_line = max(1.0, typo_units / max(wrap_lines, 1e-6))
        # After method-1 edge-margin shrink, compact two-line OCR boxes
        # (e.g. 27pt patent headers) can fall below the 1.85 visual-line
        # threshold and be misread as single-line → oversized fonts.
        line_count_height = bbox_height
        if inner_bbox_shrunk:
            line_count_height = bbox_height + 2.0 * BBOX_VERTICAL_EDGE_INSET_MAX_PT
        line_count = _estimate_line_count(
            line_count_height,
            typo_units,
            chars_per_line,
            layout_raw,
            text=text,
            font_size_pt=font_hint,
        )
        available_h = (
            max(1.0, bbox_height)
            if inner_bbox_shrunk
            else bbox_content_height_pt(
                bbox_height,
                line_count,
                font_size_pt=font_hint,
            )
        )

        estimated = available_h / (line_count * self.default_leading_em)

        block_type = _layout_block_type(layout_raw)
        if block_type == "ref_text":
            estimated = min(estimated, bbox_height * REF_TEXT_FONT_HEIGHT_RATIO)
        elif (
            _is_true_single_visual_line(
                bbox_height, layout_raw, text=text,
                font_size_pt=font_hint,
            )
            and count_embedded_newlines(text, newline_raw) == 0
        ):
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
        body_per_line = font_size_pt * REF_TEXT_LINE_METRICS_EM

        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text, layout_raw)
        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        wrap_lines = estimate_wrap_line_count(
            text, bbox_width, font_size_pt, layout_raw,
        )
        chars_per_line = max(1.0, typo_units / max(wrap_lines, 1e-6))
        line_count = _estimate_line_count(
            bbox_height,
            typo_units,
            chars_per_line,
            layout_raw,
            text=text,
            font_size_pt=font_size_pt,
        )
        line_count = max(1.0, line_count)
        visual_lines = max(1, int(math.ceil(line_count - 1e-6)))
        fit_height = max(1.0, bbox_height)

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

    def estimate_body_leading_em_at_font(
        self,
        block: RenderBlock,
        font_size_pt: float,
        layout_raw: Any = None,
    ) -> float:
        """
        Derive Typst ``par(leading)`` for multi-line body text at a known font size.

        Uses the same height model as ``pdf_font_dry_run._par_block_height_pt``:

            height ≈ font × (n × body_em + (n − 1) × leading)

        so extracted / locked font sizes keep line spacing matched to the bbox
        instead of the crude size→bucket table in ``estimate_leading``.
        """
        if font_size_pt <= 0:
            return quantize_body_leading_em(self.default_leading_em)

        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        text = block.plain_text or block.markdown_text or ""

        visual_lines = body_visual_line_count(
            text, bbox_width, font_size_pt, layout_raw,
        )

        body_per_line = font_size_pt * BODY_LINE_METRICS_EM
        if visual_lines <= 1:
            return quantize_body_leading_em(self.estimate_leading(font_size_pt))

        bodies = visual_lines * body_per_line
        gaps = max(visual_lines - 1, 1)
        leading = (bbox_height - bodies) / (gaps * max(font_size_pt, 0.1))
        return quantize_body_leading_em(leading)

    def fit_locked_preserved_stack_font_size_to_bbox(
        self,
        block: RenderBlock,
        *,
        max_font_pt: float,
        min_font_pt: Optional[float] = None,
    ) -> float:
        """
        Largest font size ≤ *max_font_pt* for a preserved ``\\n`` stack in bbox.

        Uses Typst ``stack(spacing: leading)`` height model, not paragraph wrap.
        """
        x0, y0, x1, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        bbox_width = max(1.0, x1 - x0)
        text = block.plain_text or block.markdown_text or ""
        lo = max(self.min_size_pt, float(min_font_pt or self.min_size_pt))
        hi = max(lo, float(max_font_pt))

        def fits(size_pt: float) -> bool:
            visual_lines = estimate_preserved_stack_visual_lines(
                text, bbox_width, size_pt,
            )
            lead = fit_preserved_stack_leading_em(
                size_pt,
                visual_lines,
                bbox_height,
                self.estimate_leading(size_pt),
            )
            height = preserved_stack_render_height_pt(
                size_pt, visual_lines, lead,
            )
            return height <= bbox_height + 0.5

        if fits(hi):
            return round(hi, 1)

        best = lo
        low, high = lo, hi
        for _ in range(24):
            if high - low < 0.05:
                break
            mid = (low + high) / 2.0
            if fits(mid):
                best = mid
                low = mid
            else:
                high = mid
        if fits(lo) and not fits(best):
            best = lo
        return round(max(lo, best), 1)

    def fit_locked_body_font_size_to_bbox(
        self,
        block: RenderBlock,
        *,
        layout_raw: Any = None,
        max_font_pt: float,
        min_font_pt: Optional[float] = None,
    ) -> float:
        """
        Largest font size ≤ *max_font_pt* whose body text fits the block bbox.

        Used when an extracted (often first-glyph) size overflows a multi-line
        bbox by more than ``LOCKED_MULTILINE_HEIGHT_OVERFLOW_FONT_RATIO`` of
        the font size.
        """
        x0, y0, x1, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        bbox_width = max(1.0, x1 - x0)
        text = block.plain_text or block.markdown_text or ""
        lo = max(self.min_size_pt, float(min_font_pt or self.min_size_pt))
        hi = max(lo, float(max_font_pt))

        def fits(size_pt: float) -> bool:
            lead = self.estimate_body_leading_em_at_font(
                block, size_pt, layout_raw=layout_raw,
            )
            height = estimate_body_content_height_pt(
                text, bbox_width, size_pt, lead, layout_raw,
            )
            return height <= bbox_height + 0.5

        if fits(hi):
            return round(hi, 1)

        # Binary search the largest size that still fits.
        best = lo
        low, high = lo, hi
        for _ in range(24):
            if high - low < 0.05:
                break
            mid = (low + high) / 2.0
            if fits(mid):
                best = mid
                low = mid
            else:
                high = mid
        if fits(lo) and not fits(best):
            best = lo
        return round(max(lo, best), 1)

    def estimate_font_weight(self, block: RenderBlock) -> str:
        """Determine font weight based on block type hints."""
        if block.font_weight and block.font_weight != "regular":
            return block.font_weight
        return "regular"

    def _fit_title_or_header_block(
        self,
        block: RenderBlock,
        *,
        block_text: str,
        font_size: float,
        leading_em: float,
        bbox_height: float,
        page_width_pt: Optional[float],
        always_single_line_measure: bool = False,
    ) -> RenderBlock:
        """
        Shared title/header fit: extend up to 4 overflow chars, else single-line shrink.

        When *always_single_line_measure* is True (page headers), Typst ``measure()``
        decides fit even if Python width heuristics say the line fits — avoids spurious
        wraps when cmarker renders CJK/date text slightly wider than estimated.
        """
        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        extend_width = plan_horizontal_extension_pt(
            block_text,
            block.inner_bbox,
            font_size,
            leading_em,
            page_width_pt,
        )
        if extend_width and extend_width > bbox_width + 0.5:
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading_em,
                    "fit_to_box": True,
                    "fit_single_line": True,
                    "fit_target_width_pt": extend_width,
                    "fit_min_font_size_pt": font_size,
                    "fit_max_font_size_pt": font_size,
                    "fit_min_leading_em": max(0.9, leading_em * 0.9),
                    "fit_max_height_pt": max(1.0, bbox_height),
                }
            )
        if _block_width_overflows(block_text, bbox_width, font_size):
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading_em,
                    "fit_to_box": True,
                    "fit_single_line": True,
                    "fit_min_font_size_pt": self.min_size_pt,
                    "fit_max_font_size_pt": font_size,
                    "fit_min_leading_em": max(0.8, leading_em * 0.7),
                    "fit_max_height_pt": max(1.0, bbox_height),
                }
            )
        if always_single_line_measure:
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading_em,
                    "fit_to_box": True,
                    "fit_single_line": True,
                    "fit_min_font_size_pt": self.min_size_pt,
                    "fit_max_font_size_pt": font_size,
                    "fit_min_leading_em": max(0.8, leading_em * 0.7),
                    "fit_max_height_pt": max(1.0, bbox_height),
                }
            )
        return RenderBlock(
            **{
                **block.__dict__,
                "font_size_pt": font_size,
                "leading_em": leading_em,
                "fit_to_box": False,
                "fit_single_line": False,
                "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.85),
                "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.05),
                "fit_min_leading_em": max(0.9, leading_em * 0.9),
                "fit_max_height_pt": max(1.0, bbox_height),
            }
        )

    def estimate_preserved_stack_metrics(
        self,
        block: RenderBlock,
        layout_raw: Any = None,
        *,
        inner_bbox_shrunk: bool = False,
    ) -> Tuple[float, float]:
        """
        Estimate font size and leading for embedded-newline preserved-stack blocks.

        Accounts for width-wrap inside each ``\\n`` segment (e.g. long USPC lines).
        """
        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        x0, _, x1, _ = block.inner_bbox
        bbox_width = max(1.0, x1 - x0)
        text = block.plain_text or block.markdown_text or ""

        leading_em = self.default_leading_em
        visual_lines = float(count_visual_lines_from_content(text, layout_raw))

        def _content_height(
            height_pt: float,
            lines: float,
            *,
            font_size_pt: Optional[float] = None,
        ) -> float:
            if inner_bbox_shrunk:
                return max(1.0, height_pt)
            return bbox_content_height_pt(
                height_pt, lines, font_size_pt=font_size_pt,
            )

        available_h = _content_height(bbox_height, visual_lines)
        for _ in range(6):
            estimated = available_h / preserved_stack_height_em(
                visual_lines, leading_em,
            )
            estimated = max(self.min_size_pt, min(self.max_size_pt, estimated))
            leading_em = self.estimate_leading(estimated)
            visual_lines = estimate_preserved_stack_visual_lines(
                text, bbox_width, estimated,
            )
            available_h = _content_height(
                bbox_height, visual_lines, font_size_pt=estimated,
            )

        estimated = available_h / preserved_stack_height_em(
            visual_lines, leading_em,
        )
        estimated = max(self.min_size_pt, min(self.max_size_pt, estimated))
        leading_em = fit_preserved_stack_leading_em(
            estimated,
            visual_lines,
            _content_height(bbox_height, visual_lines, font_size_pt=estimated),
            self.estimate_leading(estimated),
        )
        visual_lines = estimate_preserved_stack_visual_lines(
            text, bbox_width, estimated,
        )
        available_h = _content_height(
            bbox_height, visual_lines, font_size_pt=estimated,
        )
        if estimated * preserved_stack_height_em(visual_lines, leading_em) > available_h:
            estimated = available_h / preserved_stack_height_em(
                visual_lines, leading_em,
            )
            estimated = max(self.min_size_pt, min(self.max_size_pt, estimated))
            leading_em = fit_preserved_stack_leading_em(
                estimated,
                visual_lines,
                available_h,
                leading_em,
            )
        return round(estimated, 1), round(leading_em, 2)

    def calculate_fit_params(
        self,
        block: RenderBlock,
        *,
        preserve_font_size: bool = False,
        layout_raw: Optional[Any] = None,
        ref_unified_font_pt: Optional[float] = None,
        ref_unified_leading_em: Optional[float] = None,
        page_width_pt: Optional[float] = None,
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
        block = shrink_render_block_inner_bbox_for_edge_margin(
            block,
            layout_raw=layout_raw,
            estimate_font_size=self.estimate_font_size,
        )
        block_type = _layout_block_type(layout_raw)
        is_ref_text = is_ref_text_layout(layout_raw, block_type=block_type)
        block_text = block.plain_text or block.markdown_text or ""
        x0_pre, y0_pre, x1_pre, y1_pre = block.inner_bbox
        bbox_width_pre = max(1.0, x1_pre - x0_pre)
        font_hint_pre = _effective_font_size_hint(block.font_size_pt)
        probe_pre = (
            font_hint_pre if font_hint_pre is not None else self.default_size_pt
        )
        fit_text, preserve_breaks = resolve_embedded_newline_policy(
            block_text,
            layout_raw,
            bbox_width_pt=bbox_width_pre,
            font_size_pt=probe_pre,
        )
        if fit_text != block_text:
            # Soft-collapse so emitter does not stack body paragraphs by OCR ``\\n``.
            updates: dict = {}
            if block.plain_text:
                updates["plain_text"] = fit_text
            if block.markdown_text:
                updates["markdown_text"] = fit_text
            if updates:
                block = replace(block, **updates)
            block_text = fit_text
        newline_raw = layout_raw if preserve_breaks else None
        _, y0, _, y1 = block.inner_bbox
        bbox_height = max(1.0, y1 - y0)
        is_title = (
            is_title_layout(layout_raw, block_type=block_type)
            and should_use_title_font_sizing(
                block_text, layout_raw, bbox_height, block_type=block_type,
            )
        )
        is_page_header = is_page_header_layout(layout_raw, block_type=block_type)
        use_unified_ref = (
            is_ref_text
            and ref_unified_font_pt is not None
            and ref_unified_font_pt > 0
        )

        font_size = block.font_size_pt
        if use_unified_ref:
            font_size = ref_unified_font_pt
        elif block.font_size_locked and font_size > 0:
            # Extracted / user-locked size: keep when it still fits the bbox.
            leading = block.leading_em
            leading_locked = bool(getattr(block, "leading_em_locked", False))
            lead_hint = (
                leading
                if leading > 0 and leading != DEFAULT_LEADING_EM
                else self.estimate_leading(font_size)
            )
            # Font-aware single-line: real sizes often yield bboxes > 32pt.
            short_single_line = is_single_line_at_font(
                bbox_height,
                font_size,
                leading_em=lead_hint,
                layout_raw=layout_raw,
            )
            x0_lock, _, x1_lock, _ = block.inner_bbox
            bbox_width_lock = max(1.0, x1_lock - x0_lock)

            if leading_locked and leading > 0:
                # User-specified leading wins.
                pass
            elif short_single_line:
                if leading <= 0 or leading == DEFAULT_LEADING_EM:
                    leading = self.estimate_leading(font_size)
            elif (
                preserve_breaks
                and count_embedded_newlines(block_text, newline_raw) > 0
            ):
                # Ingredient lists / USPC: hard ``\\n`` render as a Typst stack.
                # Paragraph width-wrap under-counts lines (``\\n`` ≈ thin space)
                # and then clamps leading to BODY_LEADING_EM_MAX → overflow.
                visual_lines = estimate_preserved_stack_visual_lines(
                    block_text, bbox_width_lock, font_size,
                )
                content_h = preserved_stack_render_height_pt(
                    font_size, visual_lines, BODY_LEADING_EM_MIN,
                )
                if content_h > locked_multiline_height_limit_pt(bbox_height, font_size):
                    font_size = self.fit_locked_preserved_stack_font_size_to_bbox(
                        block,
                        max_font_pt=font_size,
                    )
                    visual_lines = estimate_preserved_stack_visual_lines(
                        block_text, bbox_width_lock, font_size,
                    )
                leading = fit_preserved_stack_leading_em(
                    font_size,
                    visual_lines,
                    bbox_height,
                    self.estimate_leading(font_size),
                )
                # Tighten font once more if min leading still overflows.
                if preserved_stack_render_height_pt(
                    font_size, visual_lines, leading,
                ) > bbox_height + 0.5:
                    font_size = self.fit_locked_preserved_stack_font_size_to_bbox(
                        block,
                        max_font_pt=font_size,
                    )
                    visual_lines = estimate_preserved_stack_visual_lines(
                        block_text, bbox_width_lock, font_size,
                    )
                    leading = fit_preserved_stack_leading_em(
                        font_size,
                        visual_lines,
                        bbox_height,
                        self.estimate_leading(font_size),
                    )
                leading = round(max(BODY_LEADING_EM_MIN, leading), 2)
                leading_locked = True
            else:
                # Multi-line + real font size: derive leading from bbox height.
                # Fallback: extracted size often reflects only the first glyph.
                # If content still overflows the bbox by more than 10% of the
                # font size even at minimum leading, refit the font downward.
                content_h = estimate_body_content_height_pt(
                    block_text,
                    bbox_width_lock,
                    font_size,
                    BODY_LEADING_EM_MIN,
                    layout_raw,
                )
                if content_h > locked_multiline_height_limit_pt(bbox_height, font_size):
                    font_size = self.fit_locked_body_font_size_to_bbox(
                        block,
                        layout_raw=layout_raw,
                        max_font_pt=font_size,
                    )
                leading = self.estimate_body_leading_em_at_font(
                    block, font_size, layout_raw=layout_raw,
                )
                leading_locked = True

            # Single-line locked text: extend horizontally — never auto-wrap.
            target_w = 0.0
            if short_single_line and not preserve_breaks:
                extend_w = plan_body_single_line_extension_pt(
                    block_text,
                    block.inner_bbox,
                    font_size,
                    leading,
                    page_width_pt,
                )
                if extend_w and extend_w > 0:
                    target_w = float(extend_w)
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading,
                    "leading_em_locked": leading_locked,
                    "preserve_line_breaks": bool(
                        preserve_breaks
                        or block.preserve_line_breaks
                    ),
                    "fit_to_box": False,
                    "fit_single_line": bool(short_single_line and not preserve_breaks),
                    "fit_target_width_pt": target_w,
                    "fit_min_font_size_pt": font_size,
                    "fit_max_font_size_pt": font_size,
                    "fit_min_leading_em": leading,
                    "fit_max_height_pt": max(1.0, bbox_height),
                    "font_size_locked": True,
                }
            )
        elif not preserve_font_size and (
            font_size <= 0
            or font_size == DEFAULT_FONT_SIZE_PT
            or _is_underfilled_tall_bbox(block, layout_raw, max(font_size, 0.0))
        ):
            font_size = self.estimate_font_size(
                block, layout_raw=layout_raw, inner_bbox_shrunk=True,
            )

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
            if preserve_breaks and count_embedded_newlines(
                block_text, newline_raw,
            ) > 0:
                _, leading = self.estimate_preserved_stack_metrics(
                    block, layout_raw=layout_raw, inner_bbox_shrunk=True,
                )
            else:
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
                    "fit_max_height_pt": max(1.0, bbox_height),
                }
            )

        if is_title:
            title_leading = (
                leading if leading > 0 and leading != DEFAULT_LEADING_EM
                else TITLE_LEADING_EM
            )
            return self._fit_title_or_header_block(
                block,
                block_text=block_text,
                font_size=font_size,
                leading_em=title_leading,
                bbox_height=bbox_height,
                page_width_pt=page_width_pt,
            )

        if is_page_header:
            header_leading = self.estimate_leading(font_size)
            return self._fit_title_or_header_block(
                block,
                block_text=block_text,
                font_size=font_size,
                leading_em=header_leading,
                bbox_height=bbox_height,
                page_width_pt=page_width_pt,
                always_single_line_measure=True,
            )

        bbox_width = max(1.0, x1 - block.inner_bbox[0])
        text = block.plain_text or block.markdown_text or ""
        typo_units = estimate_typographic_units(text, layout_raw)
        has_math = block_needs_math_fit(text, layout_raw)
        # Font-aware: extracted sizes often produce single-line bboxes > 32pt.
        short_single_line = is_single_line_at_font(
            bbox_height,
            font_size,
            leading_em=leading,
            layout_raw=layout_raw,
        )
        visual_lines = line_count_for_vertical_edge_margin(
            bbox_height,
            layout_raw,
            block_text,
            font_size_pt=font_size,
            bbox_width_pt=bbox_width,
        )
        wrap_ratio = estimate_wrap_ratio(
            text, bbox_width, font_size, layout_raw,
        )
        text_width_at_font = wrap_ratio * bbox_width
        width_overflow = text_width_at_font > bbox_width * 0.95
        will_wrap = (
            wrap_ratio > 1.05
            or width_overflow
            or (short_single_line and visual_lines >= 2.0)
        )
        # Soft body OCR ``\\n`` must not force preserve_line_breaks (layout_raw
        # may still carry newlines after plain_text was collapsed).
        has_embedded_breaks = (
            preserve_breaks
            and count_embedded_newlines(text, newline_raw) > 0
        )
        height_overflow = (
            short_single_line
            and font_size * leading > bbox_height * SHORT_BBOX_HEIGHT_OVERFLOW_RATIO
            and (is_ref_text or wrap_ratio >= 0.35)
        )
        # Multi-line body: enable Typst fit when CJK/Latin wrap needs it.
        # Latin-only 0.52em used to miss dense CJK and leave fit_to_box=False.
        content_height_est = max(1.0, wrap_ratio) * font_size * max(leading, 0.8)
        multi_line_needs_fit = (
            not short_single_line
            and typo_units > 0
            and (
                content_height_est > bbox_height * 0.92
                or wrap_ratio > 1.05
            )
        )

        # Single-line body: extend horizontally (no auto-wrap). Manual ``\\n``
        # via preserve_line_breaks is the only way to force a line break.
        if short_single_line and not has_embedded_breaks:
            extend_width = plan_body_single_line_extension_pt(
                text,
                block.inner_bbox,
                font_size,
                leading,
                page_width_pt,
            )
            if extend_width and extend_width > bbox_width + 0.5:
                return RenderBlock(
                    **{
                        **block.__dict__,
                        "font_size_pt": font_size,
                        "leading_em": leading,
                        "fit_to_box": True,
                        "fit_single_line": True,
                        "fit_target_width_pt": extend_width,
                        "fit_min_font_size_pt": font_size,
                        "fit_max_font_size_pt": font_size,
                        "fit_min_leading_em": max(0.8, leading * 0.7),
                        "fit_max_height_pt": max(1.0, bbox_height),
                    }
                )
            if will_wrap or width_overflow or has_math or height_overflow:
                # No room to extend (or math): shrink on one line — still no wrap.
                return RenderBlock(
                    **{
                        **block.__dict__,
                        "font_size_pt": font_size,
                        "leading_em": leading,
                        "fit_to_box": True,
                        "fit_single_line": True,
                        "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.5),
                        "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.2),
                        "fit_min_leading_em": max(0.8, leading * 0.7),
                        "fit_max_height_pt": max(1.0, bbox_height),
                    }
                )
            # Fits width already: still mark single-line so emitter never soft-wraps.
            # Keep ref_text / math on the single-line fit path when needed.
            needs_single_fit = bool(
                has_math
                or height_overflow
                or (is_ref_text and short_single_line)
            )
            return RenderBlock(
                **{
                    **block.__dict__,
                    "font_size_pt": font_size,
                    "leading_em": leading,
                    "fit_to_box": needs_single_fit,
                    "fit_single_line": True,
                    "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.5),
                    "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.2),
                    "fit_min_leading_em": max(0.8, leading * 0.7),
                    "fit_max_height_pt": max(1.0, bbox_height),
                }
            )

        needs_fit = typo_units > 0 and (
            text_width_at_font > bbox_width * 1.2
            or has_math
            or height_overflow
            or (is_ref_text and short_single_line)
            or multi_line_needs_fit
        )
        fit_single_line = False

        render_kind = block.render_kind
        preserve_line_breaks = bool(block.preserve_line_breaks) or has_embedded_breaks
        if preserve_line_breaks and render_kind in ("plain", "plain_line"):
            render_kind = "markdown"

        return RenderBlock(
            **{
                **block.__dict__,
                "font_size_pt": font_size,
                "leading_em": leading,
                "render_kind": render_kind,
                "preserve_line_breaks": preserve_line_breaks,
                "fit_to_box": needs_fit,
                "fit_single_line": fit_single_line,
                "fit_min_font_size_pt": max(self.min_size_pt, font_size * 0.5),
                "fit_max_font_size_pt": min(self.max_size_pt, font_size * 1.2),
                "fit_min_leading_em": max(0.8, leading * 0.7),
                "fit_max_height_pt": max(1.0, bbox_height),
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
