# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Load :class:`LayoutDocument` from a PaddleOCR ``paddle_layout.zip`` artifact."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Dict, List, Optional

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from logger import unified_logger as logger
from logger.logger import LogModule


def parse_paddle_layout_from_zip_bytes(zip_bytes: bytes) -> Optional[LayoutDocument]:
    """Rebuild LayoutDocument from ``layout.json`` inside a Paddle layout ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if "layout.json" not in zf.namelist():
                logger.warning(
                    LogModule.LAYOUT,
                    "[PADDLE-ZIP] layout.json not found in paddle layout ZIP",
                )
                return None
            data = json.loads(zf.read("layout.json").decode("utf-8"))
    except Exception as exc:
        logger.error(
            LogModule.LAYOUT,
            f"[PADDLE-ZIP] Failed to read paddle layout ZIP: {exc}",
            exc_info=True,
        )
        return None

    if not isinstance(data, dict):
        return None

    engine = str(data.get("engine") or "paddle")
    pages: List[LayoutPage] = []
    for page_data in data.get("pages") or []:
        if not isinstance(page_data, dict):
            continue
        page_index = int(page_data.get("page_index") or len(pages))
        blocks: List[LayoutBlock] = []
        for block_data in page_data.get("blocks") or []:
            if not isinstance(block_data, dict):
                continue
            bbox_raw = block_data.get("bbox")
            bbox = _parse_bbox(bbox_raw)
            if bbox is None:
                continue
            block_type = str(block_data.get("type") or "text")
            image_path: Optional[str] = None
            if block_type == "image":
                from layout.ocr_provider.paddle.layout_parser import (
                    _PADDLE_IMAGE_PATH_SENTINEL,
                )

                image_path = _PADDLE_IMAGE_PATH_SENTINEL
            blocks.append(
                LayoutBlock(
                    page_index=page_index,
                    bbox=bbox,
                    type=block_type,
                    sub_type=str(block_data.get("sub_type") or ""),
                    index=block_data.get("block_index"),
                    text=str(block_data.get("text") or block_data.get("text_preview") or "") or None,
                    tags=list(block_data.get("tags") or []),
                    image_path=image_path,
                    raw=dict(block_data),
                )
            )
        page_w = page_data.get("page_width")
        page_h = page_data.get("page_height")
        pages.append(
            LayoutPage(
                page_index=page_index,
                blocks=blocks,
                width=float(page_w) if page_w is not None else None,
                height=float(page_h) if page_h is not None else None,
            )
        )

    if not pages:
        return None
    return LayoutDocument(pages=pages, engine=engine)


def _parse_bbox(raw: Any) -> Optional[tuple[float, float, float, float]]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return tuple(float(v) for v in raw)
    except (TypeError, ValueError):
        return None
