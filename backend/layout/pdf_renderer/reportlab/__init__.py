# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
ReportLab PDF renderer implementation.

This module provides a ReportLab-based PDF renderer that directly generates
PDF files from layout documents without HTML intermediate step.
"""

# Use lazy imports to avoid circular import issues
def _get_reportlab_renderer():
    """Lazy import to avoid circular dependencies."""
    from layout.pdf_renderer.reportlab.renderer import ReportLabPDFRenderer
    return ReportLabPDFRenderer

def _get_reportlab_available():
    """Lazy import to avoid circular dependencies."""
    from layout.pdf_renderer.reportlab.renderer import REPORTLAB_AVAILABLE
    return REPORTLAB_AVAILABLE

def _get_reportlab_import_error():
    """Lazy import to avoid circular dependencies."""
    from layout.pdf_renderer.reportlab.renderer import _reportlab_import_error
    return _reportlab_import_error

# For direct imports, we still export the classes
# But we use lazy loading in __init__.py to avoid circular imports
try:
    from layout.pdf_renderer.reportlab.renderer import ReportLabPDFRenderer, REPORTLAB_AVAILABLE, _reportlab_import_error
except ImportError:
    # If import fails due to circular import, define placeholders
    ReportLabPDFRenderer = None
    REPORTLAB_AVAILABLE = False
    _reportlab_import_error = "Circular import detected"

__all__ = [
    'ReportLabPDFRenderer',
    'REPORTLAB_AVAILABLE',
    '_reportlab_import_error',
]

