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


def test_right_text_is_unsafe():
    body = r"\left\lfloor a \right\text{ceil}"
    assert mitex_unsafe_reason(body) == "invalid_right_delimiter"


def test_markdown_line_with_right_text_is_unsafe():
    from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
        markdown_line_safe_for_mitex,
    )

    line = r"4 | $\left\lfloor c_{n}^{t+1} \right\text{ceil} \leftarrow a;$"
    assert not markdown_line_safe_for_mitex(line)


def test_markdown_line_with_simple_math_is_safe():
    from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
        markdown_line_safe_for_mitex,
    )

    line = "输入：全局轮次 $T$，本地轮次 $R$。"
    assert markdown_line_safe_for_mitex(line)
