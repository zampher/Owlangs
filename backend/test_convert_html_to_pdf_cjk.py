# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: HTML→PDF export enables xeCJK for CJK content."""

import unittest
from pathlib import Path


class TestConvertHtmlToPdfCjk(unittest.TestCase):
    def test_convert_html_to_pdf_uses_xecjk_helpers(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "utils"
            / "format_convert_utils.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("def _should_use_xecjk_for_pdf", text)
        self.assertIn("def _pandoc_pdf_header_includes", text)
        self.assertIn("header-includes={current_header}", text)

    def test_cjk_detection_from_content(self) -> None:
        from utils.format_convert_utils import (
            _resolve_mainfont_for_pdf,
            _resolve_pandoc_lang_for_pdf,
            _should_use_xecjk_for_pdf,
        )

        sample = '<html lang="en"><body><h1>文档标题</h1></body></html>'
        self.assertTrue(_should_use_xecjk_for_pdf(None, sample))
        self.assertIn("YaHei", _resolve_mainfont_for_pdf(None, sample))
        self.assertEqual(_resolve_pandoc_lang_for_pdf(None, sample), "zh-CN")

    def test_en_target_with_chinese_content_uses_separate_cjk_font(self) -> None:
        from utils.format_convert_utils import (
            _pandoc_pdf_header_includes,
            _resolve_cjk_mainfont_for_pdf,
            _resolve_mainfont_for_pdf,
            _should_use_xecjk_for_pdf,
        )

        sample = '<html><body><h1>Document Title</h1><p>未翻译的中文段落</p></body></html>'
        self.assertTrue(_should_use_xecjk_for_pdf("en", sample))
        self.assertEqual(_resolve_mainfont_for_pdf("en", sample), "Calibri")
        self.assertIn("YaHei", _resolve_cjk_mainfont_for_pdf("en", sample))
        header, _ = _pandoc_pdf_header_includes(
            "Calibri",
            True,
            cjk_mainfont=_resolve_cjk_mainfont_for_pdf("en", sample),
        )
        self.assertIn("setCJKmainfont{Microsoft YaHei}", header)
        self.assertNotIn("setCJKmainfont{Calibri}", header)

    def test_pandoc_lang_overrides_html_en(self) -> None:
        from utils.format_convert_utils import _resolve_pandoc_lang_for_pdf

        self.assertEqual(_resolve_pandoc_lang_for_pdf("en", None), "")
        self.assertEqual(_resolve_pandoc_lang_for_pdf("zh", None), "zh-CN")


if __name__ == "__main__":
    unittest.main()
