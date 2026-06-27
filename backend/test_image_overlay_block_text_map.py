# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for image overlay direct block text mapping."""

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.image_overlay.block_text_map import (
    _contains_overlay_skip_markup,
    _is_non_overlay_segment_text,
    _match_source_text_to_layout_blocks,
    build_block_typography_maps_from_overlay_meta,
    build_image_overlay_block_text_map,
)


def _sample_layout_doc() -> LayoutDocument:
    return LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=111,
                height=327,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(3.0, 34.0, 13.0, 38.0),
                        type="text",
                        index=1,
                        text="CUENT :",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(13.0, 38.0, 98.0, 53.0),
                        type="image",
                        index=2,
                        text="DAYONE",
                        image_path="4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg",
                        raw={
                            "type": "image",
                            "sub_type": "text_image",
                            "bbox": [13, 38, 98, 53],
                            "blocks": [
                                {
                                    "type": "image_body",
                                    "lines": [
                                        {
                                            "spans": [
                                                {
                                                    "type": "image",
                                                    "content": "DAYONE",
                                                    "image_path": "4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg",
                                                }
                                            ]
                                        }
                                    ],
                                }
                            ],
                        },
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(26.0, 54.0, 85.0, 59.0),
                        type="text",
                        index=3,
                        text="UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(3.0, 61.0, 18.0, 64.0),
                        type="text",
                        index=4,
                        text="ARCHITECT :",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(44.0, 78.0, 67.0, 81.0),
                        type="text",
                        index=5,
                        text="Ar. NEO KIM CHENG",
                    ),
                ],
            )
        ],
        engine="mineru",
    )


