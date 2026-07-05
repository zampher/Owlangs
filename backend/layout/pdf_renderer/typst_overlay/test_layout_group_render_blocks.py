# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Integration test: layout group companion RenderBlocks reach page specs."""

import json
import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.ocr_provider.paddle.zip_loader import _enrich_layout_group_pairs_on_document
from layout.pdf_renderer.typst_overlay.emitter import render_block_to_typst
from layout.pdf_renderer.typst_overlay.models import layout_block_to_render_block
from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer
from layout.pdf_renderer.config import PDFRendererConfig


def _load_fixture_block(block_index: int) -> LayoutBlock:
    layout_path = _OWLANGS.parent / "test" / "paddle_layout" / "layout.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    for page_data in data.get("pages") or []:
        for block_data in page_data.get("blocks") or []:
            if block_data.get("block_index") != block_index:
                continue
            return LayoutBlock(
                page_index=int(page_data.get("page_index") or 0),
                bbox=tuple(block_data.get("bbox")),
                type=str(block_data.get("type") or "text"),
                sub_type=str(block_data.get("sub_type") or ""),
                index=block_index,
                text=str(block_data.get("text") or "") or None,
                tags=list(block_data.get("tags") or []),
                raw=dict(block_data),
            )
    raise KeyError(block_index)


def test_build_layout_group_companion_render_blocks_emits_typst():
    doc_pages = []
    layout_path = _OWLANGS.parent / "test" / "paddle_layout" / "layout.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    for page_data in data.get("pages") or []:
        blocks = []
        for block_data in page_data.get("blocks") or []:
            bbox = block_data.get("bbox")
            if not bbox:
                continue
            blocks.append(
                LayoutBlock(
                    page_index=int(page_data.get("page_index") or 0),
                    bbox=tuple(bbox),
                    type=str(block_data.get("type") or "text"),
                    sub_type=str(block_data.get("sub_type") or ""),
                    index=block_data.get("block_index"),
                    text=str(block_data.get("text") or "") or None,
                    tags=list(block_data.get("tags") or []),
                    raw=dict(block_data),
                )
            )
        doc_pages.append(
            LayoutPage(
                page_index=int(page_data.get("page_index") or 0),
                blocks=blocks,
                width=page_data.get("page_width"),
                height=page_data.get("page_height"),
            )
        )
    layout_doc = LayoutDocument(pages=doc_pages, engine="paddle")
    _enrich_layout_group_pairs_on_document(layout_doc, None)

    primary = _load_fixture_block(13)
    translated = "W" * 406
    group_info = TypstOverlayRenderer._split_layout_group_text(
        primary,
        translated,
        layout_doc,
    )
    assert group_info["group_parts"], "expected companion parts for block 13"

    ref_rb = layout_block_to_render_block(
        primary,
        page_index=0,
        translated_text=group_info["main_text"],
        block_id="block-13",
    )
    config = PDFRendererConfig()
    renderer = TypstOverlayRenderer(config)
    companions = renderer._build_layout_group_companion_render_blocks(
        group_info["group_parts"],
        block_key=13,
        page_index=0,
        page_width_pt=595.0,
        ref_rb=ref_rb,
        ref_unified=None,
        unified_ref_leading_em=None,
    )
    assert companions, "expected companion render blocks"
    _, companion_rb = companions[0]
    typst_src = render_block_to_typst("block-13-group-14", companion_rb)
    assert typst_src.strip(), "companion typst source must not be empty"
    assert companion_rb.plain_text, "companion must retain text"
    assert companion_rb.inner_bbox != ref_rb.inner_bbox
    assert companion_rb.inner_bbox == (301.387, 522.908, 552.792, 662.383)


def test_build_layout_group_companion_render_blocks_corrects_stale_pair_bbox():
    layout_path = _OWLANGS.parent / "test" / "paddle_layout" / "layout.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    doc_pages = []
    for page_data in data.get("pages") or []:
        blocks = []
        for block_data in page_data.get("blocks") or []:
            bbox = block_data.get("bbox")
            if not bbox:
                continue
            raw = dict(block_data)
            if block_data.get("block_index") == 13 and raw.get("_layout_group_pairs"):
                raw["_layout_group_pairs"] = [
                    {
                        "index": 14,
                        "bbox": list(bbox),
                        "page_index": 0,
                    }
                ]
            blocks.append(
                LayoutBlock(
                    page_index=int(page_data.get("page_index") or 0),
                    bbox=tuple(bbox),
                    type=str(block_data.get("type") or "text"),
                    sub_type=str(block_data.get("sub_type") or ""),
                    index=block_data.get("block_index"),
                    text=str(block_data.get("text") or "") or None,
                    tags=list(block_data.get("tags") or []),
                    raw=raw,
                )
            )
        doc_pages.append(
            LayoutPage(
                page_index=int(page_data.get("page_index") or 0),
                blocks=blocks,
                width=page_data.get("page_width"),
                height=page_data.get("page_height"),
            )
        )
    layout_doc = LayoutDocument(pages=doc_pages, engine="paddle")
    primary = next(b for b in layout_doc.iter_blocks() if b.index == 13)
    translated = "W" * 406
    group_info = TypstOverlayRenderer._split_layout_group_text(
        primary,
        translated,
        layout_doc,
    )
    assert group_info["group_parts"]
    ref_rb = layout_block_to_render_block(
        primary,
        page_index=0,
        translated_text=group_info["main_text"],
        block_id="block-13",
    )
    renderer = TypstOverlayRenderer(PDFRendererConfig())
    renderer._current_layout_doc = layout_doc
    companions = renderer._build_layout_group_companion_render_blocks(
        group_info["group_parts"],
        block_key=13,
        page_index=0,
        page_width_pt=595.0,
        ref_rb=ref_rb,
        ref_unified=None,
        unified_ref_leading_em=None,
    )
    _, companion_rb = companions[0]
    assert companion_rb.inner_bbox == (301.387, 522.908, 552.792, 662.383)
    assert companion_rb.inner_bbox != ref_rb.inner_bbox


