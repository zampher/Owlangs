# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PDF affected page computation."""

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.pdf_renderer.typst_overlay.affected_pages import (
    compute_affected_page_indices_0based,
    compute_affected_page_numbers_1based,
)


def _block(
    index: int,
    page_index: int,
    *,
    cross_page: bool = False,
) -> LayoutBlock:
    raw = {"lines": []}
    if cross_page:
        raw["lines"] = [
            {
                "spans": [
                    {"cross_page": True, "content": "overflow"},
                ],
            }
        ]
    return LayoutBlock(
        page_index=page_index,
        bbox=(0.0, 0.0, 100.0, 20.0),
        type="text",
        index=index,
        text="sample",
        raw=raw,
    )


def _layout_doc(*blocks: LayoutBlock) -> LayoutDocument:
    pages = {block.page_index: LayoutPage(page_index=block.page_index, blocks=[]) for block in blocks}
    for block in blocks:
        pages[block.page_index].blocks.append(block)
    ordered = [pages[i] for i in sorted(pages.keys())]
    return LayoutDocument(pages=ordered)


def test_affected_pages_single_segment():
    layout = _layout_doc(_block(1, 0))
    segments = [
        {"segment_index": 0, "layout_block_indices": [1]},
    ]
    assert compute_affected_page_indices_0based(layout, segments, [0]) == [0]
    assert compute_affected_page_numbers_1based(layout, segments, [0]) == [1]


def test_affected_pages_cross_page_includes_next_page():
    layout = _layout_doc(
        _block(1, 0, cross_page=True),
        _block(2, 1),
    )
    segments = [
        {"segment_index": 3, "layout_block_indices": [1]},
    ]
    assert compute_affected_page_indices_0based(layout, segments, [3]) == [0, 1]
    assert compute_affected_page_numbers_1based(layout, segments, [3]) == [1, 2]


def test_affected_pages_union_for_multiple_segments():
    layout = _layout_doc(_block(1, 0), _block(2, 1))
    segments = [
        {"segment_index": 0, "layout_block_indices": [1]},
        {"segment_index": 1, "layout_block_indices": [2]},
    ]
    assert compute_affected_page_indices_0based(layout, segments, [0, 1]) == [0, 1]
