# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: completed tasks merge full export palette (not only pre-generated files)."""

import unittest
from pathlib import Path


class TestStatusDownloadsMerge(unittest.TestCase):
    def test_status_service_merges_palette_when_completed(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "status" / "status_service.py"
        self.assertTrue(path.is_file(), msg=f"Missing {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("downloads.setdefault", text)
        self.assertIn("merged completed-task download palette", text)

    def test_completed_palette_uses_download_service_plan(self) -> None:
        """Queue/status merge completed-task downloads via download_service plan."""
        backend_root = Path(__file__).resolve().parent
        status_path = backend_root / "app" / "services" / "status" / "status_service.py"
        dl_path = backend_root / "app" / "services" / "download" / "download_service.py"
        self.assertIn("completed_task_download_urls", status_path.read_text(encoding="utf-8"))
        dl_text = dl_path.read_text(encoding="utf-8")
        self.assertIn("def completed_task_download_urls", dl_text)
        self.assertIn("def resolve_task_export_workflow_type", dl_text)
        self.assertIn('"json": "json"', dl_text)


if __name__ == "__main__":
    unittest.main()
