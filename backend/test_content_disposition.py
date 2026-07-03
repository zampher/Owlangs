# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for RFC 5987 Content-Disposition header builder."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from utils.http_content_disposition import (  # noqa: E402
    apply_content_disposition_header,
    build_content_disposition_header,
    bytes_download_response,
    file_download_response,
)


class TestContentDispositionHeader(unittest.TestCase):
    def test_ascii_filename(self) -> None:
        header = build_content_disposition_header("report_translated.pdf")
        self.assertEqual(
            header,
            'attachment; filename="report_translated.pdf"',
        )
        header.encode("latin-1")

    def test_chinese_filename_uses_rfc5987(self) -> None:
        filename = "6_PDFsam_尿素吸附_translated.pdf"
        header = build_content_disposition_header(filename)
        self.assertTrue(header.startswith("attachment;"))
        self.assertIn('filename="', header)
        self.assertIn("filename*=UTF-8''", header)
        self.assertIn("6_PDFsam_", header)
        self.assertIn("_translated.pdf", header)
        header.encode("latin-1")

    def test_inline_disposition(self) -> None:
        header = build_content_disposition_header(
            "预览.html",
            disposition="inline",
        )
        self.assertTrue(header.startswith("inline;"))
        header.encode("latin-1")

    def test_multilingual_filenames(self) -> None:
        samples = [
            "レポート_translated.pdf",  # Japanese
            "تقرير_translated.pdf",  # Arabic
            "Rapport_traduit.pdf",  # French (ASCII)
            "Документ_translated.pdf",  # Cyrillic
            "報告書_翻訳.pdf",  # CJK mix
        ]
        for filename in samples:
            with self.subTest(filename=filename):
                header = build_content_disposition_header(filename)
                header.encode("latin-1")
                if filename.isascii():
                    self.assertNotIn("filename*=", header)
                else:
                    self.assertIn("filename*=UTF-8''", header)


class TestDownloadResponseHelpers(unittest.TestCase):
    def test_file_download_response_overrides_starlette_header(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            resp = file_download_response(
                path=path,
                filename="6_PDFsam_尿素吸附_translated.pdf",
                media_type="application/pdf",
            )
            header = resp.headers["Content-Disposition"]
            self.assertIn("filename*=UTF-8''", header)
            self.assertIn('filename="', header)
            header.encode("latin-1")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_bytes_download_response_inline(self) -> None:
        resp = bytes_download_response(
            b"png-bytes",
            filename="原文_预览.png",
            media_type="image/png",
            disposition="inline",
        )
        header = resp.headers["Content-Disposition"]
        self.assertTrue(header.startswith("inline;"))
        header.encode("latin-1")

    def test_apply_content_disposition_header(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            path = tmp.name
        try:
            resp = file_download_response(path=path, filename="doc.html")
            apply_content_disposition_header(resp, "对照_预览.html", disposition="inline")
            header = resp.headers["Content-Disposition"]
            self.assertTrue(header.startswith("inline;"))
            self.assertIn("filename*=UTF-8''", header)
            header.encode("latin-1")
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
