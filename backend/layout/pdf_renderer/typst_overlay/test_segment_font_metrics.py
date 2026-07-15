# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for per-segment PDF font size helpers."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.models import RenderBlock
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    FONT_SIZE_PT_MAX,
    FONT_SIZE_PT_MIN,
    FONT_SIZE_PT_STEP,
    apply_user_font_override,
    apply_user_typography_override,
    build_block_font_map_from_segments,
    build_block_leading_map_from_segments,
    build_block_font_style_map_from_segments,
    build_block_font_weight_map_from_segments,
    clamp_font_size_pt,
    enrich_segment_font_fields,
    normalize_user_font_size_pt,
    normalize_user_font_style,
    normalize_user_font_weight,
    normalize_user_leading_em,
    primary_layout_block_index,
    segment_font_size_source,
    segment_font_style_source,
    segment_font_weight_source,
    segment_leading_em_source,
)


def test_clamp_font_size_pt_rounds_to_step():
    assert clamp_font_size_pt(9.24) == 9.2
    assert clamp_font_size_pt(72.05) == 72.0
    assert clamp_font_size_pt(0.4) == FONT_SIZE_PT_MIN


def test_normalize_user_font_size_pt_rejects_out_of_range():
    assert normalize_user_font_size_pt(None) is None
    assert normalize_user_font_size_pt(0.4) is None
    assert normalize_user_font_size_pt(0.5) == 0.5
    assert normalize_user_font_size_pt(80.0) is None
    assert normalize_user_font_size_pt(1.9) == 1.9
    assert normalize_user_font_size_pt(2.9) == 2.9
    assert normalize_user_font_size_pt(12.0) == 12.0


def test_segment_font_size_source():
    assert segment_font_size_source({}) == "auto"
    assert segment_font_size_source({"font_size_pt": 10.0}) == "user"
    assert segment_font_size_source({"font_size_pt": None}) == "auto"


def test_build_block_font_map_from_segments_expands_layout_indices():
    segments = [
        {
            "segment_index": 0,
            "font_size_pt": 11.5,
            "layout_block_indices": [3, 4],
        },
        {
            "segment_index": 1,
            "font_size_pt": None,
            "layout_block_indices": [5],
        },
        {
            "segment_index": 2,
            "font_size_pt": 9.0,
            "block_index": 7,
        },
    ]
    block_map = build_block_font_map_from_segments(segments)
    assert block_map == {3: 11.5, 4: 11.5, 7: 9.0}


def test_build_block_font_map_uses_segment_layout_block_map():
    segments = [
        {
            "segment_index": 4,
            "font_size_pt": 14.0,
        },
    ]
    task_state = {
        "segment_layout_block_map": [[], [], [], [], [12, 13]],
    }
    block_map = build_block_font_map_from_segments(segments, task_state)
    assert block_map == {12: 14.0, 13: 14.0}


def test_build_block_font_map_skips_auto_font_size_source():
    segments = [
        {
            "segment_index": 0,
            "font_size_pt": 12.0,
            "font_size_source": "auto",
            "layout_block_indices": [1],
        },
        {
            "segment_index": 1,
            "font_size_pt": 11.0,
            "font_size_source": "user",
            "layout_block_indices": [2],
        },
    ]
    block_map = build_block_font_map_from_segments(segments)
    assert block_map == {2: 11.0}


def test_apply_user_font_override_locks_fit_params():
    rb = RenderBlock(
        block_id="t",
        page_index=0,
        inner_bbox=(0.0, 0.0, 100.0, 20.0),
        plain_text="Sample text",
        markdown_text="Sample text",
        fit_to_box=True,
    )
    locked = apply_user_font_override(rb, 12.3)
    assert locked.font_size_pt == 12.3
    assert locked.fit_to_box is False
    assert locked.fit_min_font_size_pt == 12.3
    assert locked.fit_max_font_size_pt == 12.3
    assert locked.font_size_locked is True


def test_enrich_segment_font_fields_without_layout_doc():
    seg = {"font_size_pt": 10.0}
    enrich_segment_font_fields(seg, None)
    assert seg["font_size_source"] == "user"
    assert "computed_font_size_pt" not in seg
    assert "pdf_page_number" not in seg


