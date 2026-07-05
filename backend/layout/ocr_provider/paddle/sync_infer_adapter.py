# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Adapt PaddleOCR local sync APIs (/layout-parsing, /ocr) to cloud layoutParsingResults shape."""

from __future__ import annotations

from typing import Any, Dict, List

# Local PaddleOCR serving endpoints that accept JSON base64 sync POST (not cloud async jobs).
_LOCAL_SYNC_SUBMIT_PATHS = frozenset({"/ocr", "/layout-parsing"})


def is_sync_infer_submit_path(submit_path: str) -> bool:
    """True when submit endpoint is a local sync JSON API (not cloud async jobs)."""
    normalized = (submit_path or "").strip().rstrip("/") or "/api/v2/ocr/jobs"
    return normalized in _LOCAL_SYNC_SUBMIT_PATHS


def _wrap_flat_layout_page(page_item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize local /layout-parsing page payload to cloud nested shape."""
    if page_item.get("layoutParsingResults"):
        return page_item

    pruned = page_item.get("prunedResult")
    if not isinstance(pruned, dict):
        return page_item

    width = pruned.get("width")
    height = pruned.get("height")
    page_meta: Dict[str, Any] = {}
    if width is not None:
        page_meta["width"] = width
    if height is not None:
        page_meta["height"] = height

    return {
        "dataInfo": {"pages": [page_meta]} if page_meta else {"pages": []},
        "layoutParsingResults": [{"prunedResult": pruned}],
    }


def normalize_sync_infer_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert local sync response into cloud-style layoutParsingResults."""
    result = payload.get("result", payload)
    if not isinstance(result, dict):
        raise ValueError(f"Sync PaddleOCR response missing result object: {payload!r}")

    if result.get("layoutParsingResults"):
        pages = result["layoutParsingResults"]
        normalized_pages = [
            _wrap_flat_layout_page(item) if isinstance(item, dict) else item
            for item in pages
        ]
        return {"layoutParsingResults": normalized_pages}

    ocr_results = result.get("ocrResults") or []
    data_info = result.get("dataInfo") or {}
    pages_meta: List[Dict[str, Any]] = list(data_info.get("pages") or [])

    layout_parsing_results: List[Dict[str, Any]] = []
    for page_idx, ocr_item in enumerate(ocr_results):
        if not isinstance(ocr_item, dict):
            continue
        pruned = ocr_item.get("prunedResult") or {}
        if not isinstance(pruned, dict):
            continue

        if pruned.get("parsing_res_list"):
            page_meta = pages_meta[page_idx] if page_idx < len(pages_meta) else {}
            layout_parsing_results.append(
                {
                    "dataInfo": {"pages": [page_meta]} if page_meta else {"pages": []},
                    "layoutParsingResults": [{"prunedResult": pruned}],
                }
            )
            continue

        rec_texts = pruned.get("rec_texts") or []
        rec_boxes = pruned.get("rec_boxes") or []
        parsing_res_list: List[Dict[str, Any]] = []
        for order, (text, box) in enumerate(zip(rec_texts, rec_boxes)):
            content = str(text or "").strip()
            if not content:
                continue
            if not (isinstance(box, list) and len(box) == 4):
                continue
            try:
                bbox = [float(v) for v in box]
            except (TypeError, ValueError):
                continue
            parsing_res_list.append(
                {
                    "block_label": "text",
                    "block_bbox": bbox,
                    "block_content": content,
                    "block_order": order,
                }
            )

        page_meta = pages_meta[page_idx] if page_idx < len(pages_meta) else {}
        layout_parsing_results.append(
            {
                "dataInfo": {"pages": [page_meta]} if page_meta else {"pages": []},
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "parsing_res_list": parsing_res_list,
                            "width": page_meta.get("width"),
                            "height": page_meta.get("height"),
                        }
                    }
                ],
            }
        )

    return {"layoutParsingResults": layout_parsing_results}
