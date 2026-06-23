# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for HTML table parsing in Typst emitter."""

from layout.pdf_renderer.typst_overlay.emitter import (
    _parse_table_rows,
    _render_table_block,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def test_parse_table_rows_html():
    html = (
        "<table><tr><th>Col A</th><th>Col B</th></tr>"
        "<tr><td>Alpha</td><td>Beta</td></tr></table>"
    )
    rows = _parse_table_rows(html)
    assert rows == [["Col A", "Col B"], ["Alpha", "Beta"]]


def test_render_table_block_from_html():
    block = RenderBlock(
        block_id="tbl-html",
        page_index=0,
        inner_bbox=(10.0, 20.0, 110.0, 80.0),
        markdown_text=(
            "<table><tr><th>H1</th><th>H2</th></tr>"
            "<tr><td>One</td><td>Two</td></tr></table>"
        ),
        font_size_pt=10.0,
        render_kind="table",
        opaque_fill=True,
    )
    src = _render_table_block("block-tbl", block)
    assert "H1" in src
    assert "One" in src
    assert "fill: rgb(" in src
