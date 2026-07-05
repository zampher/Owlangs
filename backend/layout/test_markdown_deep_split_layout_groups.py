# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for deep-split paragraph to layout-group block mapping."""

from __future__ import annotations

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.markdown_builder import LayoutMarkdownBuilder, _build_layout_markdown


def _two_column_wrap_doc() -> LayoutDocument:
    primary = LayoutBlock(
        page_index=0,
        bbox=(41.0, 465.0, 291.0, 719.0),
        type="text",
        index=53,
        text="First paragraph in left column.\n\nSecond paragraph continues.",
        raw={},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.0, 31.0, 552.0, 192.0),
        type="text",
        index=54,
        text="",
        raw={"_layout_group_pair_of": 53},
    )
    return LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )


def test_deep_split_maps_paragraphs_to_primary_then_companion():
    builder = LayoutMarkdownBuilder(
        max_chunk_chars=8000,
        deep_split=True,
        include_structural_blocks=True,
    )
    result = _build_layout_markdown(builder, _two_column_wrap_doc())
    text_chunks = [ch for ch in result.chunks if ch.chunk_type == "text"]
    assert len(text_chunks) == 2
    assert text_chunks[0].block_indices == [53]
    assert text_chunks[0].block_texts == ["First paragraph in left column."]
    assert text_chunks[1].block_indices == [54]
    assert text_chunks[1].block_texts == ["Second paragraph continues."]


def test_deep_split_single_paragraph_keeps_companion_for_area_split():
    primary = LayoutBlock(
        page_index=0,
        bbox=(41.0, 465.0, 291.0, 719.0),
        type="text",
        index=53,
        text="Single long paragraph only.",
        raw={},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.0, 31.0, 552.0, 192.0),
        type="text",
        index=54,
        text="",
        raw={"_layout_group_pair_of": 53},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )
    builder = LayoutMarkdownBuilder(
        max_chunk_chars=8000,
        deep_split=True,
        include_structural_blocks=True,
    )
    result = _build_layout_markdown(builder, doc)
    text_chunks = [ch for ch in result.chunks if ch.chunk_type == "text"]
    assert len(text_chunks) == 1
    assert text_chunks[0].block_indices == [53, 54]
    assert text_chunks[0].block_texts == ["Single long paragraph only.", ""]
