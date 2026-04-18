# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Shared utility functions for DOCX processing.
Used by both DocxExtractor and DocxTranslator to avoid code duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docx.text.run import Run
    from docx.text.paragraph import Paragraph


def get_run_formatting_key(run: "Run") -> tuple:
    """
    Get a hashable key representing the formatting of a run.
    Used to detect formatting changes between runs.
    
    Args:
        run: A docx Run object
        
    Returns:
        Tuple of (font_name, bold, italic, underline, size, color_rgb)
    """
    if not run.font:
        return (None, None, None, None, None, None)
    
    try:
        color_rgb = None
        if run.font.color and hasattr(run.font.color, 'rgb') and run.font.color.rgb:
            color_rgb = run.font.color.rgb
    except Exception:
        color_rgb = None
    
    return (
        run.font.name,
        run.font.bold,
        run.font.italic,
        run.font.underline,
        run.font.size,
        color_rgb,
    )


def is_image_run(run: "Run") -> bool:
    """
    Check if a run contains an image.
    
    Args:
        run: A docx Run object
        
    Returns:
        True if the run contains an image, False otherwise
    """
    return '<w:drawing' in run.element.xml or '<w:pict' in run.element.xml


def paragraph_has_toc_field(paragraph: "Paragraph") -> bool:
    """
    Check if a paragraph contains a TOC field.
    
    Args:
        paragraph: A docx Paragraph object
        
    Returns:
        True if the paragraph contains a TOC field, False otherwise
    """
    try:
        p = paragraph._p  # lxml element
        
        # Check for TOC field codes
        fldChars = p.xpath('.//*[local-name()="fldChar"]')
        if not fldChars:
            # quick check for instruction text
            instrs = p.xpath('.//*[local-name()="instrText"]')
            for it in instrs:
                if 'TOC' in (it.text or ''):
                    return True
        else:
            instrs = p.xpath('.//*[local-name()="instrText"]')
            for it in instrs:
                if 'TOC' in (it.text or ''):
                    return True
                    
    except Exception:
        pass
    return False

