# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: HTML workflow PDF uses a single fast export path."""

import unittest
from pathlib import Path


class TestHtmlWorkflowPdfFastPath(unittest.TestCase):
    def test_download_service_has_html_pdf_fast_path(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "download_service.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("HTML workflow PDF fast path", text)
        self.assertIn("_html_workflow_pdf_response", text)

    def test_resolve_translated_html_prefers_export_to_html(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "download_service.py"
        )
        text = path.read_text(encoding="utf-8")
        idx = text.index("def _resolve_translated_html_for_export")
        block = text[idx : idx + 2200]
        export_pos = block.find("workflow.export_to_html")
        rebuild_pos = block.find("_rebuild_html_from_task_state")
        self.assertGreater(export_pos, 0)
        self.assertGreater(rebuild_pos, 0)
        self.assertLess(export_pos, rebuild_pos)

    def test_convert_only_uses_source_html(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "download_service.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("_is_html_convert_only_task", text)
        self.assertIn("_export_html_from_original", text)
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "output_generator.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn('elif workflow_type == "html":', text)
        idx = text.index('elif workflow_type == "html":')
        block = text[idx : idx + 2000]
        self.assertIn("to_lang=to_lang", block)


if __name__ == "__main__":
    unittest.main()
