# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Regression: revision PDF download must not call layout PDFGenerator when
ENABLE_LAYOUT_PDF_GENERATION is False (default). See download_service.py
revision branch and _pandoc_pdf_file_response_from_md.

Also: markdown_based revision path must honor renderer_type=pandoc before
requiring layout_document (reflow PDF without MinerU layout).
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
            "renderer_type == \"pandoc\"",
            source,
            msg="Revision PDF path must honor renderer_type=pandoc and use Pandoc MD→PDF.",
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

    def test_markdown_revision_pandoc_before_layout_gate(self) -> None:
        """Reflow PDF with revisions must not 404 when layout_document is missing."""
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "download_service.py"
        )
        source = path.read_text(encoding="utf-8")
        marker = (
            "Reflow (pandoc) and overlay (typst) first — pandoc does not need layout_document."
        )
        start = source.find(marker)
        self.assertGreater(start, 0, msg="markdown revision reflow/layout order comment missing")
        region = source[start : start + 4000]
        pandoc_idx = region.find('renderer_type == "pandoc"')
        layout_gate_idx = region.find(
            "PDF file detected but layout_document not available"
        )
        self.assertGreater(pandoc_idx, 0, msg="pandoc branch missing after reflow marker")
        self.assertGreater(
            layout_gate_idx,
            0,
            msg="layout gate missing after reflow marker",
        )
        self.assertLess(
            pandoc_idx,
            layout_gate_idx,
            msg="renderer_type=pandoc must be handled before layout_document gate",
        )


if __name__ == "__main__":
    unittest.main()
