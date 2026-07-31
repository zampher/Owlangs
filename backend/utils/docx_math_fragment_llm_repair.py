# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
LLM repair pipeline for segments that fail Pandoc DOCX fragment smoke tests.

Flow: run (or reuse) per-segment Pandoc markdown→docx checks → for each failing segment,
call the LLM with Pandoc stderr → apply fixes to target_text → optionally re-run checks.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from logger import unified_logger as logger
from logger.logger import LogModule

# (task_id, segment_index, original_text, stderr, llm_config) -> (fixed_text, notes)
RepairSnippetFn = Callable[
    [str, int, str, str, Optional[Dict[str, Any]]],
    Tuple[str, str],
]


def _segment_text_for_repair(seg: Dict[str, Any]) -> str:
    return str(
        seg.get("modified_text")
        or seg.get("target_text")
        or seg.get("source_text")
        or ""
    )


def _apply_target_text_fixes_to_task_state(
    task_state: Dict[str, Any],
    fixes: Dict[int, str],
) -> Dict[str, Any]:
    """
    Apply segment target_text updates (same rules as apply_formula_repairs_to_task_state).
    Local copy avoids importing latex_formula_batch_repair (pulls llm_client/agents at import time).
    """
    segs_data = task_state.get("translation_segments") or {}
    segs = segs_data.get("segments") or []
    if not isinstance(segs, list):
        return {"updated": 0, "skipped": 0}
    updated = 0
    skipped = 0
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        idx = seg.get("segment_index")
        if not isinstance(idx, int):
            continue
        if idx not in fixes:
            continue
        fixed = fixes.get(idx) or ""
        if fixed.strip():
            seg["target_text"] = fixed
            seg["modified_text"] = fixed
            seg["modified"] = True
            updated += 1
        else:
            t = str(seg.get("target_text") or "").strip()
            if t:
                skipped += 1
            else:
                fallback_text = str(seg.get("source_text") or "")
                seg["target_text"] = fallback_text
                seg["modified_text"] = fallback_text
                seg["modified"] = True
                updated += 1
    return {"updated": updated, "skipped": skipped}


_TAG_RE = re.compile(r"\\tag\{([^}]*)\}")


def _extract_tag_labels(text: str) -> List[str]:
    return _TAG_RE.findall(text or "")


def _validate_docx_llm_expansion(original: str, fixed: str) -> Tuple[bool, str]:
    """
    Reject LLM output that pastes neighboring equations or stderr context into one segment.

    Common failure: model adds an objective equation (e.g. \\tag{56}) while the segment
    only contained constraints (\\tag{57}), duplicating content above the next segment.
    """
    o = original or ""
    f = fixed or ""
    if not f.strip():
        return False, "empty_fixed"
    orig_tags = set(_extract_tag_labels(o))
    fix_tags = _extract_tag_labels(f)
    fix_tag_set = set(fix_tags)
    orig_blocks = o.count("$$") // 2
    fix_blocks = f.count("$$") // 2
    if orig_tags:
        if not fix_tag_set.issubset(orig_tags):
            introduced = sorted(fix_tag_set - orig_tags)
            return False, f"introduced_tag_labels:{introduced}"
    else:
        if len(fix_tag_set) > 2:
            return False, f"too_many_tag_labels_without_source_tags:{len(fix_tag_set)}"
    if orig_blocks >= 1 and fix_blocks > orig_blocks + 2:
        return False, f"too_many_display_blocks:{orig_blocks}->{fix_blocks}"
    if fix_blocks > orig_blocks + 4:
        return False, f"too_many_display_blocks:{orig_blocks}->{fix_blocks}"
    if len(o) >= 40 and len(f) > max(8000, len(o) * 6):
        return False, "length_ratio_exceeded"
    return True, ""


def _find_segment(task_state: Dict[str, Any], segment_index: int) -> Optional[Dict[str, Any]]:
    segs = (task_state.get("translation_segments") or {}).get("segments") or []
    if not isinstance(segs, list):
        return None
    for seg in segs:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            return seg
    return None


