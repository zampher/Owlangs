# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for partial PDF page patching."""

from __future__ import annotations

import io

import fitz
import pytest

from layout.pdf_renderer.typst_overlay.overlay_merge import (
    patch_merged_pdf_pages_from_rendered,
)


def _page_text(doc: fitz.Document, page_index: int) -> str:
    return doc[page_index].get_text("text").strip()


def _make_labeled_pdf(labels: list[str]) -> bytes:
    doc = fitz.open()
    try:
        for label in labels:
            page = doc.new_page(width=200, height=200)
            page.insert_text((36, 72), label, fontsize=14)
            shape = page.new_shape()
            shape.draw_rect(fitz.Rect(20, 20, 180, 180))
            shape.finish(color=(0, 0, 0), width=1)
            shape.commit()
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
    finally:
        doc.close()


@pytest.mark.skipif(
    not hasattr(fitz, "open"),
    reason="PyMuPDF is required for overlay merge patch tests",
)
def test_patch_merged_pdf_pages_from_rendered_preserves_untouched_pages():
    base_bytes = _make_labeled_pdf(
        ["BASE-PAGE-0", "BASE-PAGE-1", "BASE-PAGE-2", "BASE-PAGE-3"],
    )
    rendered_bytes = _make_labeled_pdf(["REPLACED-PAGE-3"])

    patched_bytes = patch_merged_pdf_pages_from_rendered(
        base_bytes,
        rendered_bytes,
        [3],
    )

    patched = fitz.open(stream=patched_bytes, filetype="pdf")
    try:
        assert len(patched) == 4
        assert _page_text(patched, 0) == "BASE-PAGE-0"
        assert _page_text(patched, 1) == "BASE-PAGE-1"
        assert _page_text(patched, 2) == "BASE-PAGE-2"
        assert _page_text(patched, 3) == "REPLACED-PAGE-3"
    finally:
        patched.close()


@pytest.mark.skipif(
    not hasattr(fitz, "open"),
    reason="PyMuPDF is required for overlay merge patch tests",
)
def test_patch_merged_pdf_pages_from_rendered_keeps_untouched_page_bytes_stable():
    base_bytes = _make_labeled_pdf(
        ["BASE-PAGE-0", "BASE-PAGE-1", "BASE-PAGE-2", "BASE-PAGE-3"],
    )
    rendered_bytes = _make_labeled_pdf(["REPLACED-PAGE-3"])

    base_doc = fitz.open(stream=base_bytes, filetype="pdf")
    try:
        untouched_pixmaps = [
            base_doc[page_index].get_pixmap(dpi=72)
            for page_index in range(3)
        ]
    finally:
        base_doc.close()

    patched_bytes = patch_merged_pdf_pages_from_rendered(
        base_bytes,
        rendered_bytes,
        [3],
    )

    patched = fitz.open(stream=patched_bytes, filetype="pdf")
    try:
        for page_index, expected_pix in enumerate(untouched_pixmaps):
            actual_pix = patched[page_index].get_pixmap(dpi=72)
            assert actual_pix.samples == expected_pix.samples
    finally:
        patched.close()
