#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Diagnose PaddleOCR local /layout-parsing failures (500, timeouts, payload limits)."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from layout.ocr_provider.paddle.capability_probe import (  # noqa: E402
    analyze_probe_payload,
    build_probe_pdf_bytes,
)
from layout.ocr_provider.paddle.sync_infer_adapter import (  # noqa: E402
    normalize_sync_infer_response,
)


def _pretty(obj: Any, limit: int = 6000) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    if len(text) > limit:
        return text[:limit] + f"\n... ({len(text) - limit} chars truncated)"
    return text


def _build_multipage_pdf(page_count: int, lines_per_page: int = 40) -> bytes:
    import fitz

    doc = fitz.open()
    for page_idx in range(page_count):
        page = doc.new_page(width=595, height=842)  # A4
        y = 72
        page.insert_text((72, y), f"Owlangs stress page {page_idx + 1}", fontsize=14)
        y += 28
        for line in range(lines_per_page):
            page.insert_text(
                (72, y),
                f"Line {line + 1}: sample paragraph text for layout parsing stress test.",
                fontsize=10,
            )
            y += 16
            if y > 780:
                break
    data = doc.tobytes()
    doc.close()
    return data


def _file_type_for_path(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"):
        return 1
    return 0


async def _post_layout_parsing(
    client: httpx.AsyncClient,
    url: str,
    file_bytes: bytes,
    *,
    label: str,
    file_type: int = 0,
    use_doc_orientation_classify: bool = False,
    headers: Optional[Dict[str, str]] = None,
    read_timeout: float = 600.0,
) -> Tuple[int, str, Optional[Dict[str, Any]], float]:
    payload = {
        "file": base64.b64encode(file_bytes).decode("ascii"),
        "fileType": file_type,
        "useDocOrientationClassify": use_doc_orientation_classify,
    }
    b64_len = len(payload["file"])
    print(f"\n--- {label} ---")
    print(
        f"  file_bytes={len(file_bytes):,}  base64_chars={b64_len:,}  "
        f"fileType={file_type}  useDocOrientationClassify={use_doc_orientation_classify}"
    )
    started = time.monotonic()
    try:
        resp = await client.post(
            url,
            json=payload,
            headers={**(headers or {}), "Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=30.0, read=read_timeout, write=300.0, pool=10.0),
        )
    except httpx.ReadTimeout:
        elapsed = time.monotonic() - started
        print(f"  RESULT: READ TIMEOUT after {elapsed:.1f}s")
        return 0, "read_timeout", None, elapsed
    except httpx.ConnectError as exc:
        elapsed = time.monotonic() - started
        print(f"  RESULT: CONNECT ERROR: {exc}")
        return 0, str(exc), None, elapsed
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"  RESULT: REQUEST ERROR: {exc}")
        traceback.print_exc()
        return 0, str(exc), None, elapsed

    elapsed = time.monotonic() - started
    body_text = resp.text
    print(f"  HTTP {resp.status_code}  elapsed={elapsed:.1f}s")
    parsed: Optional[Dict[str, Any]] = None
    if resp.headers.get("content-type", "").startswith("application/json"):
        try:
            parsed = resp.json()
        except Exception:
            parsed = None

    if resp.status_code != 200:
        print("  Response body (first 4000 chars):")
        print(body_text[:4000])
        if parsed is not None:
            print("  Parsed JSON keys:", list(parsed.keys()))
            for key in ("errorCode", "errorMsg", "logId", "detail", "message"):
                if key in parsed:
                    print(f"  {key}: {parsed.get(key)!r}")
        return resp.status_code, body_text[:2000], parsed, elapsed

    if parsed is None:
        print("  Non-JSON 200 response:")
        print(body_text[:2000])
        return resp.status_code, body_text[:2000], None, elapsed

    error_code = parsed.get("errorCode")
    if error_code not in (None, 0):
        print(f"  errorCode={error_code!r} errorMsg={parsed.get('errorMsg')!r}")
        return resp.status_code, parsed.get("errorMsg") or body_text[:2000], parsed, elapsed

    result = parsed.get("result") or {}
    layout_pages = len(result.get("layoutParsingResults") or [])
    ocr_pages = len(result.get("ocrResults") or [])
    print(f"  layoutParsingResults pages={layout_pages}  ocrResults pages={ocr_pages}")
    capability = analyze_probe_payload(parsed)
    print(f"  capability={capability.get('capability_level')}  parsing_capable={capability.get('document_parsing_capable')}")
    try:
        normalized = normalize_sync_infer_response(parsed)
        blocks = (
            normalized.get("layoutParsingResults", [{}])[0]
            .get("layoutParsingResults", [{}])[0]
            .get("prunedResult", {})
            .get("parsing_res_list", [])
        )
        print(f"  adapter blocks page0={len(blocks)}")
    except Exception as exc:
        print(f"  adapter preview failed: {exc}")
    return resp.status_code, "ok", parsed, elapsed


async def run_diag(
    base_url: str,
    *,
    submit_path: str = "/layout-parsing",
    api_key: str = "",
    pdf_path: Optional[Path] = None,
    stress_pages: List[int],
    read_timeout: float,
) -> int:
    base = base_url.rstrip("/")
    url = f"{base}{submit_path}"
    headers: Dict[str, str] = {}
    if api_key.strip():
        headers["Authorization"] = f"bearer {api_key.strip()}"

    print("=" * 72)
    print(f"PaddleOCR layout-parsing diagnostic")
    print(f"  base_url={base}")
    print(f"  submit={submit_path}")
    print("=" * 72)

    failures: List[str] = []
    async with httpx.AsyncClient() as client:
        health_url = f"{base}/health"
        try:
            health = await client.get(health_url, headers=headers, timeout=15.0)
            print(f"\n[health] GET {health_url} -> HTTP {health.status_code}")
            if health.status_code == 200:
                print(_pretty(health.json(), limit=800))
        except Exception as exc:
            print(f"\n[health] failed: {exc}")
            failures.append(f"health: {exc}")

        # 1) Same tiny probe Owlangs connectivity test uses
        probe = build_probe_pdf_bytes()
        code, msg, _, _ = await _post_layout_parsing(
            client,
            url,
            probe,
            label="probe PDF (Owlangs connectivity test size)",
            headers=headers,
            read_timeout=read_timeout,
        )
        if code != 200 or msg != "ok":
            failures.append(f"probe PDF: HTTP {code} {msg[:120]}")

        # 2) Stress multi-page synthetic PDFs
        for pages in stress_pages:
            pdf = _build_multipage_pdf(pages)
            code, msg, _, elapsed = await _post_layout_parsing(
                client,
                url,
                pdf,
                label=f"synthetic A4 PDF ({pages} page(s))",
                headers=headers,
                read_timeout=read_timeout,
            )
            if code != 200 or msg != "ok":
                failures.append(f"{pages}-page synthetic: HTTP {code} after {elapsed:.1f}s")

        # 3) User-supplied PDF (the one that fails in Owlangs)
        if pdf_path is not None:
            if not pdf_path.is_file():
                print(f"\n[file] missing: {pdf_path}")
                failures.append(f"file missing: {pdf_path}")
            else:
                data = pdf_path.read_bytes()
                code, msg, _, elapsed = await _post_layout_parsing(
                    client,
                    url,
                    data,
                    label=f"user PDF: {pdf_path.name}",
                    file_type=_file_type_for_path(pdf_path),
                    headers=headers,
                    read_timeout=read_timeout,
                )
                if code != 200 or msg != "ok":
                    failures.append(
                        f"user PDF {pdf_path.name}: HTTP {code} after {elapsed:.1f}s — {msg[:160]}"
                    )

    print("\n" + "=" * 72)
    if failures:
        print("FAILURES:")
        for item in failures:
            print(f"  - {item}")
        print("\nLikely causes when probe OK but real PDF fails:")
        print("  - Server GPU OOM / model crash on large or complex pages")
        print("  - PDF features unsupported by PaddleOCR-VL (encrypted, corrupted, huge page count)")
        print("  - Request body too large for reverse proxy (nginx/client_max_body_size)")
        print("  - Server-side timeout shorter than Owlangs client read timeout (300s)")
        print("\nCheck server container logs around logId / timestamp of the failed request.")
        return 1

    print("All diagnostic requests succeeded.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose PaddleOCR /layout-parsing 500 errors")
    parser.add_argument(
        "base_url",
        nargs="?",
        default="http://192.168.3.65:8080",
        help="PaddleOCR base URL",
    )
    parser.add_argument("--submit-path", default="/layout-parsing")
    parser.add_argument("--api-key", default="")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to the PDF that fails in Owlangs (optional)",
    )
    parser.add_argument(
        "--pages",
        default="1,5,10,20",
        help="Comma-separated page counts for synthetic stress PDFs (default: 1,5,10,20)",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=600.0,
        help="HTTP read timeout seconds per request (default: 600)",
    )
    args = parser.parse_args()
    stress_pages = []
    for part in args.pages.split(","):
        part = part.strip()
        if part.isdigit():
            stress_pages.append(int(part))
    if not stress_pages:
        stress_pages = [1, 5, 10, 20]

    code = asyncio.run(
        run_diag(
            args.base_url,
            submit_path=args.submit_path,
            api_key=args.api_key,
            pdf_path=args.pdf,
            stress_pages=stress_pages,
            read_timeout=args.read_timeout,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
