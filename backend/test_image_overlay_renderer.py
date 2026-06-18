# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Unit tests for image overlay rendering."""

import io
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from PIL import Image, ImageDraw, ImageFont

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.image_overlay.debug_output import (
    resolve_image_overlay_debug_dir,
    write_image_overlay_debug,
)
from layout.image_overlay.models import ImageOverlayConfig, ImageOverlayInput
from layout.image_overlay.pipeline import ImageOverlayPipeline
from layout.image_overlay.renderer import (
    _bbox_font_cap_px,
    _coord_scale_factors,
    _fit_text_lines,
    _image_px_to_pt,
    _plain_overlay_text,
    _preferred_font_size_px,
    _pt_to_image_px,
    _sample_cover_color,
    _scale_bbox_to_image,
    _user_font_size_px_from_pt,
    _wrap_text_for_bbox,
    dry_run_overlay_font_size_pt,
    font_loader_for_family,
)


class ImageOverlayRendererTest(unittest.TestCase):
    def test_debug_output_writes_under_temp_debug(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            debug_dir = resolve_image_overlay_debug_dir(tmp)
            self.assertIsNotNone(debug_dir)
            assert debug_dir is not None
            json_path, txt_path = write_image_overlay_debug(
                debug_dir,
                task_id="abc123",
                source_image_path=r"C:\fake\source.jpg",
                image_size=(800, 600),
                output_format="jpg",
                page_dimensions=(800.0, 600.0),
                coord_scale=(1.0, 1.0),
                drawn_blocks=[
                    {
                        "block_index": 1,
                        "block_type": "text",
                        "page_index": 0,
                        "layout_bbox": [10.0, 20.0, 100.0, 40.0],
                        "image_bbox": [10, 20, 100, 40],
                        "layout_text": "Hello",
                        "overlay_text": "你好",
                        "plain_text": "你好",
                        "mineru_font_size_pt": 12.0,
                        "user_font_size_pt": None,
                        "estimated_font_size_pt": 11.0,
                        "preferred_font_size_px": 16.0,
                    }
                ],
                skipped_blocks=[],
            )
            self.assertTrue(json_path and Path(json_path).is_file())
            self.assertTrue(txt_path and Path(txt_path).is_file())
            self.assertEqual(
                Path(tmp) / "debug" / "image_overlay" / "overlay_blocks.json",
                Path(json_path),
            )

    def test_coord_scale_when_page_size_differs_from_image(self):
        page = LayoutPage(
            page_index=0,
            width=200.0,
            height=100.0,
            blocks=[],
        )
        sx, sy = _coord_scale_factors(page, (400, 200))
        self.assertAlmostEqual(sx, 2.0)
        self.assertAlmostEqual(sy, 2.0)
        bbox = _scale_bbox_to_image((10.0, 10.0, 90.0, 40.0), page, (400, 200))
        self.assertEqual(bbox, (20, 20, 180, 80))

    def test_sample_cover_color_picks_brightest_pixel_in_strips(self):
        image = Image.new("RGB", (120, 40), color=(200, 200, 200))
        pixels = image.load()
        for y in range(10, 30):
            for x in range(27, 30):
                pixels[x, y] = (40, 40, 40)
            pixels[28, y] = (245, 245, 245)
            for x in range(70, 73):
                pixels[x, y] = (30, 30, 30)

        bbox = (30, 10, 70, 30)
        self.assertEqual(_sample_cover_color(image, bbox, "max"), (245, 245, 245))

    def test_sample_cover_color_picks_darkest_pixel_in_strips(self):
        image = Image.new("RGB", (120, 40), color=(200, 200, 200))
        pixels = image.load()
        for y in range(10, 30):
            for x in range(27, 30):
                pixels[x, y] = (40, 40, 40)
            pixels[28, y] = (245, 245, 245)
            for x in range(70, 73):
                pixels[x, y] = (30, 30, 30)

        bbox = (30, 10, 70, 30)
        self.assertEqual(_sample_cover_color(image, bbox, "min"), (30, 30, 30))

    def test_sample_cover_color_uses_average_pixel_in_strips(self):
        image = Image.new("RGB", (120, 40), color=(200, 200, 200))
        pixels = image.load()
        for y in range(10, 30):
            for x in range(27, 30):
                pixels[x, y] = (100, 100, 100)
            for x in range(70, 73):
                pixels[x, y] = (200, 200, 200)

        bbox = (30, 10, 70, 30)
        self.assertEqual(_sample_cover_color(image, bbox, "avg"), (150, 150, 150))

    def test_plain_overlay_text_preserves_ocr_line_breaks(self):
        raw = (
            "1/01, JALAN MOLEK 1/8, TAMAN MOLEK, 81100 JOHOR BAHRU, JOHOR D.T.\n"
            "TEL: 07-3554 308 FAX: 07-3511 694"
        )
        plain = _plain_overlay_text(raw)
        self.assertIn("\n", plain)
        self.assertEqual(plain.count("\n"), 1)
        self.assertTrue(plain.startswith("1/01,"))
        self.assertTrue(plain.endswith("07-3511 694"))

    def test_plain_overlay_text_preserves_spacing_and_markup(self):
        raw = "Hello   world\n**bold**  line"
        plain = _plain_overlay_text(raw)
        self.assertEqual(plain, raw)

    def test_plain_overlay_text_normalizes_line_endings_only(self):
        plain = _plain_overlay_text("a\r\nb\rc")
        self.assertEqual(plain, "a\nb\nc")

    def test_wrap_text_for_bbox_respects_embedded_newlines(self):
        image = Image.new("RGB", (400, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        text = "line one\nline two"
        lines = _wrap_text_for_bbox(text, font, 300, draw)
        self.assertGreaterEqual(len(lines), 2)
        self.assertEqual(lines[0], "line one")
        self.assertEqual(lines[1], "line two")

    def test_preferred_font_size_capped_by_bbox_height(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(3.0, 61.0, 18.0, 64.0),
            type="text",
            index=4,
            text="ARCHITECT :",
        )
        page = LayoutPage(page_index=0, width=111.0, height=327.0, blocks=[])
        bbox = (8, 170, 50, 178)
        preferred_px, bbox_cap_px = _preferred_font_size_px(
            block,
            page,
            (309, 910),
            bbox,
            "建筑师：",
            None,
        )
        self.assertAlmostEqual(bbox_cap_px, 8 * 0.9, places=2)
        self.assertLessEqual(preferred_px, bbox_cap_px)
        self.assertGreater(preferred_px, 3.0)

    def test_preferred_font_size_user_not_capped_by_bbox(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(0.0, 0.0, 100.0, 20.0),
            type="text",
            index=1,
            text="Sample",
        )
        page = LayoutPage(page_index=0, width=100.0, height=100.0, blocks=[])
        bbox = (10, 10, 90, 18)
        cap_px = _bbox_font_cap_px(bbox, "Sample text")
        _, sy = _coord_scale_factors(page, (100, 100))
        user_px, returned_cap = _preferred_font_size_px(
            block,
            page,
            (100, 100),
            bbox,
            "Sample text",
            18.0,
            estimated_pt=6.0,
        )
        self.assertAlmostEqual(returned_cap, cap_px, places=2)
        self.assertGreater(user_px, cap_px)
        self.assertAlmostEqual(
            user_px,
            _user_font_size_px_from_pt(18.0, sy),
            places=2,
        )

    def test_user_font_size_exact_on_scaled_image(self):
        """User pt maps to exact px; not limited by short OCR bbox height."""
        block = LayoutBlock(
            page_index=0,
            bbox=(3.0, 61.0, 18.0, 64.0),
            type="text",
            index=4,
            text="ARCHITECT :",
        )
        page = LayoutPage(page_index=0, width=111.0, height=327.0, blocks=[])
        bbox = (8, 170, 50, 178)
        _, sy = _coord_scale_factors(page, (309, 910))
        user_px, cap_px = _preferred_font_size_px(
            block,
            page,
            (309, 910),
            bbox,
            "建筑师：",
            6.0,
            estimated_pt=6.0,
        )
        self.assertGreater(user_px, cap_px)
        self.assertAlmostEqual(
            user_px,
            _user_font_size_px_from_pt(6.0, sy),
            places=2,
        )

    def test_user_2pt_not_inflated_when_estimated_equals_user(self):
        """Block 3 case: user=2 and estimated=2 must not expand to bbox cap."""
        page = LayoutPage(page_index=0, width=111.0, height=327.0, blocks=[])
        bbox = (72, 150, 237, 164)
        _, sy = _coord_scale_factors(page, (309, 910))
        block = LayoutBlock(
            page_index=0,
            bbox=(26.0, 54.0, 85.0, 59.0),
            type="text",
            index=3,
            text="UNIT 20-01",
        )
        user_px, cap_px = _preferred_font_size_px(
            block,
            page,
            (309, 910),
            bbox,
            "单位 20-01，蒂加大厦，1号，拉克斯马纳路，公主港，依斯干达公主城，柔佛。",
            2.0,
            estimated_pt=2.0,
        )
        self.assertAlmostEqual(user_px, _user_font_size_px_from_pt(2.0, sy), places=2)

    def test_user_font_locked_renders_exact_user_px(self):
        """Segment 6 / block 4: locked user override uses exact pt→px, not bbox auto-fit."""
        page = LayoutPage(page_index=0, width=111.0, height=327.0, blocks=[])
        bbox = (8, 170, 50, 178)
        block = LayoutBlock(
            page_index=0,
            bbox=(3.0, 61.0, 18.0, 64.0),
            type="text",
            index=4,
            text="ARCHITECT :",
        )
        text = "建筑师："
        cfg = ImageOverlayConfig()
        dummy = Image.new("RGB", (309, 910), "white")
        draw = ImageDraw.Draw(dummy)
        font_loader = font_loader_for_family("Microsoft YaHei")
        preferred_px, cap_px = _preferred_font_size_px(
            block,
            page,
            (309, 910),
            bbox,
            text,
            5.6,
            estimated_pt=1.5,
        )
        _, _, auto_fitted = _fit_text_lines(
            draw,
            text,
            bbox,
            font_loader,
            cfg,
            preferred_size_px=preferred_px,
            font_size_locked=False,
        )
        _, _, user_fitted = _fit_text_lines(
            draw,
            text,
            bbox,
            font_loader,
            cfg,
            preferred_size_px=preferred_px,
            font_size_locked=True,
        )
        self.assertGreater(preferred_px, cap_px)
        self.assertLess(auto_fitted, int(round(preferred_px)))
        self.assertEqual(user_fitted, int(round(preferred_px)))
        render_pt = dry_run_overlay_font_size_pt(
            block,
            text,
            page,
            (309, 910),
            user_pt=5.6,
        )
        self.assertAlmostEqual(render_pt, 5.6, delta=0.2)

    def test_bbox_font_cap_splits_on_embedded_newlines(self):
        bbox = (45, 270, 264, 284)
        cap = _bbox_font_cap_px(bbox, "line one\nline two")
        self.assertAlmostEqual(cap, (14 / 2) * 0.9, places=2)

    def test_erase_and_draw_produces_valid_png(self):
        img_path = Path(__file__).parent / "_tmp_overlay_source.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        source = Image.new("RGB", (400, 200), color=(240, 240, 240))
        draw = ImageDraw.Draw(source)
        draw.rectangle((40, 40, 360, 90), fill=(255, 255, 255))
        draw.text((50, 50), "Hello OCR", fill=(0, 0, 0))
        source.save(img_path, format="PNG")

        layout_doc = LayoutDocument(
            pages=[
                LayoutPage(
                    page_index=0,
                    width=400,
                    height=200,
                    blocks=[
                        LayoutBlock(
                            page_index=0,
                            bbox=(40.0, 40.0, 360.0, 90.0),
                            type="text",
                            index=1,
                            text="Hello OCR",
                        )
                    ],
                )
            ],
            engine="mineru",
        )
        config = ImageOverlayConfig(
            erase_original_text=True,
            output_format="png",
            target_language="en",
        )
        overlay_input = ImageOverlayInput(
            source_image_path=str(img_path),
            layout_document=layout_doc,
            segments=[],
            layout_zip_bytes=None,
            task_state={},
        )
        pipeline = ImageOverlayPipeline()
        result = pipeline.render(
            overlay_input,
            config,
            block_text_map={1: "Translated text"},
            task_id="test-task",
        )

        self.assertGreater(len(result.image_bytes), 100)
        self.assertEqual(result.media_type, "image/png")
        self.assertEqual(result.width, 400)
        self.assertEqual(result.height, 200)
        self.assertEqual(result.text_blocks_drawn, 1)

        with Image.open(io.BytesIO(result.image_bytes)) as rendered:
            self.assertEqual(rendered.size, (400, 200))

        try:
            img_path.unlink(missing_ok=True)
        except OSError:
            pass

    def test_dry_run_overlay_font_size_pt_matches_fitted_px(self):
        """Regression: UI computed must match fitted raster px (task 79f4fc32 block 4)."""
        page = LayoutPage(
            page_index=0,
            width=111.0,
            height=327.0,
            blocks=[
                LayoutBlock(
                    page_index=0,
                    bbox=(3.0, 61.0, 18.0, 64.0),
                    type="text",
                    index=4,
                    text="ARCHITECT :",
                ),
            ],
        )
        block = page.blocks[0]
        image_size = (309, 910)
        text = "建筑师："

        auto_pt = dry_run_overlay_font_size_pt(
            block, text, page, image_size,
        )
        self.assertIsNotNone(auto_pt)
        assert auto_pt is not None
        # Typst estimate was 1.5pt but raster fit is larger once sy + wrap are applied.
        self.assertGreater(auto_pt, 1.5)
        self.assertLess(auto_pt, 3.0)

        user_pt = dry_run_overlay_font_size_pt(
            block, text, page, image_size, user_pt=4.3,
        )
        self.assertIsNotNone(user_pt)
        assert user_pt is not None
        self.assertAlmostEqual(user_pt, 4.3, places=1)

        bbox = _scale_bbox_to_image(block.bbox, page, image_size)
        preferred_px, cap_px = _preferred_font_size_px(
            block, page, image_size, bbox, text, 4.3,
        )
        _, sy = _coord_scale_factors(page, image_size)
        self.assertGreater(preferred_px, cap_px)
        self.assertAlmostEqual(
            preferred_px,
            _user_font_size_px_from_pt(4.3, sy),
            places=2,
        )

    def test_dry_run_render_pt_below_typst_estimate_when_wrapped(self):
        """When binary fit shrinks below preferred, render pt < Typst estimate."""
        page = LayoutPage(
            page_index=0,
            width=111.0,
            height=327.0,
            blocks=[
                LayoutBlock(
                    page_index=0,
                    bbox=(3.0, 173.0, 104.0, 189.0),
                    type="text",
                    index=24,
                    text="PROPOSED DATA CENTER",
                ),
            ],
        )
        block = page.blocks[0]
        text = "拟议数据中心开发项目，位于柔佛州新山县 PTD 229937 部分地块，努沙再也科技园，柔佛"
        render_pt = dry_run_overlay_font_size_pt(
            block, text, page, (309, 910),
        )
        self.assertIsNotNone(render_pt)
        assert render_pt is not None
        # Debug task had fitted_px=13 (~3.5pt) while Typst estimate was 4.6pt.
        self.assertLessEqual(render_pt, 4.6)
        self.assertGreaterEqual(render_pt, 2.0)

    def test_enrich_overlay_uses_target_language_font_not_calibri(self):
        """Segment list must show overlay render pt (CJK font), not Typst/Calibri ~7pt."""
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            enrich_segment_font_fields,
        )

        page = LayoutPage(
            page_index=0,
            width=111.0,
            height=327.0,
            blocks=[
                LayoutBlock(
                    page_index=0,
                    bbox=(22.0, 247.0, 103.0, 260.0),
                    type="text",
                    index=26,
                    text=(
                        "VENTILATION & AIR-CONDITIONING SYSTEM -SCHEMATIC DIAGRAM "
                        "-MECHANICAL VENTILATION"
                    ),
                ),
            ],
        )
        layout_doc = LayoutDocument(pages=[page])
        text = "通风与空调系统 - 原理图 - 机械通风"
        segment = {
            "segment_index": 30,
            "target_text": text,
            "layout_block_indices": [26],
        }
        task_state = {
            "original_filename": "diagram.png",
            "overlay_source_image_size": [309, 910],
            "to_lang": "zh",
        }
        enrich_segment_font_fields(
            segment, layout_doc, text=text, task_state=task_state,
        )
        render_pt = segment.get("overlay_render_font_size_pt")
        self.assertIsNotNone(render_pt)
        assert render_pt is not None
        self.assertLess(render_pt, 5.0)
        self.assertGreater(render_pt, 2.0)
        self.assertAlmostEqual(segment["computed_font_size_pt"], render_pt, places=1)
        self.assertNotAlmostEqual(render_pt, 7.0, places=0)


if __name__ == "__main__":
    unittest.main()
