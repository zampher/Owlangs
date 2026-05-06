# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for markdown display-math counting vs layout equation alignment (DOCX export).

Run from Owlangs: pytest backend/test_md2docx_display_math_count.py -q
(md2docx_exporter imports `exporter` / `logger` as top-level names from backend/.)
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.exporter.md.md2docx_exporter import MD2DOCXExporter, MD2DOCXExporterConfig
from utils.math_md_normalize import (
    extract_display_math_inner_from_tex_fence_body,
    parse_opening_markdown_fence_language,
)


def test_sanitize_fixes_sum_subscript_spacing():
    raw = r"\sum_ {t=0}^{T_R} x + \left ( y \right )"
    out = MD2DOCXExporter._sanitize_latex_for_latex2mathml(raw)
    assert "_ {" not in out
    assert r"\sum_{t=0}" in out
    assert "\\left(" in out


def test_sanitize_merges_spaced_symbols_in_mathbf():
    """Repair/OCR often emits \\mathbf{C R}; latex2mathml rejects it (ExtraLeftOrMissingRightError)."""
    raw = r"\mathbf{C R}_d \left[ R_d, C_d \right]"
    out = MD2DOCXExporter._sanitize_latex_for_latex2mathml(raw)
    assert r"\mathbf{CR}_d" in out
    assert "C R" not in out


def test_sanitize_merges_spaced_text_word():
    raw = r"\text { w h e r e } \mathbf{A} = x"
    out = MD2DOCXExporter._sanitize_latex_for_latex2mathml(raw)
    assert r"\text{where}" in out


def test_display_math_inner_from_tex_fence_body():
    """Fenced ```tex blocks must unwrap $$...$$ so DOCX uses OMML, not code font."""
    body = (
        r"$$"
        "\n"
        r"r \sum_{t=0}^{T_R} \left(P_{c, t} + L_t\right) \leq "
        r"\sum_{t=0}^{T_R} R_{0, t}, t \in T_R, T_R \in T_C \tag {23}"
        "\n"
        r"$$"
    )
    inner = extract_display_math_inner_from_tex_fence_body(body)
    assert inner is not None
    assert r"\sum_{t=0}" in inner
    assert r"\tag {23}" in inner or r"\tag{23}" in inner


def test_fence_body_rejects_multiple_formula_pairs():
    bad = "$$\na\n$$\n$$\nb\n$$"
    assert extract_display_math_inner_from_tex_fence_body(bad) is None


def test_parse_opening_fence_language():
    assert parse_opening_markdown_fence_language("```tex") == "tex"
    assert parse_opening_markdown_fence_language("``` latex") == "latex"
    assert parse_opening_markdown_fence_language("```") == ""


def test_normalize_formula_strips_tag_space_before_brace():
    """Repairs often emit \\tag {n}; must strip before latex2mathml (same as block formulas)."""
    exp = MD2DOCXExporter(config=MD2DOCXExporterConfig())
    raw = (
        r"r \sum_{t=0}^{T_R} \left(P_{c, t} + L_t\right) \leq "
        r"\sum_{t=0}^{T_R} R_{0, t}, t \in T_R, T_R \in T_C \tag {23}"
    )
    clean, tag = exp._normalize_formula_latex(raw)
    assert tag == "23"
    assert "\\tag" not in clean


def test_paragraph_needs_tex_processing():
    assert MD2DOCXExporter._paragraph_needs_tex_processing(r"\[x\]") is True
    assert MD2DOCXExporter._paragraph_needs_tex_processing(r"\(y\)") is True
    assert MD2DOCXExporter._paragraph_needs_tex_processing("plain") is False
    assert MD2DOCXExporter._paragraph_needs_tex_processing(r"\begin{aligned}") is True


def test_count_single_line_blocks():
    lines = ["intro", "$$a$$", "$$b$$", ""]
    assert MD2DOCXExporter._count_markdown_display_math_blocks(lines) == 2


def test_count_multiline_block_once():
    lines = ["$$", r"\alpha", r"\beta", "$$", "after"]
    assert MD2DOCXExporter._count_markdown_display_math_blocks(lines) == 1


def test_count_multiline_two_blocks():
    lines = ["$$", "x", "$$", "$$", "y", "$$"]
    assert MD2DOCXExporter._count_markdown_display_math_blocks(lines) == 2