def _build_llm_config_dict(cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not cfg:
        return None
    base_url = cfg.get("base_url")
    model_id = cfg.get("model_id")
    if not base_url or not model_id:
        return None
    return cfg


def _default_repair_snippet(
    task_id: str,
    segment_index: int,
    original: str,
    stderr: str,
    llm_config_dict: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm

    tex_ctx = (stderr or "").strip() or "(no stderr captured)"
    req = LatexRepairRequest(
        error_type="docx_texmath_failure",
        tex_context=tex_ctx[:4000],
        md_context=original,
        original_md_snippet=original,
        task_id=task_id,
        segment_index=segment_index,
        llm_config=llm_config_dict,
        user_prompt=None,
    )
    result = repair_latex_snippet_with_llm(req)
    return (result.fixed_md_snippet or ""), (result.notes or "")


def repair_docx_math_fragments_with_llm(
    task_state: Dict[str, Any],
    task_id: str,
    llm_config_dict: Optional[Dict[str, Any]],
    *,
    refresh_check_first: bool = True,
    recheck_after: bool = True,
    max_segments: Optional[int] = None,
    repair_snippet_fn: Optional[RepairSnippetFn] = None,
) -> Dict[str, Any]:
    """
    Repair segments flagged by docx_math_fragment_check using LLM + Pandoc stderr context.

    Mutates task_state (segment target_text and docx_math_fragment_issues when recheck_after).

    Args:
        task_state: Task dict containing translation_segments.
        task_id: For logging.
        llm_config_dict: Same shape as llm_config_for_repair (base_url, model_id, ...).
        refresh_check_first: If True, run Pandoc fragment checks before repair (or refresh stale cache).
        recheck_after: If True, run Pandoc checks again after applying fixes and update task_state.
        max_segments: Limit number of failing segments to repair (None = all).
        repair_snippet_fn: Optional override for tests; defaults to LLM repair via latex_repair_llm.

    Returns:
        JSON-serializable summary dict.
    """
    cfg_ok = _build_llm_config_dict(llm_config_dict)
    if cfg_ok is None:
        return {
            "success": False,
            "error": "llm_config_missing",
            "message": "llm_config_for_repair is missing base_url or model_id.",
        }

    from utils.docx_math_fragment_check import (
        apply_docx_math_fragment_issues_to_task_state,
        check_all_segments_docx_math,
        docx_math_fragment_summary_to_task_payload,
    )
    # Fresh issues unless caller relies on cache without refresh
    if refresh_check_first:
        summary = apply_docx_math_fragment_issues_to_task_state(task_state)
    else:
        cached = task_state.get("docx_math_fragment_issues")
        issues_list = (cached or {}).get("issues") if isinstance(cached, dict) else None
        if not issues_list:
            summary = apply_docx_math_fragment_issues_to_task_state(task_state)
        else:
            from utils.docx_math_fragment_check import (
                DocxMathFragmentCheckSummary,
                DocxMathFragmentIssue,
            )

            summary = DocxMathFragmentCheckSummary(
                pandoc_available=bool((cached or {}).get("pandoc_available")),
                checked_segments=int((cached or {}).get("checked_segments") or 0),
                issues=[
                    DocxMathFragmentIssue(
                        segment_index=int(x.get("segment_index", -1)),
                        message=str(x.get("message") or ""),
                        stderr_snippet=str(x.get("stderr_snippet") or ""),
                        preview=str(x.get("preview") or ""),
                    )
                    for x in issues_list
                    if isinstance(x, dict)
                ],
                elapsed_seconds=0.0,
            )

    issues_before = len(summary.issues)
    if not summary.pandoc_available:
        return {
            "success": False,
            "error": "pandoc_unavailable",
            "message": "Pandoc not found; cannot run DOCX fragment checks.",
            "issues_before": issues_before,
            "segments_attempted": 0,
            "segments_updated": 0,
            "repair_details": [],
        }

    if issues_before == 0:
        out = {
            "success": True,
            "issues_before": 0,
            "segments_attempted": 0,
            "segments_updated": 0,
            "repair_details": [],
            "issues_after": 0,
            "still_failing_segment_indices": [],
        }
        task_state["docx_math_fragment_repair_last_result"] = out
        return out

    to_process = list(summary.issues)
    if max_segments is not None and max_segments >= 0:
        to_process = to_process[: int(max_segments)]

    fixes: Dict[int, str] = {}
    repair_details: List[Dict[str, Any]] = []

    for issue in to_process:
        idx = issue.segment_index
        seg = _find_segment(task_state, idx)
        if seg is None:
            repair_details.append(
                {
                    "segment_index": idx,
                    "applied": False,
                    "notes": "segment_not_found",
                }
            )
            continue

        original = _segment_text_for_repair(seg)
        if not original.strip():
            repair_details.append(
                {
                    "segment_index": idx,
                    "applied": False,
                    "notes": "empty_segment_text",
                }
            )
            continue

        stderr = (issue.stderr_snippet or "")[:4000]

        _repair = repair_snippet_fn or _default_repair_snippet

        try:
            fixed_raw, notes = _repair(task_id, idx, original, stderr, llm_config_dict)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                LogModule.RESTOR,
                "[DOCX-MATH-LLM-REPAIR] LLM call failed (task={tid}, seg={idx}): {err}",
                tid=task_id,
                idx=idx,
                err=str(e)[:200],
            )
            repair_details.append(
                {
                    "segment_index": idx,
                    "applied": False,
                    "notes": f"llm_exception:{e}",
                }
            )
            continue

        fixed = (fixed_raw or "").strip()
        notes = notes or ""

        # Defense in depth: strip ```tex fences that would hide inline/display math
        # in preview and Pandoc (see unwrap_tex_latex_fences_to_display_math).
        try:
            from utils.math_md_normalize import unwrap_tex_latex_fences_to_display_math

            fixed = unwrap_tex_latex_fences_to_display_math(fixed).strip()
        except Exception:  # noqa: BLE001
            pass

        if not fixed or fixed == (original or "").strip():
            repair_details.append(
                {
                    "segment_index": idx,
                    "applied": False,
                    "notes": notes or "unchanged_or_empty",
                }
            )
            continue

        ok_expand, reject_reason = _validate_docx_llm_expansion(original, fixed)
        if not ok_expand:
            logger.warning(
                LogModule.RESTOR,
                "[DOCX-MATH-LLM-REPAIR] Rejected LLM output (task={tid}, seg={idx}): {reason}",
                tid=task_id,
                idx=idx,
                reason=reject_reason,
            )
            repair_details.append(
                {
                    "segment_index": idx,
                    "applied": False,
                    "notes": f"rejected_llm_expansion:{reject_reason}",
                }
            )
            continue

        fixes[idx] = fixed
        repair_details.append(
            {
                "segment_index": idx,
                "applied": True,
                "notes": notes,
            }
        )
        logger.info(
            LogModule.RESTOR,
            "[DOCX-MATH-LLM-REPAIR] Applied fix (task={tid}, seg={idx})",
            tid=task_id,
            idx=idx,
        )

    apply_summary = _apply_target_text_fixes_to_task_state(task_state, fixes)
    segments_updated = int(apply_summary.get("updated") or 0)

    issues_after = issues_before
    still_failing: List[int] = []

    if recheck_after:
        summary2 = check_all_segments_docx_math(task_state)
        task_state["docx_math_fragment_issues"] = docx_math_fragment_summary_to_task_payload(summary2)
        issues_after = len(summary2.issues)
        still_failing = [x.segment_index for x in summary2.issues]

    out: Dict[str, Any] = {
        "success": True,
        "issues_before": issues_before,
        "segments_attempted": len(to_process),
        "segments_updated": segments_updated,
        "repair_details": repair_details,
        "issues_after": issues_after,
        "still_failing_segment_indices": still_failing,
        "apply_formula_repairs_summary": apply_summary,
    }
    task_state["docx_math_fragment_repair_last_result"] = out
    logger.info(
        LogModule.RESTOR,
        "[DOCX-MATH-LLM-REPAIR] Done task={tid} before={b} after={a} updated={u}",
        tid=task_id,
        b=issues_before,
        a=issues_after,
        u=segments_updated,
    )
    return out
