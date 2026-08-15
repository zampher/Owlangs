# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Integration check against Paddle layout dump:

``D:\\workspace\\localrepo\\CollabTrans\\test\\paddle_layout``

1) Offline: map ultra-long OCR digit run in layout/full.md → segment index.
2) Live: run convert_md_to_pdf on a small MD that embeds the bad block and
   assert PdfExportLatexError → Suspected bad segment: <index>.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backend.utils as _backend_utils  # noqa: E402

sys.modules["utils"] = _backend_utils

from utils.format_convert_utils import PdfExportLatexError, convert_md_to_pdf  # noqa: E402
from utils.pdf_export_failure_locator import (  # noqa: E402
    build_pdf_export_user_detail,
    extract_pdf_export_failure_context,
    match_segment_index_for_pdf_failure,
)

_FIXTURE_CANDIDATES = [
    Path(r"D:\workspace\localrepo\CollabTrans\test\paddle_layout"),
    PROJECT_ROOT / "test" / "paddle_layout",
    PROJECT_ROOT.parent / "CollabTrans" / "test" / "paddle_layout",
]


def _resolve_fixture_dir() -> Path:
    for cand in _FIXTURE_CANDIDATES:
        if (cand / "full.md").is_file() and (cand / "layout.json").is_file():
            return cand
    raise FileNotFoundError(
        "paddle_layout fixture not found under: "
        + ", ".join(str(p) for p in _FIXTURE_CANDIDATES)
    )


def _segments_from_layout(layout_path: Path) -> list[dict]:
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    segs: list[dict] = []
    for page in layout.get("pages") or []:
        for block in page.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            idx = block.get("block_index")
            if idx is None:
                continue
            text = block.get("text") or ""
            segs.append(
                {
                    "segment_index": int(idx),
                    "source_text": text,
                    "target_text": text,
                    "page_index": block.get("page_index"),
                    "type": block.get("type"),
                }
            )
    return segs


def _find_expected_bad_segment(segments: list[dict]) -> tuple[int, str]:
    for seg in segments:
        text = seg.get("source_text") or ""
        if "9" * 50 in text:
            return int(seg["segment_index"]), text
    raise AssertionError("fixture layout has no ultra-long digit run")


def main() -> int:
    fixture = _resolve_fixture_dir()
    md_path = fixture / "full.md"
    layout_path = fixture / "layout.json"
    print(f"[INFO] fixture={fixture}")

    segments = _segments_from_layout(layout_path)
    expected, bad_text = _find_expected_bad_segment(segments)
    print(f"[INFO] segments={len(segments)} expected_bad_segment={expected}")
    print(f"[INFO] bad_text_len={len(bad_text)} nine_run={max(len(m) for m in re.findall(r'9+', bad_text))}")

    # --- Phase 1: offline locator on full.md ---
    stderr = (
        "xdvipdfmx:fatal: File ended prematurely\n"
        r"Overfull \hbox (22896.2305pt too wide) in paragraph at lines 171--174"
        "\nError producing PDF.\n"
    )
    ctx = extract_pdf_export_failure_context(stderr, None, md_path)
    assert ctx is not None, "expected failure context from full.md"
    idx, basis = match_segment_index_for_pdf_failure(
        error_token=ctx.error_token or "",
        md_snippet=ctx.md_snippet or "",
        tex_snippet=ctx.tex_snippet or "",
        segments=segments,
    )
    detail = build_pdf_export_user_detail(idx, ctx.error_type or "")
    print(f"[INFO] offline type={ctx.error_type} token_len={len(ctx.error_token or '')}")
    print(f"[INFO] offline matched_segment={idx} basis={basis}")
    print(f"[INFO] offline detail={detail}")
    if idx != expected or "Suspected bad segment" not in detail:
        print(f"[FAIL] offline locator expected {expected}, got {idx}")
        return 1
    print(f"[PASS] offline locator → segment {idx}")

    # --- Phase 2: live Pandoc on minimal MD containing the bad block ---
    mini_md = (
        "# Export failure probe\n\n"
        "Normal paragraph before the bad TOC block.\n\n"
        f"{bad_text}\n\n"
        "Normal paragraph after the bad TOC block.\n"
    )
    with tempfile.TemporaryDirectory(prefix="owlangs_paddle_pdf_mini_") as tmp:
        out_pdf = Path(tmp) / "out.pdf"
        out_dir = Path(tmp) / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        print("[INFO] running convert_md_to_pdf on mini MD (bad block only)...")
        try:
            ok = convert_md_to_pdf(mini_md, str(out_pdf), output_dir=out_dir, to_lang="zh")
        except PdfExportLatexError as e:
            live_idx, live_basis = match_segment_index_for_pdf_failure(
                error_token=e.error_token or "",
                md_snippet=e.md_snippet or "",
                tex_snippet=e.tex_snippet or "",
                segments=segments,
            )
            live_detail = build_pdf_export_user_detail(live_idx, e.error_type or "")
            print(
                f"[INFO] live PdfExportLatexError type={e.error_type} "
                f"token_len={len(e.error_token or '')} line={e.line_no}"
            )
            print(f"[INFO] live matched_segment={live_idx} basis={live_basis}")
            print(f"[INFO] live detail={live_detail}")
            if live_idx == expected and "Suspected bad segment" in live_detail:
                print(f"[PASS] live Pandoc failure mapped to segment {live_idx}")
                return 0
            print(f"[FAIL] live mapping expected {expected}, got {live_idx}")
            return 1

        if ok and out_pdf.exists() and out_pdf.stat().st_size > 0:
            print("[FAIL] mini MD unexpectedly produced a PDF; toxic token did not crash engine")
            return 1
        print("[FAIL] convert_md_to_pdf returned False without PdfExportLatexError")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
