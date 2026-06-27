# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for empty OCR text layout blocks (preserve PDF background)."""

import unittest
from types import SimpleNamespace

from layout.base import LayoutBlock
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    collect_empty_text_block_protected_rects,
    collect_overlay_erase_block_indices,
    collect_segment_layout_bbox_redaction_rects,
)
from layout.pdf_renderer.typst_overlay.source_cleanup import _collect_redaction_rects


class TestEmptyTextBlockRedaction(unittest.TestCase):
    def test_has_recognized_text_paddle_empty_block_content(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={
                "block_label": "text",
                "block_content": "",
                "block_bbox": [412, 359, 615, 427],
            },
        )
        self.assertFalse(block.has_recognized_text())
        self.assertFalse(block.has_text())

    def test_collect_redaction_skips_empty_text_block(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(layout_doc)
        self.assertEqual(redaction_map, {})

    def test_empty_text_block_protected_rects(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        protected = collect_empty_text_block_protected_rects(layout_doc)
        self.assertEqual(len(protected.get(0, [])), 1)
        rect = protected[0][0]
        self.assertAlmostEqual(rect[0], 410.0)
        self.assertAlmostEqual(rect[1], 357.0)

    def test_segment_redaction_skips_empty_mapped_block_without_translation(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [2],
                "layout_block_bbox": [[412.0, 359.0, 615.0, 427.0]],
                "source_text": "placeholder",
                "target_text": "",
            },
        ]
        rects = collect_segment_layout_bbox_redaction_rects(
            segments,
            layout_doc,
        )
        self.assertEqual(rects, {})

    def test_segment_redaction_skips_empty_mapped_block_with_translation(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [2],
                "layout_block_bbox": [[412.0, 359.0, 615.0, 427.0]],
                "target_text": "Translated nearby",
            },
        ]
        rects = collect_segment_layout_bbox_redaction_rects(
            segments,
            layout_doc,
        )
        self.assertEqual(len(rects.get(0, [])), 1)

    def test_empty_text_block_stays_protected_when_overlay_scheduled(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        erase = collect_overlay_erase_block_indices(
            [{"segment_index": 0, "layout_block_indices": [2], "target_text": "Hi"}],
            None,
            layout_doc=layout_doc,
        )
        self.assertEqual(erase, {2})
        protected = collect_empty_text_block_protected_rects(
            layout_doc,
            overlay_erase_block_indices=erase,
            overlay_text_block_indices={2},
        )
        self.assertEqual(protected, {})

    def test_primary_redaction_erases_empty_block_when_overlay_erase_scheduled(self):
        block = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, override_map = _collect_redaction_rects(
            layout_doc,
            overlay_erase_block_indices={2},
        )
        self.assertEqual(len(redaction_map.get(0, [])), 1)
        self.assertEqual(override_map, {})

    def test_text_segment_redaction_not_blocked_by_adjacent_empty_ocr_bbox(self):
        """Segment bbox erase must not be clipped by empty OCR protected rects."""
        from layout.pdf_renderer.typst_overlay.source_cleanup import (
            _clip_rects_against_protected_rects,
        )

        text_block = LayoutBlock(
            page_index=0,
            bbox=(104.0, 490.0, 506.5, 589.5),
            type="text",
            index=1,
            text="Original paragraph",
            raw={"block_content": "Original paragraph"},
        )
        empty_block = LayoutBlock(
            page_index=0,
            bbox=(300.0, 742.0, 310.0, 751.5),
            type="page_number",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(page_index=0, blocks=[text_block, empty_block])
        layout_doc = SimpleNamespace(pages=[page])
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [1],
                "layout_block_bbox": [[104.0, 490.0, 506.5, 589.5]],
                "target_text": "Translated",
            },
        ]
        seg_rects = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        self.assertEqual(len(seg_rects.get(0, [])), 1)
        preserve_empty_by_page = collect_empty_text_block_protected_rects(
            layout_doc,
            overlay_text_block_indices={1},
        )
        clipped_wrong = _clip_rects_against_protected_rects(
            seg_rects[0],
            preserve_empty_by_page.get(0, []),
        )
        # Empty page_number bbox should not be merged into segment protected rects.
        self.assertEqual(len(clipped_wrong), len(seg_rects[0]))

    def test_empty_paddle_det_duplicate_not_protected_over_overlay_erase_bbox(self):
        """Empty paddle_det supplement at same bbox as overlay_erase block must not clip erasure."""
        title_bbox = (169.5, 98.0, 442.5, 138.0)
        title_block = LayoutBlock(
            page_index=0,
            bbox=title_bbox,
            type="title",
            index=0,
            text="Language Understanding",
            raw={"block_content": "Language Understanding"},
        )
        empty_duplicate = LayoutBlock(
            page_index=0,
            bbox=title_bbox,
            type="title",
            index=12,
            text="",
            raw={
                "block_content": "",
                "tags": ["paddle_det"],
            },
        )
        empty_author = LayoutBlock(
            page_index=0,
            bbox=(412.0, 359.0, 615.0, 427.0),
            type="text",
            index=2,
            text="",
            raw={"block_content": ""},
        )
        page = SimpleNamespace(
            page_index=0,
            blocks=[title_block, empty_author, empty_duplicate],
            iter_image_blocks=lambda: [],
        )
        layout_doc = SimpleNamespace(pages=[page])
        overlay_erase = {0}
        overlay_text = {0}
        protected = collect_empty_text_block_protected_rects(
            layout_doc,
            overlay_erase_block_indices=overlay_erase,
            overlay_text_block_indices=overlay_text,
        )
        # Author empty box stays protected; duplicate at title bbox is skipped.
        self.assertEqual(len(protected.get(0, [])), 1)
        author_rect = protected[0][0]
        self.assertAlmostEqual(author_rect[0], 410.0)
        self.assertAlmostEqual(author_rect[1], 357.0)

        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            overlay_erase_block_indices=overlay_erase,
        )
        self.assertEqual(len(redaction_map.get(0, [])), 1)
        erase_rect = redaction_map[0][0]
        self.assertLessEqual(erase_rect[0], title_bbox[0])
        self.assertLessEqual(erase_rect[1], title_bbox[1])
        self.assertGreaterEqual(erase_rect[2], title_bbox[2])
        self.assertGreaterEqual(erase_rect[3], title_bbox[3])

    def test_segment_redaction_clips_empty_ocr_blocks_in_overlapping_bbox(self):
        """Wide segment bbox must not erase adjacent empty OCR author boxes."""
        text_block = LayoutBlock(
            page_index=0,
            bbox=(104.0, 490.0, 506.5, 589.5),
            type="text",
            index=1,
            text="Abstract paragraph text.",
            raw={"block_content": "Abstract paragraph text."},
        )
        empty_blocks = [
            LayoutBlock(
                page_index=0,
                bbox=(412.0, 359.0, 615.0, 427.0),
                type="text",
                index=2,
                text="",
                raw={"block_label": "text", "block_content": ""},
            ),
            LayoutBlock(
                page_index=0,
                bbox=(638.0, 359.0, 791.0, 428.0),
                type="text",
                index=3,
                text="",
                raw={"block_label": "text", "block_content": ""},
            ),
            LayoutBlock(
                page_index=0,
                bbox=(811.0, 359.0, 996.0, 428.0),
                type="text",
                index=4,
                text="",
                raw={"block_label": "text", "block_content": ""},
            ),
        ]
        page = SimpleNamespace(
            page_index=0,
            blocks=[text_block, *empty_blocks],
        )
        layout_doc = SimpleNamespace(pages=[page])
        wide_bbox = [100.0, 350.0, 1000.0, 600.0]
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [1],
                "layout_block_bbox": wide_bbox,
                "target_text": "Translated abstract",
            },
        ]
        rects = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        page_rects = rects.get(0, [])
        self.assertTrue(page_rects)
        for empty in empty_blocks:
            ex0, ey0, ex1, ey1 = empty.bbox
            for rx0, ry0, rx1, ry1 in page_rects:
                overlaps = rx0 < ex1 and rx1 > ex0 and ry0 < ey1 and ry1 > ey0
                self.assertFalse(
                    overlaps,
                    f"redaction rect {page_rects} overlaps empty block {empty.bbox}",
                )


if __name__ == "__main__":
    unittest.main()
