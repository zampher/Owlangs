# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for rotated table rendering in Typst emitter."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import (
    _render_table_block,
    _table_reading_dimensions,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def _sample_table_block(**overrides) -> RenderBlock:
    base = dict(
        block_id="tbl-1",
        page_index=0,
        inner_bbox=(10.0, 20.0, 60.0, 220.0),
        markdown_text=(
            "| Col A | Col B |\n"
            "| --- | --- |\n"
            "| Alpha | Beta |\n"
            "| Gamma | Delta |\n"
        ),
        font_size_pt=10.0,
        render_kind="table",
    )
    base.update(overrides)
    return RenderBlock(**base)


def test_table_reading_dimensions_swap_for_sideways_rotation():
    assert _table_reading_dimensions(50.0, 200.0, 90) == (200.0, 50.0)
    assert _table_reading_dimensions(50.0, 200.0, 270) == (200.0, 50.0)
    assert _table_reading_dimensions(50.0, 200.0, 0) == (50.0, 200.0)
    assert _table_reading_dimensions(50.0, 200.0, 180) == (50.0, 200.0)


def test_table_rotation_90_keeps_original_row_column_data():
    src = _render_table_block("block-tbl", _sample_table_block(rotation=90))

    assert "#rotate(-90deg, origin: center" in src
    assert "block(width: 200.0pt, height: 50.0pt" in src
    assert "block(width: 50.0pt, height: 200.0pt, clip: true" in src
    # Original row-major order — grid rotation is done by Typst, not data transpose.
    assert src.index("Col A") < src.index("Col B")
    assert src.index("Alpha") < src.index("Beta")
    assert src.index("Gamma") < src.index("Delta")


def test_table_rotation_0_fills_bbox_without_rotate():
    src = _render_table_block("block-tbl", _sample_table_block(rotation=0))

    assert "#rotate(" not in src
    assert "clip: true" not in src
    assert "block(width: 50.0pt, height: 200.0pt" in src
    assert "Col A" in src
    assert "Alpha" in src


def test_table_rotation_180_keeps_original_data_and_rotates_grid():
    src = _render_table_block("block-tbl", _sample_table_block(rotation=180))

    assert "#rotate(-180deg, origin: center" in src
    assert "block(width: 50.0pt, height: 200.0pt, clip: true" in src
    assert src.index("Col A") < src.index("Col B")
    assert src.index("Alpha") < src.index("Beta")


def test_empty_table_cells_render_without_measure_scale():
    block = _sample_table_block(
        markdown_text="| H1 | H2 |\n| --- | --- |\n|  |  |\n|  |  |\n",
    )
    src = _render_table_block("block-empty", block)
    assert "measured.width" not in src
    assert "rows:" in src
