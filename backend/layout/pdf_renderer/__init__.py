# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF renderer module.

This module provides a unified interface for PDF generation from layout documents,
supporting multiple rendering backends (ReportLab, HTML-to-PDF, etc.).
"""

from layout.pdf_renderer.config import PDFRendererConfig
from layout.base import LayoutDocument
from typing import Dict, Optional
from pathlib import Path

# Lazy import to avoid circular dependencies
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

# Try to import directly, but handle circular import gracefully
try:
    from layout.pdf_renderer.reportlab.renderer import ReportLabPDFRenderer, REPORTLAB_AVAILABLE, _reportlab_import_error
except (ImportError, AttributeError):
    # If circular import occurs, use None placeholders
    ReportLabPDFRenderer = None
    REPORTLAB_AVAILABLE = False
    _reportlab_import_error = "Import error"


def render_layout_pdf(
    layout_doc: LayoutDocument,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    zip_bytes: Optional[bytes] = None,
    output_path: Optional[Path] = None,
    table_body_format: str = "html",
    equation_format: str = "text",
    target_language: Optional[str] = None,
    renderer_type: str = "reportlab",  # "reportlab" or "html_to_pdf"
    html_converter: str = "playwright",  # "playwright" or "weasyprint" (only when renderer_type="html_to_pdf")
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
        target_language: Optional target language code/name for font selection
        renderer_type: Renderer type
            - "reportlab": Use ReportLab for direct PDF generation (high precision, recommended)
            - "html_to_pdf": Use HTML-to-PDF conversion (CSS style support, future)
        html_converter: HTML→PDF converter type (only when renderer_type="html_to_pdf")
            - "playwright": Use Playwright (requires browser)
            - "weasyprint": Use WeasyPrint (pure Python, recommended)
    
    Returns:
        PDF file content as bytes
        
    Raises:
        ValueError: If renderer_type is unknown
        ImportError: If required dependencies are not available
    """
    # Create configuration
    config = PDFRendererConfig(
        translated_text_by_block_index=translated_text_by_block_index,
        zip_bytes=zip_bytes,
        table_body_format=table_body_format,
        equation_format=equation_format,
        target_language=target_language,
        output_path=output_path,
    )
    
    # Select renderer
    if renderer_type == "reportlab":
        # Use lazy import to avoid circular dependencies
        try:
            if ReportLabPDFRenderer is None:
                ReportLabPDFRenderer = _get_reportlab_renderer()
        except (NameError, TypeError):
            # ReportLabPDFRenderer not imported yet, use lazy import
            ReportLabPDFRenderer = _get_reportlab_renderer()
        renderer = ReportLabPDFRenderer(config)
    elif renderer_type == "html_to_pdf":
        # TODO: Implement HTMLToPDFRenderer
        raise NotImplementedError(
            "HTML-to-PDF renderer is not yet implemented. "
            "Use renderer_type='reportlab' for now."
        )
    else:
        raise ValueError(f"Unknown renderer_type: {renderer_type}")
    
    # Render PDF
    return renderer.render(layout_doc)


__all__ = [
    'render_layout_pdf',
    'PDFRendererConfig',
    'ReportLabPDFRenderer',
    'REPORTLAB_AVAILABLE',
    '_reportlab_import_error',
]

