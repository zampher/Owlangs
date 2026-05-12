# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: XLSX MD must use HTML-table pipeline, not segment rebuild (loses tables)."""

import unittest
from pathlib import Path


class TestXlsxMdDownloadSkipsSegmentRebuild(unittest.TestCase):
    def test_download_service_skips_segment_md_for_xlsx(self) -> None:
        backend_root = Path(__file__).resolve().parent
        dl_path = backend_root / "app" / "services" / "download" / "download_service.py"
        text = dl_path.read_text(encoding="utf-8")
        self.assertIn("skip_segment_md_for_tables", text)
        self.assertIn('wt_export == "xlsx"', text)
        self.assertIn("html_content_to_markdown", text)
        self.assertIn("xlsx MD from saved HTML", text)

    def test_output_generator_skips_segment_md_for_xlsx(self) -> None:
        backend_root = Path(__file__).resolve().parent
        og_path = backend_root / "app" / "services" / "download" / "output_generator.py"
        text = og_path.read_text(encoding="utf-8")
        self.assertIn("skip_segment_md_for_tables", text)
        self.assertIn("Markdown built from saved translated HTML", text)


if __name__ == "__main__":
    unittest.main()