def test_enrich_segment_pdf_page_number_from_layout():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(0.0, 0.0, 100.0, 20.0),
                        type="text",
                        index=0,
                        text="Hello",
                    ),
                ],
            ),
            LayoutPage(
                page_index=2,
                blocks=[
                    LayoutBlock(
                        page_index=2,
                        bbox=(0.0, 0.0, 100.0, 20.0),
                        type="image",
                        index=1,
                        image_path="img.png",
                    ),
                ],
            ),
        ],
    )

    text_seg = {"segment_index": 0, "layout_block_indices": [0]}
    enrich_segment_font_fields(text_seg, layout_doc, text="Hello")
    assert text_seg["pdf_page_number"] == 1

    image_seg = {"segment_index": 1, "block_index": 1}
    enrich_segment_font_fields(image_seg, layout_doc)
    assert image_seg["pdf_page_number"] == 3
    assert "computed_font_size_pt" not in image_seg


def test_reconcile_overlay_preserves_user_font_size_pt():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        _reconcile_overlay_user_font_size_pt,
    )

    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=309.0,
                height=910.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(10.0, 20.0, 90.0, 28.0),
                        type="text",
                        index=4,
                        text="建筑师：",
                    ),
                ],
            ),
        ],
    )
    block = layout_doc.pages[0].blocks[0]
    segment = {
        "font_size_pt": 5.9,
        "font_size_source": "user",
        "target_text": "建筑师：",
    }
    _reconcile_overlay_user_font_size_pt(
        segment,
        block,
        "建筑师：",
        layout_doc,
        layout_doc.pages[0],
        (309, 910),
    )
    assert segment["font_size_pt"] == 5.9
    assert segment.get("computed_font_size_pt") is not None
    assert abs(segment["computed_font_size_pt"] - 5.9) < 0.2


def test_enrich_segment_image_block_with_overlay_text():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=200.0,
                height=300.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(10.0, 20.0, 90.0, 35.0),
                        type="image",
                        index=2,
                        image_path="chart.png",
                        text="Revenue",
                    ),
                ],
            ),
        ],
    )
    seg = {
        "segment_index": 0,
        "layout_block_indices": [2],
        "target_text": "收入",
    }
    enrich_segment_font_fields(seg, layout_doc, text="收入")
    computed = seg.get("computed_font_size_pt")
    assert computed is not None
    assert computed >= FONT_SIZE_PT_MIN
    # Effective overlay size is bbox-capped, not raw Typst estimate alone.
    _, y0, _, y1 = layout_doc.pages[0].blocks[0].bbox
    bbox_cap = (float(y1) - float(y0))
    assert computed <= bbox_cap + 0.05


def test_enrich_segment_font_fields_small_bbox_below_legacy_min():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage

    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=111.0,
                height=327.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(3.0, 61.0, 18.0, 64.0),
                        type="text",
                        index=4,
                        text="ARCHITECT :",
                    ),
                ],
            ),
        ],
    )
    seg = {"segment_index": 4, "layout_block_indices": [4]}
    enrich_segment_font_fields(seg, layout_doc, text="建筑师：")
    computed = seg.get("computed_font_size_pt")
    assert computed is not None
    assert computed < 6.0
    assert computed >= FONT_SIZE_PT_MIN


def test_font_size_constants():
    assert FONT_SIZE_PT_MIN == 0.5
    assert FONT_SIZE_PT_MAX == 72.0
    assert FONT_SIZE_PT_STEP == 0.1


def test_normalize_user_font_weight_and_style():
    assert normalize_user_font_weight("bold") == "bold"
    assert normalize_user_font_weight("regular") == "regular"
    assert normalize_user_font_weight("invalid") is None
    assert normalize_user_font_style("italic") == "italic"
    assert normalize_user_font_style(True) == "italic"
    assert normalize_user_font_style("normal") == "normal"


def test_build_block_font_weight_and_style_maps():
    segments = [
        {
            "segment_index": 0,
            "font_weight": "bold",
            "font_style": "italic",
            "layout_block_indices": [2],
        },
    ]
    assert build_block_font_weight_map_from_segments(segments) == {2: "bold"}
    assert build_block_font_style_map_from_segments(segments) == {2: "italic"}


def test_apply_user_typography_override():
    rb = RenderBlock(
        block_id="t",
        page_index=0,
        inner_bbox=(0.0, 0.0, 100.0, 20.0),
        plain_text="Sample text",
        markdown_text="Sample text",
    )
    styled = apply_user_typography_override(
        rb, font_weight="bold", font_style="italic", leading_em=1.25,
    )
    assert styled.font_weight == "bold"
    assert styled.font_style == "italic"
    assert styled.leading_em == 1.25
    assert styled.fit_min_leading_em == 1.25
    assert styled.leading_em_locked is True
    assert styled.fit_to_box is False


