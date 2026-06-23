# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for overlay layer ordering and overlap transparency."""

import unittest
from unittest import mock

from layout.pdf_renderer.typst_overlay.layer_order import (
    background_embed_force_opaque,
    bboxes_overlap,
    ensure_opaque_backing_for_text_over_embedded_images,
    finalize_render_blocks_by_page,
    sort_render_blocks_image_under_text,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock


class TestLayerOrder(unittest.TestCase):
    def test_bboxes_overlap(self):
        self.assertTrue(bboxes_overlap((0, 0, 10, 10), (5, 5, 15, 15)))
        self.assertFalse(bboxes_overlap((0, 0, 10, 10), (10, 10, 20, 20)))

    def test_sort_render_blocks_image_under_text(self):
        image_block = RenderBlock(
            block_id="visual-chart-1",
            page_index=0,
            inner_bbox=(10, 10, 100, 100),
            render_kind="image",
            image_rel_path="images/chart.jpg",
        )
        text_block = RenderBlock(
            block_id="block-2",
            page_index=0,
            inner_bbox=(20, 20, 80, 40),
            plain_text="Hello",
            render_kind="plain_line",
        )
        sorted_blocks = sort_render_blocks_image_under_text([text_block, image_block])
        self.assertEqual(sorted_blocks[0].render_kind, "image")
        self.assertEqual(sorted_blocks[1].render_kind, "plain_line")

    def test_ensure_opaque_backing_for_text_over_embedded_images(self):
        image_bbox = (0, 0, 200, 200)
        text_on_image = RenderBlock(
            block_id="block-1",
            page_index=0,
            inner_bbox=(10, 10, 90, 30),
            plain_text="Caption",
            render_kind="plain_line",
        )
        text_off_image = RenderBlock(
            block_id="block-2",
            page_index=0,
            inner_bbox=(250, 10, 350, 30),
            plain_text="Aside",
            render_kind="plain_line",
        )
        applied = ensure_opaque_backing_for_text_over_embedded_images(
            [text_on_image, text_off_image],
            [image_bbox],
        )
        self.assertEqual(applied, 1)
        self.assertTrue(text_on_image.opaque_fill)
        self.assertFalse(text_off_image.opaque_fill)

    def test_table_keeps_opaque_fill_over_visual_regions(self):
        visual_bbox = (0, 0, 200, 200)
        table_on_image = RenderBlock(
            block_id="block-3",
            page_index=0,
            inner_bbox=(10, 10, 90, 90),
            markdown_text="| A | B |\n| --- | --- |\n| 1 | 2 |",
            render_kind="table",
            opaque_fill=True,
        )
        ensure_opaque_backing_for_text_over_embedded_images(
            [table_on_image],
            [visual_bbox],
        )
        self.assertTrue(table_on_image.opaque_fill)

    def test_background_embed_force_opaque(self):
        image_block = RenderBlock(
            block_id="visual-image-1",
            page_index=0,
            inner_bbox=(0, 0, 100, 100),
            render_kind="image",
            image_rel_path="images/photo.jpg",
        )
        on_image = RenderBlock(
            block_id="block-1",
            page_index=0,
            inner_bbox=(10, 10, 50, 30),
            plain_text="On image",
            render_kind="plain_line",
        )
        off_image = RenderBlock(
            block_id="block-2",
            page_index=0,
            inner_bbox=(120, 10, 180, 30),
            plain_text="Off image",
            render_kind="plain_line",
        )
        page_blocks = [image_block, on_image, off_image]
        self.assertTrue(background_embed_force_opaque(on_image, page_blocks))
        self.assertFalse(background_embed_force_opaque(off_image, page_blocks))

    def test_finalize_render_blocks_by_page(self):
        layout_page = mock.MagicMock()
        layout_page.page_index = 0
        layout_doc = mock.MagicMock()
        layout_doc.pages = [layout_page]

        image_block = RenderBlock(
            block_id="visual-image-1",
            page_index=0,
            inner_bbox=(0, 0, 100, 100),
            render_kind="image",
            image_rel_path="images/photo.jpg",
        )
        text_block = RenderBlock(
            block_id="caption-1",
            page_index=0,
            inner_bbox=(10, 10, 90, 30),
            plain_text="Caption",
            render_kind="plain_line",
        )
        finalized = finalize_render_blocks_by_page(
            {0: [text_block, image_block]},
            layout_doc,
        )
        self.assertEqual(finalized[0][0].render_kind, "image")
        self.assertTrue(finalized[0][1].opaque_fill)


if __name__ == "__main__":
    unittest.main()
