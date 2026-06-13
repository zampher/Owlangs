# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for user-locked font size rendering in Typst emitter."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import (
    _render_markdown_block,
    _render_plain_block,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock, RenderLineBox


def test_preserved_line_boxes_use_exact_locked_font_size():
    block = RenderBlock(
        block_id="b-1",
        page_index=0,
        inner_bbox=(10.0, 20.0, 200.0, 32.0),
        markdown_text="Line one",
        plain_text="Line one",
        font_size_pt=15.0,
        leading_em=1.1,
        font_size_locked=True,
        preserve_line_breaks=True,
        preserved_line_boxes=[
            RenderLineBox(text="Locked line", bbox=(10.0, 20.0, 200.0, 32.0)),
        ],
    )
    src = _render_markdown_block("block-1", block)
    assert "15.0pt" in src
    assert "pdftr_fit_single_line_markdown" not in src
    assert "10.32pt" not in src


def test_short_plain_block_skips_width_scaling_when_locked():
    block = RenderBlock(
        block_id="b-2",
        page_index=0,
        inner_bbox=(0.0, 0.0, 40.0, 20.0),
        plain_text="Short locked text",
        markdown_text="Short locked text",
        font_size_pt=18.0,
        font_size_locked=True,
        render_kind="plain_line",
    )
    src = _render_plain_block("block-2", block)
    assert "18.0pt" in src
    assert "scaled-font" not in src
    assert "base-size.width" not in src
