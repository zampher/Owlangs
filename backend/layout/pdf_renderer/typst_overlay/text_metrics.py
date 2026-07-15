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

# One visual line body height as em of font size (matches preserved-stack body em).
PREDICTED_LINE_BODY_EM = 1.0

# Multi-line bbox: top/bottom margin as this fraction of predicted single-line height.
BBOX_PER_LINE_EDGE_MARGIN_RATIO = 0.10

# Cap per-edge vertical inset (pt) so large fonts do not reserve excessive margin.
BBOX_VERTICAL_EDGE_INSET_MAX_PT = 1.5

# Minimum inner height (pt) after shrinking; skip shrink when bbox would collapse.
BBOX_MIN_INNER_HEIGHT_AFTER_SHRINK_PT = 4.0


def predicted_line_height_pt(
    font_size_pt: Optional[float] = None,
    *,
    line_height_pt: Optional[float] = None,
    body_em: float = PREDICTED_LINE_BODY_EM,
) -> float:
    """Predicted single-line vertical extent (pt) for multi-line edge margins."""
    if line_height_pt is not None and line_height_pt > 0:
        return float(line_height_pt)
    if font_size_pt is not None and font_size_pt > 0:
        return float(font_size_pt) * body_em
    return TYPICAL_BODY_LINE_HEIGHT_PT


def bbox_vertical_edge_inset_pt(
    line_count: float,
    *,
    font_size_pt: Optional[float] = None,
    line_height_pt: Optional[float] = None,
) -> float:
    """
    Top/bottom inset (pt) before the first and after the last visual line.

    Single-line bboxes use the full height (no edge inset). Multi-line bboxes
    reserve 10% of the predicted line height at the top and bottom, capped at
    [BBOX_VERTICAL_EDGE_INSET_MAX_PT] per edge.
    """
    if line_count < 2.0:
        return 0.0
    line_h = predicted_line_height_pt(
        font_size_pt,
        line_height_pt=line_height_pt,
    )
    raw = line_h * BBOX_PER_LINE_EDGE_MARGIN_RATIO
    return min(raw, BBOX_VERTICAL_EDGE_INSET_MAX_PT)


def shrink_inner_bbox_vertical(
    bbox: Tuple[float, float, float, float],
    line_count: float,
    *,
    font_size_pt: Optional[float] = None,
    line_height_pt: Optional[float] = None,
) -> Tuple[float, float, float, float]:
    """Shrink bbox top/bottom by multi-line edge insets (method-1 layout margin)."""
    inset = bbox_vertical_edge_inset_pt(
        line_count,
        font_size_pt=font_size_pt,
        line_height_pt=line_height_pt,
    )
    if inset <= 0:
        return bbox
    x0, y0, x1, y1 = bbox
    new_y0 = y0 + inset
    new_y1 = y1 - inset
    if new_y1 - new_y0 < BBOX_MIN_INNER_HEIGHT_AFTER_SHRINK_PT:
        return bbox
    return (x0, new_y0, x1, new_y1)


def bbox_content_height_pt(
    bbox_height_pt: float,
    line_count: float = 1.0,
    *,
    font_size_pt: Optional[float] = None,
    line_height_pt: Optional[float] = None,
) -> float:
    """
    Usable vertical extent (pt) inside an outer OCR bbox before inner_bbox shrink.

    After shrink_render_block_inner_bbox_for_edge_margin, use the inner height
    directly (max(1.0, y1 - y0)) instead of calling this helper.
    """
    return outer_bbox_content_height_pt(
        bbox_height_pt,
        line_count,
        font_size_pt=font_size_pt,
        line_height_pt=line_height_pt,
    )


def outer_bbox_content_height_pt(
    bbox_height_pt: float,
    line_count: float,
    *,
    font_size_pt: Optional[float] = None,
    line_height_pt: Optional[float] = None,
) -> float:
    """Content height inside an outer OCR bbox before inner_bbox shrink (previews)."""
    if bbox_height_pt <= 0:
        return 1.0
    inset = bbox_vertical_edge_inset_pt(
        line_count,
        font_size_pt=font_size_pt,
        line_height_pt=line_height_pt,
    )
    if inset <= 0:
        return bbox_height_pt
    return max(1.0, bbox_height_pt - 2.0 * inset)


