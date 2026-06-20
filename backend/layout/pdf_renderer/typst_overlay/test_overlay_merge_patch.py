# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for partial PDF page patching."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import fitz
import pytest

from layout.pdf_renderer.typst_overlay.overlay_merge import (
    merge_overlay_pdf,
    patch_merged_pdf_pages,
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


def _overlay_text_pdf(text: str, width: float, height: float) -> bytes:
    """Create a single-page overlay PDF with text at a known position."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=width, height=height)
        page.insert_text((36, 72), text, fontsize=14)
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
    finally:
        doc.close()


@pytest.mark.skipif(
    not hasattr(fitz, "open"),
    reason="PyMuPDF is required",
)
@pytest.mark.parametrize("width,height", [
    (300, 400),
    (612, 792),   # letter
    (595, 842),   # A4
])
def test_merge_overlay_pdf_preserves_page_dimensions(width, height):
    """Merged PDF pages must have the same dimensions as the source."""
    src_doc = fitz.open()
    try:
        for i in range(3):
            page = src_doc.new_page(width=width, height=height)
            page.insert_text((36, 72), f"SOURCE-{i}", fontsize=14)
        buffer = io.BytesIO()
        src_doc.save(buffer)
        source_bytes = buffer.getvalue()
    finally:
        src_doc.close()

    ovl_doc = fitz.open()
    try:
        for i in range(3):
            page = ovl_doc.new_page(width=width, height=height)
            page.insert_text((36, 72), f"OVERLAY-{i}", fontsize=14)
        ovl_buffer = io.BytesIO()
        ovl_doc.save(ovl_buffer)
        overlay_bytes = ovl_buffer.getvalue()
    finally:
        ovl_doc.close()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(overlay_bytes)
        overlay_path = f.name

    try:
        merged_bytes = merge_overlay_pdf(
            source_bytes,
            Path(overlay_path),
            check_page_count=True,
            compress=True,
        )
    finally:
        Path(overlay_path).unlink(missing_ok=True)

    merged = fitz.open(stream=merged_bytes, filetype="pdf")
    try:
        assert len(merged) == 3, f"Expected 3 pages, got {len(merged)}"
        for page_idx in range(3):
            page = merged[page_idx]
            page_w = float(page.rect.width)
            page_h = float(page.rect.height)
            assert abs(page_w - width) < 0.1, (
                f"Page {page_idx}: width mismatch expected={width} got={page_w}"
            )
            assert abs(page_h - height) < 0.1, (
                f"Page {page_idx}: height mismatch expected={height} got={page_h}"
            )
    finally:
        merged.close()


@pytest.mark.skipif(
    not hasattr(fitz, "open"),
    reason="PyMuPDF is required",
)
def test_merge_overlay_pdf_mixed_page_sizes():
    """Merging with mixed page sizes should preserve each page's dimensions."""
    widths = [300, 400, 500]
    heights = [400, 500, 600]

    src_doc = fitz.open()
    try:
        for i in range(3):
            page = src_doc.new_page(width=widths[i], height=heights[i])
            page.insert_text((36, 72), f"SRC-{i}", fontsize=14)
        buffer = io.BytesIO()
        src_doc.save(buffer)
        source_bytes = buffer.getvalue()
    finally:
        src_doc.close()

    ovl_doc = fitz.open()
    try:
        for i in range(3):
            page = ovl_doc.new_page(width=widths[i], height=heights[i])
            page.insert_text((36, 72), f"OVL-{i}", fontsize=14)
        ovl_buffer = io.BytesIO()
        ovl_doc.save(ovl_buffer)
        overlay_bytes = ovl_buffer.getvalue()
    finally:
        ovl_doc.close()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(overlay_bytes)
        overlay_path = f.name

    try:
        merged_bytes = merge_overlay_pdf(
            source_bytes,
            Path(overlay_path),
            check_page_count=False,
            compress=True,
        )
    finally:
        Path(overlay_path).unlink(missing_ok=True)

    merged = fitz.open(stream=merged_bytes, filetype="pdf")
    try:
        assert len(merged) == 3
        for page_idx, (expected_w, expected_h) in enumerate(zip(widths, heights)):
            page = merged[page_idx]
            page_w = float(page.rect.width)
            page_h = float(page.rect.height)
            assert abs(page_w - expected_w) < 0.1, (
                f"Page {page_idx}: width expected={expected_w} got={page_w}"
            )
            assert abs(page_h - expected_h) < 0.1, (
                f"Page {page_idx}: height expected={expected_h} got={page_h}"
            )
    finally:
        merged.close()
