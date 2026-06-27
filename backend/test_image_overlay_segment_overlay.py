# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for Paddle det supplements and segment-direct overlay."""

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.image_overlay.segment_overlay import (
    build_segment_overlay_draw_items,
    is_paddle_single_table_image_layout,
    is_single_table_image_layout,
    should_use_segment_direct_overlay,
)
from layout.ocr_provider.paddle.paddle_det_supplements import (
    append_paddle_det_supplement_blocks,
)


class PaddleDetSupplementTest(unittest.TestCase):
    def test_append_det_blocks_skips_full_page_table(self):
        blocks = [
            LayoutBlock(
                page_index=0,
                bbox=(5.0, 0.0, 306.0, 910.0),
                type="table",
                index=0,
                text="<table></table>",
            )
        ]
        next_idx = append_paddle_det_supplement_blocks(
            blocks,
            [
                {"label": "table", "bbox": [5, 0, 306, 910]},
                {"label": "text", "bbox": [31, 339, 280, 362]},
            ],
            page_index=0,
            next_block_index=1,
            page_w=309.0,
            page_h=910.0,
        )
        self.assertEqual(next_idx, 2)
        self.assertEqual(len(blocks), 2)
        self.assertIn("paddle_det", blocks[1].tags or [])


class SegmentOverlayTest(unittest.TestCase):
    def test_build_segment_overlay_draw_items(self):
        layout_doc = LayoutDocument(
            pages=[
                LayoutPage(
                    page_index=0,
                    width=309.0,
                    height=910.0,
                    blocks=[
                        LayoutBlock(
                            page_index=0,
                            bbox=(5.0, 0.0, 306.0, 910.0),
                            type="table",
                            index=0,
                            text=(
                                "<table><tr><td>A</td></tr><tr><td>B</td></tr></table>"
                            ),
                        ),
                    ],
                )
            ],
            engine="paddle",
            metadata={"coordinate_space": "image_px"},
        )
        self.assertTrue(is_paddle_single_table_image_layout(layout_doc))
        self.assertTrue(should_use_segment_direct_overlay(layout_doc))
        segments = [
            {
                "segment_index": 0,
                "source_text": "A",
                "layout_block_indices": [0],
            },
            {
                "segment_index": 1,
                "source_text": "B",
                "target_text": "B translated",
                "layout_block_indices": [0],
            },
        ]
        items = build_segment_overlay_draw_items(
            segments,
            layout_doc,
            text_field="target_text",
            image_size=(309, 910),
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].segment_index, 1)
        self.assertIn("translated", items[0].text)

    def test_mineru_single_table_uses_segment_direct_overlay(self):
        table_html = (
            "<table><tr><td>A</td></tr><tr><td>B</td></tr></table>"
        )
        layout_doc = LayoutDocument(
            pages=[
                LayoutPage(
                    page_index=0,
                    width=111.0,
                    height=327.0,
                    blocks=[
                        LayoutBlock(
                            page_index=0,
                            bbox=(2.0, 0.0, 109.0, 327.0),
                            type="table",
                            index=0,
                            text=table_html,
                        ),
                    ],
                )
            ],
            engine="mineru",
        )
        self.assertTrue(is_single_table_image_layout(layout_doc))
        self.assertTrue(should_use_segment_direct_overlay(layout_doc))
        segments = [
            {
                "segment_index": 0,
                "source_text": "A",
                "target_text": "甲",
                "layout_block_indices": [0],
            },
            {
                "segment_index": 1,
                "source_text": "B",
                "target_text": "乙",
            },
        ]
        items = build_segment_overlay_draw_items(
            segments,
            layout_doc,
            text_field="target_text",
            image_size=(309, 910),
        )
        self.assertEqual(len(items), 2)
        self.assertLess(items[0].layout_bbox[3], items[1].layout_bbox[3])


if __name__ == "__main__":
    unittest.main()