def line_count_for_vertical_edge_margin(
    bbox_height_pt: float,
    layout_raw: Any = None,
    text: str = "",
    *,
    font_size_pt: Optional[float] = None,
    bbox_width_pt: Optional[float] = None,
) -> float:
    """
    Conservative visual line count for shrinking inner_bbox.

    Avoids treating short single-line text as multi-line when only the default
    font size makes a tight bbox look tall; still honors OCR tall boxes (patent
    headers) and real width-wrap / embedded newlines.
    """
    if bbox_height_pt <= 0:
        return 1.0

    embedded_lines = float(count_visual_lines_from_content(text, layout_raw))
    if embedded_lines > 1.0:
        return max(
            embedded_lines,
            estimate_visual_line_count(
                bbox_height_pt, layout_raw, text=text, font_size_pt=font_size_pt,
            ),
        )

    # Width helpers are defined below; resolve at call time.
    wrap_ratio = 0.0
    if bbox_width_pt and bbox_width_pt > 0 and font_size_pt and font_size_pt > 0:
        wrap_ratio = estimate_wrap_ratio(
            text, bbox_width_pt, font_size_pt, layout_raw,
        )

    if wrap_ratio >= 1.05:
        return max(
            2.0,
            wrap_ratio,
            estimate_visual_line_count(
                bbox_height_pt, layout_raw, text=text, font_size_pt=font_size_pt,
            ),
        )

    height_lines_ref = estimate_visual_line_count(
        bbox_height_pt, layout_raw, text=text, font_size_pt=None,
    )
    if height_lines_ref >= 1.85:
        return max(2.0, height_lines_ref)

    if font_size_pt and font_size_pt > 0:
        height_lines_font = estimate_visual_line_count(
            bbox_height_pt, layout_raw, text=text, font_size_pt=font_size_pt,
        )
        if height_lines_font >= 2.0 and wrap_ratio >= 0.35:
            return max(2.0, height_lines_font)

    return 1.0


# Typical Latin / CJK character width-to-font-size ratios (font_fit parity).
LATIN_CHAR_WIDTH_RATIO = 0.52
CJK_CHAR_WIDTH_RATIO = 1.0


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


def _char_width_pt(ch: str, font_size_pt: float) -> float:
    if ch.isspace():
        return font_size_pt * 0.28
    if _is_cjk_char(ch):
        return font_size_pt * CJK_CHAR_WIDTH_RATIO
    return font_size_pt * LATIN_CHAR_WIDTH_RATIO


def estimate_text_width_pt(text: str, font_size_pt: float) -> float:
    """Estimate single-line text width in pt (CJK ≈ 1em, Latin ≈ 0.52em)."""
    if not text or font_size_pt <= 0:
        return 0.0
    return sum(_char_width_pt(ch, font_size_pt) for ch in text)


def estimate_wrap_ratio(
    text: str,
    bbox_width_pt: float,
    font_size_pt: float,
    layout_raw: Any = None,
) -> float:
    """
    Fractional width-wrap ratio at *font_size_pt* (may be < 1.0).

    Uses mixed CJK/Latin glyph widths (not Latin-only 0.52em). Math-heavy
    spans inflate width via typographic units when they exceed raw length.
    """
    if not text or bbox_width_pt <= 0 or font_size_pt <= 0:
        return 0.0
    width_pt = estimate_text_width_pt(text, font_size_pt)
    typo_units = estimate_typographic_units(text, layout_raw)
    raw_len = float(len(text))
    if raw_len > 0.0 and typo_units > raw_len:
        width_pt *= typo_units / raw_len
    return width_pt / bbox_width_pt


def estimate_wrap_line_count(
    text: str,
    bbox_width_pt: float,
    font_size_pt: float,
    layout_raw: Any = None,
) -> float:
    """Estimate layout line count from width wrap (at least 1.0)."""
    return max(1.0, estimate_wrap_ratio(
        text, bbox_width_pt, font_size_pt, layout_raw,
    ))


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


