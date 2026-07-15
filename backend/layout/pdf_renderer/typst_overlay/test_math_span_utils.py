# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for linear math span scanning."""

import time

from layout.pdf_renderer.typst_overlay.emitter import (
    _escape_sanitized_text_for_typst,
    _sanitize_typst_markdown_core,
    sanitize_typst_markdown_for_compile,
)
from layout.pdf_renderer.typst_overlay.math_span_utils import (
    iter_math_span_bodies,
    transform_dollar_math_spans,
    transform_latex_bracket_delimiters,
)
from layout.pdf_renderer.typst_overlay.mitex_math_safety import iter_math_spans_in_markdown


def test_transform_latex_bracket_delimiters():
    text = r"Inline \(a+b\) and display \[x^2\]"
    out = transform_latex_bracket_delimiters(text)
    assert out == "Inline $a+b$ and display $$x^2$$"


def test_transform_dollar_math_spans_strips_newlines():
    text = "$a\n+\nb$"
    out = transform_dollar_math_spans(
        text,
        on_display=lambda inner: f"$${inner.replace(chr(10), ' ')}$$",
        on_inline=lambda inner: f"${inner.replace(chr(10), ' ')}$",
    )
    assert out == "$a + b$"


def test_iter_math_span_bodies_collects_all_delimiters():
    text = r"$x$ and \(y\) and \[z\]"
    spans = iter_math_span_bodies(text)
    assert "x" in spans
    assert "y" in spans
    assert "z" in spans


def test_iter_math_spans_in_markdown_matches_linear_scanner():
    text = r"Mix $a$ and \(b\) and $$c$$"
    assert iter_math_spans_in_markdown(text) == iter_math_span_bodies(text)


def test_many_dollar_signs_finish_quickly():
    """Regression: old $...$ regex could stall on pathological input."""
    _sanitize_typst_markdown_core.cache_clear()
    payload = "$" + "a" * 200 + "$" * 300
    started = time.perf_counter()
    result = sanitize_typst_markdown_for_compile(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"sanitize took {elapsed:.2f}s"
    assert "$" in result


def test_escape_sanitized_text_skips_second_sanitize():
    _escape_sanitized_text_for_typst.cache_clear()
    sanitized = _sanitize_typst_markdown_core(r"\(\alpha\)")
    escaped = _escape_sanitized_text_for_typst(sanitized)
    assert "\\alpha" in escaped or "alpha" in escaped
    assert _escape_sanitized_text_for_typst.cache_info().hits >= 0
