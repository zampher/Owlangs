# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typographic measurement helpers for Typst overlay font fitting.

Mixed text + inline_equation blocks need width/line estimates that treat
math tokens as wider than their raw character count.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, List, Optional, Tuple

_INLINE_DOLLAR_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
_INLINE_PAREN_MATH_RE = re.compile(r"\\\((.+?)\\\)")
_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)

# Inline math tokens render wider than plain Latin letters of the same length.
INLINE_MATH_WIDTH_FACTOR = 1.85
INLINE_MATH_MIN_UNITS = 4.0
DISPLAY_MATH_LINE_UNITS = 6.0

# Single-line paragraph bbox height threshold (pt) for MinerU body text (~10-11pt font).
SINGLE_LINE_BBOX_HEIGHT_PT = 32.0

# Typical body-text line height used to infer visual line count from bbox height.
TYPICAL_BODY_LINE_HEIGHT_PT = 14.0


def text_contains_math(text: str) -> bool:
    """Return True when text includes inline or display math delimiters."""
    if not text:
        return False
    if "$" in text:
        return True
    if "\\(" in text or "\\[" in text:
        return True
    return False


def iter_inline_equation_span_contents(raw: Any) -> Iterator[str]:
    """Yield non-empty inline_equation span content strings from MinerU raw block."""
    if not isinstance(raw, dict):
        return
    for line in raw.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans") or []:
            if not isinstance(span, dict):
                continue
            if span.get("type") != "inline_equation":
                continue
            content = span.get("content")
            if isinstance(content, str) and content.strip():
                yield content.strip()


def layout_raw_has_inline_equation(raw: Any) -> bool:
    """Return True when MinerU raw block lines contain inline_equation spans."""
    for _ in iter_inline_equation_span_contents(raw):
        return True
    return False


def count_non_cross_page_lines(raw: Any) -> int:
    """Count layout lines that are not marked cross_page on any span."""
    if not isinstance(raw, dict):
        return 0
    count = 0
    for line in raw.get("lines") or []:
        if not isinstance(line, dict):
            continue
        spans = line.get("spans") or []
        if any(isinstance(s, dict) and s.get("cross_page") for s in spans):
            continue
        count += 1
    return count


def estimate_visual_line_count(bbox_height_pt: float, layout_raw: Any = None) -> float:
    """
    Estimate how many visual lines fit in the block bbox.

    MinerU often stores a wrapped paragraph as a single logical ``lines[]`` entry,
    so line count from raw is unreliable; bbox height is the primary signal.
    """
    if bbox_height_pt <= 0:
        return 1.0
    if bbox_height_pt <= SINGLE_LINE_BBOX_HEIGHT_PT:
        return 1.0
    from_height = max(1.0, bbox_height_pt / TYPICAL_BODY_LINE_HEIGHT_PT)
    from_raw = float(count_non_cross_page_lines(layout_raw)) if layout_raw else 1.0
    # Never trust raw line count alone when bbox is tall (whole paragraph as one line).
    if bbox_height_pt > SINGLE_LINE_BBOX_HEIGHT_PT:
        return max(from_height, from_raw if from_raw > 1 else from_height)
    return max(from_height, from_raw)


def block_needs_math_fit(text: str, layout_raw: Any = None) -> bool:
    """Whether Typst fit-to-box should be forced for this block."""
    return text_contains_math(text) or layout_raw_has_inline_equation(layout_raw)


def is_single_line_bbox(bbox_height_pt: float, layout_raw: Any = None) -> bool:
    """
    Heuristic: one visual line in the given bbox.

    MinerU may attach an entire multi-line paragraph to one ``lines[]`` item with a
    tall bbox; height must gate single-line mode, not ``lines`` length alone.
    """
    if bbox_height_pt <= 0:
        return False
    return bbox_height_pt <= SINGLE_LINE_BBOX_HEIGHT_PT


def _units_from_delimited_math(text: str) -> Tuple[float, int]:
    """Return (typographic units, end cursor) from delimited math patterns in text."""
    units = 0.0
    cursor = 0
    for pattern in (_DISPLAY_MATH_RE, _INLINE_DOLLAR_MATH_RE, _INLINE_PAREN_MATH_RE):
        for match in pattern.finditer(text):
            if match.start() >= cursor:
                units += float(len(text[cursor:match.start()]))
            body = match.group(1) if match.lastindex else match.group(0)
            if pattern is _DISPLAY_MATH_RE:
                units += max(len(body) * INLINE_MATH_WIDTH_FACTOR, DISPLAY_MATH_LINE_UNITS)
            else:
                units += max(len(body) * INLINE_MATH_WIDTH_FACTOR, INLINE_MATH_MIN_UNITS)
            cursor = max(cursor, match.end())
    units += float(len(text[cursor:]))
    return units, cursor


def _inline_span_bonus_units(text: str, layout_raw: Any) -> float:
    """
    Extra width units for inline_equation spans from layout raw.

    Covers citation-style spans like ``[61]`` that appear as plain text in
    translation without ``$...$`` delimiters.
    """
    bonus = 0.0
    for content in iter_inline_equation_span_contents(layout_raw):
        delimited_forms = (
            f"${content}$",
            f"\\({content}\\)",
            f"$ {content} $",
        )
        if any(form in text for form in delimited_forms):
            continue
        # Plain citation or undelimited formula in running text.
        bonus += max(INLINE_MATH_MIN_UNITS, len(content) * 0.6)
    return bonus


def estimate_typographic_units(text: str, layout_raw: Any = None) -> float:
    """
    Estimate horizontal typographic units for font/line fitting.

    Plain characters count as 1. Delimited math and layout inline_equation spans
    count heavier than their raw character length.
    """
    if not text:
        return 0.0

    units, _ = _units_from_delimited_math(text)
    if layout_raw:
        units += _inline_span_bonus_units(text, layout_raw)

    return max(units, float(len(text)))


def is_suspiciously_short_mapped_text(
    mapped_text: str,
    layout_original_text: str,
    *,
    min_ratio: float = 0.4,
) -> bool:
    """True when mapped translation is much shorter than layout source text."""
    original = (layout_original_text or "").strip()
    mapped = (mapped_text or "").strip()
    if not original or not mapped:
        return False
    if len(original) < 12:
        return False
    return len(mapped) < len(original) * min_ratio
