# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for layout group companion helpers."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.layout_group_pair_utils import (
    canonicalize_layout_group_pairs,
    distribute_text_by_weights,
    is_column_continuation_bbox,
    is_column_wrap_continuation_bbox,
    layout_group_text_parts_cover_indices,
    merge_layout_group_text_parts,
    normalize_layout_group_text_parts,
    paddle_group_cross_column_pair,
    resolve_layout_group_pairs_for_block,
    split_translated_text_for_layout_group,
    split_translated_text_for_layout_group_with_parts,
)


def test_is_column_continuation_bbox_detects_right_column():
    primary = (84.0, 1139.0, 584.0, 1324.0)
    companion = (603.0, 1046.0, 1106.0, 1325.0)
    assert is_column_continuation_bbox(primary, companion) is True


def test_is_column_continuation_bbox_rejects_unrelated_blocks():
    primary = (84.0, 1139.0, 584.0, 1324.0)
    far = (84.0, 1400.0, 584.0, 1500.0)
    assert is_column_continuation_bbox(primary, far) is False


def test_paddle_group_cross_column_pair_detects_left_right_columns():
    primary = (41.984, 465.418, 291.89, 719.373)
    companion = (302.386, 31.494, 551.792, 192.466)
    assert paddle_group_cross_column_pair(primary, companion) is True


def test_paddle_group_cross_column_pair_rejects_same_column():
    left_a = (41.984, 465.418, 291.89, 719.373)
    left_b = (41.984, 213.962, 291.39, 456.419)
    assert paddle_group_cross_column_pair(left_a, left_b) is False


def test_split_translated_text_for_layout_group_one_to_many():
    primary_bbox = (0.0, 0.0, 100.0, 200.0)
    pairs = [
        {"index": 1, "bbox": [120.0, 0.0, 220.0, 200.0], "page_index": 0},
        {"index": 2, "bbox": [240.0, 0.0, 340.0, 200.0], "page_index": 0},
    ]
    translated = "alpha beta gamma delta epsilon"
    main_text, companions = split_translated_text_for_layout_group(
        primary_bbox,
        translated,
        pairs,
    )
    assert main_text
    assert len(companions) == 2
    joined = " ".join([main_text, companions[0]["text"], companions[1]["text"]]).split()
    assert len(joined) >= 4
    assert sum(len(c["text"]) for c in companions) > 0


def test_resolve_layout_group_pairs_for_block_reverse_lookup():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    primary = LayoutBlock(
        page_index=0,
        bbox=(0.0, 0.0, 100.0, 200.0),
        type="text",
        index=17,
        text="left column",
        raw={},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(120.0, 0.0, 220.0, 200.0),
        type="text",
        index=18,
        text="",
        raw={"_layout_group_pair_of": 17},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )
    pairs = resolve_layout_group_pairs_for_block(primary, doc)
    assert len(pairs) == 1
    assert pairs[0]["index"] == 18


def test_resolve_layout_group_pairs_corrects_primary_duplicated_bbox():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    primary_bbox = (41.984, 569.4, 291.89, 661.883)
    companion_bbox = (301.387, 522.908, 552.792, 662.383)
    primary = LayoutBlock(
        page_index=0,
        bbox=primary_bbox,
        type="text",
        index=13,
        text="Primary paragraph",
        raw={
            "_layout_group_pairs": [
                {
                    "index": 14,
                    "bbox": list(primary_bbox),
                    "page_index": 0,
                }
            ]
        },
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=companion_bbox,
        type="text",
        index=14,
        text="",
        raw={"_layout_group_pair_of": 13},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )
    pairs = resolve_layout_group_pairs_for_block(primary, doc)
    assert len(pairs) == 1
    assert pairs[0]["bbox"] == [float(v) for v in companion_bbox]

    main_text, companions = split_translated_text_for_layout_group(
        primary_bbox,
        "W" * 406,
        pairs,
    )
    assert companions
    assert companions[0]["bbox"] == tuple(companion_bbox)
    assert len(main_text) < 406
    assert len(companions[0]["text"]) > 0


def test_canonicalize_layout_group_pairs_keeps_valid_metadata():
    primary_bbox = (0.0, 0.0, 100.0, 200.0)
    companion_bbox = (120.0, 0.0, 220.0, 200.0)
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=primary_bbox,
                        type="text",
                        index=1,
                        text="a",
                    ),
                    LayoutBlock(
                        page_index=0,
                        bbox=companion_bbox,
                        type="text",
                        index=2,
                        text="",
                    ),
                ],
            )
        ]
    )
    pairs = canonicalize_layout_group_pairs(
        primary_bbox,
        [{"index": 2, "bbox": list(companion_bbox), "page_index": 0}],
        doc,
    )
    assert pairs[0]["bbox"] == [float(v) for v in companion_bbox]


