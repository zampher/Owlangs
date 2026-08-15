# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Locate the Markdown/segment that caused Pandoc+XeLaTeX PDF export to fail.

Classic XeLaTeX errors expose ``l.<line>``. Engine crashes such as
``xdvipdfmx:fatal: File ended prematurely`` often only leave ``Overfull \\hbox``
hints or pathological unbreakable tokens (e.g. thousands of OCR ``9``s).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from utils.latex_repair_payload import (
    LatexErrorContext,
    _build_md_snippet,
    _detect_error_type,
    extract_latex_error_context,
)

# Unbreakable runs at/above this length routinely blow TeX box metrics.
_LONG_TOKEN_MIN_LEN = 200
_OVERFULL_LINES_RE = re.compile(
    r"Overfull\s+\\hbox\b.*?at\s+lines?\s+(\d+)(?:--(\d+))?",
    re.IGNORECASE | re.DOTALL,
)
_LONG_TOKEN_RE = re.compile(r"\S{%d,}" % _LONG_TOKEN_MIN_LEN)


def _longest_unbreakable_token(text: str) -> Tuple[str, int]:
    """Return (token, start_index) for the longest non-whitespace run, or ("", -1)."""
    best = ""
    best_at = -1
    for m in _LONG_TOKEN_RE.finditer(text or ""):
        tok = m.group(0)
        if len(tok) > len(best):
            best = tok
            best_at = m.start()
    return best, best_at


def _tex_snippet_for_lines(
    tex_lines: Sequence[str], start_line: int, end_line: int
) -> Tuple[str, str]:
    """Build numbered tex snippet and pick the longest token in that window."""
    if start_line < 1:
        start_line = 1
    if end_line < start_line:
        end_line = start_line
    ctx_start = max(0, start_line - 2)
    ctx_end = min(len(tex_lines), end_line + 1)
    window = tex_lines[ctx_start:ctx_end]
    snippet = "\n".join(f"{j + 1}: {tex_lines[j]}" for j in range(ctx_start, ctx_end))
    token, _ = _longest_unbreakable_token("\n".join(window))
    if not token and 0 <= start_line - 1 < len(tex_lines):
        token = (tex_lines[start_line - 1] or "").strip()[:240]
    return snippet, token


def extract_overfull_hbox_context(
    stderr: str,
    debug_tex_path: Path,
    debug_md_path: Optional[Path],
) -> Optional[LatexErrorContext]:
    """Parse Overfull \\hbox line ranges from XeLaTeX stderr into a context object."""
    if not stderr or not debug_tex_path.exists():
        return None
    m = _OVERFULL_LINES_RE.search(stderr)
    if not m:
        return None
    start_line = int(m.group(1))
    end_line = int(m.group(2) or m.group(1))
    try:
        tex_lines = debug_tex_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    tex_snippet, error_token = _tex_snippet_for_lines(tex_lines, start_line, end_line)
    md_snippet = _build_md_snippet(debug_md_path, error_token, error_token)
    if not md_snippet and error_token and debug_md_path and debug_md_path.exists():
        probe = error_token[:80] if len(error_token) >= 80 else error_token
        md_snippet = _build_md_snippet(debug_md_path, probe, probe)
    return LatexErrorContext(
        error_type="overfull_hbox_unbreakable",
        line_no=start_line,
        tex_snippet=tex_snippet,
        md_snippet=md_snippet or "",
        error_token=error_token or "",
        debug_md_path=debug_md_path,
        debug_tex_path=debug_tex_path,
    )


def extract_long_token_context(
    debug_tex_path: Optional[Path],
    debug_md_path: Optional[Path],
    *,
    error_type: str = "unbreakable_long_token",
) -> Optional[LatexErrorContext]:
    """Fall back to the longest unbreakable token in debug MD (then TeX)."""
    sources: List[Tuple[str, Optional[Path]]] = []
    if debug_md_path and debug_md_path.exists():
        try:
            sources.append(
                (
                    debug_md_path.read_text(encoding="utf-8", errors="replace"),
                    debug_md_path,
                )
            )
        except Exception:
            pass
    if debug_tex_path and debug_tex_path.exists():
        try:
            sources.append(
                (
                    debug_tex_path.read_text(encoding="utf-8", errors="replace"),
                    debug_tex_path,
                )
            )
        except Exception:
            pass
    best_token = ""
    best_src = ""
    for text, _path in sources:
        tok, _ = _longest_unbreakable_token(text)
        if len(tok) > len(best_token):
            best_token = tok
            best_src = text
    if len(best_token) < _LONG_TOKEN_MIN_LEN:
        return None

    md_snippet = ""
    line_no = 1
    if best_src:
        probe = best_token[:64]
        lines = best_src.splitlines()
        for i, ln in enumerate(lines):
            if probe in ln:
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                md_snippet = "\n".join(f"{j + 1}: {lines[j]}" for j in range(start, end))
                line_no = i + 1
                break
    tex_path = debug_tex_path if debug_tex_path and debug_tex_path.exists() else Path(".")
    return LatexErrorContext(
        error_type=error_type,
        line_no=line_no,
        tex_snippet=md_snippet if debug_tex_path and best_src else "",
        md_snippet=md_snippet,
        error_token=best_token,
        debug_md_path=debug_md_path,
        debug_tex_path=tex_path,
    )


