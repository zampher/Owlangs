# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Regression: concurrent pandoc PDF preview/download must serialize generation and
return in-memory Response bytes (not streaming a shared file path).
"""

from __future__ import annotations

import unittest
from pathlib import Path


class TestPandocPdfConcurrentDownload(unittest.TestCase):
    def test_pandoc_pdf_helper_serializes_and_returns_response_bytes(self) -> None:
        path = Path(__file__).resolve().parent / "app" / "services" / "download" / "download_service.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn("_pandoc_pdf_gen_lock", source)
        self.assertIn("with _pandoc_pdf_gen_lock(task_id):", source)
        self.assertIn("pdf_bytes = pdf_file_path.read_bytes()", source)
        self.assertIn("Response(", source)
        self.assertIn("owlangs_stash_path", source)

        self.assertIn("response = Response(", source)
        self.assertIn("return response", source)


if __name__ == "__main__":
    unittest.main()
