# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for chart caption extraction in layout markdown builder."""

from __future__ import annotations

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.block_types import CHART_BODY, CHART_CAPTION
from layout.markdown_builder import LayoutMarkdownBuilder, _build_layout_markdown


def _caption_sub(text: str) -> dict:
    return {
        "type": CHART_CAPTION,
        "lines": [
            {
                "spans": [
                    {"type": "text", "content": text},
                ],
            },
        ],
    }


def _chart_body_sub(image_path: str) -> dict:
    return {
        "type": CHART_BODY,
        "lines": [
            {
                "spans": [
                    {
                        "type": "chart",
                        "image_path": image_path,
                    },
                ],
            },
        ],
    }


def test_chart_emits_all_captions_in_nested_order():
    panel_label = "h"
    figure_caption = (
        "Figure 3. Piezoelectric neural stimulation restores walking in spinal cord injury."
    )
    chart_block = LayoutBlock(
        page_index=0,
        bbox=(47.0, 378.0, 557.0, 655.0),
        type="chart",
        index=10,
        image_path="images/chart_10.png",
        raw={
            "blocks": [
                _caption_sub(panel_label),
                _chart_body_sub("images/chart_10.png"),
                _caption_sub(figure_caption),
            ],
        },
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[chart_block])],
        engine="mineru",
    )
    builder = LayoutMarkdownBuilder(
        max_chunk_chars=8000,
        chart_body_format="image",
        include_images=True,
    )

    result = _build_layout_markdown(builder, doc)
    text_chunks = [ch for ch in result.chunks if ch.chunk_type == "text"]
    chart_chunks = [ch for ch in result.chunks if ch.chunk_type == CHART_BODY]

    assert len(text_chunks) == 2
    assert text_chunks[0].block_texts == [panel_label]
    assert text_chunks[1].block_texts == [figure_caption]
    assert len(chart_chunks) == 1
    assert chart_chunks[0].image_path == "images/chart_10.png"
