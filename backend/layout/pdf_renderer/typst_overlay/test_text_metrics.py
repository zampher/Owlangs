# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay text metrics."""

import unittest

from layout.pdf_renderer.typst_overlay.text_metrics import (
    block_needs_math_fit,
    estimate_typographic_units,
    is_single_line_bbox,
    is_suspiciously_short_mapped_text,
    layout_raw_has_inline_equation,
)


class TestTextMetrics(unittest.TestCase):
    def test_typographic_units_math_wider_than_plain_chars(self):
        plain = "Overall, the only extra parameters we require"
        with_math = (
            "Overall, the only extra parameters we require $W_{y}$ , and embeddings"
        )
        self.assertGreater(
            estimate_typographic_units(with_math),
            float(len(with_math)),
        )
        self.assertGreater(
            estimate_typographic_units(with_math),
            estimate_typographic_units(plain),
        )

    def test_layout_raw_inline_equation_detection(self):
        raw = {
            "lines": [
                {
                    "spans": [
                        {"type": "text", "content": "foo "},
                        {"type": "inline_equation", "content": "W_{y}"},
                    ]
                }
            ]
        }
        self.assertTrue(layout_raw_has_inline_equation(raw))
        self.assertTrue(block_needs_math_fit("plain text", raw))

    def test_single_line_bbox_heuristic(self):
        self.assertTrue(is_single_line_bbox(23.0, None))
        self.assertFalse(is_single_line_bbox(60.0, None))

    def test_suspicious_short_mapping(self):
        original = "Overall, the only extra parameters we require during fine-tuning are W_{y}"
        self.assertTrue(is_suspiciously_short_mapped_text("W_{y}", original))
        self.assertFalse(
            is_suspiciously_short_mapped_text(
                "总体而言，我们在微调期间需要的额外参数只有 \\(W_{y}\\) 以及分隔符",
                original,
            )
        )


if __name__ == "__main__":
    unittest.main()