def test_is_column_wrap_continuation_bbox_detects_bottom_left_to_top_right():
    primary = (42.484, 718.873, 257.903, 730.871)
    companion = (311.383, 31.494, 551.293, 65.988)
    assert is_column_wrap_continuation_bbox(primary, companion, page_height=842.0) is True
    assert is_column_continuation_bbox(primary, companion, page_height=842.0) is True


def test_distribute_text_by_weights_preserves_all_words():
    text = "one two three four five six"
    parts = distribute_text_by_weights(text, [1.0, 1.0, 1.0])
    assert len(parts) == 3
    assert " ".join(parts).split() == text.split()


def test_layout_group_text_parts_merge_and_cover():
    parts = normalize_layout_group_text_parts({"13": " Left ", "14": "Right"})
    assert parts == {13: "Left", 14: "Right"}
    assert layout_group_text_parts_cover_indices(parts, [13, 14]) is True
    merged = merge_layout_group_text_parts(parts, [13, 14])
    assert merged == "Left Right"


def test_layout_block_bbox_overrides_parse_and_read():
    from layout.layout_group_pair_utils import (
        parse_layout_block_bbox_overrides,
        serialize_layout_block_bbox_overrides,
    )
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        _read_segment_layout_bbox_for_block,
    )

    overrides = parse_layout_block_bbox_overrides(
        {"13": [1.0, 2.0, 3.0, 4.0], "14": [10.0, 20.0, 30.0, 40.0]},
    )
    assert overrides == {
        13: (1.0, 2.0, 3.0, 4.0),
        14: (10.0, 20.0, 30.0, 40.0),
    }
    serialized = serialize_layout_block_bbox_overrides(overrides)
    assert serialized["14"] == [10.0, 20.0, 30.0, 40.0]

    segment = {
        "layout_block_indices": [13, 14],
        "layout_block_bbox": [
            [42.0, 569.4, 291.9, 661.9],
            [301.4, 522.9, 552.8, 662.4],
        ],
        "layout_block_bbox_overrides": serialized,
    }
    assert _read_segment_layout_bbox_for_block(segment, 13, None, None) == (
        1.0,
        2.0,
        3.0,
        4.0,
    )
    assert _read_segment_layout_bbox_for_block(segment, 14, None, None) == (
        10.0,
        20.0,
        30.0,
        40.0,
    )


def test_split_translated_text_for_layout_group_with_parts():
    primary_bbox = (0.0, 0.0, 100.0, 200.0)
    pairs = [
        {"index": 14, "bbox": [120.0, 0.0, 220.0, 200.0], "page_index": 0},
    ]
    segment = {
        "layout_block_indices": [13, 14],
        "layout_group_text_parts": {"13": "Custom left", "14": "Custom right"},
    }
    main_text, companions = split_translated_text_for_layout_group_with_parts(
        segment,
        13,
        primary_bbox,
        "ignored merged text",
        pairs,
    )
    assert main_text == "Custom left"
    assert len(companions) == 1
    assert companions[0]["text"] == "Custom right"
    assert companions[0]["index"] == 14


def test_filter_valid_layout_group_pairs_rejects_group_id_mismatch():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.layout_group_pair_utils import filter_valid_layout_group_pairs

    primary = LayoutBlock(
        page_index=1,
        bbox=(41.984, 31.494, 290.891, 158.472),
        type="text",
        index=50,
        text="Cross-page continuation paragraph text.",
        raw={"group_id": 0},
    )
    companion = LayoutBlock(
        page_index=1,
        bbox=(302.386, 31.494, 551.792, 192.466),
        type="text",
        index=54,
        text="",
        raw={"group_id": 3, "_layout_group_pair_of": 50},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=1, blocks=[primary, companion])],
        engine="paddle",
    )
    pairs = [
        {
            "index": 54,
            "bbox": [302.386, 31.494, 551.792, 192.466],
            "page_index": 1,
        }
    ]
    filtered = filter_valid_layout_group_pairs(primary, pairs, doc)
    assert filtered == []


def test_filter_valid_layout_group_pairs_keeps_same_group_id_companion():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.layout_group_pair_utils import filter_valid_layout_group_pairs

    primary = LayoutBlock(
        page_index=0,
        bbox=(41.984, 569.4, 291.89, 661.883),
        type="text",
        index=13,
        text="Left column paragraph.",
        raw={"group_id": 17},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(301.387, 522.908, 552.792, 662.383),
        type="text",
        index=14,
        text="",
        raw={"group_id": 17, "_layout_group_pair_of": 13},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion])],
        engine="paddle",
    )
    pairs = [
        {
            "index": 14,
            "bbox": [301.387, 522.908, 552.792, 662.383],
            "page_index": 0,
        }
    ]
    filtered = filter_valid_layout_group_pairs(primary, pairs, doc)
    assert len(filtered) == 1
    assert filtered[0]["index"] == 14


