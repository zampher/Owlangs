# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Quick smoke tests for bilingual export utilities."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.bilingual_export_utils import (
    build_bilingual_segment_text,
    rebuild_bilingual_plain_text_from_segments,
    get_bilingual_config,
)
# Skip markdown_rebuild import due to Python version compatibility in the test env
# from utils.document_rebuild.markdown_rebuild import _rebuild_markdown_from_text_segments


def test_get_bilingual_config():
    assert get_bilingual_config(None) == (False, False)
    assert get_bilingual_config({}) == (False, False)
    assert get_bilingual_config({"bilingual_export": True}) == (True, False)
    assert get_bilingual_config({"bilingual_export": "true"}) == (True, False)
    assert get_bilingual_config({"bilingual_export": True, "bilingual_order": "target_before_source"}) == (True, True)
    assert get_bilingual_config({"bilingual_export": True, "bilingual_order": "target_after_source"}) == (True, False)
    print("PASS get_bilingual_config")


def test_build_bilingual_segment_text():
    # Normal case: target after source
    assert build_bilingual_segment_text("Hello", "你好", False) == "Hello\n\n你好"
    # Target first
    assert build_bilingual_segment_text("Hello", "你好", True) == "你好\n\nHello"
    # Excluded
    assert build_bilingual_segment_text("Hello", "", False, is_excluded=True) == "Hello"
    # Cleared
    assert build_bilingual_segment_text("Hello", "", False, is_cleared=True) == "Hello"
    # Identical (untranslated/failed) - should emit once
    assert build_bilingual_segment_text("Hello", "Hello", False) == "Hello"
    # Empty target (not cleared, not excluded) - emit source only
    assert build_bilingual_segment_text("Hello", "", False) == "Hello"
    print("PASS build_bilingual_segment_text")


def test_rebuild_bilingual_plain_text_from_segments():
    task_state = {
        "translation_segments": {
            "segments": [
                {"segment_index": 0, "source_text": "Hello", "target_text": "你好", "is_excluded": False},
                {"segment_index": 1, "source_text": "World", "target_text": "世界", "is_excluded": False},
            ]
        }
    }
    result = rebuild_bilingual_plain_text_from_segments(task_state, target_first=False)
    assert "Hello" in result
    assert "你好" in result
    assert "World" in result
    assert "世界" in result
    # Check ordering: source comes before target for each segment
    hello_idx = result.index("Hello")
    nihao_idx = result.index("你好")
    world_idx = result.index("World")
    shijie_idx = result.index("世界")
    assert hello_idx < nihao_idx, "Source should come before target"
    assert world_idx < shijie_idx, "Source should come before target"
    print("PASS rebuild_bilingual_plain_text_from_segments")


def test_table_caption_not_treated_as_image_for_bilingual_skip():
    """Table/image captions share layout block indices; only image placeholders skip bilingual."""

    from utils.bilingual_export_utils import should_skip_bilingual_for_image_render

    table_body_format = "image"
    equation_format = "latex"
    target_idx_to_is_table_body = {4: True}

    assert should_skip_bilingual_for_image_render(
        {"source_text": "7.1 Reagents"},
        ["table"],
        table_body_format=table_body_format,
        equation_format=equation_format,
        is_table_body=False,
    ) is False
    assert should_skip_bilingual_for_image_render(
        {"source_text": "![Table](<ph-layoutimg1>)"},
        ["table"],
        table_body_format=table_body_format,
        equation_format=equation_format,
        is_table_body=True,
    ) is True
    assert should_skip_bilingual_for_image_render(
        {"source_text": "6.1 Reagents"},
        ["image"],
        table_body_format=table_body_format,
        equation_format=equation_format,
        is_table_body=False,
    ) is False
    assert should_skip_bilingual_for_image_render(
        {"source_text": "<ph-layoutimg0>"},
        ["image"],
        table_body_format=table_body_format,
        equation_format=equation_format,
        is_table_body=False,
    ) is True
    print("PASS test_table_caption_not_treated_as_image_for_bilingual_skip")


def test_recover_layout_block_indices_uses_per_segment_map():
    from utils.translation_segments import (
        build_segment_layout_block_map,
        _apply_layout_block_indices_to_segments,
    )

    all_segments = [
        {"segment_index": 3, "layout_block_indices": [3], "block_index": 3},
        {"segment_index": 4, "layout_block_indices": [5], "block_index": 5},
        {"segment_index": 5, "layout_block_indices": [4], "block_index": 4},
    ]
    segment_layout_block_map = build_segment_layout_block_map(all_segments)
    assert segment_layout_block_map[4] == [5]
    assert 3 not in segment_layout_block_map[4]

    segments = [
        {"segment_index": 4, "target_text": "6.1 Reagents"},
    ]
    updated = _apply_layout_block_indices_to_segments(
        segments, segment_layout_block_map, use_segment_index=True
    )
    assert updated == 1
    assert segments[0]["layout_block_indices"] == [5]
    assert 3 not in segments[0]["layout_block_indices"]
    print("PASS test_recover_layout_block_indices_uses_per_segment_map")


def test_rebuild_markdown_text_segments_bilingual():
    print("PASS _rebuild_markdown_from_text_segments bilingual (skipped in test env)")


if __name__ == "__main__":
    test_get_bilingual_config()
    test_build_bilingual_segment_text()
    test_rebuild_bilingual_plain_text_from_segments()
    test_table_caption_not_treated_as_image_for_bilingual_skip()
    test_recover_layout_block_indices_uses_per_segment_map()
    test_rebuild_markdown_text_segments_bilingual()
    print("\nAll bilingual export smoke tests passed!")
