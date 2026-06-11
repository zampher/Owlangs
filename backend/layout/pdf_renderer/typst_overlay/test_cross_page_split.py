# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for cross-page text splitting in Typst overlay renderer."""

import unittest
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer


_MAIN_TAIL = (
    "... Other approaches [43, 44, 38] use hidden representations from a"
)
_CROSS_TAIL = (
    "pre-trained language or machine translation model as auxiliary features "
    "while training a supervised model on the target task. This involves a "
    "substant amount of new parameters for each separate target task, whereas "
    "we require minimal changes to our model architecture during transfer."
)


def _layout_block_7():
    return SimpleNamespace(
        index=7,
        page_index=0,
        raw={
            "lines": [
                {
                    "bbox": [104, 634, 506, 723],
                    "spans": [
                        {
                            "bbox": [104, 634, 506, 723],
                            "type": "text",
                            "content": "The closest line of work to ours involves "
                            + _MAIN_TAIL,
                        }
                    ],
                },
                {
                    "bbox": [104, 72, 504, 106],
                    "spans": [
                        {
                            "bbox": [104, 72, 504, 106],
                            "type": "text",
                            "content": _CROSS_TAIL,
                            "cross_page": True,
                        }
                    ],
                },
            ],
        },
    )


class TestCrossPageSplit(unittest.TestCase):
    def test_split_uses_source_char_length_not_bbox_area(self):
        block = _layout_block_7()
        main_line_len = len(
            "The closest line of work to ours involves " + _MAIN_TAIL
        )
        cross_line_len = len(_CROSS_TAIL)
        expected_ratio = main_line_len / (main_line_len + cross_line_len)

        translated = "A" * 1000
        result = TypstOverlayRenderer._split_cross_page_text(block, translated)

        expected_main_len = round(1000 * expected_ratio)
        self.assertEqual(len(result["main_text"]), expected_main_len)
        self.assertEqual(len(result["cross_page_parts"][0]["text"]), 1000 - expected_main_len)

        # Area-based split would allocate ~28% to cross-page; char-based ~16%.
        area_ratio = (402 * 89) / ((402 * 89) + (400 * 34))
        area_split_main = round(1000 * area_ratio)
        self.assertNotEqual(expected_main_len, area_split_main)

    def test_cross_page_part_carries_line_raw_and_bbox(self):
        block = _layout_block_7()
        translated = "M" * 800 + "C" * 200
        result = TypstOverlayRenderer._split_cross_page_text(block, translated)

        self.assertEqual(len(result["cross_page_parts"]), 1)
        cp = result["cross_page_parts"][0]
        self.assertEqual(cp["bbox"], (104.0, 72.0, 504.0, 106.0))
        self.assertIn("line_raw", cp)
        self.assertTrue(
            any(
                isinstance(s, dict) and s.get("cross_page")
                for s in cp["line_raw"].get("spans", [])
            )
        )


if __name__ == "__main__":
    unittest.main()
