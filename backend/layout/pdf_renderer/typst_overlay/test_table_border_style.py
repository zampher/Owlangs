# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for table border style presets and emitter output."""

from __future__ import annotations

import re
import unittest

from layout.pdf_renderer.typst_overlay.emitter import (
    _estimate_table_column_widths_pt,
    _render_table_block,
    _resolve_table_row_heights_pt,
    _typst_table_columns_spec,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.table_border_style import (
    TABLE_BORDER_STYLE_BOOKTABS,
    TABLE_BORDER_STYLE_BOOKTABS_2,
    TABLE_BORDER_STYLE_BOOKTABS_3,
    TABLE_BORDER_STYLE_GRID,
    TABLE_BORDER_STYLE_HORIZONTAL,
    TABLE_BORDER_STYLE_NONE,
    TABLE_BORDER_STYLE_OUTER,
    booktabs_header_row_count,
    build_block_table_border_style_map_from_segments,
    group_adjacent_equal_row_cells,
    is_booktabs_border_style,
    normalize_table_border_style,
    resolve_table_border_style,
)


def _sample_table_block(**overrides) -> RenderBlock:
    base = dict(
        block_id="tbl-style",
        page_index=0,
        inner_bbox=(10.0, 20.0, 210.0, 135.0),
        markdown_text=(
            "| Symbol | Description |\n"
            "| --- | --- |\n"
            "| N | Client count. |\n"
            "| K | Class count. |\n"
        ),
        font_size_pt=10.0,
        render_kind="table",
        opaque_fill=True,
    )
    base.update(overrides)
    return RenderBlock(**base)


class TestTableBorderStyleNormalization(unittest.TestCase):
    def test_valid_styles(self):
        for style in (
            TABLE_BORDER_STYLE_GRID,
            TABLE_BORDER_STYLE_BOOKTABS,
            TABLE_BORDER_STYLE_BOOKTABS_2,
            TABLE_BORDER_STYLE_BOOKTABS_3,
            TABLE_BORDER_STYLE_HORIZONTAL,
            TABLE_BORDER_STYLE_OUTER,
            TABLE_BORDER_STYLE_NONE,
        ):
            self.assertEqual(normalize_table_border_style(style), style)
            self.assertEqual(normalize_table_border_style(style.upper()), style)

    def test_invalid_style_returns_none(self):
        self.assertIsNone(normalize_table_border_style("fancy"))

    def test_resolve_none_when_stroke_zero(self):
        self.assertEqual(
            resolve_table_border_style(TABLE_BORDER_STYLE_GRID, stroke_pt=0.0),
            TABLE_BORDER_STYLE_NONE,
        )

    def test_build_block_map_from_segments(self):
        segments = [
            {
                "segment_index": 1,
                "layout_block_indices": [62],
                "table_border_style": "booktabs",
            },
        ]
        block_map = build_block_table_border_style_map_from_segments(segments, {})
        self.assertEqual(block_map[62], TABLE_BORDER_STYLE_BOOKTABS)

    def test_table_border_style_map_with_bbox_override(self):
        segments = [
            {
                "segment_index": 1,
                "layout_block_indices": [62],
                "table_border_style": "booktabs_2",
                "layout_block_bbox_override": [10.0, 20.0, 200.0, 135.0],
            },
        ]
        block_map = build_block_table_border_style_map_from_segments(segments, {})
        self.assertEqual(block_map[62], TABLE_BORDER_STYLE_BOOKTABS_2)

    def test_booktabs_header_row_count_helpers(self):
        self.assertTrue(is_booktabs_border_style(TABLE_BORDER_STYLE_BOOKTABS_2))
        self.assertEqual(booktabs_header_row_count(TABLE_BORDER_STYLE_BOOKTABS), 1)
        self.assertEqual(booktabs_header_row_count(TABLE_BORDER_STYLE_BOOKTABS_2), 2)
        self.assertEqual(booktabs_header_row_count(TABLE_BORDER_STYLE_BOOKTABS_3), 3)
        self.assertEqual(booktabs_header_row_count(TABLE_BORDER_STYLE_GRID), 0)

    def test_group_adjacent_equal_row_cells(self):
        self.assertEqual(
            group_adjacent_equal_row_cells(["A", "A", "B", "B", "B"]),
            [("A", 2), ("B", 3)],
        )
        self.assertEqual(
            group_adjacent_equal_row_cells(["X", "Y", "Z"]),
            [("X", 1), ("Y", 1), ("Z", 1)],
        )
        self.assertEqual(
            group_adjacent_equal_row_cells(["  A  ", "A", ""]),
            [("A", 2), ("", 1)],
        )


class TestEmitterTableBorderStyles(unittest.TestCase):
    def test_booktabs_default_emits_hlines_and_fixed_rows(self):
        src = _render_table_block("block-booktabs-default", _sample_table_block())
        self.assertIn("table.hline(stroke:", src)
        self.assertIn("table.header(", src)
        self.assertIn("stroke: none,", src)
        self.assertIn("rows:", src)
        self.assertNotIn("table.cell(fill:", src)

    def test_grid_explicit_emits_full_stroke_and_fixed_rows(self):
        src = _render_table_block(
            "block-grid",
            _sample_table_block(table_border_style=TABLE_BORDER_STYLE_GRID),
        )
        self.assertIn("stroke: 0.5pt + rgb(", src)
        self.assertIn("rows:", src)
        self.assertIn("fill: rgb(", src)

    def test_booktabs_merges_adjacent_equal_title_cells(self):
        block = _sample_table_block(
            table_border_style=TABLE_BORDER_STYLE_BOOKTABS,
            markdown_text=(
                "| Group | Group | Item |\n"
                "| --- | --- | --- |\n"
                "| a | b | c |\n"
            ),
        )
        src = _render_table_block("block-booktabs-merge-1", block)
        self.assertIn("table.cell(colspan: 2)", src)
        self.assertNotIn("stroke: (bottom:", src)

    def test_booktabs_merge_draws_bottom_rule_between_title_rows(self):
        block = _sample_table_block(
            table_border_style=TABLE_BORDER_STYLE_BOOKTABS_2,
            markdown_text=(
                "| Param | Param | Value |\n"
                "| Name | Type | Data |\n"
                "| --- | --- | --- |\n"
                "| a | b | c |\n"
            ),
        )
        src = _render_table_block("block-booktabs-merge-2", block)
        self.assertIn("table.cell(colspan: 2, stroke: (bottom:", src)
        self.assertEqual(src.count("weight: \"bold\""), 5)

    def test_booktabs_two_header_rows(self):
        block = _sample_table_block(
            table_border_style=TABLE_BORDER_STYLE_BOOKTABS_2,
            markdown_text=(
                "| Title A | Title B |\n"
                "| Sub A | Sub B |\n"
                "| --- | --- |\n"
                "| N | Client count. |\n"
                "| K | Class count. |\n"
            ),
        )
        src = _render_table_block("block-booktabs-2", block)
        self.assertIn("table.header(", src)
        self.assertEqual(src.count("weight: \"bold\""), 4)
        self.assertEqual(src.count("weight: \"regular\""), 4)

    def test_booktabs_three_header_rows(self):
        block = _sample_table_block(
            table_border_style=TABLE_BORDER_STYLE_BOOKTABS_3,
            markdown_text=(
                "| Title A | Title B |\n"
                "| Sub A | Sub B |\n"
                "| Unit A | Unit B |\n"
                "| --- | --- |\n"
                "| N | Client count. |\n"
            ),
        )
        src = _render_table_block("block-booktabs-3", block)
        self.assertIn("table.header(", src)
        self.assertEqual(src.count("weight: \"bold\""), 6)
        self.assertEqual(src.count("weight: \"regular\""), 2)

    def test_booktabs_emits_hlines_and_fixed_rows(self):
        src = _render_table_block(
            "block-booktabs",
            _sample_table_block(table_border_style=TABLE_BORDER_STYLE_BOOKTABS),
        )
        self.assertIn("table.hline(stroke:", src)
        self.assertIn("table.header(", src)
        self.assertIn("stroke: none,", src)
        self.assertIn("rows:", src)
        self.assertNotIn("table.cell(fill:", src)

    def test_booktabs_columns_expand_to_bbox_width(self):
        src = _render_table_block(
            "block-booktabs-cols",
            _sample_table_block(table_border_style=TABLE_BORDER_STYLE_BOOKTABS),
        )
        match = re.search(r"columns: \((.+?)\),", src)
        self.assertIsNotNone(match)
        columns = match.group(1)
        self.assertNotIn("auto", columns)
        widths = [float(part.replace("pt", "")) for part in columns.split(", ")]
        self.assertEqual(len(widths), 2)
        self.assertAlmostEqual(sum(widths), 192.0, delta=2.0)
        self.assertGreater(widths[1], widths[0])

    def test_horizontal_emits_horizontal_stroke_callback(self):
        src = _render_table_block(
            "block-horizontal",
            _sample_table_block(table_border_style=TABLE_BORDER_STYLE_HORIZONTAL),
        )
        self.assertIn("top:", src)
        self.assertIn("left: none", src)
        self.assertIn("rows:", src)

    def test_outer_emits_outer_stroke_callback(self):
        src = _render_table_block(
            "block-outer",
            _sample_table_block(table_border_style=TABLE_BORDER_STYLE_OUTER),
        )
        self.assertIn("if y == 0", src)
        self.assertIn("if x == 0", src)

    def test_none_style_omits_lines(self):
        src = _render_table_block(
            "block-none",
            _sample_table_block(
                table_border_style=TABLE_BORDER_STYLE_NONE,
                table_stroke_pt=1.0,
            ),
        )
        self.assertIn("stroke: none,", src)
        self.assertNotIn("table.hline", src)


class TestTableColumnWidthFill(unittest.TestCase):
    def test_narrow_content_scales_columns_to_layout_width(self):
        rows = [
            ["Symbol", "Description"],
            ["N", "Client count."],
            ["K", "Class count."],
        ]
        spec = _typst_table_columns_spec(rows, 2, 200.0, 8.0, inset_pt=4.0)
        self.assertIn("pt", spec)
        widths = [
            float(part.strip().replace("pt", ""))
            for part in spec.strip("()").split(",")
        ]
        self.assertAlmostEqual(sum(widths), 192.0, delta=1.0)
        self.assertGreater(widths[1], widths[0])

    def test_wide_content_uses_proportional_pt_widths(self):
        rows = [
            ["A", "B"],
            ["x" * 80, "y" * 80],
        ]
        spec = _typst_table_columns_spec(rows, 2, 120.0, 10.0, inset_pt=4.0)
        self.assertIn("pt", spec)
        self.assertNotIn("auto", spec)
        widths = [
            float(part.strip().replace("pt", ""))
            for part in spec.strip("()").split(",")
        ]
        self.assertAlmostEqual(sum(widths), 112.0, delta=1.0)

    def test_column_widths_follow_widest_cell_per_column(self):
        rows = [
            ["ID", "Long description column"],
            ["1", "short"],
            ["22", "Another much longer translated sentence."],
        ]
        widths = _estimate_table_column_widths_pt(rows, 2, 9.0)
        self.assertGreater(widths[1], widths[0])


class TestTableRowHeightFill(unittest.TestCase):
    def test_booktabs_rows_fill_layout_height(self):
        block = _sample_table_block(table_border_style=TABLE_BORDER_STYLE_BOOKTABS)
        src = _render_table_block("block-booktabs-rows", block)
        match = re.search(r"rows: \((.+?)\),", src)
        self.assertIsNotNone(match)
        row_heights = [
            float(part.replace("pt", ""))
            for part in match.group(1).split(", ")
        ]
        self.assertEqual(len(row_heights), 3)
        # avail = layout_height(115) - 2*inset - 3*stroke for booktabs hlines
        self.assertAlmostEqual(sum(row_heights), 105.5, delta=2.0)

    def test_resolve_row_heights_scales_to_avail_height(self):
        rows = [
            ["Symbol", "Description"],
            ["N", "Client count."],
            ["K", "Class count."],
        ]
        column_widths = [40.0, 152.0]
        heights = _resolve_table_row_heights_pt(
            rows,
            2,
            115.0,
            column_widths,
            10.0,
            10.0,
            inset_pt=4.0,
            border_style=TABLE_BORDER_STYLE_BOOKTABS,
            stroke_pt=0.5,
        )
        self.assertEqual(len(heights), 3)
        self.assertAlmostEqual(sum(heights), 105.5, delta=1.0)


if __name__ == "__main__":
    unittest.main()
