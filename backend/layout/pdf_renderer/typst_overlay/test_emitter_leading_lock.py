# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for user-locked leading with font-only fit in Typst emitter."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import (
    _block_markdown_fit_call,
    _render_markdown_block,
    build_typst_overlay_source,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock, RenderPageSpec


def test_block_markdown_fit_call_uses_fixed_leading_when_locked():
    block = RenderBlock(
        block_id="b-1",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 80.0),
        markdown_text="Sample paragraph text",
        font_size_pt=11.0,
        fit_min_font_size_pt=8.0,
        leading_em=1.45,
        fit_min_leading_em=1.45,
        leading_em_locked=True,
    )
    call = _block_markdown_fit_call(
        block,
        "md_var",
        fit_height_pt=72.0,
        font_style="normal",
        first_line_indent_pt=0.0,
        justify_text="false",
    )
    assert "pdftr_fit_markdown_fixed_leading" in call
    assert "leading: 1.45em" in call
    assert "pdftr_fit_markdown(" not in call


def test_block_markdown_fit_call_uses_auto_leading_when_unlocked():
    block = RenderBlock(
        block_id="b-2",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 80.0),
        markdown_text="Sample paragraph text",
        font_size_pt=11.0,
        fit_min_font_size_pt=8.0,
        leading_em=1.25,
        fit_min_leading_em=0.95,
        leading_em_locked=False,
    )
    call = _block_markdown_fit_call(
        block,
        "md_var",
        fit_height_pt=72.0,
        font_style="normal",
        first_line_indent_pt=0.0,
        justify_text="false",
    )
    assert "pdftr_fit_markdown(" in call
    assert "pdftr_fit_markdown_fixed_leading" not in call


def test_render_markdown_block_emits_fixed_leading_fit():
    block = RenderBlock(
        block_id="b-3",
        page_index=0,
        inner_bbox=(10.0, 20.0, 210.0, 120.0),
        markdown_text="Long translated paragraph that should use font-only fit.",
        font_size_pt=10.5,
        fit_min_font_size_pt=7.0,
        leading_em=1.35,
        fit_min_leading_em=1.35,
        leading_em_locked=True,
        fit_to_box=True,
    )
    src = _render_markdown_block("block-3", block)
    assert "pdftr_fit_markdown_fixed_leading" in src
    assert "leading: 1.35em" in src


def test_typst_overlay_source_includes_fixed_leading_helper():
    page = RenderPageSpec(page_index=0, page_width_pt=595.0, page_height_pt=842.0, blocks=[])
    src = build_typst_overlay_source([page])
    assert "pdftr_fit_markdown_fixed_leading" in src
