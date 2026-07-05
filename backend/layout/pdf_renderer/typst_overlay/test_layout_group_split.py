# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for Typst layout group text splitting."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer


def test_split_layout_group_text_returns_companion_parts():
    block = LayoutBlock(
        page_index=0,
        bbox=(0.0, 0.0, 100.0, 200.0),
        type="text",
        index=5,
        text="Source paragraph",
        raw={
            "_layout_group_pairs": [
                {"index": 6, "bbox": [110.0, 0.0, 210.0, 200.0], "page_index": 0},
            ]
        },
    )
    translated = "one two three four five six seven eight"
    result = TypstOverlayRenderer._split_layout_group_text(block, translated)
    assert result["main_text"]
    assert len(result["group_parts"]) == 1
    assert result["group_parts"][0]["text"]
    assert result["group_parts"][0]["block_id"] == "block-5-group-6"


def test_split_layout_group_text_uses_stored_parts():
    block = LayoutBlock(
        page_index=0,
        bbox=(0.0, 0.0, 100.0, 200.0),
        type="text",
        index=13,
        text="Source paragraph",
        raw={
            "_layout_group_pairs": [
                {"index": 14, "bbox": [110.0, 0.0, 210.0, 200.0], "page_index": 0},
            ]
        },
    )
    segment = {
        "layout_block_indices": [13, 14],
        "layout_group_text_parts": {"13": "Stored left", "14": "Stored right"},
    }
    result = TypstOverlayRenderer._split_layout_group_text(
        block,
        "area split fallback text",
        segment=segment,
    )
    assert result["main_text"] == "Stored left"
    assert len(result["group_parts"]) == 1
    assert result["group_parts"][0]["text"] == "Stored right"


def test_split_layout_group_text_reverse_lookup_from_companion_metadata():
    primary = LayoutBlock(
        page_index=0,
        bbox=(0.0, 0.0, 100.0, 200.0),
        type="text",
        index=17,
        text="Source paragraph",
        raw={"block_index": 17},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(110.0, 0.0, 210.0, 200.0),
        type="text",
        index=18,
        text="",
        raw={"block_index": 18, "_layout_group_pair_of": 17},
    )
    layout_doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )
    translated = "one two three four five six seven eight nine ten"
    result = TypstOverlayRenderer._split_layout_group_text(
        primary,
        translated,
        layout_doc,
    )
    assert result["main_text"]
    assert len(result["group_parts"]) == 1
    assert result["group_parts"][0]["text"]
    assert len(result["main_text"]) < len(translated)
