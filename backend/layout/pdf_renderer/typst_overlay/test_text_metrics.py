# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay text metrics."""

import unittest

from layout.pdf_renderer.typst_overlay.text_metrics import (
    block_needs_math_fit,
    count_embedded_newlines,
    count_visual_lines_from_content,
    estimate_typographic_units,
    estimate_visual_line_count,
    is_single_line_bbox,
    is_suspiciously_short_mapped_text,
    layout_raw_has_inline_equation,
)

# layout.json Introduction paragraph: 1 MinerU line, bbox height 101pt, 3 citations
INTRO_MULTI_CITATION_RAW = {
    "lines": [
        {
            "spans": [
                {"type": "text", "content": "The ability to learn effectively from raw text ... resources  "},
                {"type": "inline_equation", "content": "[61]"},
                {"type": "text", "content": " . In these situations ... embeddings  "},
                {"type": "inline_equation", "content": "[10, 39, 42]"},
                {"type": "text", "content": "  to improve performance ... tasks  "},
                {"type": "inline_equation", "content": "[8, 11, 26, 45]"},
                {"type": "text", "content": " ."},
            ]
        }
    ]
}

# layout.json index 7: NLI paragraph, bbox height 88pt, 1 citation
NLI_CITATION_RAW = {
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

    def test_single_line_bbox_uses_height_not_mineru_line_count(self):
        self.assertTrue(is_single_line_bbox(23.0, INTRO_MULTI_CITATION_RAW))
        self.assertFalse(is_single_line_bbox(101.0, INTRO_MULTI_CITATION_RAW))
        self.assertFalse(is_single_line_bbox(88.0, NLI_CITATION_RAW))

    def test_visual_line_count_from_tall_bbox(self):
        self.assertGreaterEqual(estimate_visual_line_count(101.0, INTRO_MULTI_CITATION_RAW), 5.0)
        self.assertGreaterEqual(estimate_visual_line_count(88.0, NLI_CITATION_RAW), 4.0)
        self.assertEqual(estimate_visual_line_count(23.0, None), 1.0)

    def test_plain_citation_bonus_from_layout_raw(self):
        text = "some interest [58, 35, 44] , the task remains"
        without_raw = estimate_typographic_units(text)
        with_raw = estimate_typographic_units(text, NLI_CITATION_RAW)
        self.assertGreater(with_raw, without_raw)

    def test_multi_citation_intro_plain_text(self):
        text = (
            "The ability ... resources [61] . In ... embeddings [10, 39, 42] "
            "to improve ... tasks [8, 11, 26, 45] ."
        )
        units = estimate_typographic_units(text, INTRO_MULTI_CITATION_RAW)
        self.assertGreater(units, float(len(text)))

    def test_suspicious_short_mapping(self):
        original = "Overall, the only extra parameters we require during fine-tuning are W_{y}"
        self.assertTrue(is_suspiciously_short_mapped_text("W_{y}", original))
        self.assertFalse(
            is_suspiciously_short_mapped_text(
                "总体而言，我们在微调期间需要的额外参数只有 \\(W_{y}\\) 以及分隔符",
                original,
            )
        )

    def test_embedded_newline_in_span_counts_as_two_lines(self):
        raw = {
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": "(12) United States Patent\nEisen",
                        }
                    ]
                }
            ]
        }
        self.assertEqual(count_embedded_newlines("", raw), 1)
        self.assertEqual(count_visual_lines_from_content("", raw), 2)
        # bbox height 31pt: was treated as 1 line; should infer ~2 lines
        self.assertGreaterEqual(estimate_visual_line_count(31.0, raw), 2.0)

    def test_tight_bbox_single_line_stays_one_line(self):
        self.assertEqual(estimate_visual_line_count(14.0, None, text="US 8,672,145 B2"), 1.0)
        self.assertEqual(estimate_visual_line_count(23.0, None), 1.0)

    def test_short_two_line_bbox_from_height_rounding(self):
        """27pt patent field: two lines even without embedded \\n in translated text."""
        self.assertGreaterEqual(
            estimate_visual_line_count(27.0, None, text="(56) References Cited U.S. PATENT DOCUMENTS"),
            2.0,
        )


if __name__ == "__main__":
    unittest.main()
