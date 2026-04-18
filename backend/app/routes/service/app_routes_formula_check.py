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
from utils.latex_formula_checker import check_snippets_with_pandoc
from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm

router = APIRouter()


def _extract_formula_snippets_from_task(task_state: Dict[str, Any]) -> List[str]:
    """
    Extract formula snippets from task_state for integrity checks.

    This relies on translation_segments metadata (e.g. block_type/is_equation).
    It is deliberately conservative: only segments clearly marked为公式才参与检查。
    """
    formula_texts: List[str] = []
    segs_data = task_state.get("translation_segments") or {}
    segments = segs_data.get("segments") or []
    if not isinstance(segments, list):
        return formula_texts

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        block_type = seg.get("block_type") or ""
        is_equation = bool(seg.get("is_equation"))
        if not (is_equation or block_type in ("equation", "formula")):
            continue
        text = seg.get("target_text") or seg.get("source_text") or ""
        if not text or not str(text).strip():
            continue
        formula_texts.append(str(text))

    # Fallback: if没有任何显式标记的公式片段，尝试用简单启发式从段落中找包含 LaTeX 标记的片段，
    # 例如含有 '$', '\(', '\[', '\frac', '\sum', '\int', '\mathbf', '\underset' 等。
    if not formula_texts:
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = seg.get("target_text") or seg.get("source_text") or ""
            if not text or not str(text).strip():
                continue
            s = str(text)
            has_latex_hint = any(
                hint in s
                for hint in (
                    "$",
                    r"\(",
                    r"\[",
                    r"\frac",
                    r"\sum",
                    r"\int",
                    r"\mathbf",
                    r"\mathcal",
                    r"\underset",
                    r"\overset",
                )
            )
            if has_latex_hint:
                formula_texts.append(s)

    return formula_texts


class SegmentLatexRepairPayload(BaseModel):
    """Request body for repairing a single translation segment with LLM."""

    segment_index: int
    text: str
    source_text: Optional[str] = None


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

    formula_texts = _extract_formula_snippets_from_task(task_state)
    if not formula_texts:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] No formula segments found for task {task_id}; skipping check",
            task_id=task_id,
        )

    # Log input snippets (truncate long ones to avoid noisy logs)
    try:
        preview_snippets = [
            (idx, (txt[:120] + "...") if len(txt) > 120 else txt)
            for idx, txt in enumerate(formula_texts)
        ]
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Running formula check for task {task_id}: snippet_count={count}, previews={previews}",
            task_id=task_id,
            count=len(formula_texts),
            previews=preview_snippets[:10],
        )
    except Exception:
        # Best-effort logging; do not break the API on logging failure.
        pass

    result = check_snippets_with_pandoc(formula_texts)

    # Build a compact JSON payload for frontend.
    payload = {
        "task_id": task_id,
        "pandoc_available": result.pandoc_available,
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
            for issue in result.issues
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

