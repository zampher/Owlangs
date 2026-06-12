# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: preview=1 serves HTML inline for compare reader iframes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from starlette.responses import FileResponse

from backend.app.routes.service.app_routes_download import _apply_inline_preview_headers


class TestDownloadPreviewInline(unittest.TestCase):
    def test_apply_inline_preview_headers_for_html(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            path = tmp.name
        try:
            resp = FileResponse(path=path, filename="doc.html")
            _apply_inline_preview_headers(resp, "html", True)
            self.assertEqual(
                resp.headers["Content-Disposition"],
                'inline; filename="doc.html"',
            )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_skip_inline_for_pdf(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        try:
            resp = FileResponse(path=path, filename="doc.pdf")
            _apply_inline_preview_headers(resp, "pdf", True)
            self.assertNotIn(
                "inline",
                resp.headers.get("Content-Disposition", "").lower(),
            )
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
