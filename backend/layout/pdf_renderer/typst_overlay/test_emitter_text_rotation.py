# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for rotated flow-text rendering in Typst emitter."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.emitter import (
    _render_markdown_block,
    _render_plain_block,
    _rotated_reading_dimensions,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def _sample_text_block(**overrides) -> RenderBlock:
    base = dict(
        block_id="txt-1",
        page_index=0,
        inner_bbox=(10.0, 20.0, 60.0, 220.0),
        markdown_text="Sample translated paragraph for rotation testing.",
        font_size_pt=10.0,
        render_kind="markdown",
        fit_to_box=True,
    )
    base.update(overrides)
    return RenderBlock(**base)


def test_reading_dimensions_swap_for_sideways_text():
    assert _rotated_reading_dimensions(50.0, 200.0, 90) == (200.0, 50.0)
    assert _rotated_reading_dimensions(50.0, 200.0, 270) == (200.0, 50.0)
    assert _rotated_reading_dimensions(50.0, 200.0, 180) == (50.0, 200.0)


def test_markdown_rotation_90_uses_clipped_bbox_and_swapped_inner():
    src = _render_markdown_block(
        "block-md",
        _sample_text_block(rotation=90),
    )

    assert "block(width: 200.0pt, height: 50.0pt" in src
    assert "block(width: 50.0pt, height: 200.0pt, clip: true" in src
    assert "#rotate(-90deg, origin: center" in src
    assert "align(center + horizon)" in src


def test_markdown_rotation_0_has_no_clip_or_rotate():
    src = _render_markdown_block(
        "block-md",
        _sample_text_block(rotation=0),
    )

    assert "clip: true" not in src
    assert "#rotate(" not in src
    assert "block(width: 50.0pt, height: 200.0pt" in src


def test_plain_short_text_rotation_180_clips_to_bbox():
    src = _render_plain_block(
        "block-plain",
        _sample_text_block(
            plain_text="Short",
            markdown_text="",
            render_kind="plain",
            fit_to_box=False,
            rotation=180,
        ),
    )

    assert "block(width: 50.0pt, height: 200.0pt, clip: true" in src
    assert "#rotate(-180deg, origin: center" in src
    assert "block_plain_inner" in src
    # inner is bound inside the same #context as measure/place
    assert src.index("#context {") < src.index("let block_plain_inner")
    assert src.index("let block_plain_inner") < src.rindex("}")


def test_plain_short_text_rotation_0_places_inner_inside_context():
    src = _render_plain_block(
        "block-plain",
        _sample_text_block(
            plain_text="Hi",
            markdown_text="",
            render_kind="plain",
            fit_to_box=False,
            rotation=0,
        ),
    )

    assert "place(top + left" in src
    assert "block_plain_inner" in src
    assert src.index("let block_plain_inner") < src.index("place(top + left")
    # No orphan placement outside the measure context
    assert src.rstrip().endswith("}")
