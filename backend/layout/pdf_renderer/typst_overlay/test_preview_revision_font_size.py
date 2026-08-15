# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Preview-revision font size must stick for tables and locked emitters."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import (
    _estimate_table_font_pt,
    _render_table_block,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    apply_user_font_override,
)


def test_estimate_table_font_pt_respects_font_size_locked():
    rows = [["aaaa", "bbbb"], ["cccc", "dddd"]]
    auto_pt = _estimate_table_font_pt(
        layout_width=80.0,
        layout_height=40.0,
        row_count=2,
        col_count=2,
        rows=rows,
        block_font_pt=18.0,
        border_style="grid",
        font_size_locked=False,
    )
    locked_pt = _estimate_table_font_pt(
        layout_width=80.0,
        layout_height=40.0,
        row_count=2,
        col_count=2,
        rows=rows,
        block_font_pt=18.0,
        border_style="grid",
        font_size_locked=True,
    )
    assert locked_pt == 18.0
    assert auto_pt < locked_pt


def test_render_table_block_uses_locked_user_font_size():
    rb = RenderBlock(
        block_id="table-1",
        page_index=0,
        inner_bbox=(0.0, 0.0, 80.0, 40.0),
        markdown_text="| a | b |\n| --- | --- |\n| c | d |",
        plain_text="| a | b |\n| --- | --- |\n| c | d |",
        render_kind="table",
        table_rows=[["a", "b"], ["c", "d"]],
        font_size_pt=10.0,
    )
    locked = apply_user_font_override(rb, 16.0)
    assert locked.font_size_locked is True
    src = _render_table_block("block-table-1", locked)
    assert "16.0pt" in src
    # Auto path would clamp well below 16pt for this tiny bbox.
    assert "5.0pt" not in src
