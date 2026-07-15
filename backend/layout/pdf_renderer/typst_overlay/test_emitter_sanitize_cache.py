# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for Typst emitter sanitize/prepare caches."""

from layout.pdf_renderer.typst_overlay.emitter import (
    _escape_typst_string,
    _prepare_table_cell_for_typst,
    _prepare_user_text_for_typst,
    _sanitize_typst_markdown_core,
    sanitize_typst_markdown_for_compile,
)


def test_sanitize_typst_markdown_core_is_cached():
    _sanitize_typst_markdown_core.cache_clear()
    text = "Hello $x^2$ world"
    first = _sanitize_typst_markdown_core(text)
    second = _sanitize_typst_markdown_core(text)
    assert first == second
    info = _sanitize_typst_markdown_core.cache_info()
    assert info.hits >= 1


def test_prepare_user_text_for_typst_escapes_and_caches():
    _prepare_user_text_for_typst.cache_clear()
    text = 'Say "hi"\nline2'
    first = _prepare_user_text_for_typst(text)
    second = _prepare_user_text_for_typst(text)
    assert first == second
    assert '\\"' in first
    assert "\\n" in first


def test_prepare_table_cell_fast_path_skips_heavy_sanitize():
    _prepare_table_cell_for_typst.cache_clear()
    plain = "Dataset A"
    assert _prepare_table_cell_for_typst(plain) == _escape_typst_string(plain)


def test_sanitize_fast_path_for_plain_text():
    _sanitize_typst_markdown_core.cache_clear()
    plain = "Introduction to causal inference."
    assert _sanitize_typst_markdown_core(plain) == plain


def test_sanitize_typst_markdown_for_compile_matches_core():
    text = r"\(\alpha + \beta\)"
    assert sanitize_typst_markdown_for_compile(text) == _sanitize_typst_markdown_core(text)

