#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Probe a PaddleOCR deployment the same way Owlangs connectivity tests do."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# Allow importing backend modules when run from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from layout.ocr_provider.paddle.capability_probe import (  # noqa: E402
    analyze_openapi_paths,
    analyze_probe_payload,
    build_paddle_test_user_message,
    build_probe_pdf_bytes,
)
from layout.ocr_provider.paddle.sync_infer_adapter import (  # noqa: E402
    normalize_sync_infer_response,
)


def _pretty(obj: Any, limit: int = 4000) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    if len(text) > limit:
        return text[:limit] + f"\n... ({len(text) - limit} chars truncated)"
    return text


async def _fetch_openapi(client: httpx.AsyncClient, base: str) -> Dict[str, Any]:
    for path in ("/openapi.json", "/docs/openapi.json"):
        url = f"{base}{path}"
        try:
            resp = await client.get(url)
            print(f"GET {url} -> HTTP {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    info = analyze_openapi_paths(data.get("paths"))
                    print(f"OpenAPI paths: {info}")
                    return info
        except Exception as exc:
            print(f"OpenAPI fetch failed for {url}: {exc}")
    info = analyze_openapi_paths(None)
    print(f"OpenAPI not found; assuming: {info}")
    return info


async def probe_paddleocr(base_url: str, api_key: str = "", submit_path: str = "/layout-parsing") -> int:
    base = base_url.strip().rstrip("/")
    headers: Dict[str, str] = {}
    if api_key.strip():
        headers["Authorization"] = f"bearer {api_key.strip()}"

    print("=" * 60)
    print(f"PaddleOCR probe: {base}")
    print(f"Submit path: {submit_path}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        health_url = f"{base}/health"
        try:
            health = await client.get(health_url, headers=headers)
            print(f"\n[1] GET {health_url} -> HTTP {health.status_code}")
            if health.status_code == 200:
                print(_pretty(health.json(), limit=500))
        except Exception as exc:
            print(f"\n[1] Health check failed: {exc}")

        openapi_info = await _fetch_openapi(client, base)

        sync_url = f"{base}{submit_path}"
        pdf_bytes = build_probe_pdf_bytes()
        payload = {
            "file": base64.b64encode(pdf_bytes).decode("ascii"),
            "fileType": 0,
            "useDocOrientationClassify": False,
        }
        print(f"\n[2] POST {sync_url} (probe PDF, {len(pdf_bytes)} bytes)")
        try:
            resp = await client.post(
                sync_url,
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
            )
        except httpx.ConnectError as exc:
            print(f"CONNECT ERROR: {exc}")
            print("\nOwlangs would show: paddle_unreachable (service not reachable)")
            return 2

        print(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:2000])
            print("\nOwlangs would show: connection test FAILED")
            return 1

        body = resp.json()
        print("\n[3] Raw response (summary)")
        result = body.get("result") or {}
        ocr_results = result.get("ocrResults") or []
        layout_results = result.get("layoutParsingResults") or []
        print(f"  ocrResults pages: {len(ocr_results)}")
        print(f"  layoutParsingResults pages: {len(layout_results)}")
        if layout_results:
            pruned = (layout_results[0].get("prunedResult") or {})
            if not pruned:
                inner = (layout_results[0].get("layoutParsingResults") or [{}])[0]
                pruned = inner.get("prunedResult") or {}
            parsing = pruned.get("parsing_res_list") or []
            print(f"  page0 parsing_res_list count: {len(parsing)}")
            if parsing:
                labels = [b.get("block_label") for b in parsing[:8]]
                print(f"  page0 block_label sample: {labels}")
        if ocr_results:
            pruned = (ocr_results[0].get("prunedResult") or {})
            rec_texts = pruned.get("rec_texts") or []
            parsing = pruned.get("parsing_res_list") or []
            print(f"  page0 rec_texts count: {len(rec_texts)}")
            print(f"  page0 parsing_res_list count: {len(parsing)}")
            if rec_texts:
                print(f"  page0 rec_texts sample: {rec_texts[:3]!r}")
            if parsing:
                labels = [b.get("block_label") for b in parsing[:8]]
                print(f"  page0 block_label sample: {labels}")

        capability = analyze_probe_payload(body)
        print("\n[4] Owlangs capability analysis")
        print(_pretty(capability))

        message = build_paddle_test_user_message(
            platform="paddle_local",
            base=base,
            capability=capability,
            api_style=str(openapi_info.get("api_style") or "unknown"),
            reachable=True,
        )
        print("\n[5] Owlangs user message")
        print(message)

        if capability.get("document_parsing_capable"):
            print("\nRESULT: OK — document parsing capable (Owlangs test would PASS)")
            exit_code = 0
        else:
            print("\nRESULT: WARNING — reachable but NOT VL document parsing")
            print("  Your server works for basic OCR, but Owlangs needs PaddleOCR-VL-1.6 layout blocks.")
            exit_code = 3

        try:
            normalized = normalize_sync_infer_response(body)
            blocks = (
                normalized.get("layoutParsingResults", [{}])[0]
                .get("layoutParsingResults", [{}])[0]
                .get("prunedResult", {})
                .get("parsing_res_list", [])
            )
            print(f"\n[6] After Owlangs sync adapter: {len(blocks)} blocks")
            if blocks:
                labels = [b.get("block_label") for b in blocks[:10]]
                print(f"  block_labels: {labels}")
        except Exception as exc:
            print(f"\n[6] Adapter preview failed: {exc}")

        return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe PaddleOCR like Owlangs does")
    parser.add_argument(
        "base_url",
        nargs="?",
        default="http://localhost:8080",
        help="PaddleOCR base URL (default: http://localhost:8080)",
    )
    parser.add_argument("--api-key", default="", help="Optional bearer token")
    parser.add_argument(
        "--submit-path",
        default="/layout-parsing",
        help="Submit endpoint path (default: /layout-parsing for local VL layout)",
    )
    args = parser.parse_args()
    code = asyncio.run(probe_paddleocr(args.base_url, args.api_key, args.submit_path))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
