# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for MinerU <details> block preservation during markdown split."""

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.markdown_splitter import (
    merge_adjacent_details_fragments,
    split_markdown_text,
    split_text_into_paragraphs,
)


MINERU_TEXT_IMAGE_MD = """CUENT :

<details>
<summary>text_image</summary>

DAYONE
</details>

UNIT 20-01, TEEGA TOWER, NO. 1, JALAN LAKSAMANA, PUTERI HARBOUR, ISKANDAR PUTERI, JOHOR.

ARCHITECT :
"""


class MarkdownSplitterDetailsTest(unittest.TestCase):
    def test_deep_split_keeps_text_image_details_as_one_segment(self):
        chunks = split_markdown_text(
            MINERU_TEXT_IMAGE_MD,
            max_block_size=5000,
            deep_split=True,
        )
        details_chunks = [
            chunk for chunk in chunks if "text_image" in chunk or "DAYONE" in chunk
        ]
        self.assertEqual(len(details_chunks), 1)
        self.assertIn("<details>", details_chunks[0].lower())
        self.assertIn("dayone", details_chunks[0].lower())
        self.assertIn("</details>", details_chunks[0].lower())

    def test_split_text_into_paragraphs_preserves_details_block(self):
        paragraphs = split_text_into_paragraphs(MINERU_TEXT_IMAGE_MD)
        details_paragraphs = [
            para for para in paragraphs if "text_image" in para or "DAYONE" in para
        ]
        self.assertEqual(len(details_paragraphs), 1)
        self.assertIn("DAYONE", details_paragraphs[0])

    def test_merge_adjacent_details_fragments_repairs_legacy_split(self):
        broken = [
            "<details>\n<summary>text_image</summary>",
            "DAYONE\n</details>",
        ]
        merged = merge_adjacent_details_fragments(broken)
        self.assertEqual(len(merged), 1)
        self.assertIn("DAYONE", merged[0])
        self.assertIn("</details>", merged[0])


if __name__ == "__main__":
    unittest.main()
