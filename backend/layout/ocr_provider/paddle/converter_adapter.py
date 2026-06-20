# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Paddle-to-Converter adapter.

Wraps :class:`PaddleOCRProvider` to expose the synchronous
``converter.convert(document)`` interface expected by
:class:`MarkdownBasedWorkflow`.

The adapter is called via ``asyncio.to_thread()``, so it runs in a
non-main thread.  A module-level ``threading.Event`` is wired to
SIGINT so that Ctrl+C can cancel an in-progress polling loop without
blocking process shutdown.
"""

import asyncio
import io
import json
import signal
import threading
import zipfile
from typing import Any, Dict, Optional

from ir.attachment_manager import AttachMent
from ir.document import Document
from ir.markdown_document import MarkdownDocument
from layout.base import LayoutDocument
from layout.ocr_provider.paddle.provider import PaddleOCRProvider, PaddleOCRConfig
from logger import unified_logger as logger
from logger.logger import LogModule

# ---------------------------------------------------------------------------
# Global cancel events — set by SIGINT handler to unblock polling threads
# ---------------------------------------------------------------------------
_cancel_events: list[threading.Event] = []
_events_lock = threading.Lock()


def _add_cancel_event(event: threading.Event) -> None:
    with _events_lock:
        _cancel_events.append(event)


def _remove_cancel_event(event: threading.Event) -> None:
    with _events_lock:
        try:
            _cancel_events.remove(event)
        except ValueError:
            pass


def _fire_all_cancel_events() -> None:
    with _events_lock:
        for evt in _cancel_events:
            evt.set()
    logger.info(LogModule.LAYOUT, f"PaddleOCR: cancelled {len(_cancel_events)} active conversion(s)")


# ---------------------------------------------------------------------------
# SIGINT integration
# ---------------------------------------------------------------------------
_prev_sigint = signal.getsignal(signal.SIGINT)


def _sigint_handler(signum, frame):
    """Fire cancel events, then chain to the previous handler (e.g. uvicorn)."""
    _fire_all_cancel_events()
    if _prev_sigint is not None and _prev_sigint != signal.default_int_handler:
        _prev_sigint(signum, frame)
    else:
        signal.default_int_handler(signum, frame)


try:
    signal.signal(signal.SIGINT, _sigint_handler)
except ValueError:
    # Not in the main thread — signals are already handled elsewhere
    pass


# ---------------------------------------------------------------------------
class PaddleToConverterAdapter:
    """
    Adapter that wraps a PaddleOCRProvider to match the ConverterMineru
    interface consumed by MarkdownBasedWorkflow.
    """

    def __init__(self, config: PaddleOCRConfig):
        self.config = config
        self._cancel_event = threading.Event()
        self._provider: Optional[PaddleOCRProvider] = None
        self.layout_document: Optional[LayoutDocument] = None
        self.attachments = []
        self.raw_data: Optional[Dict[str, Any]] = None

    def convert(self, document: Document) -> MarkdownDocument:
        """Run PaddleOCR conversion synchronously (blocks until done)."""
        _add_cancel_event(self._cancel_event)
        try:
            if self._cancel_event.is_set():
                raise KeyboardInterrupt("PaddleOCR conversion cancelled before start")
            self._provider = PaddleOCRProvider(self.config, cancel_event=self._cancel_event)
            result = asyncio.run(self._provider.convert(document))
            self.layout_document = result.layout_document
            self.raw_data = result.raw_data
            self._attach_layout_zip(result)
            return result.markdown_document
        except asyncio.CancelledError:
            logger.info(LogModule.LAYOUT, "PaddleOCR conversion cancelled by user")
            raise KeyboardInterrupt("PaddleOCR conversion cancelled")
        finally:
            _remove_cancel_event(self._cancel_event)
            self._provider = None

    def _attach_layout_zip(self, result) -> None:
        """Build paddle_layout.zip from the OCR result and attach to workflow."""
        try:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Raw PaddleOCR API response (JSON)
                if result.raw_data:
                    zf.writestr("paddle_raw.json", json.dumps(
                        result.raw_data, ensure_ascii=False, indent=2,
                    ))
                # Extracted markdown
                md_bytes = result.markdown_document.content
                if md_bytes:
                    zf.writestr("full.md", md_bytes.decode("utf-8", errors="replace"))
                # Layout blocks JSON (same structure as layout_blocks.json debug)
                if result.layout_document:
                    ld = result.layout_document
                    pages_data = []
                    for page in ld.pages:
                        blocks_data = []
                        for block in page.blocks:
                            bbox = block.bbox if hasattr(block, "bbox") else None
                            blocks_data.append({
                                "page_index": block.page_index,
                                "block_index": block.index,
                                "type": getattr(block, "type", "?"),
                                "sub_type": getattr(block, "sub_type", ""),
                                "bbox": list(bbox) if bbox else None,
                                "text": (getattr(block, "text", "") or ""),
                                "tags": list(getattr(block, "tags", []) or []),
                            })
                        pages_data.append({
                            "page_index": page.page_index,
                            "page_width": page.width,
                            "page_height": page.height,
                            "blocks": blocks_data,
                        })
                    zf.writestr("layout.json", json.dumps({
                        "engine": getattr(ld, "engine", "paddle"),
                        "page_count": ld.page_count,
                        "total_blocks": sum(len(p["blocks"]) for p in pages_data),
                        "pages": pages_data,
                    }, ensure_ascii=False, indent=2))
            zip_bytes = zip_buffer.getvalue()
            self.attachments.append(AttachMent(
                "paddle",
                Document.from_bytes(content=zip_bytes, suffix=".zip", stem="paddle_layout"),
            ))
            logger.debug(
                LogModule.LAYOUT,
                f"[PADDLE] Built paddle_layout.zip ({len(zip_bytes)} bytes)",
            )
        except Exception as e:
            logger.warning(LogModule.LAYOUT, f"[PADDLE] Failed to build layout ZIP: {e}")
