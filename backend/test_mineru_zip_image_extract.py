# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for MinerU nested ZIP image path resolution."""

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

from layout.pdf_renderer.shared.block_processor import BlockProcessor
from utils.image_placeholder_utils import materialize_markdown_images_from_zip


class MineruZipImageExtractTest(unittest.TestCase):
    def _build_nested_zip(self) -> bytes:
        buf = io.BytesIO()
        image_name = "4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg"
        nested = f"doc_hash/hybrid_auto/images/{image_name}"
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(nested, b"fake-jpeg-bytes")
        return buf.getvalue()

    def test_extract_image_from_zip_by_basename(self):
        zip_bytes = self._build_nested_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            data = BlockProcessor.extract_image_from_zip(
                zf, f"images/4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg"
            )
        self.assertEqual(data, b"fake-jpeg-bytes")

    def test_materialize_markdown_images_from_zip(self):
        zip_bytes = self._build_nested_zip()
        md = "![fig](images/4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg)"
        out_dir = Path(self._build_nested_zip.__name__)  # dummy, use temp
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp)
            new_md, saved = materialize_markdown_images_from_zip(md, zip_bytes, out_path)
            self.assertEqual(len(saved), 1)
            self.assertIn("./images/", new_md)
            self.assertTrue(saved[0].exists())


if __name__ == "__main__":
    unittest.main()
