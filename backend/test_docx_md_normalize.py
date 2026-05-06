"""Tests for DOCX Markdown <sup>/<sub> normalization."""

import unittest

from utils.docx_md_normalize import normalize_docx_markdown_sup_sub


class TestDocxMdNormalize(unittest.TestCase):
    def test_author_line_superscripts(self):
        src = (
            "云 李<sup>1</sup> | 志宏 黄<sup>2</sup> | tubs 辰<sup>1,2</sup>"
        )
        out = normalize_docx_markdown_sup_sub(src)
        self.assertIn("¹", out)
        self.assertIn("²", out)
        self.assertIn("¹,²", out)
        self.assertNotIn("<sup>", out)

    def test_subscript_digits(self):
        src = "H<sub>2</sub>O and CO<sub>2</sub>"
        out = normalize_docx_markdown_sup_sub(src)
        self.assertIn("H₂O", out)
        self.assertIn("CO₂", out)

    def test_unknown_sup_preserved_for_raw_html(self):
        src = r"note<sup>*</sup> end"
        out = normalize_docx_markdown_sup_sub(src)
        self.assertIn("<sup>", out)

    def test_skips_fenced_code(self):
        src = "```\nX<sup>2</sup>\n```\nY<sup>2</sup>"
        out = normalize_docx_markdown_sup_sub(src)
        self.assertIn("<sup>2</sup>", out)
        self.assertIn("Y²", out)


if __name__ == "__main__":
    unittest.main()
