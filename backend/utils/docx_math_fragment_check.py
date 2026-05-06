# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Per-segment Pandoc DOCX smoke test: locate fragments whose TeX math fails texmath (OMML).

Uses the same Markdown preprocessing as convert_md_to_docx (math normalize, sup/sub,
algorithm wrap) then runs pandoc -t docx on one segment at a time and scans stderr.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule

# Must match format_convert_utils.convert_md_to_docx pandoc_format
PANDOC_DOCX_FROM = "markdown+pipe_tables+hard_line_breaks+raw_html"

_DOCX_MATH_WARNING_PATTERNS = (
    "could not convert tex math",
    "unexpected control sequence \\tag",
    "unexpected '}'",
    "unexpected ']'",
    "missing $ inserted",
)


def _prepare_segment_like_docx_export(text: str) -> str:
    from utils.docx_algorithm_latex_wrap import wrap_bare_latex_for_docx_algorithms
    from utils.docx_md_normalize import normalize_docx_markdown_sup_sub
    from utils.format_convert_utils import (
        _ensure_blank_line_before_pipe_tables,
        _html_tables_in_md_to_pipe_tables,
        _normalize_pipe_table_separators,
    )
    from utils.math_md_normalize import normalize_md_math_for_pandoc_export

    t = normalize_md_math_for_pandoc_export(text)
    t = normalize_docx_markdown_sup_sub(t)
    t = wrap_bare_latex_for_docx_algorithms(t)
    # Match convert_md_to_docx table normalization (no data-URI resolution per fragment).
    t = _html_tables_in_md_to_pipe_tables(t)
    t = _normalize_pipe_table_separators(t)
    t = _ensure_blank_line_before_pipe_tables(t)
    return t


def _get_pandoc_path() -> Optional[Path]:
    try:
        from utils.format_convert_utils import _get_pandoc_path as _gp

        return _gp()
    except Exception:  # noqa: BLE001
        return None


def _stderr_has_docx_math_issue(stderr: str) -> bool:
    low = (stderr or "").lower()
    return any(p in low for p in _DOCX_MATH_WARNING_PATTERNS)


@dataclass
class DocxMathFragmentIssue:
    segment_index: int
    message: str
    stderr_snippet: str
    preview: str


@dataclass
class DocxMathFragmentCheckSummary:
    pandoc_available: bool
    checked_segments: int
    issues: List[DocxMathFragmentIssue]
    elapsed_seconds: float


def check_segment_docx_math_pandoc(
    segment_text: str,
    segment_index: int,
    pandoc_path: Path,
) -> Optional[DocxMathFragmentIssue]:
    """
    Run Pandoc markdown -> docx on a single prepared segment; return issue if stderr matches.
    """
    md = _prepare_segment_like_docx_export(segment_text or "")
    if not md.strip():
        return None

    with tempfile.TemporaryDirectory(prefix="owlangs_docx_frag_") as td:
        tdir = Path(td)
        md_path = tdir / "fragment.md"
        out_path = tdir / "fragment.docx"
        md_path.write_text(md, encoding="utf-8")
        try:
            proc = subprocess.run(  # noqa: S603
                [
                    str(pandoc_path),
                    "-f",
                    PANDOC_DOCX_FROM,
                    str(md_path),
                    "-t",
                    "docx",
                    "-o",
                    str(out_path),
                ],
                capture_output=True,
                timeout=120,
                check=False,
                cwd=str(tdir),
            )
        except subprocess.TimeoutExpired:
            return DocxMathFragmentIssue(
                segment_index=segment_index,
                message="Pandoc DOCX smoke test timed out",
                stderr_snippet="timeout",
                preview=md.replace("\n", " ")[:200],
            )
        except Exception as e:  # noqa: BLE001
            return DocxMathFragmentIssue(
                segment_index=segment_index,
                message=f"Pandoc invocation failed: {e}",
                stderr_snippet=str(e)[:300],
                preview=md.replace("\n", " ")[:200],
            )

        err = (proc.stderr or b"").decode("utf-8", errors="ignore")
        if proc.returncode != 0:
            return DocxMathFragmentIssue(
                segment_index=segment_index,
                message="Pandoc exited non-zero while converting segment to DOCX",
                stderr_snippet=err[:1200],
                preview=md.replace("\n", " ")[:200],
            )
        if _stderr_has_docx_math_issue(err):
            # Extract first TeX-math warning block for logging/UI
            snippet = err[:1200]
            return DocxMathFragmentIssue(
                segment_index=segment_index,
                message="Pandoc/texmath reported a problem converting math in this segment (DOCX path).",
                stderr_snippet=snippet,
                preview=md.replace("\n", " ")[:200],
            )
    return None


