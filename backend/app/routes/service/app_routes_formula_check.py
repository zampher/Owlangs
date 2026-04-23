# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Service routes for LaTeX formula integrity checks.

These routes are small but self-contained so that we can later plug in
LLM-based repair flows without polluting other translation/download modules.
"""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.services.task import task_manager
from logger import unified_logger as logger
from logger.logger import LogModule
from utils.latex_formula_checker import check_snippets_with_pandoc, check_segments_with_katex
from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm

router = APIRouter()


def _extract_formula_snippets_from_task(task_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract formula snippets from task_state for integrity checks.

    Uses has_latex_content() to detect segments containing LaTeX math,
    rather than relying on metadata flags (is_equation / block_type) that
    are often not set in practice.

    Returns a list of dicts: [{"segment_index": int, "text": str}, ...]
    so that downstream checkers can report the REAL segment index instead
    of an arbitrary list position.
    """
    from utils.latex_repair_payload import has_latex_content

    results: List[Dict[str, Any]] = []
    segs_data = task_state.get("translation_segments") or {}
    segments = segs_data.get("segments") or []
    if not isinstance(segments, list):
        return results

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        idx = seg.get("segment_index")
        if not isinstance(idx, int):
            continue
        text = seg.get("target_text") or seg.get("source_text") or ""
        if not text or not str(text).strip():
            continue
        if has_latex_content(str(text)):
            results.append({"segment_index": idx, "text": str(text)})

    return results


class SegmentLatexRepairPayload(BaseModel):
    """Request body for repairing a single translation segment with LLM."""

    segment_index: int
    text: str
    source_text: Optional[str] = None
    user_prompt: Optional[str] = None


@router.post("/latex-formula-check/{task_id}")
async def latex_formula_check(task_id: str):
    """
    Check LaTeX formula snippets for integrity using Pandoc.

    - Only runs when Pandoc is available; otherwise returns pandoc_available=False.
    - Operates on pre-classified formula segments (not全量 Markdown) to降低复杂度.
    """
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    formula_data = _extract_formula_snippets_from_task(task_state)
    if not formula_data:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] No formula segments found for task {task_id}; skipping check",
            task_id=task_id,
        )

    # Log input snippets (truncate long ones to avoid noisy logs)
    try:
        preview_snippets = [
            (item["segment_index"], (item["text"][:120] + "...") if len(item["text"]) > 120 else item["text"])
            for item in formula_data
        ]
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Running formula check for task {task_id}: snippet_count={count}, previews={previews}",
            task_id=task_id,
            count=len(formula_data),
            previews=preview_snippets[:10],
        )
    except Exception:
        # Best-effort logging; do not break the API on logging failure.
        pass

    result = check_snippets_with_pandoc(formula_data)

    # Also run KaTeX (HTML preview) check on all segments that contain math.
    # This catches errors that Pandoc/XeLaTeX may silently accept but KaTeX rejects.
    segs_data = []
    segs_raw = (task_state.get("translation_segments") or {}).get("segments") or []
    if isinstance(segs_raw, list):
        for seg in segs_raw:
            if not isinstance(seg, dict):
                continue
            idx = seg.get("segment_index")
            if not isinstance(idx, int):
                continue
            text = seg.get("target_text") or seg.get("source_text") or ""
            if text and str(text).strip():
                segs_data.append({"segment_index": idx, "text": str(text)})

    katex_result = check_segments_with_katex(segs_data)

    # Merge Pandoc and KaTeX issues.
    all_issues = list(result.issues)
    all_issues.extend(katex_result.issues)

    # Build a compact JSON payload for frontend.
    payload = {
        "task_id": task_id,
        "pandoc_available": result.pandoc_available,
        "katex_available": katex_result.katex_available,
        "snippet_count": len(result.snippets),
        "snippets": [
            {
                "index": sn.index,
                "text": sn.text,
            }
            for sn in result.snippets
        ],
        "issues": [
            {
                "snippet_index": issue.snippet_index,
                "message": issue.message,
                "severity": issue.severity,
                "raw_stderr": issue.raw_stderr,
            }
            for issue in all_issues
        ],
    }

    try:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Result for task {task_id}: pandoc_available={pandoc}, snippet_count={snips}, issue_count={issues}",
            task_id=task_id,
            pandoc=result.pandoc_available,
            snips=len(result.snippets),
            issues=len(result.issues),
        )
    except Exception:
        pass

    return JSONResponse(content=payload)


@router.post("/latex-formula-repair-segment/{task_id}")
async def latex_formula_repair_segment(task_id: str, body: SegmentLatexRepairPayload):
    """
    Repair a single translation segment (mixed text + formula) using the same LLM
    platform configuration as the translation task.

    Workflow:
    - Frontend passes task_id + segment_index + current translated text.
    - Backend reuses llm_config_for_repair from task_state.
    - LLM suggests a fixed text; backend does NOT mutate task_state.
    - Frontend is responsible for showing diff and, if accepted, calling
      updateTranslationSegment to persist the change.
    """
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    llm_cfg = task_state.get("llm_config_for_repair")

    # Use the provided segment text as both context and original snippet.
    req = LatexRepairRequest(
        error_type="manual_segment_repair",
        tex_context="",
        md_context=body.text,
        original_md_snippet=body.text,
        task_id=task_id,
        segment_index=body.segment_index,
        llm_config=llm_cfg,
        user_prompt=body.user_prompt,
    )
    llm_result = repair_latex_snippet_with_llm(req)

    logger.info(
        LogModule.RESTOR,
        "[LATEX-REPAIR] Segment repair suggestion (task_id={tid}, segment_index={idx}): "
        "len_orig={lo}, len_fixed={lf}",
        tid=task_id,
        idx=body.segment_index,
        lo=len(body.text or ""),
        lf=len(llm_result.fixed_md_snippet or ""),
    )

    return JSONResponse(
        content={
            "task_id": task_id,
            "segment_index": body.segment_index,
            "original_text": body.text,
            "fixed_text": llm_result.fixed_md_snippet,
            "notes": llm_result.notes,
        }
    )

