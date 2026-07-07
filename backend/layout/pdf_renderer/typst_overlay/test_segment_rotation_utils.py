# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for bbox-based sideways text rotation inference."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.pdf_renderer.typst_overlay.segment_rotation_utils import (
    DEFAULT_AUTO_ROTATION_ASPECT_RATIO,
    build_rotation_by_block_index,
    infer_sideways_rotation_from_bbox,
)


def test_infer_rotation_requires_high_aspect_ratio():
    # Segment 29-like margin strip: w=13, h=763
    bbox = (573.0, 9.0, 586.0, 772.0)
    assert infer_sideways_rotation_from_bbox(
        bbox,
        aspect_ratio_threshold=20.0,
        page_width_pt=596.0,
    ) == 270
    assert infer_sideways_rotation_from_bbox(
        bbox,
        aspect_ratio_threshold=100.0,
        page_width_pt=596.0,
    ) == 0


def test_infer_rotation_left_margin_uses_270():
    bbox = (10.0, 20.0, 23.0, 400.0)
    assert infer_sideways_rotation_from_bbox(
        bbox,
        aspect_ratio_threshold=20.0,
        page_width_pt=600.0,
    ) == 270


def test_manual_rotation_wins_over_auto():
    segments = [
        {
            "segment_index": 29,
            "rotation": 180,
            "layout_block_indices": [29],
            "layout_block_bbox": [[573.0, 9.0, 586.0, 772.0]],
        },
    ]
    rotation_map = build_rotation_by_block_index(
        segments,
        {},
        auto_rotation_enabled=True,
        auto_rotation_aspect_ratio=DEFAULT_AUTO_ROTATION_ASPECT_RATIO,
    )
    assert rotation_map[29] == 180


def test_auto_rotation_applies_when_enabled():
    segments = [
        {
            "segment_index": 29,
            "layout_block_indices": [29],
            "layout_block_bbox": [[573.0, 9.0, 586.0, 772.0]],
        },
    ]
    disabled = build_rotation_by_block_index(
        segments,
        {},
        auto_rotation_enabled=False,
    )
    assert disabled == {}

    enabled = build_rotation_by_block_index(
        segments,
        {},
        auto_rotation_enabled=True,
        auto_rotation_aspect_ratio=20.0,
    )
    assert enabled[29] == 270


def test_auto_rotation_uses_configured_degrees():
    segments = [
        {
            "segment_index": 29,
            "layout_block_indices": [29],
            "layout_block_bbox": [[573.0, 9.0, 586.0, 772.0]],
        },
    ]
    enabled = build_rotation_by_block_index(
        segments,
        {},
        auto_rotation_enabled=True,
        auto_rotation_aspect_ratio=20.0,
        auto_rotation_degrees=90,
    )
    assert enabled[29] == 90
