# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typst Overlay PDF Renderer.

This module provides a high-fidelity PDF export approach inspired by
RetainPDF's overlay rendering architecture. Instead of rebuilding the
PDF from scratch (like ReportLab does), it:

1. Cleans original text from the source PDF (using PyMuPDF redaction)
2. Generates a Typst overlay with precisely positioned translated text
3. Merges the overlay onto the cleaned source PDF

This preserves the original PDF's visual structure (background images,
table borders, decorative elements) while replacing text with translations.
"""

from layout.pdf_renderer.typst_overlay.renderer import (
    TypstOverlayRenderer, TYPST_OVERLAY_AVAILABLE, _typst_overlay_import_error
)
from layout.pdf_renderer.typst_overlay.models import (
    RenderBlock, RenderPageSpec, RenderLineBox,
)
from layout.pdf_renderer.typst_overlay.font_fit import (
    FontFitCalculator,
    estimate_font_size_from_bbox,
    estimate_leading_from_bbox,
)
from layout.pdf_renderer.typst_overlay.compiler import (
    TypstCompiler, compile_overlay_pdf, is_typst_available,
)

__all__ = [
    "TypstOverlayRenderer",
    "TYPST_OVERLAY_AVAILABLE",
    "_typst_overlay_import_error",
    "RenderBlock",
    "RenderPageSpec",
    "RenderLineBox",
    "FontFitCalculator",
    "estimate_font_size_from_bbox",
    "estimate_leading_from_bbox",
    "TypstCompiler",
    "compile_overlay_pdf",
    "is_typst_available",
]
