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


def test_sanitize_strips_newlines_inside_inline_math():
    text = "Cell value $R_{m}\nC_{d}$ end"
    out = sanitize_typst_markdown_for_compile(text)
    assert "\n" not in out.split("$")[1]
    assert "R_{m}" in out and "C_{d}" in out


def test_sanitize_strips_literal_backslash_n_inside_inline_math():
    text = r"Cell value $R_{m}\nC_{d}$ end"
    out = sanitize_typst_markdown_for_compile(text)
    inner = out.split("$")[1]
    assert r"\n" not in inner
    assert "R_{m}" in out and "C_{d}" in out


def test_sanitize_glued_ndiff_inside_math_becomes_text_not_variable():
    """Regression: LLM \\ndiff in math must not become mitex unknown variable: diff."""
    text = r"Profit $P_{t}\ndiff$ here"
    out = sanitize_typst_markdown_for_compile(text)
    inner = out.split("$")[1]
    assert r"\ndiff" not in inner
    assert r"\text{diff}" in inner
    assert "P_{t}" in inner


def test_sanitize_glued_ndiff_outside_math_becomes_plain_word():
    text = r"Compare results\ndiff across cases"
    out = sanitize_typst_markdown_for_compile(text)
    assert r"\ndiff" not in out
    assert " diff " in out or out.endswith(" diff across cases")


def test_sanitize_preserves_nu_and_nabla_after_backslash_n():
    text = r"$a=\nu+\nabla f$"
    out = sanitize_typst_markdown_for_compile(text)
    assert r"\nu" in out
    assert r"\nabla" in out


def test_sanitize_diff_command_maps_to_mathrm_d():
    text = r"$\diff x$"
    out = sanitize_typst_markdown_for_compile(text)
    assert r"\mathrm{d}" in out
    assert r"\diff" not in out


def test_render_table_block_cell_with_literal_backslash_n_not_wrapped_as_math():
    """Regression: LLM \\n in table cell must not become $...$ math for mitex."""
    block = RenderBlock(
        block_id="tbl-literal-n",
        page_index=0,
        inner_bbox=(10.0, 20.0, 200.0, 120.0),
        markdown_text=(
            "| Reagent | Amount |\n"
            "| --- | --- |\n"
            r"| PVA | 2.28 克\n(=1,838 克聚乙烯醇) |"
        ),
        font_size_pt=10.0,
        render_kind="table",
        opaque_fill=True,
    )
    src = _render_table_block("block-tbl-n", block)
    assert r"$\n$" not in src
    assert "2.28 克" in src
    assert "cmarker.render(" in src


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
