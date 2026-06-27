# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Pytest wrapper for test/png MinerU overlay fixture."""

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from tools.test_png_mineru_overlay import (  # noqa: E402
    DEFAULT_LAYOUT_JSON,
    build_segments_from_mineru_table_html,
    run_overlay_test,
)


class TestPngMineruOverlay(unittest.TestCase):
    def test_layout_fixture_builds_segments(self):
        from layout.mineru_layout_model import parse_layout_json
        from layout.image_overlay.block_text_map import _resolve_table_block_html

        if not DEFAULT_LAYOUT_JSON.is_file():
            self.skipTest(f"fixture missing: {DEFAULT_LAYOUT_JSON}")

        layout_doc = parse_layout_json(DEFAULT_LAYOUT_JSON)
        table_block = layout_doc.pages[0].blocks[0]
        table_html = _resolve_table_block_html(table_block)
        segments = build_segments_from_mineru_table_html(table_html)
        self.assertGreaterEqual(len(segments), 10)
        sources = " ".join(seg["source_text"] for seg in segments)
        self.assertIn("UNIT 20-01", sources)
        self.assertIn("PUTERI HARBOUR", sources)

    def test_overlay_render_and_validation(self):
        if not DEFAULT_LAYOUT_JSON.is_file():
            self.skipTest(f"fixture missing: {DEFAULT_LAYOUT_JSON}")

        validation = run_overlay_test(
            DEFAULT_LAYOUT_JSON,
            allow_synthetic=True,
        )
        self.assertTrue(
            validation.passed,
            msg=f"overlay validation failed: {validation.errors}",
        )
        self.assertGreaterEqual(validation.metrics.get("renderer_drawn_count", 0), 1)
        self.assertGreaterEqual(validation.metrics.get("bbox_subdivided_count", 0), 2)


if __name__ == "__main__":
    unittest.main()
