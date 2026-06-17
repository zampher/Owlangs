# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for MinerU image_data_map helpers."""

import io
import sys
import unittest
import zipfile
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.mineru_image_data_map import (
    lookup_image_data_entry,
    populate_image_data_map_from_mineru_zip,
)


class MineruImageDataMapTest(unittest.TestCase):
    def _build_nested_zip(self) -> bytes:
        buf = io.BytesIO()
        image_name = "4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg"
        nested = f"doc_hash/hybrid_auto/images/{image_name}"
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(nested, b"fake-jpeg-bytes")
        return buf.getvalue()

    def test_populate_registers_markdown_lookup_keys(self):
        image_data_map = {}
        task_state = {"layout_source_zip": self._build_nested_zip()}
        added = populate_image_data_map_from_mineru_zip(image_data_map, task_state)
        self.assertGreater(added, 0)
        entry = lookup_image_data_entry(
            image_data_map,
            "images/4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg",
        )
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertTrue(entry["data"].startswith("data:image/"))


if __name__ == "__main__":
    unittest.main()
