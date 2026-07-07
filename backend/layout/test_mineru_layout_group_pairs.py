# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for MinerU column layout group pairing (multi-column safe)."""

from __future__ import annotations

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.layout_group_pair_utils import (
    CROSS_PAGE_PAIR_OF_KEY,
    LAYOUT_GROUP_PAIR_OF_KEY,
    LAYOUT_GROUP_PAIRS_KEY,
    is_flow_column_continuation_bbox,
    is_same_row_parallel_column_pair,
    resolve_layout_group_pairs_for_block,
)
from layout.markdown_builder import LayoutMarkdownBuilder, _build_layout_markdown
from layout.mineru_layout_model import _finalize_mineru_layout_document
from layout.ocr_provider.mineru.layout_group_pairs import (
    apply_mineru_merge_prev_layout_group_pairs,
    apply_mineru_spatial_layout_group_pairs,
)
from layout.ocr_provider.paddle.layout_group_pairs import apply_spatial_layout_group_pairs
from layout.ocr_provider.paddle.zip_loader import _enrich_layout_group_pairs_on_document


def test_same_row_parallel_columns_detected():
    left = (40.0, 100.0, 260.0, 140.0)
    right = (320.0, 102.0, 540.0, 142.0)
    assert is_same_row_parallel_column_pair(left, right, page_width=595.0)


def test_flow_column_continuation_not_same_row_parallel():
    primary = (39.0, 566.0, 293.0, 663.0)
    companion = (301.4, 522.9, 552.8, 662.4)
    assert not is_same_row_parallel_column_pair(primary, companion, page_width=595.0)
    assert is_flow_column_continuation_bbox(
        primary,
        companion,
        page_height=842.0,
        page_width=595.0,
    )


def test_spatial_pairs_empty_flow_companion_not_same_row_parallel():
    primary = LayoutBlock(
        page_index=0,
        bbox=(39.0, 566.0, 293.0, 663.0),
        type="text",
        index=13,
        text="Left column paragraph text that continues",
        raw={"type": "text"},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.4, 522.9, 552.8, 662.4),
        type="text",
        index=14,
        text="",
        raw={"type": "text"},
    )
    blocks = [primary, companion]
    paired = apply_mineru_spatial_layout_group_pairs(
        blocks,
        page_height=842.0,
        page_width=595.0,
    )
    assert paired == 1
    assert companion.raw.get(LAYOUT_GROUP_PAIR_OF_KEY) == 13


def test_spatial_rejects_same_row_parallel_empty_companion():
    left = LayoutBlock(
        page_index=0,
        bbox=(40.0, 100.0, 260.0, 140.0),
        type="text",
        index=0,
        text="Top left paragraph.",
        raw={"type": "text"},
    )
    right = LayoutBlock(
        page_index=0,
        bbox=(320.0, 100.0, 540.0, 140.0),
        type="text",
        index=1,
        text="",
        raw={"type": "text"},
    )
    blocks = [left, right]
    paired = apply_mineru_spatial_layout_group_pairs(
        blocks,
        page_height=842.0,
        page_width=595.0,
    )
    assert paired == 0


def test_spatial_rejects_same_row_parallel_text_blocks():
    left = LayoutBlock(
        page_index=0,
        bbox=(40.0, 200.0, 260.0, 240.0),
        type="text",
        index=2,
        text="Left column row text.",
        raw={"type": "text"},
    )
    right = LayoutBlock(
        page_index=0,
        bbox=(320.0, 200.0, 540.0, 240.0),
        type="text",
        index=3,
        text="Right column row text.",
        raw={"type": "text"},
    )
    blocks = [left, right]
    paired = apply_mineru_spatial_layout_group_pairs(
        blocks,
        page_height=842.0,
        page_width=595.0,
    )
    assert paired == 0


def test_merge_prev_rejects_same_row_parallel_heading_and_body():
    primary = LayoutBlock(
        page_index=0,
        bbox=(40.0, 520.0, 134.0, 536.0),
        type="text",
        index=10,
        text="Section heading",
        raw={"type": "text"},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.0, 522.0, 552.0, 661.0),
        type="text",
        index=11,
        text="Right column body on the same row.",
        raw={"type": "text", "merge_prev": True, "lines_deleted": True},
    )
    blocks = [primary, companion]
    paired = apply_mineru_merge_prev_layout_group_pairs(
        blocks,
        page_height=842.0,
        page_width=595.0,
    )
    assert paired == 0


