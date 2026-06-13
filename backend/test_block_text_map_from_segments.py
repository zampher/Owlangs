# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PDF block text map built from translation segments."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_pdf_generator_module():
    spec = importlib.util.spec_from_file_location(
        "pdf_generator_standalone",
        BACKEND_DIR / "app" / "services" / "download" / "pdf_generator.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_pdf_generator = _load_pdf_generator_module()
PDFGenerator = _pdf_generator.PDFGenerator
_segment_export_text = _pdf_generator._segment_export_text
_expand_renderable_block_indices = _pdf_generator._expand_renderable_block_indices

from layout.base import LayoutBlock, LayoutDocument, LayoutPage  # noqa: E402
from layout.mineru_layout_model import parse_layout_json  # noqa: E402


def test_segment_export_text_prefers_modified_over_target():
    seg = {"target_text": "译文", "modified_text": "人工修订"}
    assert _segment_export_text(seg, "target_text") == "人工修订"


def test_segment_export_text_falls_back_to_target_when_no_modified():
    seg = {"target_text": "译文", "modified_text": None}
    assert _segment_export_text(seg, "target_text") == "译文"


def test_build_block_text_map_uses_target_when_only_some_segments_have_modified():
    layout_doc = parse_layout_json(PROJECT_ROOT / "test" / "layout-1.json")
    generator = PDFGenerator(task_manager=None)
    segments = [
        {
            "segment_index": 0,
            "layout_block_indices": [10],
            "modified_text": "edited",
            "target_text": "ignored",
        },
        {
            "segment_index": 27,
            "layout_block_indices": [27],
            "target_text": "摘要标题译文",
        },
        {
            "segment_index": 28,
            "layout_block_indices": [28],
            "target_text": "摘要正文译文",
        },
    ]
    block_map = generator.build_block_text_map_from_segments(
        layout_doc,
        segments,
        text_field="target_text",
        task_state={},
        is_deep_split_enabled=False,
    )
    assert block_map[10] == "edited"
    assert block_map[27] == "摘要标题译文"
    assert block_map[28] == "摘要正文译文"


def test_build_block_text_map_resolves_segment_layout_block_map():
    layout_doc = parse_layout_json(PROJECT_ROOT / "test" / "layout-1.json")
    generator = PDFGenerator(task_manager=None)
    segments = [
        {
            "segment_index": 28,
            "target_text": "摘要正文译文",
        },
    ]
    task_state = {
        "segment_layout_block_map": [[] for _ in range(28)] + [[28]],
    }
    block_map = generator.build_block_text_map_from_segments(
        layout_doc,
        segments,
        text_field="target_text",
        task_state=task_state,
        is_deep_split_enabled=False,
    )
    assert block_map[28] == "摘要正文译文"


def test_expand_list_block_to_text_children():
    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(308.0, 320.0, 528.0, 502.0),
                        type="list",
                        index=12,
                        text="",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(310.0, 411.0, 444.0, 421.0),
                        type="text",
                        index=13,
                        text="(57) ABSTRACT",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=(308.0, 423.0, 528.0, 503.0),
                        type="text",
                        index=14,
                        text="A sorbent polymer is provided...",
                    ),
                ],
            )
        ]
    )
    block_index_to_type = {12: "list", 13: "text", 14: "text"}
    block_index_to_bbox = {
        12: (308.0, 320.0, 528.0, 502.0),
        13: (310.0, 411.0, 444.0, 421.0),
        14: (308.0, 423.0, 528.0, 503.0),
    }
    expanded = _expand_renderable_block_indices(
        [12],
        layout_doc,
        block_index_to_type,
        block_index_to_bbox,
    )
    assert expanded == [13, 14]

    generator = PDFGenerator(task_manager=None)
    block_map = generator.build_block_text_map_from_segments(
        layout_doc,
        [
            {
                "segment_index": 12,
                "layout_block_indices": [12],
                "target_text": "(57) ABSTRACT\nTranslated abstract body",
            }
        ],
        text_field="target_text",
        task_state={},
        is_deep_split_enabled=False,
    )
    assert block_map[13] == "(57) ABSTRACT"
    assert block_map[14] == "Translated abstract body"
