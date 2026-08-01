# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""When no overlay blocks exist, Typst overlay must still write output_path."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz

from layout.base import LayoutDocument, LayoutPage
from layout.pdf_renderer.config import PDFRendererConfig
from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer


class TestEmptyOverlayOutput(unittest.TestCase):
    def test_no_render_blocks_writes_output_path(self):
        with tempfile.TemporaryDirectory(prefix="owlangs_empty_overlay_") as tmp_dir:
            tmp = Path(tmp_dir)
            source_pdf = tmp / "source.pdf"
            output_pdf = tmp / "out_converted.pdf"

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "source")
            doc.save(str(source_pdf))
            doc.close()

            config = PDFRendererConfig(
                source_pdf_path=source_pdf,
                output_path=output_pdf,
            )
            renderer = TypstOverlayRenderer(config)
            layout_doc = LayoutDocument(
                pages=[LayoutPage(page_index=0, width=595.0, height=842.0, blocks=[])],
                engine="paddle",
            )

            pdf_bytes = renderer.render(layout_doc)

            self.assertTrue(
                output_pdf.is_file(),
                "output_path must be written on empty overlay",
            )
            self.assertGreater(output_pdf.stat().st_size, 0)
            self.assertEqual(pdf_bytes, output_pdf.read_bytes())
            self.assertEqual(pdf_bytes, source_pdf.read_bytes())


if __name__ == "__main__":
    unittest.main()
