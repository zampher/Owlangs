# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for per-block PDF page numbers on layout segments."""

from __future__ import annotations

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from utils.format_convert_utils import (
    build_layout_block_page_number_map,
    page_numbers_for_layout_block_indices,
    sync_segment_layout_block_page_numbers,
)


def _doc_with_pages() -> LayoutDocument:
    page0 = LayoutPage(
        page_index=0,
        width=600.0,
        height=800.0,
        blocks=[
            LayoutBlock(
                page_index=0,
                type="text",
                bbox=(40.0, 520.0, 290.0, 660.0),
                index=13,
                text="left column",
            ),
            LayoutBlock(
                page_index=0,
                type="text",
                bbox=(301.0, 520.0, 552.0, 661.0),
                index=14,
                text="right column",
            ),
        ],
    )
    page1 = LayoutPage(
        page_index=1,
        width=600.0,
        height=800.0,
        blocks=[
            LayoutBlock(
                page_index=1,
                type="text",
                bbox=(41.0, 31.0, 291.0, 157.0),
                index=24,
                text="next page continuation",
            ),
        ],
    )
    return LayoutDocument(pages=[page0, page1], engine="mineru")


def test_page_numbers_for_cross_page_segment_indices() -> None:
    doc = _doc_with_pages()
    page_map = build_layout_block_page_number_map(doc)
    assert page_map[13] == 1
    assert page_map[14] == 1
    assert page_map[24] == 2

    pages = page_numbers_for_layout_block_indices(
        [13, 24, 14],
        layout_document=doc,
        page_number_map=page_map,
    )
    assert pages == [1, 2, 1]


def test_sync_segment_layout_block_page_numbers() -> None:
    doc = _doc_with_pages()
    segment = {
        "segment_index": 13,
        "layout_block_indices": [13, 24, 14],
        "layout_block_bbox": [
            [40.0, 520.0, 290.0, 660.0],
            [41.0, 31.0, 291.0, 157.0],
            [301.0, 520.0, 552.0, 661.0],
        ],
    }
    assert sync_segment_layout_block_page_numbers(segment, doc) is True
    assert segment["layout_block_page_numbers"] == [1, 2, 1]
    assert sync_segment_layout_block_page_numbers(segment, doc) is False
