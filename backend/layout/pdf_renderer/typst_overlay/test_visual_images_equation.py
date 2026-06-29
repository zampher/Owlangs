# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for equation content normalization in Typst overlay rendering."""

from layout.pdf_renderer.typst_overlay.visual_images import (
    normalize_equation_content_for_typst,
)


def test_normalize_bare_latex_gets_display_delimiters():
    out = normalize_equation_content_for_typst("x = 1")
    assert out == "$$x = 1$$"


def test_normalize_multi_line_bare_latex_gets_display_delimiters():
    out = normalize_equation_content_for_typst("x = 1\ny = 2")
    assert out == "$$x = 1\ny = 2$$"


def test_normalize_preserves_double_dollar_delimiters():
    out = normalize_equation_content_for_typst("$$x = 1$$")
    assert out == "$$x = 1$$"


def test_normalize_preserves_single_dollar_delimiters():
    out = normalize_equation_content_for_typst("$x = 1$")
    assert out == "$x = 1$"


def test_normalize_preserves_bracket_delimiters():
    out = normalize_equation_content_for_typst(r"\[x = 1\]")
    assert out == r"\[x = 1\]"


def test_normalize_preserves_paren_delimiters():
    out = normalize_equation_content_for_typst(r"\(x = 1\)")
    assert out == r"\(x = 1\)"


def test_normalize_returns_none_for_empty_or_none():
    assert normalize_equation_content_for_typst("") is None
    assert normalize_equation_content_for_typst(None) is None
    assert normalize_equation_content_for_typst("   ") is None


def test_normalize_strips_outer_whitespace():
    out = normalize_equation_content_for_typst("  x = 1  ")
    assert out == "$$x = 1$$"
