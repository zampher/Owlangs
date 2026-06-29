# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for $...$ / LaTeX math in Typst overlay emitter."""

from layout.pdf_renderer.typst_overlay.emitter import (
    _render_markdown_block,
    _render_table_block,
    _typst_plain_text_expr,
    sanitize_typst_markdown_for_compile,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def test_sanitize_normalizes_paren_math_delimiters():
    text = "Overall parameters are \\(W_{y}\\) and more."
    out = sanitize_typst_markdown_for_compile(text)
    assert "$W_{y}$" in out
    assert "\\(" not in out


def test_typst_plain_text_expr_uses_cmarker():
    expr = _typst_plain_text_expr(
        "myvar", 10.0, 1.2, "regular", "normal", "rgb(0, 0, 0)", 0.0, "false",
    )
    assert "cmarker.render(myvar, math: mitex)" in expr


def test_render_markdown_block_wraps_bare_equation_in_display_math():
    block = RenderBlock(
        block_id="eq-bare",
        page_index=0,
        inner_bbox=(10.0, 20.0, 200.0, 120.0),
        markdown_text="$$x = 1$$",
        font_size_pt=10.0,
        render_kind="markdown",
        opaque_fill=True,
    )
    src = _render_markdown_block("block-eq", block)
    assert "cmarker.render(" in src
    assert "x = 1" in src


def test_render_table_block_inline_math_uses_cmarker_not_raw_content():
    block = RenderBlock(
        block_id="tbl-math",
        page_index=0,
        inner_bbox=(10.0, 20.0, 200.0, 120.0),
        markdown_text=(
            "| Reagent | Amount |\n"
            "| --- | --- |\n"
            "| EDC $\\cdot$ HCl | 2.0 g |"
        ),
        font_size_pt=10.0,
        render_kind="table",
        opaque_fill=True,
    )
    src = _render_table_block("block-tbl", block)
    assert "cmarker.render(" in src
    assert "cdot" in src
    # Raw Typst content injection (no cmarker) caused unknown variable: cdot
    assert "[EDC $" not in src
    assert "#let block_tbl_cell_" in src
