# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for method-1 inner_bbox vertical edge margin (10% line height, 1.5pt cap)."""

from __future__ import annotations

import unittest

from layout.pdf_renderer.typst_overlay.font_fit import (
    FontFitCalculator,
    shrink_render_block_inner_bbox_for_edge_margin,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.text_metrics import (
    BBOX_VERTICAL_EDGE_INSET_MAX_PT,
    bbox_vertical_edge_inset_pt,
    outer_bbox_content_height_pt,
    shrink_inner_bbox_vertical,
)


class TestBboxVerticalEdgeInset(unittest.TestCase):
    def test_single_line_no_inset(self):
        self.assertEqual(bbox_vertical_edge_inset_pt(1.0), 0.0)

    def test_two_line_default_ten_percent_of_fourteen(self):
        self.assertAlmostEqual(bbox_vertical_edge_inset_pt(2.0), 1.4)

    def test_ten_pt_font_two_lines(self):
        self.assertAlmostEqual(
            bbox_vertical_edge_inset_pt(2.0, font_size_pt=10.0),
            1.0,
        )

    def test_large_font_capped_at_one_point_five(self):
        self.assertAlmostEqual(
            bbox_vertical_edge_inset_pt(2.0, font_size_pt=20.0),
            BBOX_VERTICAL_EDGE_INSET_MAX_PT,
        )

    def test_shrink_inner_bbox_applies_insets(self):
        bbox = (0.0, 100.0, 200.0, 122.0)
        shrunk = shrink_inner_bbox_vertical(bbox, 2.0, font_size_pt=10.0)
        self.assertAlmostEqual(shrunk[1], 101.0)
        self.assertAlmostEqual(shrunk[3], 121.0)

    def test_outer_bbox_content_height_before_shrink(self):
        outer_h = 100.0
        inset = bbox_vertical_edge_inset_pt(2.0, font_size_pt=10.0)
        self.assertAlmostEqual(
            outer_bbox_content_height_pt(outer_h, 2.0, font_size_pt=10.0),
            outer_h - 2.0 * inset,
        )
        inner_h = outer_h - 2.0 * inset
        self.assertLess(inner_h, outer_h)


class TestRenderBlockShrink(unittest.TestCase):
    def test_calculate_fit_params_shrinks_multi_line_bbox(self):
        calc = FontFitCalculator()
        bbox = (104.0, 511.0, 506.0, 599.0)
        outer_h = bbox[3] - bbox[1]
        block = RenderBlock(
            block_id="multi",
            page_index=0,
            inner_bbox=bbox,
            plain_text="Line one\nLine two",
            markdown_text="Line one\nLine two",
        )
        fitted = calc.calculate_fit_params(block, layout_raw={})
        inner_h = fitted.inner_bbox[3] - fitted.inner_bbox[1]
        inset = bbox_vertical_edge_inset_pt(
            2.0,
            font_size_pt=fitted.font_size_pt,
        )
        self.assertLess(inner_h, outer_h)
        self.assertAlmostEqual(inner_h, outer_h - 2.0 * inset, delta=0.5)

    def test_single_line_bbox_unchanged(self):
        block = RenderBlock(
            block_id="single",
            page_index=0,
            inner_bbox=(0.0, 0.0, 200.0, 12.0),
            plain_text="One line",
        )
        shrunk = shrink_render_block_inner_bbox_for_edge_margin(block, layout_raw={})
        self.assertEqual(shrunk.inner_bbox, block.inner_bbox)


if __name__ == "__main__":
    unittest.main()
