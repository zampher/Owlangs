# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: HTML workflow stash plan includes PDF variants for queue download."""

import unittest
from pathlib import Path


class TestStashExportPlanHtmlPdf(unittest.TestCase):
    def test_html_workflow_plan_includes_single_html_pdf(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            'if wt == "html":\n'
            '            plan.append(("pdf", "pdf", {"renderer_type": "html"}))',
            text,
        )
        self.assertNotIn(
            'if wt == "html":\n'
            '            plan.append(("pdf", "pdf", {"renderer_type": "html"}))\n'
            '            plan.append(("pdf_reflow", "pdf", {"renderer_type": "pandoc"}))',
            text,
        )

    def test_build_plan_for_html_task(self) -> None:
        from backend.app.services.download.download_service import _build_stash_export_plan

        plan = _build_stash_export_plan(
            {
                "original_filename": "page.html",
                "workflow_type": "html",
                "translation_segments": {"segments": [{"segment_index": 0}]},
            }
        )
        keys = [item[0] for item in plan]
        self.assertIn("pdf", keys)
        self.assertNotIn("pdf_reflow", keys)
        pdf_kwargs = next(kwargs for key, _, kwargs in plan if key == "pdf")
        self.assertEqual(pdf_kwargs.get("renderer_type"), "html")


if __name__ == "__main__":
    unittest.main()
