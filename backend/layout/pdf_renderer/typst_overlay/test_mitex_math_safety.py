# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for mitex math safety heuristics."""

from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
    is_mitex_safe_latex,
    mitex_unsafe_reason,
    should_fallback_mitex_equation_to_image,
    strip_math_delimiters,
)


def test_strip_math_delimiters_inline_and_display():
    assert strip_math_delimiters("$x$") == "x"
    assert strip_math_delimiters("$$x = 1$$") == "x = 1"


def test_begin_array_is_unsafe():
    body = r"\begin{array}{r l} a & b \end{array}"
    assert mitex_unsafe_reason(body) == "latex_environment"
    assert not is_mitex_safe_latex(body)


def test_align_star_falls_back_for_latex_and_text_formats():
    """equation_format=latex must not emit mitex for LaTeX environments."""
    body = (
        r"$$\begin{align*}m_{j}&=\max_{l\in\{1,\ldots,k\}}"
        r"\frac{\exp\big((\log z_{j}+\xi_{j}^{l})/\tau\big)}"
        r"{\sum_{j^{\prime}=1}^{N}"
        r"\exp\big((\log z_{j^{\prime}}+\xi_{j^{\prime}}^{l})/\tau\big)}"
        r"\end{align*}$$"
    )
    assert should_fallback_mitex_equation_to_image(
        body, equation_format="latex",
    ) == "latex_environment"
    assert should_fallback_mitex_equation_to_image(
        body, equation_format="text",
    ) == "latex_environment"
    assert should_fallback_mitex_equation_to_image(
        body, equation_format="image",
    ) is None


def test_safe_inline_equation_does_not_fallback_for_latex_format():
    body = r"$$\mathcal{L}_{cls}=\ell(\hat{h}(\hat{g}(x)), y)$$"
    assert should_fallback_mitex_equation_to_image(
        body, equation_format="latex",
    ) is None


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
    body = r"\left( a \right\text{ceil}"
    assert mitex_unsafe_reason(body) == "invalid_right_delimiter"


def test_left_floor_closed_with_right_dot_is_unsafe():
    """OCR/LLM often emits \\left\\lfloor ... \\right. which breaks mitex."""
    body = (
        r"\left\lfloor \theta_{n}^{t+1} \leftarrow "
        r"\theta_{n}^{t+1} - \eta \nabla \mathcal{L}; \right."
    )
    assert mitex_unsafe_reason(body) == "mismatched_floor_ceil"
    assert not is_mitex_safe_latex(body)


def test_matched_left_floor_right_rfloor_is_safe():
    body = r"\left\lfloor c_{n}^{t+1}, s_{n}^{t+1} \right\rfloor"
    assert mitex_unsafe_reason(body) is None


def test_markdown_algorithm_floor_dot_line_is_unsafe():
    from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
        markdown_line_safe_for_mitex,
    )

    line = (
        r"13 $\left\lfloor \theta_{n}^{t+1} \leftarrow "
        r"\theta_{n}^{t+1} - \eta \nabla \mathcal{L}; \right.$"
    )
    assert not markdown_line_safe_for_mitex(line)


def test_paren_delimiter_artifact_is_unsafe():
    body = r"E_{t} \)"
    assert mitex_unsafe_reason(body) == "paren_delimiter_artifact"
    assert not is_mitex_safe_latex(body)


def test_markdown_line_with_paren_delimited_math_is_checked():
    from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
        markdown_line_safe_for_mitex,
    )

    line = r"记为 \( R_{m} \) 和 \( R_{d} \)"
    assert markdown_line_safe_for_mitex(line)


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


def test_bare_not_is_unsafe():
    """Bare \\not breaks mitex 0.2.6 with missing argument: it."""
    assert mitex_unsafe_reason(r"\not") == "bare_not"
    assert not is_mitex_safe_latex(r"\not")


def test_not_perp_is_safe():
    assert mitex_unsafe_reason(r"\not\perp") is None
    assert is_mitex_safe_latex(r"\not\perp")


def test_markdown_split_not_perp_is_unsafe_before_sanitize():
    from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
        markdown_line_safe_for_mitex,
    )

    # Scanner may glue $\not$$\perp$ into one body containing $$; still unsafe.
    line = "对于碰撞结构，我们有X $\\not$$\\perp$ Z | Y。"
    assert not markdown_line_safe_for_mitex(line)
    assert mitex_unsafe_reason(r"\not$$\perp") == "embedded_dollar_delimiter"
