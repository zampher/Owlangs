# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
ReportLab PDF renderer implementation.

This module provides a ReportLab-based PDF renderer that directly generates
PDF files from layout documents without HTML intermediate step.
"""

import io
from typing import Dict, Optional
from pathlib import Path

from layout.base import LayoutDocument
from layout.pdf_renderer.base import BasePDFRenderer
from layout.pdf_renderer.config import PDFRendererConfig
from logger.logger import unified_logger, LogModule

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    REPORTLAB_AVAILABLE = True
    _reportlab_import_error = None
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    _reportlab_import_error = str(e)
    unified_logger.warning(
        LogModule.RESTOR,
        "ReportLab not available. Import error: {error}. Install with: pip install reportlab",
        error=e,
    )


class ReportLabPDFRenderer(BasePDFRenderer):
    """
    ReportLab-based PDF renderer.
    
    This renderer uses ReportLab to directly generate PDF files from
    layout documents, providing high-fidelity positioning and text rendering.
    """
    
    def __init__(self, config: PDFRendererConfig):
        """
        Initialize ReportLab PDF renderer.
        
        Args:
            config: PDF renderer configuration
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for ReportLab PDF renderer. "
                f"Install with: pip install reportlab. Error: {_reportlab_import_error}"
            )
        
        super().__init__(config)
        
        # Start font registration in background thread (non-blocking startup)
        # Fonts will be registered asynchronously, and will be available when needed
        # This avoids blocking startup with font registration for all languages
        try:
            self.font_utils.register_all_fonts(background=True)
        except Exception as e:
            unified_logger.warning(
                LogModule.RESTOR,
                f"[REPORTLAB] Failed to start background font registration: {e}"
            )
    
    def render(self, layout_doc: LayoutDocument) -> bytes:
        """
        Render LayoutDocument to PDF using ReportLab.
        
        This method implements the main rendering logic. For now, it delegates
        to the original `render_layout_pdf_reportlab` function. In a future phase,
        the logic will be fully migrated to this class.
        
        Args:
            layout_doc: LayoutDocument instance
            
        Returns:
            PDF file content as bytes
        """
        # For now, delegate to the original function
        # TODO: Migrate the full rendering logic here in phases
        # Use lazy import to avoid circular import issues
        import importlib
        pdf_renderer_module = importlib.import_module('layout.pdf_renderer_reportlab')
        render_layout_pdf_reportlab = getattr(pdf_renderer_module, 'render_layout_pdf_reportlab')
        
        return render_layout_pdf_reportlab(
            layout_doc=layout_doc,
            translated_text_by_block_index=self.config.translated_text_by_block_index,
            zip_bytes=self.config.zip_bytes,
            output_path=self.config.output_path,
            table_body_format=self.config.table_body_format,
            equation_format=getattr(self.config, "equation_format", "text"),
            target_language=self.config.target_language,
        )

