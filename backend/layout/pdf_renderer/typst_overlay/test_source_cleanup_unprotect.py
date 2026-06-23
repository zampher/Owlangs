# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for redaction clipping with unprotected embedded-image blocks."""

import unittest
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.source_cleanup import (
    _clip_rects_against_skipped_blocks,
)


class TestSourceCleanupUnprotect(unittest.TestCase):
    def test_text_redaction_not_clipped_by_unprotected_image(self):
        image_block = SimpleNamespace(
            index=0,
            page_index=0,
            type="image",
            bbox=(0.0, 0.0, 100.0, 100.0),
            text=None,
            has_text=lambda: False,
            should_skip_redaction=lambda: False,
        )
        page = SimpleNamespace(page_index=0, blocks=[image_block])
        layout_doc = SimpleNamespace(pages=[page])

        text_rect = (10.0, 10.0, 90.0, 40.0)
        clipped = _clip_rects_against_skipped_blocks(
            [text_rect],
            layout_doc,
            page_index=0,
            skip_block_indices=set(),
            unprotect_block_indices={0},
        )
        self.assertEqual(clipped, [text_rect])

    def test_text_redaction_still_clipped_by_protected_image(self):
        image_block = SimpleNamespace(
            index=0,
            page_index=0,
            type="image",
            bbox=(0.0, 0.0, 100.0, 100.0),
            text=None,
            has_text=lambda: False,
            should_skip_redaction=lambda: False,
        )
        page = SimpleNamespace(page_index=0, blocks=[image_block])
        layout_doc = SimpleNamespace(pages=[page])

        text_rect = (10.0, 10.0, 90.0, 40.0)
        clipped = _clip_rects_against_skipped_blocks(
            [text_rect],
            layout_doc,
            page_index=0,
            skip_block_indices=set(),
            unprotect_block_indices=None,
        )
        self.assertEqual(clipped, [])


if __name__ == "__main__":
    unittest.main()
