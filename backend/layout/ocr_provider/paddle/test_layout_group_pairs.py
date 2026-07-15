# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for Paddle layout group companion pairing."""

import json
import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.base import LayoutBlock
from layout.ocr_provider.paddle.layout_group_pairs import apply_paddle_layout_group_pairs
from layout.ocr_provider.paddle.layout_parser import parse_paddle_layout

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "test" / "paddle_layout"


def _block_by_index(blocks, index: int) -> LayoutBlock:
    for block in blocks:
        if block.index == index:
            return block
    raise KeyError(index)


def test_apply_figure_wrap_pairs_abstract_continuation_with_inset_image():
    from layout.ocr_provider.paddle.layout_group_pairs import (
        apply_figure_wrap_layout_group_pairs,
    )
    from layout.layout_group_pair_utils import LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP

    blocks = [
        LayoutBlock(
            page_index=0,
            bbox=(48.493, 316.461, 310.453, 448.445),
            type="text",
            index=9,
            text="ABSTRACT: Left column wraps beside the TOC graphic and continues",
            raw={"group_id": 14, "block_order": 9},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(48.993, 448.445, 557.416, 537.434),
            type="text",
            index=10,
            text="below the figure as a full-width continuation sentence.",
            raw={"group_id": 16, "block_order": 10},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(316.452, 318.461, 553.416, 437.946),
            type="image",
            index=22,
            text="",
            raw={"group_id": 15, "block_order": 22},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(48.993, 539.433, 522.421, 562.43),
            type="text",
            index=11,
            text="KEYWORDS: piezoelectric nanotransducer",
            raw={"group_id": 17, "block_order": 11},
        ),
    ]

    paired = apply_figure_wrap_layout_group_pairs(blocks, page_width=595.0)
    assert paired == 1
    primary = _block_by_index(blocks, 9)
    companion = _block_by_index(blocks, 10)
    keywords = _block_by_index(blocks, 11)

    assert companion.raw.get("_layout_group_pair_of") == 9
    assert companion.raw.get("_layout_group_pair_kind") == LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP
    assert not (companion.text or "").strip()
    assert "continues" in (primary.text or "")
    assert "full-width continuation" in (primary.text or "")
    assert any(p.get("index") == 10 for p in (primary.raw.get("_layout_group_pairs") or []))
    assert keywords.raw.get("_layout_group_pair_of") is None
    assert (keywords.text or "").startswith("KEYWORDS")


def test_apply_figure_wrap_pairs_requires_inset_image():
    from layout.ocr_provider.paddle.layout_group_pairs import (
        apply_figure_wrap_layout_group_pairs,
    )

    blocks = [
        LayoutBlock(
            page_index=0,
            bbox=(48.0, 300.0, 300.0, 420.0),
            type="text",
            index=1,
            text="Narrow paragraph without an inset image.",
            raw={"group_id": 1, "block_order": 1},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(48.0, 420.0, 540.0, 500.0),
            type="text",
            index=2,
            text="Wider continuation that must not pair without a figure notch.",
            raw={"group_id": 2, "block_order": 2},
        ),
    ]
    assert apply_figure_wrap_layout_group_pairs(blocks, page_width=595.0) == 0
    assert _block_by_index(blocks, 2).raw.get("_layout_group_pair_of") is None


def test_apply_figure_wrap_pairs_inset_left_strip_empty_companion():
    """Wide text above + empty left strip beside inset figure (Causality PDF page 0)."""
    from layout.ocr_provider.paddle.layout_group_pairs import (
        apply_figure_wrap_layout_group_pairs,
    )
    from layout.layout_group_pair_utils import LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP

    primary_text = (
        "This paragraph runs full column width above the figure and should "
        "continue in the narrow strip to the left of Figure 1."
    )
    blocks = [
        LayoutBlock(
            page_index=0,
            bbox=(305.0, 350.5, 548.5, 579.0),
            type="text",
            index=9,
            text=primary_text,
            raw={"group_id": 10, "block_order": 9},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(305.5, 583.0, 412.5, 715.0),
            type="text",
            index=10,
            text="",
            raw={"group_id": 10, "block_order": 10},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(430.0, 590.0, 544.5, 657.0),
            type="image",
            index=12,
            text="",
            raw={"group_id": 12, "block_order": 12},
        ),
    ]

    paired = apply_figure_wrap_layout_group_pairs(blocks, page_width=612.0)
    assert paired == 1
    primary = _block_by_index(blocks, 9)
    companion = _block_by_index(blocks, 10)

    assert companion.raw.get("_layout_group_pair_of") == 9
    assert companion.raw.get("_layout_group_pair_kind") == LAYOUT_GROUP_PAIR_KIND_FIGURE_WRAP
    # Empty companion: do not merge OCR; keep text on primary for area-based split later.
    assert (primary.text or "") == primary_text
    assert not (companion.text or "").strip()
    assert any(p.get("index") == 10 for p in (primary.raw.get("_layout_group_pairs") or []))


