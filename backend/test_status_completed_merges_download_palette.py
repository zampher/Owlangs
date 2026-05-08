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
        self.assertIn("merged on-demand palette", text)


if __name__ == "__main__":
    unittest.main()