def test_finalize_keeps_same_row_multi_column_as_separate_segments():
    left = LayoutBlock(
        page_index=0,
        bbox=(40.0, 200.0, 260.0, 240.0),
        type="text",
        index=0,
        text="Left column row text.",
        raw={"type": "text"},
    )
    right = LayoutBlock(
        page_index=0,
        bbox=(320.0, 200.0, 540.0, 240.0),
        type="text",
        index=1,
        text="Right column row text.",
        raw={"type": "text"},
    )
    pages_dict = {0: [left, right]}
    pdf_info = [{"page_idx": 0, "page_size": [595.0, 842.0]}]
    doc = _finalize_mineru_layout_document(pages_dict, pdf_info)
    result = _build_layout_markdown(LayoutMarkdownBuilder(deep_split=False), doc)
    multi_block_chunks = [
        chunk for chunk in result.chunks if len(chunk.block_indices) >= 2
    ]
    assert multi_block_chunks == []
    assert len(result.chunks) == 2


def test_finalize_pairs_empty_flow_companion_into_single_segment():
    primary = LayoutBlock(
        page_index=0,
        bbox=(39.0, 566.0, 293.0, 663.0),
        type="text",
        index=13,
        text="Left column paragraph text that continues",
        raw={"type": "text"},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.4, 522.9, 552.8, 662.4),
        type="text",
        index=14,
        text="",
        raw={"type": "text"},
    )
    pages_dict = {0: [primary, companion]}
    pdf_info = [{"page_idx": 0, "page_size": [595.0, 842.0]}]
    doc = _finalize_mineru_layout_document(pages_dict, pdf_info)
    result = _build_layout_markdown(LayoutMarkdownBuilder(deep_split=False), doc)
    multi_block_chunks = [
        chunk for chunk in result.chunks if len(chunk.block_indices) >= 2
    ]
    assert len(multi_block_chunks) == 1
    assert multi_block_chunks[0].block_indices == [13, 14]
    assert companion.raw.get(LAYOUT_GROUP_PAIR_OF_KEY) == 13
    assert any(
        p.get("index") == 14
        for p in (primary.raw.get(LAYOUT_GROUP_PAIRS_KEY) or [])
    )


def test_cross_page_companion_not_layout_group_paired_with_right_column():
    """Cross-page left companion must not pair with same-row right column (seg 26 case)."""
    cross_page_left = LayoutBlock(
        page_index=1,
        bbox=(41.0, 31.0, 291.0, 157.0),
        type="text",
        index=24,
        text=None,
        raw={"type": "text", CROSS_PAGE_PAIR_OF_KEY: 20},
    )
    right_column = LayoutBlock(
        page_index=1,
        bbox=(299.0, 29.0, 554.0, 195.0),
        type="text",
        index=28,
        text="Right column paragraph body on page two.",
        raw={"type": "text"},
    )
    blocks = [cross_page_left, right_column]
    apply_spatial_layout_group_pairs(
        blocks,
        page_height=842.0,
        page_width=595.0,
    )
    assert cross_page_left.raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is None
    assert resolve_layout_group_pairs_for_block(right_column, None) == []


def test_mineru_enrich_on_document_skips_paddle_spatial_for_cross_page():
    """Typst/API enrich must not apply Paddle spatial pairing on MinerU engine docs."""
    cross_page_left = LayoutBlock(
        page_index=1,
        bbox=(41.0, 31.0, 291.0, 157.0),
        type="text",
        index=24,
        text=None,
        raw={"type": "text", CROSS_PAGE_PAIR_OF_KEY: 20},
    )
    right_column = LayoutBlock(
        page_index=1,
        bbox=(299.0, 29.0, 554.0, 195.0),
        type="text",
        index=28,
        text="Right column paragraph body on page two.",
        raw={"type": "text"},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=1, blocks=[cross_page_left, right_column], width=595.0, height=842.0)],
        engine="mineru",
    )
    _enrich_layout_group_pairs_on_document(doc, None)
    assert cross_page_left.raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is None
    assert resolve_layout_group_pairs_for_block(right_column, doc) == []


def test_finalize_segment_keeps_two_blocks_for_column_flow_not_three():
    """Column-flow segment stays at two blocks; cross-page must not add a third."""
    primary = LayoutBlock(
        page_index=0,
        bbox=(39.0, 566.0, 293.0, 663.0),
        type="text",
        index=13,
        text="Left column paragraph text that continues",
        raw={"type": "text"},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.4, 522.9, 552.8, 662.4),
        type="text",
        index=14,
        text="",
        raw={"type": "text"},
    )
    pages_dict = {0: [primary, companion]}
    pdf_info = [{"page_idx": 0, "page_size": [595.0, 842.0]}]
    doc = _finalize_mineru_layout_document(pages_dict, pdf_info)
    _enrich_layout_group_pairs_on_document(doc, None)
    result = _build_layout_markdown(LayoutMarkdownBuilder(deep_split=False), doc)
    multi_block_chunks = [
        chunk for chunk in result.chunks if len(chunk.block_indices) >= 2
    ]
    assert len(multi_block_chunks) == 1
    assert multi_block_chunks[0].block_indices == [13, 14]
    assert len(multi_block_chunks[0].block_indices) == 2
