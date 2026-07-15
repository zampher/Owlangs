# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay visual image placement."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer
from layout.pdf_renderer.typst_overlay.visual_images import (
    PADDLE_SOURCE_PDF_IMAGE_SENTINEL,
    collect_paddle_source_pdf_image_placements,
    collect_visual_image_placements,
    extract_image_bytes_from_pdf_region,
    is_paddle_source_pdf_image_path,
    lookup_image_bytes,
    extract_equation_content,
    extract_equation_image_path,
)


class TestVisualImagePlacements(unittest.TestCase):
    def test_lookup_image_bytes_by_basename(self):
        image_map = {"images/abc123.jpg": b"payload"}
        self.assertEqual(lookup_image_bytes(image_map, "abc123.jpg"), b"payload")

    def test_collect_chart_placements_when_format_image(self):
        chart_block = SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path=None,
            is_equation=lambda: False,
            raw={
                "blocks": [
                    {
                        "type": "chart_body",
                        "bbox": [110.0, 441.0, 302.0, 610.0],
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "chart",
                                        "image_path": "394134b7dae435ee.jpg",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=5, blocks=[chart_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"394134b7dae435ee.jpg": b"chart-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="image",
            table_body_format="html",
            image_data_map=image_map,
        )

        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].block_index, 82)
        self.assertEqual(placements[0].block_type, "chart")
        self.assertEqual(placements[0].page_index, 5)

    def test_skip_chart_placements_when_format_html(self):
        chart_block = SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path="394134b7dae435ee.jpg",
            is_equation=lambda: False,
            raw={"blocks": []},
        )
        page = SimpleNamespace(page_index=5, blocks=[chart_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"394134b7dae435ee.jpg": b"chart-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="html",
            table_body_format="html",
            image_data_map=image_map,
        )

        self.assertEqual(placements, [])

    def test_collect_equation_placements_when_format_image(self):
        eq_block = SimpleNamespace(
            type="interline_equation",
            index=35,
            bbox=(100.0, 200.0, 500.0, 240.0),
            image_path=None,
            is_equation=lambda: True,
            raw={
                "lines": [
                    {
                        "spans": [
                            {
                                "type": "interline_equation",
                                "image_path": "eqhash123.jpg",
                                "content": "L_1(U)=...",
                            }
                        ]
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=1, blocks=[eq_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"eqhash123.jpg": b"equation-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="image",
            table_body_format="html",
            equation_format="image",
            image_data_map=image_map,
        )

        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].block_index, 35)
        self.assertEqual(placements[0].block_type, "equation")
        self.assertEqual(extract_equation_image_path(eq_block), "eqhash123.jpg")

    def test_collect_layout_image_placements(self):
        image_block = SimpleNamespace(
            type="image",
            index=12,
            bbox=(50.0, 80.0, 250.0, 280.0),
            image_path="banner_photo.jpg",
            is_equation=lambda: False,
        )
        page = SimpleNamespace(page_index=0, blocks=[image_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"banner_photo.jpg": b"photo-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="image",
            table_body_format="html",
            equation_format="text",
            image_data_map=image_map,
        )

        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].block_index, 12)
        self.assertEqual(placements[0].block_type, "image")
        self.assertEqual(placements[0].page_index, 0)

    def test_skip_equation_placements_when_format_text(self):
        eq_block = SimpleNamespace(
            type="interline_equation",
            index=35,
            bbox=(100.0, 200.0, 500.0, 240.0),
            image_path="eqhash123.jpg",
            is_equation=lambda: True,
            raw={},
        )
        page = SimpleNamespace(page_index=1, blocks=[eq_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"eqhash123.jpg": b"equation-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="image",
            table_body_format="html",
            equation_format="text",
            image_data_map=image_map,
        )

        self.assertEqual(placements, [])

    def test_append_visual_images_writes_into_work_dir(self):
        table_block = SimpleNamespace(
            type="table",
            index=68,
            bbox=(76.0, 639.0, 295.0, 738.0),
            image_path=None,
            is_equation=lambda: False,
            raw={
                "blocks": [
                    {
                        "type": "table_body",
                        "bbox": [76.0, 639.0, 295.0, 738.0],
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "table",
                                        "image_path": "7fd5c0d0ae5e5fe06ac5bfa7c4c0b44aaa22355dfff50d590e0124085837b301.jpg",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=3, blocks=[table_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {
            "7fd5c0d0ae5e5fe06ac5bfa7c4c0b44aaa22355dfff50d590e0124085837b301.jpg": b"table-jpg",
        }
        render_blocks_by_page: dict = {}

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            renderer = TypstOverlayRenderer.__new__(TypstOverlayRenderer)
            renderer.config = SimpleNamespace(
                chart_body_format="image",
                table_body_format="image",
                equation_format="text",
            )
            extra_redaction, embedded_ids = renderer._append_visual_image_render_blocks(
                layout_doc,
                render_blocks_by_page,
                work_dir=work_dir,
                image_data_map=image_map,
            )
            # Image format preserves original PDF — no embed or extra redaction.
            self.assertEqual(extra_redaction, {})
            self.assertEqual(embedded_ids, set())
            self.assertEqual(render_blocks_by_page, {})

    def test_append_visual_images_skips_chart_equation_when_image_format(self):
        chart_block = SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path=None,
            is_equation=lambda: False,
            raw={
                "blocks": [
                    {
                        "type": "chart_body",
                        "bbox": [110.0, 441.0, 302.0, 610.0],
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "chart",
                                        "image_path": "chart.jpg",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
        eq_block = SimpleNamespace(
            type="interline_equation",
            index=35,
            bbox=(100.0, 200.0, 500.0, 240.0),
            image_path=None,
            is_equation=lambda: True,
            raw={
                "lines": [
                    {
                        "spans": [
                            {
                                "type": "interline_equation",
                                "image_path": "eq.jpg",
                            }
                        ]
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=0, blocks=[chart_block, eq_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"chart.jpg": b"chart", "eq.jpg": b"eq"}
        render_blocks_by_page: dict = {}

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            renderer = TypstOverlayRenderer.__new__(TypstOverlayRenderer)
            renderer.config = SimpleNamespace(
                chart_body_format="image",
                table_body_format="html",
                equation_format="image",
            )
            extra_redaction, embedded_ids = renderer._append_visual_image_render_blocks(
                layout_doc,
                render_blocks_by_page,
                work_dir=work_dir,
                image_data_map=image_map,
            )
            self.assertEqual(extra_redaction, {})
            self.assertEqual(embedded_ids, set())
            self.assertEqual(render_blocks_by_page, {})


    def test_extract_equation_content_reads_paddle_block_content(self):
        eq_block = SimpleNamespace(
            type="interline_equation",
            index=3,
            text=None,
            raw={"block_content": r"\mathcal{L} = \|x\|^2"},
            is_equation=lambda: True,
        )
        self.assertEqual(
            extract_equation_content(eq_block),
            r"\mathcal{L} = \|x\|^2",
        )


class TestPaddleSourcePdfImages(unittest.TestCase):
    def test_is_paddle_source_pdf_image_path(self):
        self.assertTrue(is_paddle_source_pdf_image_path(PADDLE_SOURCE_PDF_IMAGE_SENTINEL))
        self.assertFalse(is_paddle_source_pdf_image_path("photo.jpg"))

    def test_collect_paddle_source_pdf_image_placements(self):
        image_block = SimpleNamespace(
            type="image",
            index=12,
            bbox=(50.0, 80.0, 250.0, 280.0),
            image_path=PADDLE_SOURCE_PDF_IMAGE_SENTINEL,
            is_equation=lambda: False,
        )
        text_block = SimpleNamespace(
            type="text",
            index=13,
            bbox=(10.0, 10.0, 100.0, 30.0),
            image_path=None,
            is_equation=lambda: False,
        )
        page = SimpleNamespace(page_index=0, blocks=[image_block, text_block])
        layout_doc = SimpleNamespace(pages=[page])

        placements = collect_paddle_source_pdf_image_placements(layout_doc)

        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].block_index, 12)
        self.assertEqual(placements[0].block_type, "image")

    def test_append_paddle_images_extracts_from_source_pdf(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF required")

        image_block = SimpleNamespace(
            type="image",
            index=7,
            bbox=(40.0, 50.0, 140.0, 150.0),
            image_path=PADDLE_SOURCE_PDF_IMAGE_SENTINEL,
            is_equation=lambda: False,
        )
        page = SimpleNamespace(page_index=0, blocks=[image_block])
        layout_doc = SimpleNamespace(pages=[page])
        render_blocks_by_page: dict = {}

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            pdf_path = work_dir / "source.pdf"
            doc = fitz.open()
            page_obj = doc.new_page(width=300, height=400)
            page_obj.draw_rect(fitz.Rect(40, 50, 140, 150), fill=(0.2, 0.6, 0.9))
            doc.save(pdf_path)
            doc.close()

            renderer = TypstOverlayRenderer.__new__(TypstOverlayRenderer)
            renderer.config = SimpleNamespace(
                chart_body_format="image",
                table_body_format="html",
                equation_format="text",
            )
            extra_redaction, embedded_ids = renderer._append_visual_image_render_blocks(
                layout_doc,
                render_blocks_by_page,
                work_dir=work_dir,
                image_data_map={},
                source_pdf_path=pdf_path,
            )

            self.assertEqual(embedded_ids, {7})
            self.assertEqual(len(extra_redaction.get(0, [])), 1)
            self.assertEqual(len(render_blocks_by_page.get(0, [])), 1)
            self.assertEqual(
                render_blocks_by_page[0][0].image_rel_path,
                "images/paddle_img_7.png",
            )
            self.assertTrue((work_dir / "images" / "paddle_img_7.png").exists())

    def test_extract_image_bytes_from_pdf_region(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF required")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "page.pdf"
            doc = fitz.open()
            page_obj = doc.new_page(width=200, height=200)
            page_obj.draw_rect(fitz.Rect(20, 30, 80, 90), fill=(1, 0, 0))
            doc.save(pdf_path)
            doc.close()

            png_bytes = extract_image_bytes_from_pdf_region(
                pdf_path,
                0,
                (20.0, 30.0, 80.0, 90.0),
            )
            self.assertIsNotNone(png_bytes)
            self.assertTrue(png_bytes.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
