# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Detect PaddleOCR deployment capabilities (VL layout vs text-only OCR)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

# Owlangs requires document parsing (titles/tables/formulas), not plain line OCR.
CAPABILITY_VL_LAYOUT = "vl_layout"
CAPABILITY_TEXT_OCR_ONLY = "text_ocr_only"
CAPABILITY_CLOUD_ASYNC = "cloud_async"
CAPABILITY_UNKNOWN = "unknown"


def build_probe_pdf_bytes() -> bytes:
    """Build a minimal one-page PDF for capability probing."""
    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=200, height=200)
        page.insert_text((24, 100), "Owlangs layout probe", fontsize=11)
        data = doc.tobytes()
        doc.close()
        return data
    except Exception:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 200 200]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 24 100 Td (Owlangs) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n"
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
        )


def _iter_parsing_res_lists(payload: Any) -> Iterable[List[Dict[str, Any]]]:
    if not isinstance(payload, dict):
        return
    result = payload.get("result", payload)
    if not isinstance(result, dict):
        return

    layout_results = result.get("layoutParsingResults")
    if isinstance(layout_results, list):
        for page_payload in layout_results:
            if not isinstance(page_payload, dict):
                continue
            # Local /layout-parsing: prunedResult sits directly on each page item.
            flat_pruned = page_payload.get("prunedResult")
            if isinstance(flat_pruned, dict):
                parsing = flat_pruned.get("parsing_res_list")
                if isinstance(parsing, list):
                    yield parsing
            inner = page_payload.get("layoutParsingResults") or []
            for item in inner:
                if not isinstance(item, dict):
                    continue
                pruned = item.get("prunedResult") or {}
                parsing = pruned.get("parsing_res_list")
                if isinstance(parsing, list):
                    yield parsing

    ocr_results = result.get("ocrResults")
    if isinstance(ocr_results, list):
        for item in ocr_results:
            if not isinstance(item, dict):
                continue
            pruned = item.get("prunedResult") or {}
            if not isinstance(pruned, dict):
                continue
            parsing = pruned.get("parsing_res_list")
            if isinstance(parsing, list):
                yield parsing
            elif pruned.get("rec_texts"):
                yield []


def analyze_probe_payload(payload: Any) -> Dict[str, Any]:
    """Classify a probe OCR response."""
    has_rec_texts = False
    has_parsing_res_list = False
    block_labels: Set[str] = set()

    if not isinstance(payload, dict):
        return _capability_result(CAPABILITY_UNKNOWN, has_rec_texts, block_labels)

    result = payload.get("result", payload)
    if isinstance(result, dict):
        for ocr_item in result.get("ocrResults") or []:
            if not isinstance(ocr_item, dict):
                continue
            pruned = ocr_item.get("prunedResult") or {}
            if isinstance(pruned, dict) and pruned.get("rec_texts"):
                has_rec_texts = True

    for parsing_list in _iter_parsing_res_lists(payload):
        if not parsing_list:
            continue
        has_parsing_res_list = True
        for block in parsing_list:
            if not isinstance(block, dict):
                continue
            label = str(block.get("block_label") or "text").strip().lower()
            block_labels.add(label)

    if has_parsing_res_list:
        # parsing_res_list means the layout-parsing API responded (even if probe PDF is text-only).
        level = CAPABILITY_VL_LAYOUT
    elif has_rec_texts and not has_parsing_res_list:
        level = CAPABILITY_TEXT_OCR_ONLY
    else:
        level = CAPABILITY_UNKNOWN

    return _capability_result(level, has_rec_texts, block_labels)


def analyze_openapi_paths(paths: Any) -> Dict[str, Any]:
    """Infer API style from OpenAPI path list."""
    if not isinstance(paths, dict):
        return {"api_style": "unknown", "has_cloud_jobs_api": False, "has_sync_infer_api": False}
    path_keys = {str(k).rstrip("/") for k in paths.keys()}
    has_cloud = "/api/v2/ocr/jobs" in path_keys
    has_sync = ("/ocr" in path_keys or "/layout-parsing" in path_keys) and not has_cloud
    if has_cloud:
        api_style = "cloud_async"
    elif has_sync:
        api_style = "sync_infer"
    else:
        api_style = "unknown"
    return {
        "api_style": api_style,
        "has_cloud_jobs_api": has_cloud,
        "has_sync_infer_api": has_sync,
    }


def _capability_result(
    level: str,
    has_rec_texts: bool,
    block_labels: Set[str],
) -> Dict[str, Any]:
    document_parsing_capable = level == CAPABILITY_VL_LAYOUT or level == CAPABILITY_CLOUD_ASYNC
    warning_code: Optional[str] = None
    if level == CAPABILITY_TEXT_OCR_ONLY:
        warning_code = "paddle_text_ocr_only"
    elif level == CAPABILITY_UNKNOWN:
        warning_code = "paddle_capability_unknown"

    return {
        "capability_level": level,
        "document_parsing_capable": document_parsing_capable,
        "has_rec_texts": has_rec_texts,
        "layout_block_labels": sorted(block_labels),
        "warning_code": warning_code,
    }


def build_paddle_test_user_message(
    *,
    platform: str,
    base: str,
    capability: Dict[str, Any],
    api_style: str,
    reachable: bool,
) -> str:
    """Build user-facing test summary (English; UI may localize via warning_code)."""
    label = "PaddleOCR Cloud" if platform == "paddle" else "PaddleOCR Local"
    if not reachable:
        return f"{label} is not reachable at {base}"

    level = capability.get("capability_level")
    if level == CAPABILITY_VL_LAYOUT:
        labels = capability.get("layout_block_labels") or []
        hint = f", layout labels: {', '.join(labels[:6])}" if labels else ""
        return f"{label} OK at {base}: document layout parsing detected{hint}"

    if level == CAPABILITY_CLOUD_ASYNC:
        return (
            f"{label} OK at {base}: cloud async API POST /api/v2/ocr/jobs detected "
            f"(PaddleOCR-VL-1.6 document parsing expected)"
        )

    if level == CAPABILITY_TEXT_OCR_ONLY:
        return (
            f"{label} reachable at {base}, but only basic text OCR was detected "
            f"(response has rec_texts text lines, no layout blocks like doc_title/table/formula). "
            f"Owlangs needs PaddleOCR-VL-1.6 document parsing. Example: deploy the cloud-style "
            f"API POST /api/v2/ocr/jobs with model PaddleOCR-VL-1.6, or local POST /layout-parsing."
        )

    if api_style == "sync_infer":
        return (
            f"{label} reachable at {base} (local sync API), but PaddleOCR-VL layout "
            f"parsing could not be verified. Deploy PP-StructureV3 or PaddleOCR-VL serving "
            f"with POST /layout-parsing (not infer-only POST /ocr)."
        )

    return f"{label} API is reachable at {base}, but document parsing capability is unverified"