def test_filter_keeps_same_row_empty_paddle_companion_task_958f08a7():
    """Paddle-paired empty right column must survive same-row parallel filter."""
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.layout_group_pair_utils import (
        filter_valid_layout_group_pairs,
        resolve_layout_group_pairs_for_block,
    )

    primary = LayoutBlock(
        page_index=0,
        bbox=(48.493, 663.918, 293.456, 755.407),
        type="text",
        index=0,
        text="tions, we first tested their responsive performance under LIFU.",
        raw={"group_id": 19},
    )
    companion = LayoutBlock(
        page_index=0,
        bbox=(311.453, 663.918, 557.416, 755.907),
        type="text",
        index=1,
        text="",
        raw={"group_id": 19, "_layout_group_pair_of": 0},
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[primary, companion], width=607.4, height=800.9)],
        engine="paddle",
    )
    pairs = [
        {
            "index": 1,
            "bbox": [311.453, 663.918, 557.416, 755.907],
            "page_index": 0,
        }
    ]
    filtered = filter_valid_layout_group_pairs(primary, pairs, doc)
    assert len(filtered) == 1
    assert filtered[0]["index"] == 1
    resolved = resolve_layout_group_pairs_for_block(primary, doc)
    assert len(resolved) == 1
    assert resolved[0]["index"] == 1


def test_apply_layout_block_indices_preserves_layout_group_companions():
    from utils.translation_segments import _apply_layout_block_indices_to_segments

    segments = [
        {
            "segment_index": 19,
            "layout_block_indices": [13, 14],
            "layout_block_bbox": [
                [42.0, 569.4, 291.9, 661.9],
                [301.4, 522.9, 552.8, 662.4],
            ],
        }
    ]
    block_map = [[] for _ in range(20)]
    block_map[19] = [13]
    updated = _apply_layout_block_indices_to_segments(segments, block_map)
    assert updated == 0
    assert segments[0]["layout_block_indices"] == [13, 14]


def test_sort_layout_block_indices_reading_order_same_page_before_cross_page():
    from types import SimpleNamespace

    from layout.layout_group_pair_utils import sort_layout_block_indices_reading_order

    doc = SimpleNamespace(
        pages=[
            SimpleNamespace(
                page_index=0,
                blocks=[
                    SimpleNamespace(
                        index=13,
                        page_index=0,
                        bbox=[40.0, 520.0, 290.0, 660.0],
                    ),
                    SimpleNamespace(
                        index=14,
                        page_index=0,
                        bbox=[300.0, 520.0, 550.0, 660.0],
                    ),
                ],
            ),
            SimpleNamespace(
                page_index=1,
                blocks=[
                    SimpleNamespace(
                        index=24,
                        page_index=1,
                        bbox=[40.0, 30.0, 290.0, 160.0],
                    ),
                ],
            ),
        ]
    )
    doc.iter_blocks = lambda: (
        block
        for page in doc.pages
        for block in page.blocks
    )

    ordered = sort_layout_block_indices_reading_order(
        [13, 24, 14],
        doc,
        13,
    )
    assert ordered == [13, 14, 24]


def test_split_translated_text_for_overlay_blocks_three_bboxes():
    from types import SimpleNamespace

    from layout.layout_group_pair_utils import split_translated_text_for_overlay_blocks

    doc = SimpleNamespace(
        pages=[
            SimpleNamespace(
                page_index=0,
                blocks=[
                    SimpleNamespace(
                        index=13,
                        page_index=0,
                        bbox=[0.0, 0.0, 100.0, 200.0],
                        raw={"_cross_page_pairs": [{"index": 24, "bbox": [0.0, 0.0, 80.0, 50.0], "page_index": 1}]},
                    ),
                    SimpleNamespace(
                        index=14,
                        page_index=0,
                        bbox=[120.0, 0.0, 220.0, 200.0],
                        raw={"_layout_group_pair_of": 13},
                    ),
                ],
            ),
            SimpleNamespace(
                page_index=1,
                blocks=[
                    SimpleNamespace(
                        index=24,
                        page_index=1,
                        bbox=[0.0, 0.0, 80.0, 50.0],
                        raw={"_cross_page_pair_of": 13},
                    ),
                ],
            ),
        ]
    )
    doc.iter_blocks = lambda: (
        block
        for page in doc.pages
        for block in page.blocks
    )

    primary = doc.pages[0].blocks[0]
    segment = {
        "layout_block_indices": [13, 24, 14],
        "layout_group_text_parts": {
            "13": "Left column",
            "14": "Right column",
            "24": "Next page tail",
        },
    }
    result = split_translated_text_for_overlay_blocks(
        segment,
        primary,
        "Left column Right column Next page tail",
        doc,
    )
    assert result["used_segment_order"] is True
    assert result["main_text"] == "Left column"
    assert len(result["companion_specs"]) == 2
    by_index = {spec["index"]: spec for spec in result["companion_specs"]}
    assert by_index[14]["text"] == "Right column"
    assert by_index[14]["page_index"] == 0
    assert by_index[24]["text"] == "Next page tail"
    assert by_index[24]["page_index"] == 1