def extract_pdf_export_failure_context(
    stderr: str,
    debug_tex_path: Optional[Path],
    debug_md_path: Optional[Path],
) -> Optional[LatexErrorContext]:
    """Best-effort context for Pandoc PDF failures (classic + overfull + long token).

    For ``xdvipdfmx`` / Overfull crashes, prefer the longest unbreakable MD token for
    segment matching: debug ``.tex`` written without ``--standalone`` often has
    line numbers that do not match the PDF-engine compile log.
    """
    lowered = (stderr or "").lower()
    engine_crash = (
        "file ended prematurely" in lowered
        or "xdvipdfmx" in lowered
        or "dimension too large" in lowered
        or ("overfull" in lowered and "hbox" in lowered)
    )

    classic: Optional[LatexErrorContext] = None
    if debug_tex_path and debug_tex_path.exists():
        classic = extract_latex_error_context(stderr or "", debug_tex_path, debug_md_path)
        if (
            classic is not None
            and not engine_crash
            and (classic.md_snippet or classic.tex_snippet or classic.error_token)
        ):
            return classic

    overfull: Optional[LatexErrorContext] = None
    if debug_tex_path and debug_tex_path.exists():
        overfull = extract_overfull_hbox_context(stderr or "", debug_tex_path, debug_md_path)

    long_type = (
        "xdvipdfmx_unbreakable_token"
        if ("xdvipdfmx" in lowered or "file ended prematurely" in lowered)
        else "unbreakable_long_token"
    )
    long_ctx = extract_long_token_context(
        debug_tex_path,
        debug_md_path,
        error_type=long_type if engine_crash else "unbreakable_long_token",
    )

    if long_ctx is not None and len(long_ctx.error_token or "") >= _LONG_TOKEN_MIN_LEN:
        if overfull is not None:
            return LatexErrorContext(
                error_type=overfull.error_type or long_ctx.error_type,
                line_no=overfull.line_no or long_ctx.line_no,
                tex_snippet=overfull.tex_snippet or long_ctx.tex_snippet,
                md_snippet=long_ctx.md_snippet or overfull.md_snippet,
                error_token=long_ctx.error_token,
                debug_md_path=debug_md_path,
                debug_tex_path=debug_tex_path or long_ctx.debug_tex_path,
            )
        return long_ctx

    if overfull is not None and (overfull.error_token or overfull.tex_snippet):
        return overfull

    if classic is not None and (classic.md_snippet or classic.tex_snippet or classic.error_token):
        return classic

    return long_ctx


def _segment_search_text(seg: Dict[str, Any]) -> str:
    return (
        (seg.get("modified_text") or "")
        or (seg.get("target_text") or "")
        or (seg.get("source_text") or "")
        or ""
    )


def match_segment_index_for_pdf_failure(
    *,
    error_token: str = "",
    md_snippet: str = "",
    tex_snippet: str = "",
    segments: Sequence[Any],
) -> Tuple[Optional[int], str]:
    """Map failure context to a translation ``segment_index``.

    Returns ``(segment_index_or_None, match_basis)``.
    """
    if not isinstance(segments, list) or not segments:
        return None, "no_segments"

    def _strip_line_numbers(snippet: str) -> List[str]:
        out: List[str] = []
        for ln in (snippet or "").splitlines():
            clean = re.sub(r"^\d+:\s*", "", ln).strip()
            if len(clean) >= 4:
                out.append(clean)
        return out

    token = (error_token or "").strip()
    if len(token) >= _LONG_TOKEN_MIN_LEN:
        probe = token[:120]
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = _segment_search_text(seg)
            if text and (token in text or probe in text):
                idx = seg.get("segment_index")
                if isinstance(idx, int):
                    return idx, "long_token"

    for label, snippet in (
        ("md_snippet", md_snippet),
        ("tex_snippet", tex_snippet),
    ):
        lines = _strip_line_numbers(snippet or "")
        lines = sorted(lines, key=len, reverse=True)
        for ln in lines[:12]:
            if len(ln) < 16 and not (token and ln in token):
                continue
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                text = _segment_search_text(seg)
                if text and ln in text:
                    idx = seg.get("segment_index")
                    if isinstance(idx, int):
                        return idx, label

    if token:
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = _segment_search_text(seg)
            if text and token in text:
                idx = seg.get("segment_index")
                if isinstance(idx, int):
                    return idx, f"error_token:{token[:40]}"

    return None, "unmatched"


def build_pdf_export_user_detail(segment_index: Optional[int], error_type: str = "") -> str:
    """User-facing HTTP detail; keeps the ``Suspected bad segment`` marker for the UI."""
    if segment_index is None:
        return (
            "PDF generation failed due to a LaTeX/PDF-engine error. "
            "Could not identify a single bad segment automatically. "
            "请检查含异常 OCR 噪声或超长不可断文本的片段后重试。"
        )
    reason = ""
    if error_type in (
        "overfull_hbox_unbreakable",
        "unbreakable_long_token",
        "xdvipdfmx_unbreakable_token",
    ):
        reason = (
            " It likely contains an unbreakable ultra-long token "
            "(e.g. OCR digit noise) that crashes XeLaTeX/xdvipdfmx."
        )
    return (
        f"PDF generation failed due to a LaTeX/PDF-engine error. "
        f"Suspected bad segment: {segment_index}.{reason} "
        f"请打开并检查片段 {segment_index}，修复或排除后重试导出。"
    )


def detect_pdf_failure_error_type(stderr: str) -> str:
    """Classify PDF engine failure when classic LaTeX typing is unavailable."""
    lowered = (stderr or "").lower()
    if "overfull" in lowered and "hbox" in lowered:
        return "overfull_hbox_unbreakable"
    if "file ended prematurely" in lowered or "xdvipdfmx" in lowered:
        return "xdvipdfmx_unbreakable_token"
    if "dimension too large" in lowered:
        return "dimension_too_large"
    return _detect_error_type(stderr or "")
