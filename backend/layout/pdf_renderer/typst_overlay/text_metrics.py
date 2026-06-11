# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typographic measurement helpers for Typst overlay font fitting.

Mixed text + inline_equation blocks need width/line estimates that treat
math tokens as wider than their raw character count.
"""

from __future__ import annotations

import re
from typing import Any, Optional

_INLINE_DOLLAR_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
_INLINE_PAREN_MATH_RE = re.compile(r"\\\((.+?)\\\)")
_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)

# Inline math tokens render wider than plain Latin letters of the same length.
INLINE_MATH_WIDTH_FACTOR = 1.85
INLINE_MATH_MIN_UNITS = 4.0
DISPLAY_MATH_LINE_UNITS = 6.0

# Single-line paragraph bbox height threshold (pt) for MinerU body text.
SINGLE_LINE_BBOX_HEIGHT_PT = 28.0


def text_contains_math(text: str) -> bool:
    """Return True when text includes inline or display math delimiters."""
    if not text:
        return False
    if "$" in text:
        return True
    if "\\(" in text or "\\[" in text:
        return True
    return False


def layout_raw_has_inline_equation(raw: Any) -> bool:
    """Return True when MinerU raw block lines contain inline_equation spans."""
    if not isinstance(raw, dict):
        return False
    for line in raw.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans") or []:
            if isinstance(span, dict) and span.get("type") == "inline_equation":
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


def block_needs_math_fit(text: str, layout_raw: Any = None) -> bool:
    """Whether Typst fit-to-box should be forced for this block."""
    return text_contains_math(text) or layout_raw_has_inline_equation(layout_raw)


def is_single_line_bbox(bbox_height_pt: float, layout_raw: Any = None) -> bool:
    """Heuristic: one visual line in the given bbox / layout lines."""
    if bbox_height_pt > 0 and bbox_height_pt <= SINGLE_LINE_BBOX_HEIGHT_PT:
        return True
    line_count = count_non_cross_page_lines(layout_raw)
    return line_count == 1


def estimate_typographic_units(text: str) -> float:
    """
    Estimate horizontal typographic units for font/line fitting.

    Plain characters count as 1. Inline math segments count heavier.
    """
    if not text:
        return 0.0

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
            cursor = match.end()
    units += float(len(text[cursor:]))

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