def test_apply_figure_wrap_pairs_inset_left_strip_requires_image():
    from layout.ocr_provider.paddle.layout_group_pairs import (
        apply_figure_wrap_layout_group_pairs,
    )

    blocks = [
        LayoutBlock(
            page_index=0,
            bbox=(305.0, 350.5, 548.5, 579.0),
            type="text",
            index=9,
            text="Wide primary above an empty left strip without a figure.",
            raw={"group_id": 10, "block_order": 9},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(305.5, 583.0, 412.5, 715.0),
            type="text",
            index=10,
            text="",
            raw={"group_id": 10, "block_order": 10},
        ),
    ]
    assert apply_figure_wrap_layout_group_pairs(blocks, page_width=612.0) == 0
    assert _block_by_index(blocks, 10).raw.get("_layout_group_pair_of") is None


def test_apply_group_pairs_one_primary_two_empty_companions():
    blocks = [
        LayoutBlock(
            page_index=0,
            bbox=(0.0, 0.0, 100.0, 200.0),
            type="text",
            index=0,
            text="Merged paragraph text for three columns.",
            raw={"group_id": 1, "block_order": 1},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(110.0, 0.0, 210.0, 200.0),
            type="text",
            index=1,
            text="",
            raw={"group_id": 1, "block_order": 2},
        ),
        LayoutBlock(
            page_index=0,
            bbox=(220.0, 0.0, 320.0, 200.0),
            type="text",
            index=2,
            text="",
            raw={"group_id": 1, "block_order": 3},
        ),
    ]
    apply_paddle_layout_group_pairs(blocks)

    primary = _block_by_index(blocks, 0)
    companion_a = _block_by_index(blocks, 1)
    companion_b = _block_by_index(blocks, 2)

    assert primary.raw.get("_layout_group_pairs")
    assert len(primary.raw["_layout_group_pairs"]) == 2
    assert companion_a.raw.get("_layout_group_pair_of") == 0
    assert companion_b.raw.get("_layout_group_pair_of") == 0


def test_parse_paddle_layout_pairs_column_split_from_fixture():
    raw_path = _FIXTURE_DIR / "paddle_raw.json"
    if not raw_path.is_file():
        return

    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    doc = parse_paddle_layout(payload, pdf_page_dims=[(595.0, 842.0)])
    assert doc is not None

    paired_primary = None
    paired_companion = None
    for block in doc.iter_blocks():
        pairs = (block.raw or {}).get("_layout_group_pairs") or []
        if pairs:
            paired_primary = block
        if (block.raw or {}).get("_layout_group_pair_of") is not None and not (block.text or "").strip():
            paired_companion = block

    assert paired_primary is not None, "expected at least one primary with layout group pairs"
    assert paired_companion is not None, "expected at least one empty companion block"
def test_apply_spatial_layout_group_pairs_column_wrap_fixture():
    import json
    from layout.base import LayoutBlock, LayoutDocument, LayoutPage
    from layout.ocr_provider.paddle.layout_group_pairs import apply_spatial_layout_group_pairs

    layout_path = _FIXTURE_DIR / "layout.json"
    if not layout_path.is_file():
        return

    data = json.loads(layout_path.read_text(encoding="utf-8"))
    page_data = next(p for p in data["pages"] if p.get("page_index") == 3)
    blocks = []
    for block_data in page_data.get("blocks") or []:
        bbox = block_data.get("bbox")
        if not bbox:
            continue
        blocks.append(
            LayoutBlock(
                page_index=3,
                bbox=tuple(bbox),
                type=str(block_data.get("type") or "text"),
                index=block_data.get("block_index"),
                text=str(block_data.get("text") or "") or None,
                raw=dict(block_data),
            )
        )
    apply_spatial_layout_group_pairs(blocks, page_height=float(page_data.get("page_height") or 842.0))
    primary_125 = _block_by_index(blocks, 125)
    companion_126 = _block_by_index(blocks, 126)
    assert companion_126.raw.get("_layout_group_pair_of") == 125
    assert any(
        p.get("index") == 126
        for p in (primary_125.raw.get("_layout_group_pairs") or [])
    )


def test_apply_spatial_layout_group_pairs_page1_fixture():
    import json
    from layout.ocr_provider.paddle.layout_parser import parse_paddle_layout

    raw_path = _FIXTURE_DIR / "paddle_raw.json"
    if not raw_path.is_file():
        return

    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    doc = parse_paddle_layout(payload, pdf_page_dims=[(595.0, 842.0)])
    assert doc is not None

    primary_50 = _block_by_index(doc.pages[1].blocks, 50)
    companion_54 = _block_by_index(doc.pages[1].blocks, 54)
    # Block 50 is a cross-page continuation with its own OCR text (group_id=0).
    # Block 54 is an empty duplicate zone with a different group_id (3) and must
    # not steal segment 26 text via spatial column pairing.
    assert companion_54.raw.get("_layout_group_pair_of") is None or (
        companion_54.raw.get("_layout_group_pair_of") != 50
    )
    assert not any(
        p.get("index") == 54
        for p in (primary_50.raw.get("_layout_group_pairs") or [])
    )

    primary_53 = _block_by_index(doc.pages[1].blocks, 53)
    assert companion_54.raw.get("_layout_group_pair_of") == 53
    assert any(
        p.get("index") == 54
        for p in (primary_53.raw.get("_layout_group_pairs") or [])
    )

    primary_13 = _block_by_index(doc.pages[0].blocks, 13)
    companion_14 = _block_by_index(doc.pages[0].blocks, 14)
    assert companion_14.raw.get("_layout_group_pair_of") == 13
