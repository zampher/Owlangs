# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for source cleanup rect compaction after clipping."""

from layout.pdf_renderer.typst_overlay.source_cleanup import (
    _clip_rects_against_protected_rects,
    _compact_page_redaction_rects,
    _compact_page_redaction_rects_preserving,
    _dedupe_rects_not_covered,
    _merge_overlapping_rects_until_stable,
)


def test_compact_page_redaction_rects_merges_clip_fragments():
    protected = [(50.0, 50.0, 60.0, 200.0)]
    raw = [(40.0, 40.0, 100.0, 220.0)]
    clipped = _clip_rects_against_protected_rects(raw, protected)
    assert len(clipped) > 1

    compact = _compact_page_redaction_rects(clipped, merge=True)
    assert len(compact) < len(clipped)
    assert len(compact) >= 1


def test_compact_preserving_does_not_refill_protected_hole():
    """AABB merge of left/right fragments must not cover a protected chart gap."""
    protected = [(50.0, 40.0, 70.0, 100.0)]
    # Fragments left and right of the protected chart hole.
    fragments = [
        (10.0, 40.0, 50.0, 100.0),
        (70.0, 40.0, 110.0, 100.0),
        (10.0, 40.0, 110.0, 50.0),
        (10.0, 90.0, 110.0, 100.0),
    ]
    naive = _compact_page_redaction_rects(fragments, merge=True)
    # Naive merge may produce a single rect covering the protected hole.
    covering = any(
        x0 <= 50.0 and y0 <= 40.0 and x1 >= 70.0 and y1 >= 100.0
        for x0, y0, x1, y1 in naive
    )
    preserved = _compact_page_redaction_rects_preserving(
        fragments, protected, merge=True,
    )
    for x0, y0, x1, y1 in preserved:
        # No preserved redaction rect may fully cover the protected bbox.
        assert not (x0 <= 50.0 and y0 <= 40.0 and x1 >= 70.0 and y1 >= 100.0)
    # And no preserved rect may intersect the protected interior.
    for x0, y0, x1, y1 in preserved:
        assert x1 <= 50.0 or x0 >= 70.0 or y1 <= 40.0 or y0 >= 100.0
    assert covering or len(preserved) >= 1  # document why preserving matters


def test_merge_overlapping_rects_until_stable_reduces_count():
    rects = [
        (0.0, 0.0, 10.0, 10.0),
        (9.0, 0.0, 20.0, 10.0),
        (19.0, 0.0, 30.0, 10.0),
        (29.0, 0.0, 40.0, 10.0),
    ]
    merged = _merge_overlapping_rects_until_stable(rects)
    assert len(merged) == 1
    assert merged[0] == (0.0, 0.0, 40.0, 10.0)


def test_dedupe_rects_not_covered_skips_subsumed_override_originals():
    existing = [(40.0, 53.5, 293.4, 194.5), (301.4, 46.0, 552.8, 88.5)]
    override = [
        (40.0, 53.5, 293.4, 194.5),
        (999.0, 999.0, 1000.0, 1000.0),
    ]
    kept = _dedupe_rects_not_covered(override, existing)
    assert kept == [(999.0, 999.0, 1000.0, 1000.0)]
