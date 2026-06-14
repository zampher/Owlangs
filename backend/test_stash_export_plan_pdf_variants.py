# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: PDF markdown_based export plan includes preserve + reflow variants."""

import unittest
from pathlib import Path


class TestStashExportPlanPdfVariants(unittest.TestCase):
    def test_markdown_based_pdf_plan_snippets(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            'plan.append(("pdf", "pdf", {"renderer_type": "typst_overlay"}))',
            text,
        )
        self.assertIn(
            'plan.append(("pdf_reflow", "pdf", {"renderer_type": "pandoc"}))',
            text,
        )
        self.assertIn('def _pdf_stash_key_for_download', text)


if __name__ == "__main__":
    unittest.main()
