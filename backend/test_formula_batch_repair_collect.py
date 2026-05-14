"""Unit tests for formula batch repair segment selection (layout / metadata gating)."""

import unittest

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from utils.latex_formula_batch_repair import collect_formula_items


def _layout_doc(*blocks: LayoutBlock) -> LayoutDocument:
    return LayoutDocument(pages=[LayoutPage(page_index=0, blocks=list(blocks))], engine="test")


class TestCollectFormulaItems(unittest.TestCase):
    def test_skips_dollar_in_plain_text_block(self) -> None:
        doc = _layout_doc(
            LayoutBlock(page_index=0, bbox=(0, 0, 1, 1), type="text", index=0, text="Price $5"),
        )
        task_state = {
            "layout_document": doc,
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 0,
                        "source_text": "Price $5",
                        "target_text": "价格 $5",
                        "layout_block_indices": [0],
                    }
                ]
            },
        }
        self.assertEqual(collect_formula_items(task_state), [])

    def test_collects_interline_equation_by_layout_index(self) -> None:
        doc = _layout_doc(
            LayoutBlock(
                page_index=0,
                bbox=(0, 0, 1, 1),
                type="interline_equation",
                index=0,
                text=r"$$\alpha$$",
            ),
        )
        task_state = {
            "layout_document": doc,
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 0,
                        "source_text": r"$$\alpha$$",
                        "target_text": r"$$\beta$$",
                        "layout_block_indices": [0],
                    }
                ]
            },
        }
        items = collect_formula_items(task_state)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].segment_index, 0)

    def test_collects_via_segment_info_block_type(self) -> None:
        task_state = {
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 1,
                        "source_text": "x",
                        "target_text": "y",
                        "segment_info": {"block_type": "formula"},
                    }
                ]
            },
        }
        items = collect_formula_items(task_state)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].segment_index, 1)

    def test_collects_via_top_level_block_type(self) -> None:
        task_state = {
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 2,
                        "source_text": "a",
                        "target_text": "b",
                        "block_type": "equation",
                    }
                ]
            },
        }
        items = collect_formula_items(task_state)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].segment_index, 2)

    def test_skips_image_segments(self) -> None:
        doc = _layout_doc(
            LayoutBlock(
                page_index=0,
                bbox=(0, 0, 1, 1),
                type="interline_equation",
                index=0,
                text=r"$$\gamma$$",
            ),
        )
        task_state = {
            "layout_document": doc,
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 0,
                        "source_text": r"$$\gamma$$",
                        "target_text": r"$$\gamma$$",
                        "layout_block_indices": [0],
                        "is_image": True,
                    }
                ]
            },
        }
        self.assertEqual(collect_formula_items(task_state), [])


if __name__ == "__main__":
    unittest.main()
