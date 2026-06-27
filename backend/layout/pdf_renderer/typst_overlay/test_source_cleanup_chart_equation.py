# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for chart/equation format-aware source PDF redaction."""

import unittest
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.source_cleanup import _collect_redaction_rects
from layout.pdf_renderer.typst_overlay.visual_images import block_preserves_source_pdf_visual


class TestSourceCleanupChartEquation(unittest.TestCase):
    def _chart_block(self):
        return SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: False,
            should_skip_redaction=lambda: True,
            raw={
                "blocks": [
                    {
                        "type": "chart_body",
                        "bbox": [110.0, 441.0, 302.0, 610.0],
                        "lines": [],
                    }
                ]
            },
        )

    def _equation_block(self):
        return SimpleNamespace(
            type="interline_equation",
            index=35,
            bbox=(100.0, 200.0, 500.0, 240.0),
            image_path=None,
            is_equation=lambda: True,
            has_text=lambda: True,
            should_skip_redaction=lambda: False,
            raw={
                "lines": [
                    {
                        "spans": [
                            {
                                "type": "interline_equation",
                                "content": "E=mc^2",
                            }
                        ]
                    }
                ]
            },
        )

    def test_chart_image_format_skips_redaction(self):
        chart_block = self._chart_block()
        page = SimpleNamespace(page_index=0, blocks=[chart_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            chart_body_format="image",
            equation_format="text",
        )
        self.assertEqual(redaction_map, {})
        self.assertTrue(
            block_preserves_source_pdf_visual(
                chart_block,
                chart_body_format="image",
                equation_format="text",
            )
        )

    def test_chart_html_format_redacts_body_bbox(self):
        chart_block = self._chart_block()
        page = SimpleNamespace(page_index=0, blocks=[chart_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            chart_body_format="html",
            equation_format="text",
        )
        self.assertEqual(len(redaction_map.get(0, [])), 1)
        rect = redaction_map[0][0]
        self.assertAlmostEqual(rect[0], 108.0)
        self.assertAlmostEqual(rect[1], 439.0)

    def test_equation_image_format_skips_redaction(self):
        eq_block = self._equation_block()
        page = SimpleNamespace(page_index=0, blocks=[eq_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            chart_body_format="image",
            equation_format="image",
        )
        self.assertEqual(redaction_map, {})

    def test_table_image_format_skips_redaction(self):
        table_block = SimpleNamespace(
            type="table",
            index=10,
            bbox=(76.0, 639.0, 295.0, 738.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: False,
            should_skip_redaction=lambda: True,
            raw={
                "blocks": [
                    {
                        "type": "table_body",
                        "bbox": [76.0, 639.0, 295.0, 738.0],
                        "lines": [],
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=0, blocks=[table_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            table_body_format="image",
            chart_body_format="image",
        )
        self.assertEqual(redaction_map, {})

    def test_equation_text_format_redacts_bbox(self):
        eq_block = self._equation_block()
        page = SimpleNamespace(page_index=0, blocks=[eq_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            chart_body_format="image",
            equation_format="text",
        )
        self.assertEqual(len(redaction_map.get(0, [])), 1)
        rect = redaction_map[0][0]
        self.assertAlmostEqual(rect[0], 98.0)
        self.assertAlmostEqual(rect[1], 198.0)


if __name__ == "__main__":
    unittest.main()