class ImageOverlayBlockTextMapTest(unittest.TestCase):
    def test_skip_image_markdown_segment(self):
        seg = {
            "segment_index": 2,
            "is_image": True,
            "layout_block_indices": [2],
            "target_text": "![](images/abc.jpg)",
        }
        self.assertTrue(_is_non_overlay_segment_text(seg["target_text"], seg))

    def test_skip_details_opening_fragment(self):
        text = "<details>\n<summary>文字图片</summary>"
        self.assertTrue(_contains_overlay_skip_markup(text))
        self.assertTrue(_is_non_overlay_segment_text(text, {"segment_index": 3}))

    def test_source_text_matches_layout_block_not_segment_index(self):
        layout_doc = _sample_layout_doc()
        layout_texts = {
            1: "CUENT :",
            3: "UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
            4: "ARCHITECT :",
            5: "Ar. NEO KIM CHENG",
        }
        block_types = {1: "text", 2: "image", 3: "text", 4: "text", 5: "text"}

        self.assertEqual(
            _match_source_text_to_layout_blocks("ARCHITECT :", layout_texts, block_types),
            [4],
        )
        self.assertEqual(
            _match_source_text_to_layout_blocks(
                "UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
                layout_texts,
                block_types,
            ),
            [3],
        )

    def test_direct_map_uses_source_text_when_segment_indices_misaligned(self):
        layout_doc = _sample_layout_doc()
        segments = [
            {
                "segment_index": 1,
                "source_text": "CUENT :",
                "layout_block_indices": [1],
                "target_text": "客户：",
            },
            {
                "segment_index": 2,
                "is_image": True,
                "source_text": "![](images/x.jpg)",
                "layout_block_indices": [2],
                "target_text": "![](images/x.jpg)",
            },
            {
                "segment_index": 3,
                "source_text": "<details>\n<summary>text_image</summary>\nDAYONE\n</details>",
                "layout_block_indices": [3, 4],
                "target_text": "<details>\n<summary>文字图片</summary>\nDAYONE\n</details>",
            },
            {
                "segment_index": 4,
                "source_text": "UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
                "layout_block_indices": [4],
                "target_text": "单位 20-01，TEEGA 大厦，1号，拉克斯马纳路，公主港，依斯干达公主城，柔佛州。",
            },
            {
                "segment_index": 5,
                "source_text": "ARCHITECT :",
                "layout_block_indices": [5],
                "target_text": "建筑师：",
            },
            {
                "segment_index": 6,
                "source_text": "Ar. NEO KIM CHENG",
                "layout_block_indices": [6],
                "target_text": "建筑师 黄金成",
            },
        ]
        result = build_image_overlay_block_text_map(
            layout_doc,
            segments,
            text_field="target_text",
            task_state={"segment_layout_block_map": [[], [], [2], [3, 4], [4], [5], [6]]},
        )
        block_map = result.block_text_map
        self.assertEqual(block_map.get(1), "客户：")
        self.assertEqual(
            block_map.get(3),
            "单位 20-01，TEEGA 大厦，1号，拉克斯马纳路，公主港，依斯干达公主城，柔佛州。",
        )
        self.assertEqual(block_map.get(4), "建筑师：")
        self.assertEqual(block_map.get(5), "建筑师 黄金成")
        self.assertEqual(
            result.block_segment_meta[3]["resolution_method"],
            "source_text_match",
        )

    def test_typography_maps_follow_overlay_block_provenance(self):
        layout_doc = _sample_layout_doc()
        segments = [
            {
                "segment_index": 5,
                "source_text": "ARCHITECT :",
                "layout_block_indices": [5],
                "target_text": "建筑师：",
                "font_size_pt": 14.0,
                "font_size_source": "user",
            },
            {
                "segment_index": 6,
                "source_text": "Ar. NEO KIM CHENG",
                "layout_block_indices": [6],
                "target_text": "建筑师 黄金成",
            },
        ]
        result = build_image_overlay_block_text_map(
            layout_doc,
            segments,
            text_field="target_text",
            task_state={"segment_layout_block_map": [[], [], [2], [3, 4], [4], [5], [6]]},
        )
        font_map, _ = build_block_typography_maps_from_overlay_meta(
            segments,
            result.block_segment_meta,
        )
        self.assertEqual(result.block_text_map.get(4), "建筑师：")
        self.assertEqual(font_map.get(4), 14.0)
        self.assertNotIn(5, font_map)

    def test_resolve_overlay_primary_block_prefers_source_text_match(self):
        from layout.image_overlay.block_text_map import (
            resolve_overlay_primary_text_block_index,
        )

        layout_doc = _sample_layout_doc()
        segment = {
            "segment_index": 5,
            "source_text": "ARCHITECT :",
            "layout_block_indices": [5],
            "target_text": "建筑师：",
        }
        block_idx = resolve_overlay_primary_text_block_index(
            segment,
            layout_doc,
            task_state={"segment_layout_block_map": [[], [], [2], [3, 4], [4], [5], [6]]},
        )
        self.assertEqual(block_idx, 4)

    def test_assign_overlay_layout_block_indices_fixes_misaligned_map(self):
        from layout.image_overlay.block_text_map import (
            assign_overlay_layout_block_indices_for_segments,
        )

        layout_doc = _sample_layout_doc()
        segments = [
            {
                "segment_index": 1,
                "source_text": "CUENT :",
                "layout_block_indices": [1],
                "target_text": "客户：",
            },
            {
                "segment_index": 2,
                "is_image": True,
                "source_text": "![](images/x.jpg)",
                "layout_block_indices": [2],
                "target_text": "![](images/x.jpg)",
            },
            {
                "segment_index": 3,
                "source_text": "<details>\n<summary>text_image</summary>\nDAYONE\n</details>",
                "layout_block_indices": [3, 4],
                "target_text": "<details>\n<summary>文字图片</summary>\nDAYONE\n</details>",
            },
            {
                "segment_index": 4,
                "source_text": "UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
                "layout_block_indices": [4],
                "target_text": "单位 20-01，TEEGA 大厦，1号，拉克斯马纳路，公主港，依斯干达公主城，柔佛州。",
            },
            {
                "segment_index": 5,
                "source_text": "ARCHITECT :",
                "layout_block_indices": [5],
                "target_text": "建筑师：",
            },
            {
                "segment_index": 6,
                "source_text": "Ar. NEO KIM CHENG",
                "layout_block_indices": [6],
                "target_text": "建筑师 黄金成",
            },
        ]
        task_state = {
            "segment_layout_block_map": [[], [], [2], [3, 4], [4], [5], [6]],
        }
        updated = assign_overlay_layout_block_indices_for_segments(
            segments,
            layout_doc,
            task_state,
            claim_blocks=True,
        )
        self.assertGreater(updated, 0)
        self.assertEqual(segments[2]["layout_block_indices"], [2])
        self.assertEqual(segments[3]["layout_block_indices"], [3])
        self.assertEqual(segments[4]["layout_block_indices"], [4])
        self.assertEqual(segments[5]["layout_block_indices"], [5])
        block_assignments = [
            seg["layout_block_indices"][0]
            for seg in segments
            if seg.get("layout_block_indices")
        ]
        self.assertEqual(len(block_assignments), len(set(block_assignments)))

    def test_text_image_details_maps_to_image_block_bbox(self):
        from layout.image_overlay.block_text_map import (
            _resolve_mineru_details_image_block_index,
        )

        layout_doc = _sample_layout_doc()
        segment = {
            "segment_index": 3,
            "source_text": "<details>\n<summary>text_image</summary>\nDAYONE\n</details>",
            "target_text": "<details>\n<summary>文字图片</summary>\nDAYONE\n</details>",
        }
        block_idx = _resolve_mineru_details_image_block_index(segment, layout_doc)
        self.assertEqual(block_idx, 2)

    def test_split_closing_details_fragment_maps_to_image_block(self):
        from layout.image_overlay.block_text_map import (
            _resolve_mineru_details_image_block_index,
        )

        layout_doc = _sample_layout_doc()
        segment = {
            "segment_index": 5,
            "source_text": "DAYONE\n</details>",
            "target_text": "DAYONE\n</details>",
        }
        block_idx = _resolve_mineru_details_image_block_index(segment, layout_doc)
        self.assertEqual(block_idx, 2)

    def test_assign_ignores_wrong_segment_layout_block_map(self):
        from layout.image_overlay.block_text_map import (
            assign_overlay_layout_block_indices_for_segments,
        )

        layout_doc = _sample_layout_doc()
        segments = [
            {
                "segment_index": 1,
                "source_text": "CUENT :",
                "layout_block_indices": [99],
                "target_text": "客户：",
            },
            {
                "segment_index": 2,
                "source_text": "![](images/x.jpg)",
                "layout_block_indices": [2],
                "target_text": "![](images/x.jpg)",
            },
            {
                "segment_index": 3,
                "source_text": "<details>\n<summary>text_image</summary>\nDAYONE\n</details>",
                "layout_block_indices": [99],
                "target_text": "<details>\n<summary>文字图片</summary>\nDAYONE\n</details>",
            },
            {
                "segment_index": 4,
                "source_text": "UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.",
                "layout_block_indices": [99],
                "target_text": "单位 20-01",
            },
            {
                "segment_index": 5,
                "source_text": "ARCHITECT :",
                "layout_block_indices": [99],
                "target_text": "建筑师：",
            },
            {
                "segment_index": 6,
                "source_text": "Ar. NEO KIM CHENG",
                "layout_block_indices": [99],
                "target_text": "建筑师 黄金成",
            },
        ]
        task_state = {
            "segment_layout_block_map": [[], [], [2], [3, 4], [4], [5], [6]],
        }
        assign_overlay_layout_block_indices_for_segments(
            segments,
            layout_doc,
            task_state,
            claim_blocks=True,
        )
        self.assertEqual(segments[0]["layout_block_indices"], [1])
        self.assertEqual(segments[2]["layout_block_indices"], [2])
        self.assertEqual(segments[2]["layout_block_indices_resolution"], "mineru_text_image")
        self.assertEqual(segments[3]["layout_block_indices"], [3])
        self.assertEqual(segments[4]["layout_block_indices"], [4])
        self.assertEqual(segments[5]["layout_block_indices"], [5])

    def test_markdown_image_segment_maps_to_layout_image_block(self):
        from layout.image_overlay.block_text_map import (
            _resolve_markdown_image_block_index,
            assign_overlay_layout_block_indices_for_segments,
        )

        layout_doc = _sample_layout_doc()
        hash_name = (
            "4812d07ab014233ee9c5a7a9c80e8e9b7c8ad8dd8c3b343ee7f7a90d2b741ea9.jpg"
        )
        segment = {
            "segment_index": 2,
            "is_image": True,
            "source_text": f"![](images/{hash_name})",
            "target_text": f"![](images/{hash_name})",
        }
        self.assertEqual(
            _resolve_markdown_image_block_index(
                segment,
                layout_doc,
                claimed_blocks=set(),
            ),
            2,
        )

        cleared = dict(segment)
        assign_overlay_layout_block_indices_for_segments(
            [cleared],
            layout_doc,
            {},
            claim_blocks=True,
        )
        self.assertEqual(cleared["layout_block_indices"], [2])
        self.assertEqual(cleared["layout_block_indices_resolution"], "markdown_image")

    def test_html_table_segment_maps_to_layout_table_block(self):
        from layout.image_overlay.block_text_map import (
            _resolve_table_block_index,
            assign_overlay_layout_block_indices_for_segments,
        )

        table_html = "<table><tr><td>A</td><td>B</td></tr></table>"
        layout_doc = LayoutDocument(
            pages=[
                LayoutPage(
                    page_index=0,
                    width=200,
                    height=200,
                    blocks=[
                        LayoutBlock(
                            page_index=0,
                            bbox=(10.0, 10.0, 90.0, 50.0),
                            type="table",
                            index=0,
                            text=table_html,
                        ),
                        LayoutBlock(
                            page_index=0,
                            bbox=(10.0, 60.0, 90.0, 80.0),
                            type="text",
                            index=1,
                            text="After table",
                        ),
                    ],
                )
            ],
            engine="mineru",
        )
        segment = {
            "segment_index": 1,
            "source_text": table_html,
            "target_text": table_html,
        }
        self.assertEqual(
            _resolve_table_block_index(layout_doc, claimed_blocks=set()),
            0,
        )
        assign_overlay_layout_block_indices_for_segments(
            [segment],
            layout_doc,
            {},
            claim_blocks=True,
        )
        self.assertEqual(segment["layout_block_indices"], [0])
        self.assertEqual(segment["layout_block_indices_resolution"], "layout_table")

    def test_single_table_layout_proportional_bbox_subdivision(self):
        from layout.image_overlay.block_text_map import (
            assign_proportional_bboxes_for_single_table_layout,
        )

        table_html = (
            "<table><tr><td>Row A</td></tr><tr><td>Row B</td></tr>"
            "<tr><td>Row C</td></tr></table>"
        )
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
                            text=table_html,
                        ),
                    ],
                )
            ],
            engine="paddle",
            metadata={"coordinate_space": "image_px"},
        )
        segments = [
            {
                "segment_index": 0,
                "source_text": "Row A",
                "layout_block_indices": [0],
            },
            {
                "segment_index": 1,
                "source_text": "Row B",
                "layout_block_indices": [0],
            },
            {
                "segment_index": 2,
                "source_text": "Row C",
                "layout_block_indices": [0],
            },
        ]
        updated = assign_proportional_bboxes_for_single_table_layout(
            segments,
            layout_doc,
        )
        self.assertEqual(updated, 3)
        bboxes = [seg["layout_block_bbox"][0] for seg in segments]
        self.assertLess(bboxes[0][3], bboxes[2][3])
        self.assertNotIn("layout_block_bbox_space", segments[0])

    def test_mineru_nested_table_html_enables_bbox_subdivision(self):
        from layout.base import LayoutBlock, LayoutDocument, LayoutPage
        from layout.image_overlay.block_text_map import (
            _resolve_table_block_html,
            assign_proportional_bboxes_for_single_table_layout,
        )
        from layout.mineru_layout_model import _extract_text_from_layout_block

        table_html = (
            "<table><tr><td>CLIENT:</td></tr><tr><td>DAYONE</td></tr>"
            "<tr><td>ARCHITECT:</td></tr></table>"
        )
        raw_block = {
            "type": "table_body",
            "bbox": [2, 0, 109, 327],
            "lines": [
                {
                    "spans": [
                        {"type": "table", "html": table_html},
                    ],
                },
            ],
        }
        self.assertEqual(_extract_text_from_layout_block(raw_block), table_html)

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
                            text=None,
                            raw={
                                "type": "table",
                                "bbox": [2, 0, 109, 327],
                                "blocks": [raw_block],
                            },
                        ),
                    ],
                )
            ],
            engine="mineru",
        )
        self.assertEqual(_resolve_table_block_html(layout_doc.pages[0].blocks[0]), table_html)

        segments = [
            {"segment_index": 0, "source_text": "CLIENT:", "layout_block_indices": [0]},
            {"segment_index": 1, "source_text": "DAYONE"},
            {"segment_index": 2, "source_text": "ARCHITECT:"},
        ]
        updated = assign_proportional_bboxes_for_single_table_layout(segments, layout_doc)
        self.assertEqual(updated, 3)
        self.assertLess(segments[0]["layout_block_bbox"][0][3], segments[2]["layout_block_bbox"][0][3])

    def test_html_range_to_layout_y_uses_primary_row_not_union(self):
        from layout.image_overlay.block_text_map import _html_range_to_layout_y

        row_spans = [
            (0, 10, 0.0, 10.0),
            (10, 20, 10.0, 30.0),
            (20, 30, 30.0, 60.0),
        ]
        table_html = "0123456789" + "0123456789" + "0123456789"
        top, bottom = _html_range_to_layout_y(
            12,
            18,
            row_spans,
            table_html=table_html,
            fragment="234567",
        )
        self.assertGreaterEqual(top, 10.0)
        self.assertLessEqual(bottom, 30.0)
        self.assertLess(bottom - top, 20.0)

    def test_intra_row_line_split_assigns_distinct_bands(self):
        from layout.image_overlay.block_text_map import (
            assign_proportional_bboxes_for_single_table_layout,
        )
        from layout.base import LayoutBlock, LayoutDocument, LayoutPage

        table_html = (
            "<table><tr><td colspan=\"5\">DAYONE\n"
            "UNIT 20-01, TEEGA TOWER\n"
            "PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR</td></tr></table>"
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
        segments = [
            {
                "segment_index": 0,
                "source_text": "UNIT 20-01, TEEGA TOWER",
                "layout_block_indices": [0],
            },
            {
                "segment_index": 1,
                "source_text": "PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR",
            },
        ]
        updated = assign_proportional_bboxes_for_single_table_layout(
            segments,
            layout_doc,
        )
        self.assertEqual(updated, 2)
        bbox0 = segments[0]["layout_block_bbox"][0]
        bbox1 = segments[1]["layout_block_bbox"][0]
        self.assertLess(bbox0[1], bbox1[1])
        self.assertLess(bbox0[3], bbox1[3])

    def test_extract_paddle_det_boxes_from_nested_layout_det_res(self):
        from layout.ocr_provider.paddle.paddle_det_supplements import (
            extract_paddle_det_boxes_from_pruned,
        )

        pruned = {
            "layout_det_res": {
                "boxes": [
                    {"label": "text", "coordinate": [10, 20, 100, 40]},
                    {"label": "table", "coordinate": [0, 0, 300, 900]},
                ]
            }
        }
        boxes = extract_paddle_det_boxes_from_pruned(pruned)
        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0]["label"], "text")

    def test_weighted_table_row_spans_skip_empty_rows(self):
        from layout.image_overlay.block_text_map import _build_table_row_y_spans

        table_html = (
            "<table>"
            "<tr><td></td></tr><tr><td></td></tr><tr><td></td></tr>"
            "<tr><td>REV.</td><td>DESCRIPTION</td></tr>"
            "<tr><td colspan=\"4\">CLIENT :</td></tr>"
            "</table>"
        )
        spans = _build_table_row_y_spans(table_html, 0.0, 910.0)
        self.assertEqual(len(spans), 5)
        empty_height = spans[0][3] - spans[0][2]
        rev_height = spans[3][3] - spans[3][2]
        self.assertLess(empty_height, rev_height)
        self.assertLess(empty_height, 5.0)


if __name__ == "__main__":
    unittest.main()
