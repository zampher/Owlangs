# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF renderer module.

This module provides a unified interface for PDF generation from layout documents,
supporting multiple rendering backends (ReportLab, Typst Overlay, etc.).
"""

from layout.pdf_renderer.config import PDFRendererConfig
from layout.base import LayoutDocument
from typing import Dict, Optional, Union
from pathlib import Path


# ---- Lazy import helpers for ReportLab ----

def _get_reportlab_renderer():
    """Lazy import ReportLab renderer."""
    from layout.pdf_renderer.reportlab.renderer import ReportLabPDFRenderer
    return ReportLabPDFRenderer

def _get_reportlab_available():
    """Lazy import REPORTLAB_AVAILABLE."""
    from layout.pdf_renderer.reportlab.renderer import REPORTLAB_AVAILABLE
    return REPORTLAB_AVAILABLE

def _get_reportlab_import_error():
    """Lazy import _reportlab_import_error."""
    from layout.pdf_renderer.reportlab.renderer import _reportlab_import_error
    return _reportlab_import_error


# ---- Lazy import helpers for Typst Overlay ----

def _get_typst_overlay_renderer():
    """Lazy import TypstOverlayRenderer."""
    from layout.pdf_renderer.typst_overlay.renderer import TypstOverlayRenderer
    return TypstOverlayRenderer

def _get_typst_overlay_available():
    """Lazy import TYPST_OVERLAY_AVAILABLE."""
    from layout.pdf_renderer.typst_overlay.renderer import TYPST_OVERLAY_AVAILABLE
    return TYPST_OVERLAY_AVAILABLE

def _get_typst_overlay_import_error():
    """Lazy import _typst_overlay_import_error."""
    from layout.pdf_renderer.typst_overlay.renderer import _typst_overlay_import_error
    return _typst_overlay_import_error


# Try to import directly, but handle circular import gracefully
try:
    from layout.pdf_renderer.reportlab.renderer import ReportLabPDFRenderer, REPORTLAB_AVAILABLE, _reportlab_import_error
except (ImportError, AttributeError):
    ReportLabPDFRenderer = None
    REPORTLAB_AVAILABLE = False
    _reportlab_import_error = "Import error"

try:
    from layout.pdf_renderer.typst_overlay.renderer import (
        TypstOverlayRenderer, TYPST_OVERLAY_AVAILABLE, _typst_overlay_import_error,
    )
except (ImportError, AttributeError):
    TypstOverlayRenderer = None
    TYPST_OVERLAY_AVAILABLE = False
    _typst_overlay_import_error = "Import error"


# ---- Unified entry point ----

def render_layout_pdf(
    layout_doc: LayoutDocument,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    zip_bytes: Optional[bytes] = None,
    output_path: Optional[Path] = None,
    table_body_format: str = "html",
    equation_format: str = "text",
    chart_body_format: str = "image",
    target_language: Optional[str] = None,
    renderer_type: str = "reportlab",
    html_converter: str = "playwright",
    # Typst overlay params
    source_pdf_path: Optional[Union[str, Path]] = None,
    typst_font_family: Optional[str] = None,
) -> bytes:
    """
    Unified PDF rendering entry point.

    This function provides a unified interface for PDF generation from layout documents.
    It supports multiple rendering backends and can be easily extended.

    Args:
        layout_doc: LayoutDocument instance
        translated_text_by_block_index: Optional mapping from block index to translated text
        zip_bytes: Optional ZIP bytes for extracting images
        output_path: Optional path to save PDF file (for debugging)
        table_body_format: Table format ("html" or "image")
        equation_format: Equation format ("text" for LaTeX or "image" for rendered images)
        chart_body_format: Chart format ("html" or "image")
        target_language: Optional target language code/name for font selection
        renderer_type: Renderer type
            - "reportlab": Use ReportLab for direct PDF generation (current default)
            - "html_to_pdf": Use HTML-to-PDF conversion (future)
            - "typst_overlay": Use Typst overlay rendering for highest fidelity PDF
        html_converter: HTML→PDF converter type (only when renderer_type="html_to_pdf")
        source_pdf_path: Path to the original PDF file (required for "typst_overlay")
        typst_font_family: Typst font family for "typst_overlay" (default: "Noto Sans CJK SC")

    Returns:
        PDF file content as bytes

    Raises:
        ValueError: If renderer_type is unknown
        ImportError: If required dependencies are not available
    """
    from logger.logger import unified_logger, LogModule

    # Create configuration
    config = PDFRendererConfig(
        translated_text_by_block_index=translated_text_by_block_index,
        zip_bytes=zip_bytes,
        table_body_format=table_body_format,
        equation_format=equation_format,
        chart_body_format=chart_body_format,
        target_language=target_language,
        output_path=output_path,
        source_pdf_path=source_pdf_path,
        typst_font_family=typst_font_family,
    )

    # Select renderer
    if renderer_type == "reportlab":
        try:
            renderer_cls = ReportLabPDFRenderer
            if renderer_cls is None:
                renderer_cls = _get_reportlab_renderer()
        except (NameError, TypeError):
            renderer_cls = _get_reportlab_renderer()
        renderer = renderer_cls(config)

    elif renderer_type == "typst_overlay":
        try:
            renderer_cls = TypstOverlayRenderer
            if renderer_cls is None:
                renderer_cls = _get_typst_overlay_renderer()
        except (NameError, TypeError):
            renderer_cls = _get_typst_overlay_renderer()

        if source_pdf_path is None:
            raise ValueError(
                "source_pdf_path is required for renderer_type='typst_overlay'. "
                "Pass the path to the original PDF file."
            )
        unified_logger.info(
            LogModule.RESTOR,
            f"[PDF_RENDERER] Using Typst overlay renderer for: {source_pdf_path}"
        )
        renderer = renderer_cls(config)

    elif renderer_type == "html_to_pdf":
        raise NotImplementedError(
            "HTML-to-PDF renderer is not yet implemented. "
            "Use renderer_type='reportlab' or 'typst_overlay'."
        )

    else:
        raise ValueError(
            f"Unknown renderer_type: {renderer_type}. "
            "Supported types: 'reportlab', 'typst_overlay', 'html_to_pdf'"
        )

    # Render PDF
    return renderer.render(layout_doc)


__all__ = [
    'render_layout_pdf',
    'PDFRendererConfig',
    'ReportLabPDFRenderer',
    'REPORTLAB_AVAILABLE',
    '_reportlab_import_error',
    'TypstOverlayRenderer',
    'TYPST_OVERLAY_AVAILABLE',
    '_typst_overlay_import_error',
]
