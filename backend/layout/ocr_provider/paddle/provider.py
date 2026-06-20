# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PaddleOCR provider — implements :class:`OCRProvider` backed by PaddleOCR.
"""

from dataclasses import dataclass
import threading
from typing import Any, Dict, List, Optional, Tuple

from ir.document import Document
from ir.markdown_document import MarkdownDocument
from layout.ocr_provider.base import OCRProvider
from layout.ocr_provider.types import OCRProviderResult
from layout.ocr_provider.paddle.api_client import PaddleOCRClient
from layout.ocr_provider.paddle.layout_parser import (
    parse_paddle_layout,
    extract_paddle_markdown,
)
from logger import unified_logger as logger
from logger.logger import LogModule


def _read_pdf_page_dims(pdf_bytes: bytes) -> Optional[List[Tuple[float, float]]]:
    """Read PDF page dimensions in points using PyMuPDF.

    Returns a list of (width_pt, height_pt) tuples, one per page,
    or None if the PDF cannot be opened.
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            dims: List[Tuple[float, float]] = []
            for page in doc:
                rect = page.rect
                dims.append((float(rect.width), float(rect.height)))
            return dims
        finally:
            doc.close()
    except Exception as e:
        logger.warning(LogModule.LAYOUT, f"Failed to read PDF page dimensions: {e}")
        return None


@dataclass
class PaddleOCRConfig:
    """Configuration for PaddleOCR provider."""

    token: str = ""
    base_url: str = "https://paddleocr.aistudio-app.com"
    api_endpoints: Optional[Dict[str, str]] = None
    model: str = "default"
    poll_interval: float = 3.0
    max_wait: float = 1800.0
    concurrent: int = 3
    use_doc_orientation_classify: bool = False
    restructure_pages: bool = False

    def gethash(self):
        return (
            self.token,
            self.base_url,
            self.model,
            self.poll_interval,
            self.max_wait,
            self.concurrent,
            self.use_doc_orientation_classify,
            self.restructure_pages,
        )


class PaddleOCRProvider(OCRProvider):
    """OCR provider backed by PaddleOCR async API."""

    def __init__(self, config: PaddleOCRConfig, cancel_event: Optional[threading.Event] = None):
        self._config = config
        self._client = PaddleOCRClient(
            token=config.token,
            base_url=config.base_url,
            api_endpoints=config.api_endpoints,
            poll_interval=config.poll_interval,
            max_wait=config.max_wait,
            model=config.model,
            use_doc_orientation_classify=config.use_doc_orientation_classify,
            restructure_pages=config.restructure_pages,
            cancel_event=cancel_event,
        )

    async def convert(self, document: Document) -> OCRProviderResult:
        """Submit PDF, poll until done, parse layout and markdown."""
        async with self._client as client:
            job_id = await client.submit_job(document.content)
            result = await client.poll_job(job_id)
            raw_data = await client.download_result(result)

            # For image sources, skip reading PDF page dims: PaddleOCR renders
            # the image internally and returns bbox in that render's pixel
            # space.  Using 1:1 mapping (1 px = 1 pt) keeps the coordinate
            # space self-consistent and avoids DPI mismatch between the
            # PaddleOCR render and the overlay render.
            is_image_source = document.suffix.lower() in (
                ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp",
            )
            pdf_page_dims = (
                None if is_image_source
                else _read_pdf_page_dims(document.content)
            )
            layout_doc = parse_paddle_layout(raw_data, pdf_page_dims=pdf_page_dims)
            markdown_text = extract_paddle_markdown(raw_data)
            md_doc = MarkdownDocument(content=markdown_text.encode(), suffix=".md")

            logger.info(LogModule.LAYOUT, f"PaddleOCR conversion complete: {layout_doc.page_count} pages")
            return OCRProviderResult(
                layout_document=layout_doc,
                markdown_document=md_doc,
                raw_data=raw_data,
            )

    def support_format(self) -> list[str]:
        return [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"]