def count_embedded_newlines(text: str = "", layout_raw: Any = None) -> int:
    """Return the maximum number of ``\\n`` characters in text or MinerU spans."""
    max_newlines = 0
    if text:
        max_newlines = max(max_newlines, text.count("\n"))
    if isinstance(layout_raw, dict):
        for line in layout_raw.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                content = span.get("content")
                if isinstance(content, str):
                    max_newlines = max(max_newlines, content.count("\n"))
    return max_newlines


# Patent / structured field markers that should keep soft newlines as stack lines.
_STRUCTURED_FIELD_LINE_RE = re.compile(
    r"^\(\d{1,2}\)\s|"
    r"\bU\.?\s*S\.?\s*Cl\b|"
    r"\bUSPC\b|"
    r"References Cited|"
    r"Field of Classification|"
    r"United States Patent|"
    r"Patent Documents|"
    r"See application file",
    re.IGNORECASE,
)


def newline_bearing_text(text: str = "", layout_raw: Any = None) -> str:
    """
    Text that carries embedded newlines for preserve/soft heuristics.

    Prefer the translated/plain text when it contains ``\\n``; otherwise use the
    first MinerU span content that still embeds newlines (OCR soft breaks).
    """
    if text and "\n" in text:
        return text
    if isinstance(layout_raw, dict):
        for line in layout_raw.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                content = span.get("content")
                if isinstance(content, str) and "\n" in content:
                    return content
    return text or ""


def collapse_soft_embedded_newlines(text: str) -> str:
    """Turn soft body ``\\n`` into spaces so Typst can reflow as one paragraph."""
    if not text or "\n" not in text:
        return text
    collapsed = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    return re.sub(r" {2,}", " ", collapsed).strip()


def _looks_like_structured_field_line(line: str) -> bool:
    t = (line or "").strip()
    if not t:
        return False
    if _STRUCTURED_FIELD_LINE_RE.search(t):
        return True
    # Very short caption/label line (e.g. inventor surname under patent header).
    return len(t) <= 32


def should_preserve_embedded_newlines(
    text: str = "",
    layout_raw: Any = None,
    *,
    bbox_width_pt: float,
    font_size_pt: float,
) -> bool:
    """
    Whether embedded ``\\n`` should force preserved-stack layout.

    Patent field labels / short header stacks keep newlines. Soft OCR/body
    breaks inside wrapping paragraphs are collapsed so reflow + fit can fill
    tall boxes (otherwise fit_max is capped near the tiny stack font).
    """
    if count_embedded_newlines(text, layout_raw) <= 0:
        return False

    bearing = newline_bearing_text(text, layout_raw)
    parts = [p.strip() for p in bearing.split("\n") if p.strip()]
    if len(parts) <= 1:
        return False

    probe = max(6.0, float(font_size_pt) if font_size_pt > 0 else 10.0)
    width = max(1.0, float(bbox_width_pt))
    short_count = 0
    wrapping_units = 0.0
    total_units = 0.0
    label_like = 0
    for part in parts:
        if _looks_like_structured_field_line(part):
            label_like += 1
        units = estimate_typographic_units(part, None)
        total_units += units
        if estimate_wrap_ratio(part, width, probe, None) <= 1.05:
            short_count += 1
        else:
            wrapping_units += units

    # Keep patent / form-style stacks.
    if label_like >= 1:
        return True
    # Soft body paragraphs: every logical line already wraps as running text.
    if short_count == 0:
        return False
    # Soft break before a short trailer ("See also.") after a wrapping body.
    if total_units > 0 and wrapping_units / total_units >= 0.55:
        return False
    return short_count >= 1


