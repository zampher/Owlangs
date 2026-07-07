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
    paddle_raw_payload: Optional[Dict[str, Any]] = None
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if "layout.json" not in zf.namelist():
                logger.warning(
                    LogModule.LAYOUT,
                    "[PADDLE-ZIP] layout.json not found in paddle layout ZIP",
                )
                return None
            data = json.loads(zf.read("layout.json").decode("utf-8"))
            if "paddle_raw.json" in zf.namelist():
                try:
                    raw_loaded = json.loads(zf.read("paddle_raw.json").decode("utf-8"))
                    if isinstance(raw_loaded, dict):
                        paddle_raw_payload = raw_loaded
                except Exception:
                    pass
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

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    doc = LayoutDocument(pages=pages, engine=engine, metadata=dict(metadata))
    det_boxes = metadata.get("paddle_det_boxes") or []
    if not det_boxes and paddle_raw_payload:
        det_boxes = _collect_det_boxes_from_paddle_raw(paddle_raw_payload)
        if det_boxes:
            doc.metadata["paddle_det_boxes"] = det_boxes
    if isinstance(det_boxes, list) and det_boxes:
        from layout.ocr_provider.paddle.paddle_det_supplements import (
            append_paddle_det_supplement_blocks,
        )

        for page in doc.pages:
            page_w = float(page.width or 1.0)
            page_h = float(page.height or 1.0)
            append_paddle_det_supplement_blocks(
                page.blocks,
                det_boxes,
                page_index=page.page_index,
                next_block_index=max(
                    (int(b.index) for b in page.blocks if b.index is not None),
                    default=-1,
                ) + 1,
                page_w=page_w,
                page_h=page_h,
            )
    if metadata.get("coordinate_space"):
        doc.metadata["coordinate_space"] = metadata["coordinate_space"]
    elif engine == "paddle":
        doc.metadata.setdefault("coordinate_space", "image_px")
    _enrich_layout_group_pairs_on_document(doc, paddle_raw_payload)
    return doc


def _enrich_layout_group_pairs_on_document(
    doc: LayoutDocument,
    paddle_raw_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Backward-compatible wrapper; see layout.layout_group_enrichment."""
    from layout.layout_group_enrichment import enrich_layout_group_pairs_on_document

    engine = (getattr(doc, "engine", None) or "").strip().lower()
    use_paddle_groups = paddle_raw_payload is not None or engine == "paddle"
    enrich_layout_group_pairs_on_document(
        doc,
        paddle_raw_payload,
        apply_paddle_groups=use_paddle_groups,
        log_prefix="PADDLE-ZIP" if use_paddle_groups else "MINERU-GROUP",
    )


def _merge_group_pair_meta_from_paddle_raw(
    doc: LayoutDocument,
    paddle_raw_payload: Dict[str, Any],
) -> None:
    """Copy group_id / pair metadata from a fresh paddle_raw parse by block index."""
    from layout.layout_group_pair_utils import (
        LAYOUT_GROUP_PAIR_OF_KEY,
        LAYOUT_GROUP_PAIRS_KEY,
    )
    from layout.ocr_provider.paddle.layout_parser import parse_paddle_layout

    page_dims = []
    for page in doc.pages:
        width = float(page.width) if page.width else 595.0
        height = float(page.height) if page.height else 842.0
        page_dims.append((width, height))
    if not page_dims:
        page_dims = [(595.0, 842.0)]

    parsed = parse_paddle_layout(paddle_raw_payload, pdf_page_dims=page_dims)
    if parsed is None:
        return

    meta_by_index: Dict[int, Dict[str, Any]] = {}
    for block in parsed.iter_blocks():
        if block.index is None:
            continue
        raw = block.raw if isinstance(block.raw, dict) else {}
        payload: Dict[str, Any] = {}
        for key in (
            "group_id",
            "block_order",
            LAYOUT_GROUP_PAIRS_KEY,
            LAYOUT_GROUP_PAIR_OF_KEY,
        ):
            if raw.get(key) is not None:
                payload[key] = raw.get(key)
        if payload:
            meta_by_index[int(block.index)] = payload

    merged = 0
    for block in doc.iter_blocks():
        if block.index is None:
            continue
        payload = meta_by_index.get(int(block.index))
        if not payload:
            continue
        raw = dict(block.raw or {})
        changed = False
        for key, value in payload.items():
            if raw.get(key) is None and value is not None:
                raw[key] = value
                changed = True
        if changed:
            block.raw = raw
            merged += 1

    if merged:
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLE-ZIP] Merged paddle_raw group metadata into {merged} layout block(s)",
        )


def _append_det_blocks_to_zip_layout(doc: LayoutDocument) -> None:
    from layout.ocr_provider.paddle.paddle_det_supplements import (
        append_paddle_det_supplement_blocks,
        paddle_det_boxes_from_layout_doc,
    )

    det_boxes = paddle_det_boxes_from_layout_doc(doc)
    if not det_boxes:
        return
    for page in doc.pages:
        page_w = float(page.width or 1.0)
        page_h = float(page.height or 1.0)
        next_idx = max(
            (int(b.index) for b in page.blocks if b.index is not None),
            default=-1,
        ) + 1
        append_paddle_det_supplement_blocks(
            page.blocks,
            det_boxes,
            page_index=page.page_index,
            next_block_index=next_idx,
            page_w=page_w,
            page_h=page_h,
        )


def _collect_det_boxes_from_paddle_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract layout det boxes from a stored paddle_raw.json payload."""
    from layout.ocr_provider.paddle.paddle_det_supplements import (
        extract_paddle_det_boxes_from_pruned,
    )

    collected: List[Dict[str, Any]] = []
    for chunk in raw_data.get("layoutParsingResults") or []:
        if not isinstance(chunk, dict):
            continue
        for inner in chunk.get("layoutParsingResults") or []:
            if not isinstance(inner, dict):
                continue
            pruned = inner.get("prunedResult")
            if isinstance(pruned, dict):
                collected.extend(extract_paddle_det_boxes_from_pruned(pruned))
    return collected


def _parse_bbox(raw: Any) -> Optional[tuple[float, float, float, float]]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return tuple(float(v) for v in raw)
    except (TypeError, ValueError):
        return None
