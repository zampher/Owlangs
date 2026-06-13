# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay font fitting."""

import unittest

from layout.pdf_renderer.typst_overlay.font_fit import (
    FontFitCalculator,
    REF_TEXT_MAX_LEADING_EM,
    estimate_title_font_size_pt,
    is_patent_field_label,
    quantize_ref_font_size_pt,
    quantize_ref_leading_em,
    should_use_title_font_sizing,
)
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

    def test_ref_text_short_translation_fits_bbox(self):
        calc = FontFitCalculator()
        raw = {
            "type": "ref_text",
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": "[21] J. Howard and S. Ruder. Universal language model fine-tuning for text classification. Association for Computational Linguistics (ACL), 2018.",
                        }
                    ]
                }
            ],
        }
        long_text = (
            "[21] J. Howard and S. Ruder. Universal language model fine-tuning "
            "for text classification. Association for Computational Linguistics (ACL), 2018."
        )
        short_text = "[21] Howard与Ruder，2018。"

        for text in (long_text, short_text):
            block = RenderBlock(
                block_id="ref",
                page_index=0,
                inner_bbox=(106.0, 643.0, 504.0, 664.0),
                plain_text=text,
                markdown_text=text,
            )
            fitted = calc.calculate_fit_params(block, layout_raw=raw)
            self.assertTrue(fitted.fit_to_box)
            self.assertLessEqual(fitted.font_size_pt, 21.0 * 0.48 + 0.1)
            self.assertLessEqual(
                fitted.font_size_pt * fitted.leading_em,
                21.0 * 0.85 + 0.1,
            )

    def test_ref_text_block_33_layout_bbox(self):
        calc = FontFitCalculator()
        raw = {
            "type": "ref_text",
            "lines": [{"spans": [{"type": "text", "content": "[33] P. Liang..."}]}],
        }
        text = (
            "[33] P. Liang. Semi-supervised learning for natural language. "
            "PhD thesis, Massachusetts Institute of Technology, 2005."
        )
        block = RenderBlock(
            block_id="ref33",
            page_index=0,
            inner_bbox=(107.0, 333.0, 505.0, 354.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted.fit_to_box)
        self.assertLessEqual(fitted.font_size_pt, 10.5)

    def test_compute_unified_ref_font_size_uses_median(self):
        calc = FontFitCalculator()
        self.assertEqual(calc.compute_unified_ref_font_size([7.5, 10.0, 8.0, 9.0]), 8.0)
        self.assertEqual(calc.compute_unified_ref_font_size([7.5, 10.0, 8.0]), 7.5)
        self.assertIsNone(calc.compute_unified_ref_font_size([]))

    def test_quantize_ref_font_size_floor_half_pt(self):
        self.assertEqual(quantize_ref_font_size_pt(10.1), 10.0)
        self.assertEqual(quantize_ref_font_size_pt(10.6), 10.5)
        self.assertEqual(quantize_ref_font_size_pt(10.0), 10.0)
        self.assertEqual(quantize_ref_font_size_pt(10.5), 10.5)

    def test_unified_ref_font_quantizes_median(self):
        calc = FontFitCalculator()
        self.assertEqual(calc.compute_unified_ref_font_size([10.1, 10.2, 10.3]), 9.5)
        self.assertEqual(calc.compute_unified_ref_font_size([10.6, 10.7, 10.8]), 10.0)

    def test_ref_text_blocks_share_unified_font(self):
        calc = FontFitCalculator()
        raw = {
            "type": "ref_text",
            "lines": [{"spans": [{"type": "text", "content": "[1] Example."}]}],
        }
        bboxes = [
            (106.0, 643.0, 504.0, 664.0),
            (106.0, 620.0, 504.0, 641.0),
            (106.0, 597.0, 504.0, 618.0),
        ]
        texts = [
            "[1] Short ref.",
            "[2] Medium length reference entry for testing.",
            (
                "[3] P. Liang. Semi-supervised learning for natural language. "
                "PhD thesis, Massachusetts Institute of Technology, 2005."
            ),
        ]
        candidates = []
        for bbox, text in zip(bboxes, texts):
            block = RenderBlock(
                block_id="ref",
                page_index=0,
                inner_bbox=bbox,
                plain_text=text,
                markdown_text=text,
            )
            candidates.append(calc.estimate_font_size(block, layout_raw=raw))
        unified = calc.compute_unified_ref_font_size(candidates)
        self.assertIsNotNone(unified)

        leading_candidates = []
        for bbox, text in zip(bboxes, texts):
            block = RenderBlock(
                block_id="ref",
                page_index=0,
                inner_bbox=bbox,
                plain_text=text,
                markdown_text=text,
            )
            leading_candidates.append(
                calc.estimate_ref_text_leading_em(block, unified, layout_raw=raw)
            )
        unified_leading = calc.compute_unified_ref_leading_em(leading_candidates)
        self.assertIsNotNone(unified_leading)
        self.assertLessEqual(unified_leading, REF_TEXT_MAX_LEADING_EM)
        self.assertLess(unified_leading, 1.25)

        for bbox, text in zip(bboxes, texts):
            block = RenderBlock(
                block_id="ref",
                page_index=0,
                inner_bbox=bbox,
                plain_text=text,
                markdown_text=text,
            )
            fitted = calc.calculate_fit_params(
                block,
                layout_raw=raw,
                ref_unified_font_pt=unified,
                ref_unified_leading_em=unified_leading,
            )
            self.assertEqual(fitted.font_size_pt, unified)
            self.assertEqual(fitted.leading_em, unified_leading)
            self.assertFalse(fitted.fit_to_box)
            self.assertEqual(fitted.fit_min_font_size_pt, unified)
            self.assertEqual(fitted.fit_max_font_size_pt, unified)
            self.assertEqual(fitted.fit_min_leading_em, unified_leading)

    def test_ref_text_leading_fits_typical_bbox(self):
        calc = FontFitCalculator()
        raw = {"type": "ref_text", "lines": [{"spans": [{"type": "text", "content": "[1] x"}]}]}
        block = RenderBlock(
            block_id="ref",
            page_index=0,
            inner_bbox=(106.0, 643.0, 504.0, 664.0),
            plain_text="[1] Short bibliography entry.",
            markdown_text="[1] Short bibliography entry.",
        )
        leading = calc.estimate_ref_text_leading_em(block, 10.0, layout_raw=raw)
        self.assertLessEqual(leading, REF_TEXT_MAX_LEADING_EM)
        self.assertGreaterEqual(leading, 0.48)

    def test_quantize_ref_leading_floor(self):
        self.assertEqual(quantize_ref_leading_em(0.63), 0.60)
        self.assertEqual(quantize_ref_leading_em(0.67), 0.65)
        self.assertEqual(quantize_ref_leading_em(0.72), 0.70)

    def test_section_title_single_line_bbox(self):
        """MinerU section heading: tight ~11pt bbox, one lines[] entry."""
        raw = {
            "type": "title",
            "bbox": [105, 464, 192, 475],
            "lines": [{"spans": [{"type": "text", "content": "1 Introduction"}]}],
        }
        size = estimate_title_font_size_pt(11.0, raw)
        self.assertGreaterEqual(size, 10.0)
        self.assertLessEqual(size, 11.0)

    def test_document_title_tall_bbox(self):
        """Paper title: ~41pt bbox, one logical line but multiple visual lines."""
        raw = {
            "type": "title",
            "bbox": [170, 97, 442, 138],
            "lines": [{
                "spans": [{
                    "type": "text",
                    "content": "Improving Language Understanding by Generative Pre-Training",
                }],
            }],
        }
        size = estimate_title_font_size_pt(41.0, raw)
        self.assertGreaterEqual(size, 12.0)
        self.assertLessEqual(size, 16.0)

    def test_title_blocks_skip_fit_to_box(self):
        calc = FontFitCalculator()
        raw = {
            "type": "title",
            "lines": [{"spans": [{"type": "text", "content": "1 Introduction"}]}],
        }
        block = RenderBlock(
            block_id="title",
            page_index=0,
            inner_bbox=(105.0, 464.0, 192.0, 475.0),
            plain_text="1 Introduction",
            markdown_text="1 Introduction",
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertFalse(fitted.fit_to_box)
        self.assertGreaterEqual(fitted.font_size_pt, 10.0)

    def test_patent_header_two_lines_smaller_font(self):
        calc = FontFitCalculator()
        raw = {
            "type": "text",
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": "(12) United States Patent\nEisen",
                        }
                    ]
                }
            ],
        }
        text = "(12) United States Patent\nEisen"
        block = RenderBlock(
            block_id="patent_hdr",
            page_index=0,
            inner_bbox=(76.0, 67.0, 256.0, 98.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted.preserve_line_breaks)
        self.assertEqual(fitted.render_kind, "markdown")
        self.assertLessEqual(fitted.font_size_pt, 12.0)
        self.assertGreaterEqual(fitted.font_size_pt, 8.0)

    def test_narrow_patent_number_enables_fit_when_translation_wraps(self):
        calc = FontFitCalculator()
        raw = {
            "type": "text",
            "lines": [{"spans": [{"type": "text", "content": "US 8,672,145 B2"}]}],
        }
        translated = "美国专利 US 8,672,145 B2 号"
        block = RenderBlock(
            block_id="patent_no",
            page_index=0,
            inner_bbox=(430.0, 70.0, 528.0, 84.0),
            plain_text=translated,
            markdown_text=translated,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted.fit_to_box)

    def test_uspc_classification_two_embedded_lines(self):
        """layout-1.json index 20: (52) U.S. Cl. + long USPC line with embedded newline."""
        calc = FontFitCalculator()
        raw = {
            "type": "text",
            "bbox": [311, 118, 528, 148],
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": (
                                "(52) U.S. Cl.\n"
                                "USPC ..... 210/502.1; 210/290; 210/348; "
                                "210/488; 210/489; 210/490"
                            ),
                        }
                    ]
                }
            ],
        }
        # Medium translation without \\n still sits in a ~30pt two-line bbox.
        text = (
            "(52) U.S. Cl. USPC ..... 210/502.1; 210/290; 210/348; "
            "210/488; 210/489"
        )
        block = RenderBlock(
            block_id="uspc",
            page_index=0,
            inner_bbox=(311.0, 118.0, 528.0, 148.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertLessEqual(fitted.font_size_pt, 12.0)
        self.assertGreaterEqual(fitted.font_size_pt, 7.0)

        text_with_breaks = (
            "(52) U.S. Cl.\n"
            "USPC ..... 210/502.1; 210/290; 210/348; 210/488; 210/489; 210/490"
        )
        block_nl = RenderBlock(
            block_id="uspc_nl",
            page_index=0,
            inner_bbox=(311.0, 118.0, 528.0, 148.0),
            plain_text=text_with_breaks,
            markdown_text=text_with_breaks,
        )
        fitted_nl = calc.calculate_fit_params(block_nl, layout_raw=raw)
        self.assertTrue(fitted_nl.preserve_line_breaks)
        self.assertLessEqual(fitted_nl.font_size_pt, 12.0)

    def test_references_cited_two_line_patent_header(self):
        """layout-1.json (56) References Cited: 27pt bbox, two visual lines."""
        calc = FontFitCalculator()
        raw = {
            "type": "text",
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": "(56) References Cited\nU.S. PATENT DOCUMENTS",
                        }
                    ]
                }
            ],
        }
        bbox = (311.0, 195.0, 474.0, 222.0)
        # Translation may collapse the embedded newline; bbox height still implies 2 lines.
        text = "(56) References Cited U.S. PATENT DOCUMENTS"
        block = RenderBlock(
            block_id="ref_cited",
            page_index=0,
            inner_bbox=bbox,
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw={})
        self.assertLessEqual(fitted.font_size_pt, 11.0)
        self.assertGreaterEqual(fitted.font_size_pt, 7.5)

        fitted_raw = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertTrue(fitted_raw.preserve_line_breaks)
        self.assertLessEqual(fitted_raw.font_size_pt, 11.0)

    def test_local_mineru_patent_title_mislabel_uses_body_font(self):
        """middle.json tags (56) References Cited as type title — must not use 23pt title sizing."""
        calc = FontFitCalculator()
        raw = {
            "type": "title",
            "bbox": [310, 194, 474, 221],
            "lines": [
                {
                    "spans": [
                        {
                            "type": "text",
                            "content": "(56) References Cited U.S. PATENT DOCUMENTS",
                        }
                    ]
                }
            ],
        }
        text = "(56) References Cited U.S. PATENT DOCUMENTS"
        self.assertTrue(is_patent_field_label(text, raw))
        self.assertFalse(should_use_title_font_sizing(text, raw, 27.0))
        block = RenderBlock(
            block_id="patent_ref_title",
            page_index=0,
            inner_bbox=(310.0, 194.0, 474.0, 221.0),
            plain_text=text,
            markdown_text=text,
        )
        fitted = calc.calculate_fit_params(block, layout_raw=raw)
        self.assertLessEqual(fitted.font_size_pt, 11.0)
        self.assertGreaterEqual(fitted.font_size_pt, 7.5)
        self.assertTrue(fitted.fit_to_box)


if __name__ == "__main__":
    unittest.main()
