# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import unittest
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    collect_bbox_override_redaction_rects,
    collect_excluded_segment_protected_rects,
    collect_partial_overlay_block_indices,
    collect_segment_layout_bbox_redaction_rects,
    segment_skips_overlay,
)
from layout.pdf_renderer.typst_overlay.source_cleanup import _collect_redaction_rects


class TestSegmentRedactionRects(unittest.TestCase):
    def _layout_doc(self):
        table_block = SimpleNamespace(
            index=0,
            page_index=0,
            type="table",
            bbox=(2.0, 0.0, 109.0, 327.0),
        )
        page = SimpleNamespace(page_index=0, blocks=[table_block])
        return SimpleNamespace(pages=[page])

    def test_collect_segment_layout_bbox_redaction_rects(self):
        layout_doc = self._layout_doc()
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "target_text": "A",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "B",
            },
        ]
        rects = collect_segment_layout_bbox_redaction_rects(
            segments,
            layout_doc,
        )
        self.assertEqual(len(rects[0]), 2)
        self.assertLess(rects[0][0][1], rects[0][1][1])

    def test_excluded_segment_not_redacted_but_protected(self):
        layout_doc = self._layout_doc()
        segments = [
            {
                "segment_index": 0,
                "is_excluded": True,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "source_text": "ORIG",
                "target_text": "ORIG",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "Translated",
            },
        ]
        redact = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        protected = collect_excluded_segment_protected_rects(segments, layout_doc)
        self.assertEqual(len(redact.get(0, [])), 1)
        self.assertEqual(len(protected.get(0, [])), 1)
        self.assertTrue(segment_skips_overlay(segments[0]))


    def test_translation_failed_segment_not_redacted_but_protected(self):
        layout_doc = self._layout_doc()
        segments = [
            {
                "segment_index": 0,
                "is_failed": True,
                "needs_retry": True,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "source_text": "ORIG",
                "target_text": "",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "Translated",
            },
        ]
        redact = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        protected = collect_excluded_segment_protected_rects(segments, layout_doc)
        self.assertEqual(len(redact.get(0, [])), 1)
        self.assertEqual(len(protected.get(0, [])), 1)
        self.assertTrue(segment_skips_overlay(segments[0]))

    def test_translation_failed_same_as_source_still_overlays(self):
        """English references returned unchanged must render, not leave blank holes."""
        ref = (
            "[1] Smith J, et al. CT-FFR validation study. "
            "Journal of Cardiology. 2020;12(3):45-52."
        )
        seg = {
            "segment_index": 150,
            "is_failed": True,
            "needs_retry": True,
            "chunk_type": "ref_text",
            "layout_block_indices": [0],
            "layout_block_bbox": [[10.0, 20.0, 90.0, 120.0]],
            "source_text": ref,
            "target_text": ref,
        }
        self.assertFalse(segment_skips_overlay(seg))

        layout_doc = self._layout_doc()
        redact = collect_segment_layout_bbox_redaction_rects([seg], layout_doc)
        protected = collect_excluded_segment_protected_rects([seg], layout_doc)
        self.assertEqual(len(redact.get(0, [])), 1)
        self.assertEqual(protected, {})

    def test_partial_overlay_block_indices(self):
        segments = [
            {
                "segment_index": 0,
                "is_excluded": True,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "source_text": "ORIG",
                "target_text": "ORIG",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "Translated",
            },
        ]
        partial = collect_partial_overlay_block_indices(segments)
        self.assertEqual(partial, {0})

    def test_excluded_segment_protected_with_block_bbox_fallback(self):
        layout_doc = self._layout_doc()
        segments = [
            {
                "segment_index": 0,
                "is_failed": True,
                "layout_block_indices": [0],
                "source_text": "ORIG",
                "target_text": "",
            },
        ]
        protected = collect_excluded_segment_protected_rects(segments, layout_doc)
        self.assertEqual(len(protected.get(0, [])), 1)
        rect = protected[0][0]
        self.assertAlmostEqual(rect[0], 0.0)
        self.assertAlmostEqual(rect[1], 0.0)

    def test_mixed_block_translated_redaction_survives_failed_protection(self):
        from layout.base import LayoutBlock
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            collect_overlay_erase_block_indices,
            collect_segment_bbox_overlay_block_indices,
        )
        from layout.pdf_renderer.typst_overlay.source_cleanup import (
            _clip_rects_against_skipped_blocks,
        )

        block = LayoutBlock(
            page_index=0,
            bbox=(0.0, 0.0, 200.0, 100.0),
            type="text",
            index=0,
            text="ORIGINAL LINE ONE\nORIGINAL LINE TWO",
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        segments = [
            {
                "segment_index": 0,
                "is_failed": True,
                "needs_retry": True,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "source_text": "ORIG",
                "target_text": "",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "Translated",
            },
        ]
        overlay_blocks = collect_segment_bbox_overlay_block_indices(
            segments, layout_doc,
        )
        self.assertIn(0, overlay_blocks)
        redact = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        protected = collect_excluded_segment_protected_rects(
            segments,
            layout_doc,
            segment_bbox_overlay_blocks=overlay_blocks,
        )
        erase = collect_overlay_erase_block_indices(segments, None)
        clipped = _clip_rects_against_skipped_blocks(
            redact[0],
            layout_doc,
            0,
            set(),
            extra_protected_rects=protected.get(0),
            overlay_erase_block_indices=erase,
        )
        self.assertEqual(len(redact.get(0, [])), 1)
        self.assertEqual(len(protected.get(0, [])), 1)
        self.assertEqual(len(clipped), 1)
        self.assertGreater(clipped[0][1], 45.0)

    def test_all_translated_segments_same_block_use_segment_bbox_overlay(self):
        from layout.base import LayoutBlock
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            collect_segment_bbox_overlay_block_indices,
        )

        block = LayoutBlock(
            page_index=0,
            bbox=(0.0, 0.0, 200.0, 100.0),
            type="text",
            index=0,
            text="Line one\nLine two",
        )
        page = SimpleNamespace(page_index=0, blocks=[block])
        layout_doc = SimpleNamespace(pages=[page])
        segments = [
            {
                "segment_index": 0,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 20.0, 90.0, 40.0]],
                "target_text": "A",
            },
            {
                "segment_index": 1,
                "layout_block_indices": [0],
                "layout_block_bbox": [[10.0, 50.0, 90.0, 70.0]],
                "target_text": "B",
            },
        ]
        overlay_blocks = collect_segment_bbox_overlay_block_indices(
            segments, layout_doc,
        )
        self.assertIn(0, overlay_blocks)
        redact = collect_segment_layout_bbox_redaction_rects(segments, layout_doc)
        self.assertEqual(len(redact.get(0, [])), 2)

    def test_segment_bbox_only_skips_full_block_redaction(self):
        text_block = SimpleNamespace(
            type="text",
            index=5,
            bbox=(10.0, 20.0, 200.0, 80.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: True,
            should_skip_redaction=lambda: False,
            raw={},
        )
        page = SimpleNamespace(page_index=0, blocks=[text_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, _ = _collect_redaction_rects(
            layout_doc,
            segment_bbox_only_block_indices={5},
        )
        self.assertEqual(redaction_map, {})

    def test_overlay_erase_segment_bbox_only_queues_override_original(self):
        text_block = SimpleNamespace(
            type="text",
            index=5,
            bbox=(10.0, 20.0, 200.0, 80.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: True,
            should_skip_redaction=lambda: False,
            raw={},
        )
        page = SimpleNamespace(page_index=0, blocks=[text_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        redaction_map, override_map = _collect_redaction_rects(
            layout_doc,
            segment_bbox_only_block_indices={5},
            overlay_erase_block_indices={5},
        )
        self.assertEqual(redaction_map, {})
        self.assertEqual(len(override_map.get(0, [])), 1)

    def test_overlay_erase_segment_bbox_only_queues_user_override_bbox(self):
        text_block = SimpleNamespace(
            type="text",
            index=5,
            bbox=(10.0, 20.0, 200.0, 80.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: True,
            should_skip_redaction=lambda: False,
            raw={},
        )
        page = SimpleNamespace(page_index=0, blocks=[text_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        _, override_map = _collect_redaction_rects(
            layout_doc,
            segment_bbox_only_block_indices={5},
            overlay_erase_block_indices={5},
            bbox_override_by_block_index={5: (5.0, 15.0, 210.0, 95.0)},
        )
        self.assertEqual(len(override_map.get(0, [])), 2)

    def test_overlay_erase_empty_ocr_segment_bbox_only_queues_erase(self):
        empty_block = SimpleNamespace(
            type="text",
            index=5,
            bbox=(10.0, 20.0, 200.0, 80.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: False,
            should_skip_redaction=lambda: False,
            raw={},
            text="",
            block_content="",
        )
        page = SimpleNamespace(page_index=0, blocks=[empty_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        _, override_map = _collect_redaction_rects(
            layout_doc,
            segment_bbox_only_block_indices={5},
            overlay_erase_block_indices={5},
        )
        self.assertEqual(len(override_map.get(0, [])), 1)

    def test_partial_overlay_block_not_in_override_original(self):
        text_block = SimpleNamespace(
            type="text",
            index=5,
            bbox=(10.0, 20.0, 200.0, 80.0),
            image_path=None,
            is_equation=lambda: False,
            has_text=lambda: True,
            should_skip_redaction=lambda: False,
            raw={},
        )
        page = SimpleNamespace(page_index=0, blocks=[text_block], iter_image_blocks=lambda: [])
        layout_doc = SimpleNamespace(pages=[page])
        _, override_map = _collect_redaction_rects(
            layout_doc,
            segment_bbox_only_block_indices={5},
            overlay_erase_block_indices={5},
            partial_overlay_block_indices={5},
        )
        self.assertEqual(override_map, {})

        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            segment_skips_redaction,
        )
        seg = {
            "is_failed": True,
            "chunk_type": "chart_body",
            "layout_block_indices": [82],
            "source_text": "x",
            "target_text": "",
        }
        self.assertTrue(
            segment_skips_redaction(
                seg,
                chart_body_format="image",
                table_body_format="html",
                equation_format="text",
            )
        )

    def test_image_format_chart_body_segment_skips_redaction_even_when_ok(self):
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            segment_skips_redaction,
        )
        seg = {
            "chunk_type": "chart_body",
            "is_image": True,
            "target_text": "![Chart](layoutimg1)",
        }
        self.assertTrue(
            segment_skips_redaction(
                seg,
                chart_body_format="image",
                table_body_format="html",
                equation_format="text",
            )
        )


    def test_collect_bbox_override_redaction_rects(self):
        layout_doc = self._layout_doc()
        rects = collect_bbox_override_redaction_rects(
            {0: (12.0, 22.0, 88.0, 38.0)},
            layout_doc,
            {0},
        )
        self.assertEqual(len(rects[0]), 1)
        self.assertEqual(rects[0][0][0], 10.0)
        self.assertEqual(rects[0][0][1], 20.0)


if __name__ == "__main__":
    unittest.main()