def test_build_block_bbox_override_map_assigns_per_block_bboxes():
    from layout.layout_group_pair_utils import bboxes_nearly_equal
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        build_block_bbox_override_map_from_segments,
    )

    layout_path = _OWLANGS.parent / "test" / "paddle_layout" / "layout.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    doc_pages = []
    for page_data in data.get("pages") or []:
        blocks = []
        for block_data in page_data.get("blocks") or []:
            bbox = block_data.get("bbox")
            if not bbox:
                continue
            blocks.append(
                LayoutBlock(
                    page_index=int(page_data.get("page_index") or 0),
                    bbox=tuple(bbox),
                    type=str(block_data.get("type") or "text"),
                    sub_type=str(block_data.get("sub_type") or ""),
                    index=block_data.get("block_index"),
                    text=str(block_data.get("text") or "") or None,
                    tags=list(block_data.get("tags") or []),
                    raw=dict(block_data),
                )
            )
        doc_pages.append(
            LayoutPage(
                page_index=int(page_data.get("page_index") or 0),
                blocks=blocks,
                width=page_data.get("page_width"),
                height=page_data.get("page_height"),
            )
        )
    layout_doc = LayoutDocument(pages=doc_pages, engine="paddle")
    segment = {
        "segment_index": 12,
        "layout_block_indices": [13, 14],
        "layout_block_bbox": [
            [42.0, 569.4, 291.9, 661.9],
            [301.4, 522.9, 552.8, 662.4],
        ],
        "target_text": "左栏译文。右栏续文。",
        "source_text": "Left column text. Right column continuation.",
    }
    block_map = build_block_bbox_override_map_from_segments(
        [segment],
        None,
        layout_doc,
    )
    assert 13 in block_map and 14 in block_map
    assert not bboxes_nearly_equal(block_map[13], block_map[14])
    assert block_map[14][0] > 300.0


def test_companion_render_ignores_duplicate_primary_bbox_override():
    primary = _load_fixture_block(13)
    layout_path = _OWLANGS.parent / "test" / "paddle_layout" / "layout.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    doc_pages = []
    for page_data in data.get("pages") or []:
        blocks = []
        for block_data in page_data.get("blocks") or []:
            bbox = block_data.get("bbox")
            if not bbox:
                continue
            blocks.append(
                LayoutBlock(
                    page_index=int(page_data.get("page_index") or 0),
                    bbox=tuple(bbox),
                    type=str(block_data.get("type") or "text"),
                    sub_type=str(block_data.get("sub_type") or ""),
                    index=block_data.get("block_index"),
                    text=str(block_data.get("text") or "") or None,
                    tags=list(block_data.get("tags") or []),
                    raw=dict(block_data),
                )
            )
        doc_pages.append(
            LayoutPage(
                page_index=int(page_data.get("page_index") or 0),
                blocks=blocks,
                width=page_data.get("page_width"),
                height=page_data.get("page_height"),
            )
        )
    layout_doc = LayoutDocument(pages=doc_pages, engine="paddle")
    _enrich_layout_group_pairs_on_document(layout_doc, None)

    translated = "W" * 406
    group_info = TypstOverlayRenderer._split_layout_group_text(
        primary,
        translated,
        layout_doc,
    )
    ref_rb = layout_block_to_render_block(
        primary,
        page_index=0,
        translated_text=group_info["main_text"],
        block_id="block-13",
    )
    primary_bbox = tuple(float(v) for v in primary.bbox)
    renderer = TypstOverlayRenderer(
        PDFRendererConfig(
            bbox_override_by_block_index={
                13: primary_bbox,
                14: primary_bbox,
            },
        ),
    )
    renderer._current_layout_doc = layout_doc
    companions = renderer._build_layout_group_companion_render_blocks(
        group_info["group_parts"],
        block_key=13,
        page_index=0,
        page_width_pt=595.0,
        ref_rb=ref_rb,
        ref_unified=None,
        unified_ref_leading_em=None,
    )
    _, companion_rb = companions[0]
    assert companion_rb.inner_bbox == (301.387, 522.908, 552.792, 662.383)
    assert companion_rb.inner_bbox != primary_bbox
