# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for mitex math safety heuristics."""

from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
    is_mitex_safe_latex,
    mitex_unsafe_reason,
    strip_math_delimiters,
)


def test_strip_math_delimiters_inline_and_display():
    assert strip_math_delimiters("$x$") == "x"
    assert strip_math_delimiters("$$x = 1$$") == "x = 1"


def test_begin_array_is_unsafe():
    body = r"\begin{array}{r l} a & b \end{array}"
    assert mitex_unsafe_reason(body) == "latex_environment"
    assert not is_mitex_safe_latex(body)


def test_simple_clinical_loss_is_safe():
    body = r"\mathcal{L}_{cls}=\ell(\hat{h}(\hat{g}(\pmb{x}^{o})), y)"
    assert mitex_unsafe_reason(body) is None
    assert is_mitex_safe_latex(body)


def test_unbalanced_braces_is_unsafe():
    body = r"\frac{a}{b"
    assert mitex_unsafe_reason(body) == "unbalanced_braces"


def test_unbalanced_left_right_is_unsafe():
    body = r"\left\| x \right\| y \left("
    assert mitex_unsafe_reason(body) == "unbalanced_left_right"


def test_tag_is_unsafe():
    body = r"x = 1\tag{10}"
    assert mitex_unsafe_reason(body) == "latex_tag"