def resolve_embedded_newline_policy(
    text: str = "",
    layout_raw: Any = None,
    *,
    bbox_width_pt: float,
    font_size_pt: float,
) -> Tuple[str, bool]:
    """
    Resolve soft vs preserved newlines for font fit.

    Returns ``(text_for_fit, preserve_line_breaks)``. Soft body newlines are
    collapsed in the returned text; layout_raw may still contain OCR ``\\n``.
    """
    if count_embedded_newlines(text, layout_raw) <= 0:
        return text, False
    if should_preserve_embedded_newlines(
        text,
        layout_raw,
        bbox_width_pt=bbox_width_pt,
        font_size_pt=font_size_pt,
    ):
        return text, True
    return collapse_soft_embedded_newlines(text), False


def count_visual_lines_from_content(text: str = "", layout_raw: Any = None) -> int:
    """Visual line count implied by embedded newlines (0 newlines → 1 line)."""
    newline_count = count_embedded_newlines(text, layout_raw)
    if newline_count <= 0:
        return 1
    return newline_count + 1


def estimate_visual_line_count(
    bbox_height_pt: float,
    layout_raw: Any = None,
    text: str = "",
    *,
    font_size_pt: Optional[float] = None,
) -> float:
    """
    Estimate how many visual lines fit in the block bbox.

    MinerU often stores a wrapped paragraph as a single logical ``lines[]`` entry,
    so line count from raw is unreliable; bbox height is the primary signal.
    Embedded ``\\n`` in span content (e.g. patent headers) also signals multiple lines
    even when ``lines[]`` has only one entry and bbox height is ≤ 32pt.
    """
    if bbox_height_pt <= 0:
        return 1.0

    line_h = predicted_line_height_pt(font_size_pt)
    from_height = max(1.0, bbox_height_pt / line_h)
    from_raw = float(count_non_cross_page_lines(layout_raw)) if layout_raw else 1.0
    embedded_lines = float(count_visual_lines_from_content(text, layout_raw))

    if bbox_height_pt <= SINGLE_LINE_BBOX_HEIGHT_PT:
        if embedded_lines > 1.0:
            return max(embedded_lines, from_height)
        # Compact two-line fields: use font-aware line height (not fixed 14pt).
        if from_height >= 1.85:
            return max(2.0, from_height, from_raw if from_raw > 1.0 else from_height)
        return 1.0

    lines = max(from_height, from_raw if from_raw > 1.0 else from_height)
    if embedded_lines > 1.0:
        lines = max(lines, embedded_lines)
    return lines


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


_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?")


def latex_math_visible_length(body: str) -> float:
    """
    Approximate visible glyph count from LaTeX math source.

    Command names (``\\mathbf``, ``\\left``, …) and structural braces inflate
    raw length without matching painted width; strip them before width fit.
    """
    s = body or ""
    s = _LATEX_CMD_RE.sub("", s)
    # Escaped single chars: \{ \} \, \; etc.
    s = re.sub(r"\\.", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("^", "").replace("_", "")
    s = re.sub(r"\s+", "", s)
    return float(len(s))


def _math_body_typographic_units(body: str, *, display: bool) -> float:
    """Width units for a delimited math body (LaTeX-aware)."""
    raw = float(len(body or ""))
    visible = latex_math_visible_length(body)
    # Keep short tokens (W_{y}) heavier than plain letters; cap command bloat.
    effective = max(visible, min(raw, visible * 1.5 + 2.0))
    floor = DISPLAY_MATH_LINE_UNITS if display else INLINE_MATH_MIN_UNITS
    return max(effective * INLINE_MATH_WIDTH_FACTOR, floor)


def _units_from_delimited_math(text: str) -> Tuple[float, int]:
    """Return (typographic units, end cursor) from delimited math patterns in text."""
    units = 0.0
    cursor = 0
    for pattern in (_DISPLAY_MATH_RE, _INLINE_DOLLAR_MATH_RE, _INLINE_PAREN_MATH_RE):
        for match in pattern.finditer(text):
            if match.start() >= cursor:
                units += float(len(text[cursor:match.start()]))
            body = match.group(1) if match.lastindex else match.group(0)
            units += _math_body_typographic_units(
                body, display=pattern is _DISPLAY_MATH_RE,
            )
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
