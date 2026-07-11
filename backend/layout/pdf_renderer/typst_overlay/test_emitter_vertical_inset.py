# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for Typst emitter vertical layout (margin via shrunk inner_bbox, not pad)."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import _render_markdown_block, _render_plain_block
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def test_render_plain_block_long_text_fit_does_not_crash():
    long_text = "A" * 50
    block = RenderBlock(
        block_id="plain-long",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 80.0),
        plain_text=long_text,
        font_size_pt=10.0,
        fit_to_box=True,
        fit_max_height_pt=72.0,
        fit_min_font_size_pt=7.0,
        leading_em=1.25,
    )
    src = _render_plain_block("block-plain-long", block)
    assert "pdftr_fit_markdown" in src


def test_render_markdown_block_no_typst_edge_pad_for_multi_line():
    block = RenderBlock(
        block_id="multi",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 80.0),
        markdown_text="Line one\nLine two of translated text.",
        font_size_pt=10.0,
        fit_min_font_size_pt=7.0,
        leading_em=1.25,
        fit_to_box=True,
        fit_max_height_pt=72.0,
    )
    src = _render_markdown_block("block-multi", block)
    assert "pad(top:" not in src


def test_render_plain_block_short_multi_line_bbox_no_typst_edge_pad():
    block = RenderBlock(
        block_id="plain-short-multi",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 64.0),
        plain_text="Short two-line block.",
        font_size_pt=10.0,
        fit_to_box=False,
    )
    src = _render_plain_block("block-plain-short-multi", block)
    assert "pad(top:" not in src


def test_render_plain_block_locked_font_multi_line_bbox_no_typst_edge_pad():
    block = RenderBlock(
        block_id="plain-locked-multi",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 64.0),
        plain_text="Locked font paragraph with enough height for two lines.",
        font_size_pt=10.0,
        font_size_locked=True,
    )
    src = _render_plain_block("block-plain-locked-multi", block)
    assert "pad(top:" not in src


def test_render_markdown_block_no_vertical_pad_for_single_line_bbox():
    block = RenderBlock(
        block_id="single",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 12.0),
        markdown_text="Single line header",
        font_size_pt=10.0,
        fit_to_box=False,
        fit_max_height_pt=12.0,
    )
    src = _render_markdown_block("block-single", block)
    assert "pad(top:" not in src
