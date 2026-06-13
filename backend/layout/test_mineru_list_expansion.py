# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for MinerU list-container expansion during layout parse."""

from __future__ import annotations

from layout.markdown_builder import LayoutMarkdownBuilder, _build_layout_markdown
from layout.mineru_layout_model import (
    _append_mineru_block_to_pages,
    _finalize_mineru_layout_document,
)


def _sample_list_para_block() -> dict:
    return {
        "bbox": [308, 320, 528, 502],
        "type": "list",
        "blocks": [
            {
                "type": "text",
                "bbox": [310, 411, 444, 421],
                "lines": [
                    {
                        "spans": [
                            {"type": "text", "content": "(57) ABSTRACT"},
                        ]
                    }
                ],
            },
            {
                "type": "text",
                "bbox": [308, 423, 528, 503],
                "lines": [
                    {
                        "spans": [
                            {
                                "type": "text",
                                "content": "A sorbent polymer is provided that interacts with urea.",
                            }
                        ]
                    }
                ],
            },
        ],
    }


def test_append_mineru_block_expands_list_into_parent_and_children():
    pages_dict: dict[int, list] = {}
    global_index = _append_mineru_block_to_pages(
        pages_dict,
        page_idx=0,
        block_data=_sample_list_para_block(),
        global_index=12,
    )
    assert global_index == 15
    blocks = pages_dict[0]
    assert len(blocks) == 3
    assert blocks[0].index == 12
    assert blocks[0].type == "list"
    assert not (blocks[0].text or "").strip()
    assert blocks[1].index == 13
    assert blocks[1].type == "text"
    assert "(57) ABSTRACT" in (blocks[1].text or "")
    assert blocks[2].index == 14
    assert "sorbent polymer" in (blocks[2].text or "")


def test_middle_json_style_list_yields_one_segment_per_child_block():
    pages_dict: dict[int, list] = {}
    global_index = 0
    global_index = _append_mineru_block_to_pages(
        pages_dict,
        0,
        _sample_list_para_block(),
        global_index,
    )
    doc = _finalize_mineru_layout_document(
        pages_dict,
        pdf_info=[{"page_idx": 0, "page_size": [612, 792]}],
    )

    builder = LayoutMarkdownBuilder(
        max_chunk_chars=8000,
        deep_split=False,
        include_structural_blocks=True,
    )
    result = _build_layout_markdown(builder, doc)

    text_chunks = [ch for ch in result.chunks if ch.chunk_type == "text"]
    abstract_chunks = [
        ch for ch in text_chunks if "ABSTRACT" in (ch.text or "") or "sorbent" in (ch.text or "")
    ]
    assert len(abstract_chunks) == 2
    assert abstract_chunks[0].block_indices == [1]
    assert abstract_chunks[1].block_indices == [2]
    assert all(len(ch.block_indices) == 1 for ch in text_chunks)
