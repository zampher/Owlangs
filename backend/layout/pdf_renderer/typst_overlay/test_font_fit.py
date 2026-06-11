# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay font fitting."""

import unittest

from layout.pdf_renderer.typst_overlay.font_fit import FontFitCalculator
from layout.pdf_renderer.typst_overlay.models import RenderBlock


class TestFontFitCalculator(unittest.TestCase):
    def test_math_block_forces_fit_to_box(self):
        calc = FontFitCalculator()
        raw = {
            "lines": [
                {
                    "spans": [
                        {"type": "text", "content": "Overall, parameters are "},
                        {"type": "inline_equation", "content": "W_{y}"},
                        {"type": "text", "content": " and more."},
                    ]
                }
            ]
        }
        text = "Overall, parameters are $W_{y}$ and more."
        block = RenderBlock(
            block_id="b1",
            page_index=0,
            inner_bbox=(104.0, 700.0, 504.0, 723.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted.fit_to_box)
        self.assertTrue(fitted.fit_single_line)

    def test_short_plain_text_does_not_force_fit(self):
        calc = FontFitCalculator()
        text = "Hello"
        block = RenderBlock(
            block_id="b2",
            page_index=0,
            inner_bbox=(104.0, 700.0, 504.0, 723.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw={})
        self.assertFalse(fitted.fit_to_box)


    def test_tall_paragraph_with_citations_uses_multiline_fit(self):
        calc = FontFitCalculator()
        raw = {
            "lines": [
                {
                    "spans": [
                        {"type": "text", "content": "Natural Language Inference ... interest  "},
                        {"type": "inline_equation", "content": "[58, 35, 44]"},
                        {"type": "text", "content": " , the task remains challenging ..."},
                    ]
                }
            ]
        }
        text = (
            "Natural Language Inference ... interest [58, 35, 44] , "
            "the task remains challenging due to ..."
        )
        block = RenderBlock(
            block_id="b3",
            page_index=0,
            inner_bbox=(104.0, 511.0, 506.0, 599.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted.fit_to_box)
        self.assertFalse(fitted.fit_single_line)


if __name__ == "__main__":
    unittest.main()
