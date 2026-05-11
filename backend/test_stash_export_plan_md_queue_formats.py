# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: queue/status stash plan lists MD + md_zip for TXT/XLSX/PPTX/EPUB/MOBI."""

import unittest
from pathlib import Path


class TestStashExportPlanMdQueueFormats(unittest.TestCase):
    def test_download_service_plan_includes_md_palette_for_five_formats(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        self.assertTrue(path.is_file(), msg=f"Missing {path}")
        text = path.read_text(encoding="utf-8")
        # Exact snippets from _build_stash_export_plan (must stay aligned with runtime behavior).
        self.assertIn(
            'elif wt == "txt":\n        for ft in ("html", "txt", "md"):',
            text,
        )
        self.assertIn(
            'elif wt == "xlsx":\n        plan.append(("xlsx", "xlsx", {}))\n'
            '        for ft in ("html", "md"):',
            text,
        )
        self.assertIn(
            'elif wt == "pptx":\n        for ft in ("pptx", "html", "md"):',
            text,
        )
        self.assertIn(
            'elif wt == "epub":\n        for ft in ("epub", "html", "md"):',
            text,
        )
        self.assertIn(
            'elif wt == "mobi":\n        plan.append(("mobi", "mobi", {}))\n'
            '        plan.append(("epub", "epub", {}))\n'
            '        for ft in ("html", "md"):',
            text,
        )

    def test_workflows_define_export_to_markdown(self) -> None:
        """Ensure HTML-based workflows delegate MD export to html_content_to_markdown."""
        backend_root = Path(__file__).resolve().parent
        workflow_root = backend_root / "workflow"
        expected_snippet = (
            "return html_content_to_markdown(self.export_to_html())"
        )
        for name in (
            "txt_workflow.py",
            "epub_workflow.py",
            "xlsx_workflow.py",
            "pptx_workflow.py",
            "mobi_workflow.py",
        ):
            path = workflow_root / name
            self.assertTrue(path.is_file(), msg=f"Missing {path}")
            body = path.read_text(encoding="utf-8")
            self.assertIn("def export_to_markdown", body, msg=name)
            self.assertIn(expected_snippet, body, msg=name)


if __name__ == "__main__":
    unittest.main()
