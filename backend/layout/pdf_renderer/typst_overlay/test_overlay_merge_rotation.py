# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for overlay merge on rotated source PDF pages."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import fitz
import pytest

from layout.pdf_renderer.typst_overlay.overlay_merge import merge_overlay_pdf


def _avg_channel(page: fitz.Page, rect: fitz.Rect) -> float:
    pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(0.02, 0.02))
    samples = pix.samples
    step = pix.n
    n = len(samples) // step
    if n == 0:
        return 0.0
    return sum(samples[i] for i in range(0, len(samples), step)) / n


@pytest.mark.skipif(
    not hasattr(fitz, "open"),
    reason="PyMuPDF is required for overlay merge rotation tests",
)
def test_merge_overlay_normalizes_rotated_source_page():
    """Overlay content must land on layout coordinates when source has rotation."""
    table_region = fitz.Rect(3070, 1506, 3343, 2202)

    base_doc = fitz.open()
    overlay_doc = fitz.open()
    try:
        base_page = base_doc.new_page(width=2384, height=3370)
        base_page.set_rotation(270)
        assert round(base_page.rect.width) == 3370
        assert round(base_page.rect.height) == 2384
        base_page.draw_rect(table_region, fill=(0.4, 0.4, 0.4))

        overlay_page = overlay_doc.new_page(width=3370, height=2384)
        overlay_page.draw_rect(table_region, fill=(1, 1, 1))
        overlay_page.insert_text((3080, 1520), "OVERLAY-TABLE", fontsize=14)

        base_buf = io.BytesIO()
        overlay_buf = io.BytesIO()
        base_doc.save(base_buf)
        overlay_doc.save(overlay_buf)

        with tempfile.TemporaryDirectory() as tmp:
            overlay_path = Path(tmp) / "overlay.pdf"
            overlay_path.write_bytes(overlay_buf.getvalue())
            merged_bytes = merge_overlay_pdf(base_buf.getvalue(), overlay_path)

        merged_doc = fitz.open(stream=merged_bytes, filetype="pdf")
        merged_page = merged_doc[0]
        assert merged_page.rotation == 0
        assert _avg_channel(merged_page, table_region) > 200.0
        words = merged_page.get_text("words", clip=table_region)
        assert any(w[4] == "OVERLAY-TABLE" for w in words)
        merged_doc.close()
    finally:
        base_doc.close()
        overlay_doc.close()
