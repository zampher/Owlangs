# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for Typst overlay PDF preview cache fingerprint."""

from layout.pdf_renderer.typst_overlay.pdf_preview_cache import (
    compute_typst_overlay_content_fingerprint,
    get_pdf_preview_cache,
    store_pdf_preview_cache,
)


def test_fingerprint_changes_when_segment_text_changes():
    segments = [{"segment_index": 0, "target_text": "A", "modified_text": "A"}]
    first = compute_typst_overlay_content_fingerprint(
        segments,
        equation_format="text",
        table_body_format="html",
        chart_body_format="image",
    )
    segments[0]["modified_text"] = "B"
    second = compute_typst_overlay_content_fingerprint(
        segments,
        equation_format="text",
        table_body_format="html",
        chart_body_format="image",
    )
    assert first != second


def test_fingerprint_stable_for_same_content():
    segments = [{"segment_index": 0, "target_text": "A", "font_size_pt": 10.0}]
    first = compute_typst_overlay_content_fingerprint(
        segments,
        equation_format="text",
        table_body_format="html",
        chart_body_format="image",
        font_size_by_block_index={1: 10.0},
    )
    second = compute_typst_overlay_content_fingerprint(
        segments,
        equation_format="text",
        table_body_format="html",
        chart_body_format="image",
        font_size_by_block_index={1: 10.0},
    )
    assert first == second


def test_store_pdf_preview_cache_tracks_full_render(tmp_path):
    task_state: dict = {}
    pdf_path = tmp_path / "preview.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    store_pdf_preview_cache(
        task_state,
        content_hash="abc",
        pdf_path=pdf_path,
        partial_render=True,
    )
    assert get_pdf_preview_cache(task_state).get("has_full_render") is False

    store_pdf_preview_cache(
        task_state,
        content_hash="def",
        pdf_path=pdf_path,
        partial_render=False,
    )
    assert get_pdf_preview_cache(task_state).get("has_full_render") is True

    store_pdf_preview_cache(
        task_state,
        content_hash="ghi",
        pdf_path=pdf_path,
        partial_render=True,
    )
    assert get_pdf_preview_cache(task_state).get("has_full_render") is True
