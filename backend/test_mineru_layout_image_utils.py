# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for MinerU layout helpers and PNG/image rebuild promotion."""

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.mineru_layout_utils import (
    is_mineru_layout_image,
    is_mineru_layout_source,
    is_original_image_format_request,
    needs_mineru_zip_restore,
    original_image_download_extension,
)


class MineruLayoutUtilsTest(unittest.TestCase):
    def test_image_extensions_detected(self):
        self.assertTrue(is_mineru_layout_image("scan.PNG"))
        self.assertTrue(is_mineru_layout_image("photo.jpg"))
        self.assertFalse(is_mineru_layout_image("notes.md"))

    def test_layout_source_includes_pdf_and_images(self):
        self.assertTrue(is_mineru_layout_source("paper.pdf"))
        self.assertTrue(is_mineru_layout_source("figure.jpeg"))
        self.assertFalse(is_mineru_layout_source("readme.txt"))

    def test_needs_mineru_zip_restore_matches_layout_sources(self):
        self.assertTrue(needs_mineru_zip_restore("doc.pdf"))
        self.assertTrue(needs_mineru_zip_restore("chart.png"))
        self.assertFalse(needs_mineru_zip_restore("article.html"))

    def test_original_image_download_extension(self):
        self.assertEqual(original_image_download_extension("scan.PNG"), "png")
        self.assertIsNone(original_image_download_extension("notes.md"))

    def test_is_original_image_format_request(self):
        self.assertTrue(is_original_image_format_request("png", "figure.png"))
        self.assertTrue(is_original_image_format_request("jpeg", "photo.jpg"))
        self.assertFalse(is_original_image_format_request("pdf", "figure.png"))


if __name__ == "__main__":
    unittest.main()
