#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export and preview routes for Owlangs.

This module contains routes for PDF export and file preview functionality.
"""

import io
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from backend.app.models.service import PdfExportHtmlRequest, PdfExportRequest
from utils.http_content_disposition import streaming_download_response

# Create router
router = APIRouter()

# Check for Playwright availability
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@router.post("/export/pdf")
async def export_pdf(req: PdfExportRequest):
    """Export PDF from various formats."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Playwright not installed, cannot generate PDF. Please install optional dependency 'pdf_export'."
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Set content based on request type
            if req.html:
                await page.set_content(req.html)
            elif req.url:
                await page.goto(req.url)
            else:
                raise HTTPException(status_code=400, detail="Either 'html' or 'url' must be provided")

            # Generate PDF
            pdf_buffer = await page.pdf(
                format=req.format or "A4",
                margin=req.margin or {"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                print_background=req.print_background or True,
                landscape=req.landscape or False
            )

            await browser.close()

            # Return PDF as streaming response
            return streaming_download_response(
                io.BytesIO(pdf_buffer),
                filename=req.filename or "document.pdf",
                media_type="application/pdf",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@router.post("/export/pdf/from-html")
async def export_pdf_from_html(req: PdfExportHtmlRequest):
    """Export PDF from HTML content."""
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Playwright not installed, cannot generate PDF. Please install optional dependency 'pdf_export'."
        )

    try:
        import io
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            html_text = req.html
            base_href = (req.base_url or '').rstrip('/') + '/'
            
            # Enhance HTML content to ensure images and tables display correctly
            enhanced_html = html_text
            
            # Add base tag to ensure relative paths are parsed correctly
            if base_href and "<head" in enhanced_html:
                enhanced_html = enhanced_html.replace("<head>", f"<head><base href=\"{base_href}\">", 1)
            elif base_href:
                enhanced_html = f"<head><base href=\"{base_href}\"></head>" + enhanced_html
            
            # Add CSS to ensure images and tables display correctly in PDF
            css_enhancement = """
            <style>
                /* Ensure images display correctly in PDF */
                img {
                    max-width: 100% !important;
                    height: auto !important;
                    page-break-inside: avoid;
                }
                
                /* Ensure tables display correctly in PDF */
                table {
                    width: 100% !important;
                    border-collapse: collapse !important;
                    page-break-inside: avoid;
                }
                
                th, td {
                    border: 1px solid #ddd !important;
                    padding: 8px !important;
                    text-align: left !important;
                }
                
                /* Ensure proper page breaks */
                .page-break {
                    page-break-before: always;
                }
                
                /* Ensure text is readable */
                body {
                    font-family: Arial, sans-serif !important;
                    font-size: 12px !important;
                    line-height: 1.4 !important;
                    color: #000 !important;
                }
            </style>
            """
            
            # Insert CSS into HTML
            if "<head>" in enhanced_html:
                enhanced_html = enhanced_html.replace("<head>", f"<head>{css_enhancement}", 1)
            else:
                enhanced_html = f"<head>{css_enhancement}</head>" + enhanced_html

            await page.set_content(enhanced_html)

            # Generate PDF with enhanced settings
            pdf_buffer = await page.pdf(
                format=req.format or "A4",
                margin=req.margin or {"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                print_background=req.print_background or True,
                landscape=req.landscape or False,
                prefer_css_page_size=True
            )

            await browser.close()

            # Return PDF as streaming response
            return streaming_download_response(
                io.BytesIO(pdf_buffer),
                filename=req.filename or "document.pdf",
                media_type="application/pdf",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@router.post("/preview/docx", response_class=HTMLResponse)
async def preview_docx(file: UploadFile = File(...)):
    """Convert a DOCX file to HTML for preview using mammoth."""
    try:
        content = await file.read()
        from utils.office_preview_utils import docx_bytes_to_html

        return HTMLResponse(content=docx_bytes_to_html(content))
    except RuntimeError as e:
        detail = str(e)
        status = 503 if "mammoth" in detail.lower() else 500
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX preview failed: {e}")


@router.post("/preview/xlsx", response_class=HTMLResponse)
async def preview_xlsx(file: UploadFile = File(...), max_rows: int = 200):
    """Convert an XLSX file to HTML for preview (all sheets, capped rows)."""
    try:
        content = await file.read()
        from utils.office_preview_utils import xlsx_bytes_to_html

        return HTMLResponse(content=xlsx_bytes_to_html(content, max_rows=max_rows))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"XLSX preview failed: {e}")


@router.post("/preview/pptx", response_class=HTMLResponse)
async def preview_pptx(file: UploadFile = File(...)):
    """Convert a PPTX file to HTML slides for preview using python-pptx."""
    try:
        content = await file.read()
        from utils.office_preview_utils import pptx_bytes_to_html

        return HTMLResponse(content=pptx_bytes_to_html(content))
    except RuntimeError as e:
        detail = str(e)
        status = 503 if "python-pptx" in detail.lower() else 500
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPTX preview failed: {e}")


@router.post("/preview/epub", response_class=HTMLResponse)
async def preview_epub(file: UploadFile = File(...)):
    """Convert an EPUB file to HTML for compare-reading preview."""
    try:
        content = await file.read()
        from utils.ebook_preview_utils import epub_bytes_to_html

        return HTMLResponse(content=epub_bytes_to_html(content))
    except RuntimeError as e:
        detail = str(e)
        status = 503 if "ebooklib" in detail.lower() else 500
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EPUB preview failed: {e}")


@router.post("/preview/mobi", response_class=HTMLResponse)
async def preview_mobi(file: UploadFile = File(...)):
    """Convert a MOBI/AZW file to HTML for compare-reading preview."""
    try:
        content = await file.read()
        from utils.ebook_preview_utils import mobi_bytes_to_html

        return HTMLResponse(content=mobi_bytes_to_html(content))
    except RuntimeError as e:
        detail = str(e)
        lower = detail.lower()
        # 503 only when required packages are missing; bad/corrupt files are 400.
        if "requires" in lower and ("package" in lower or "install" in lower):
            status = 503
        elif "failed" in lower or "invalid" in lower or "corrupt" in lower:
            status = 400
        else:
            status = 500
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"MOBI/AZW preview failed: {e}")