def check_all_segments_docx_math(
    task_state: Dict[str, Any],
    *,
    max_workers: int = 4,
) -> DocxMathFragmentCheckSummary:
    """
    Check every translation segment that contains LaTeX-like content.

    Results are suitable for task_state['docx_math_fragment_issues'] and frontend alerts.
    """
    t0 = time.perf_counter()
    pandoc_path = _get_pandoc_path()
    if not pandoc_path:
        return DocxMathFragmentCheckSummary(
            pandoc_available=False,
            checked_segments=0,
            issues=[],
            elapsed_seconds=time.perf_counter() - t0,
        )

    from utils.latex_repair_payload import has_latex_content

    segs = (task_state.get("translation_segments") or {}).get("segments") or []
    if not isinstance(segs, list):
        return DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=0,
            issues=[],
            elapsed_seconds=time.perf_counter() - t0,
        )

    jobs: List[tuple[int, str]] = []
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        idx = seg.get("segment_index")
        if not isinstance(idx, int):
            continue
        text = str(seg.get("target_text") or seg.get("source_text") or "")
        if not text.strip() or not has_latex_content(text):
            continue
        jobs.append((idx, text))

    issues: List[DocxMathFragmentIssue] = []
    if not jobs:
        return DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=0,
            issues=[],
            elapsed_seconds=time.perf_counter() - t0,
        )

    def _one(job: tuple[int, str]) -> Optional[DocxMathFragmentIssue]:
        idx, txt = job
        return check_segment_docx_math_pandoc(txt, idx, pandoc_path)

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futs = {pool.submit(_one, j): j[0] for j in jobs}
        for fut in as_completed(futs):
            try:
                r = fut.result()
                if r is not None:
                    issues.append(r)
            except Exception as e:  # noqa: BLE001
                seg_idx = futs.get(fut, -1)
                issues.append(
                    DocxMathFragmentIssue(
                        segment_index=seg_idx,
                        message=f"DOCX fragment check worker failed: {e}",
                        stderr_snippet=str(e)[:400],
                        preview="",
                    )
                )

    issues.sort(key=lambda x: x.segment_index)
    elapsed = time.perf_counter() - t0
    logger.info(
        LogModule.RESTOR,
        "[DOCX-MATH-FRAG] Checked={n} issues={k} elapsed_s={es:.2f}",
        n=len(jobs),
        k=len(issues),
        es=elapsed,
    )
    return DocxMathFragmentCheckSummary(
        pandoc_available=True,
        checked_segments=len(jobs),
        issues=issues,
        elapsed_seconds=elapsed,
    )


def docx_math_fragment_summary_to_task_payload(summary: DocxMathFragmentCheckSummary) -> Dict[str, Any]:
    """JSON-serializable dict for task_state / API."""
    return {
        "pandoc_available": summary.pandoc_available,
        "checked_segments": summary.checked_segments,
        "issue_count": len(summary.issues),
        "elapsed_seconds": round(summary.elapsed_seconds, 3),
        "issues": [asdict(x) for x in summary.issues],
    }


def apply_docx_math_fragment_issues_to_task_state(
    task_state: Dict[str, Any],
    *,
    task_id: Optional[str] = None,
    task_manager: Any = None,
) -> DocxMathFragmentCheckSummary:
    """
    Run per-segment Pandoc DOCX smoke tests and set task_state['docx_math_fragment_issues'].
    Optional task_manager log when issues are found.
    """
    summary = check_all_segments_docx_math(task_state)
    task_state["docx_math_fragment_issues"] = docx_math_fragment_summary_to_task_payload(summary)
    if task_id and task_manager and summary.issues:
        try:
            task_manager.add_log(
                task_id,
                "warning",
                f"DOCX formula fragment check: {len(summary.issues)} segment(s) with Pandoc/texmath warnings "
                f"(see docx_math_fragment_issues).",
            )
        except Exception:  # noqa: BLE001
            pass
    return summary
