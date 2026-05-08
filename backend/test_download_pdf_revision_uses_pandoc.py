# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Regression: revision PDF download must not call layout PDFGenerator when
ENABLE_LAYOUT_PDF_GENERATION is False (default). See download_service.py
revision branch and _pandoc_pdf_file_response_from_md.
"""

import ast
import unittest
from pathlib import Path


class TestDownloadPdfRevisionPandocPath(unittest.TestCase):
    def test_download_service_has_layout_flag_branch_for_revision_pdf(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        self.assertTrue(path.is_file(), msg=f"Missing {path}")
        source = path.read_text(encoding="utf-8")
        self.assertIn(
            "ENABLE_LAYOUT_PDF_GENERATION",
            source,
            msg="Revision PDF path must branch on ENABLE_LAYOUT_PDF_GENERATION so Pandoc is used when flag is False.",
        )
        self.assertIn(
            "_pandoc_pdf_file_response_from_md",
            source,
            msg="Pandoc MD→PDF helper must be used for revision downloads when layout path is off.",
        )
        tree = ast.parse(source)
        names = {
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn(
            "_pandoc_pdf_file_response_from_md",
            names,
            msg="Module-level helper _pandoc_pdf_file_response_from_md must exist.",
        )


if __name__ == "__main__":
    unittest.main()
