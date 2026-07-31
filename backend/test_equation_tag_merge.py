# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for merging orphan equation numbers into display math as \\tag."""

import unittest

from utils.equation_tag_merge import (
    inject_tag_into_display_math,
    merge_equation_number_tags_in_texts,
    merge_orphan_equation_number_paragraphs,
    promote_tagged_display_math_to_equation,
)
from utils.format_convert_utils import _sanitize_md_for_pdf
from utils.math_md_normalize import normalize_md_math_for_pandoc_export


class TestEquationTagMerge(unittest.TestCase):
    def test_inject_tag_into_display_math(self):
        src = "$$\n x = 1 \n$$"
        out = inject_tag_into_display_math(src, "1")
        self.assertIn(r"\tag{1}", out)
        self.assertTrue(out.strip().startswith("$$"))
        self.assertTrue(out.strip().endswith("$$"))

    def test_merge_trailing_number_paragraph(self):
        md = "$$\n\\max F = 1\n$$\n\n(1)\n\nNext para."
        out = merge_orphan_equation_number_paragraphs(md)
        self.assertIn(r"\tag{1}", out)
        self.assertNotIn("\n\n(1)\n", out)
        self.assertIn("Next para.", out)

    def test_normalize_merges_orphan_number(self):
        md = "$$\na=b\n$$\n\n(3)"
        out = normalize_md_math_for_pandoc_export(md)
        self.assertIn(r"\tag{3}", out)
        self.assertNotRegex(out, r"\$\$\s*\n\s*\(3\)")

    def test_bbox_pairs_out_of_order_number(self):
        # Reading order: (2) before its formula; bbox Y aligns with formula.
        texts = [
            "$$\n\\max F\n$$",
            "(1)",
            "(2)",
            "$$\ns.t.:\n$$",
            "$$\nE_t=G_t\n$$",
        ]
        bboxes = [
            (100.0, 268.0, 520.0, 294.0),  # formula 1
            (538.0, 282.0, 550.0, 293.0),  # (1) same row
            (538.0, 353.0, 550.0, 364.0),  # (2) same row as E_t
            (100.0, 297.0, 200.0, 307.0),  # s.t.
            (100.0, 352.0, 520.0, 365.0),  # E_t formula
        ]
        out, n = merge_equation_number_tags_in_texts(texts, bboxes)
        self.assertEqual(n, 2)
        self.assertIn(r"\tag{1}", out[0])
        self.assertEqual(out[1], "")
        self.assertEqual(out[2], "")
        self.assertIn(r"\tag{2}", out[4])
        self.assertNotIn(r"\tag", out[3])

    def test_promote_tagged_display_to_equation(self):
        md = "$$\nx=1 \\tag{1}\n$$"
        out = promote_tagged_display_math_to_equation(md)
        self.assertIn(r"\begin{equation}", out)
        self.assertIn(r"\tag{1}", out)
        self.assertIn(r"\end{equation}", out)
        self.assertNotIn("$$", out)

    def test_pdf_sanitize_keeps_tag_inside_display_math(self):
        """Regression: promote→equation was backslash-doubled by _sanitize_md_for_pdf."""
        md = "$$\n\\max F_{C}=1 \\tag{1}\n$$\n\nNext."
        # Pipeline used by convert_md_to_pdf (without promote).
        out = normalize_md_math_for_pandoc_export(md)
        out = _sanitize_md_for_pdf(out)
        self.assertIn("$$", out)
        self.assertIn(r"\tag{1}", out)
        self.assertIn(r"\max", out)
        # Must not double-escape math commands inside $$...$$.
        self.assertNotIn(r"\\max", out)
        self.assertNotIn(r"\\tag", out)
        self.assertNotIn(r"\begin{equation}", out)

    def test_pdf_sanitize_breaks_promoted_equation_without_math_guard(self):
        """Documents why convert_md_to_pdf must not promote to equation env."""
        md = "$$\n\\max F=1 \\tag{1}\n$$"
        promoted = promote_tagged_display_math_to_equation(md)
        sanitized = _sanitize_md_for_pdf(promoted)
        # Outside $$...$$, sanitize doubles backslashes → broken for XeLaTeX.
        self.assertIn(r"\\begin{equation}", sanitized)
        self.assertIn(r"\\max", sanitized)


if __name__ == "__main__":
    unittest.main()