def test_apply_user_typography_override_leading_locks_leading_keeps_fit():
    rb = RenderBlock(
        block_id="t",
        page_index=0,
        inner_bbox=(0.0, 0.0, 100.0, 40.0),
        plain_text="Multi line sample text for leading lock",
        markdown_text="Multi line sample text for leading lock",
        fit_to_box=True,
        fit_single_line=True,
    )
    styled = apply_user_typography_override(rb, leading_em=1.05)
    assert styled.leading_em == 1.05
    assert styled.fit_min_leading_em == 1.05
    assert styled.leading_em_locked is True
    assert styled.fit_to_box is True
    assert styled.fit_single_line is True
    assert styled.fit_max_font_size_pt == rb.font_size_pt
    assert styled.fit_min_font_size_pt == rb.font_size_pt


def test_apply_user_typography_override_tightening_leading_locks_font_size():
    rb = RenderBlock(
        block_id="t",
        page_index=0,
        inner_bbox=(0.0, 0.0, 100.0, 40.0),
        plain_text="Multi line sample text for leading lock",
        markdown_text="Multi line sample text for leading lock",
        font_size_pt=10.0,
        leading_em=1.25,
        fit_to_box=True,
    )
    styled = apply_user_typography_override(rb, leading_em=0.9)
    assert styled.leading_em == 0.9
    assert styled.fit_max_font_size_pt == 10.0
    assert styled.fit_min_font_size_pt == 10.0


def test_apply_user_typography_override_loosening_leading_keeps_font_range():
    rb = RenderBlock(
        block_id="t",
        page_index=0,
        inner_bbox=(0.0, 0.0, 100.0, 40.0),
        plain_text="Multi line sample text for leading lock",
        markdown_text="Multi line sample text for leading lock",
        font_size_pt=10.0,
        leading_em=1.0,
        fit_min_font_size_pt=6.0,
        fit_to_box=True,
    )
    styled = apply_user_typography_override(rb, leading_em=1.2)
    assert styled.leading_em == 1.2
    assert styled.fit_max_font_size_pt == 10.0
    assert styled.fit_min_font_size_pt == 6.0


def test_normalize_user_leading_em():
    assert normalize_user_leading_em(None) is None
    assert normalize_user_leading_em(1.25) == 1.25
    assert normalize_user_leading_em(1.24) == 1.25
    assert normalize_user_leading_em(0.2) is None


def test_build_block_leading_map_from_segments():
    segments = [
        {
            "segment_index": 0,
            "leading_em": 1.5,
            "layout_block_indices": [4],
        },
    ]
    assert build_block_leading_map_from_segments(segments) == {4: 1.5}


def test_segment_leading_em_source():
    assert segment_leading_em_source({}) == "auto"
    assert segment_leading_em_source({"leading_em": 1.25}) == "user"


def test_segment_font_weight_and_style_source():
    assert segment_font_weight_source({}) == "auto"
    assert segment_font_weight_source({"font_weight": "bold"}) == "user"
    assert segment_font_style_source({"font_style": "italic"}) == "user"


def test_primary_layout_block_index_from_task_state_map():
    segment = {"segment_index": 2}
    task_state = {"layout_chunk_block_map": [[], [5], [10, 11]]}
    type_map = {10: "text", 11: "image"}
    assert primary_layout_block_index(segment, type_map, task_state) == 10


def test_build_layout_block_maps_and_batch_enrichment_share_maps():
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        build_layout_block_maps,
        enrich_segments_font_fields,
    )

    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(0.0, 0.0, 100.0, 20.0),
                        type="text",
                        index=0,
                        text="Hello",
                    ),
                ],
            ),
        ],
    )
    block_map, type_map = build_layout_block_maps(layout_doc)
    assert block_map[0].text == "Hello"
    assert type_map[0] == "text"

    segments = [
        {"segment_index": 0, "target_text": "Hello", "layout_block_indices": [0]},
    ]
    enrich_segments_font_fields(layout_doc, segments, text_field="target_text")
    assert segments[0].get("computed_font_size_pt") is not None
    assert segments[0].get("pdf_page_number") == 1
