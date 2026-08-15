# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: PdfExportLatexError HTTP detail must reach the client.

On-demand reflow PDF rebuild used to catch all Exception (including HTTPException)
and replace Suspected-bad-segment detail with a generic rebuilt-Markdown message.
"""

from __future__ import annotations

import unittest
from pathlib import Path


class TestPdfExportHttpDetailPassthrough(unittest.TestCase):
    def test_download_service_rethrows_http_exception_on_pandoc_paths(self) -> None:
        src = Path(__file__).resolve().parent / "app" / "services" / "download" / "download_service.py"
        text = src.read_text(encoding="utf-8")
        marker = "Preserve PdfExportLatexError → Suspected bad segment detail for the UI."
        self.assertGreaterEqual(
            text.count(marker),
            2,
            "Both pandoc on-demand rebuild paths must re-raise HTTPException",
        )
        # Ensure the swallow-all pattern is not restored without the re-raise.
        # After each marker, the next non-comment statement should be `raise`.
        idx = 0
        found = 0
        while True:
            pos = text.find(marker, idx)
            if pos < 0:
                break
            found += 1
            tail = text[pos : pos + 120]
            self.assertIn("raise", tail)
            idx = pos + len(marker)
        self.assertEqual(found, text.count(marker))

    def test_user_detail_marker_for_frontend(self) -> None:
        from utils.pdf_export_failure_locator import build_pdf_export_user_detail

        detail = build_pdf_export_user_detail(26, "overfull_hbox_unbreakable")
        self.assertIn("Suspected bad segment: 26", detail)
        self.assertIn("片段 26", detail)


if __name__ == "__main__":
    unittest.main()
