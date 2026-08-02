# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Queued stash plan must not pre-generate embedded single-file MD for layout PDFs."""

from __future__ import annotations

import unittest
from pathlib import Path


class TestStashSkipEmbeddedMd(unittest.TestCase):
    def test_markdown_based_plan_marks_embedded_md_stash_skip(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "app"
            / "services"
            / "download"
            / "download_service.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn('"_stash_skip": True', text)
        self.assertIn(
            'for ft in ("docx", "html"):',
            text,
        )
        self.assertIn('get("_stash_skip")', text)


if __name__ == "__main__":
    unittest.main()
