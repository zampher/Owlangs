# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.pdf_renderer.typst_overlay.font_fit import FontFitCalculator
from layout.pdf_renderer.typst_overlay.pdf_font_dry_run import dry_run_pdf_font_size_pt
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    compute_block_render_fit_metrics,
    enrich_segment_font_fields,
)


def test_pdf_dry_run_shrinks_long_translation_below_estimate():
    """Long CJK translation in a narrow bbox: render pt < Python estimate."""
    text = (
        "6. 制备 MPS-IV-009（聚苯甲酸乙烯酯 0.33 聚乙醛酸乙烯酯 0.66）"
    )
    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=400.0,
                height=800.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(96.0, 123.0, 275.0, 145.0),
                        type="text",
                        index=2,
                        text=text,
                    ),
                ],
            ),
        ],
    )
    block = layout_doc.pages[0].blocks[0]
    calc = FontFitCalculator()
    estimated = compute_block_render_fit_metrics(block, text, calculator=calc)
    assert estimated is not None
    estimate_pt = estimated[0]
    assert estimate_pt >= 8.0

    render_pt = dry_run_pdf_font_size_pt(block, text, calculator=calc)
    assert render_pt is not None
    assert render_pt <= estimate_pt
    assert render_pt >= 6.0


def test_enrich_pdf_segment_sets_overlay_render_font_size_pt():
    text = "胶状物（MPS-V-005）在与乙酸乙酯、二氯甲烷（DCM）、氯仿和甲醇等溶剂接触时发生溶胀。"
    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=400.0,
                height=800.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(75.0, 81.0, 295.0, 113.0),
                        type="text",
                        index=1,
                        text=text,
                    ),
                ],
            ),
        ],
    )
    segment = {
        "segment_index": 1,
        "target_text": text,
        "layout_block_indices": [1],
    }
    enrich_segment_font_fields(segment, layout_doc, text=text)
    render_pt = segment.get("overlay_render_font_size_pt")
    computed = segment.get("computed_font_size_pt")
    assert render_pt is not None
    assert computed == render_pt


def test_pdf_dry_run_user_override_returns_exact_pt():
    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=400.0,
                height=800.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(96.0, 123.0, 275.0, 145.0),
                        type="text",
                        index=2,
                        text="Sample",
                    ),
                ],
            ),
        ],
    )
    block = layout_doc.pages[0].blocks[0]
    render_pt = dry_run_pdf_font_size_pt(block, "Sample text", user_pt=11.3)
    assert render_pt == 11.3


def test_pdf_dry_run_short_plain_applies_width_scale_like_emitter():
    """Short plain auto label must reflect Typst scaled-font, not preferred pt."""
    text = "制备工艺概述"
    # Narrow bbox forces width shrink below preferred size.
    layout_doc = LayoutDocument(
        pages=[
            LayoutPage(
                page_index=0,
                width=400.0,
                height=800.0,
                blocks=[
                    LayoutBlock(
                        page_index=0,
                        bbox=(100.0, 100.0, 140.0, 118.0),
                        type="text",
                        index=3,
                        text=text,
                    ),
                ],
            ),
        ],
    )
    block = layout_doc.pages[0].blocks[0]
    calc = FontFitCalculator()
    preferred = compute_block_render_fit_metrics(block, text, calculator=calc)
    assert preferred is not None
    preferred_pt = preferred[0]
    assert preferred_pt >= 8.0

    render_pt = dry_run_pdf_font_size_pt(block, text, calculator=calc)
    assert render_pt is not None
    assert render_pt < preferred_pt

    # Locking the auto label must match dry-run (Preview-revision WYSIWYG).
    locked_pt = dry_run_pdf_font_size_pt(block, text, user_pt=render_pt, calculator=calc)
    assert locked_pt == render_pt
