from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

from logger import unified_logger as logger
from logger.logger import LogModule
from utils.llm_client import LLMConfig, LLMMessage, llm_chat


@dataclass
class FormulaRepairItem:
    segment_index: int
    source_text: str
    target_text: str


@dataclass
class FormulaBatchRepairConfig:
    batch_size: int = 12
    temperature: float = 0.1


def _get_formula_repair_debug_dir(task_id: str) -> Path:
    # Use OS temp dir so it works in local + server environments.
    # Keep the directory name stable for easier troubleshooting.
    root = Path(tempfile.gettempdir()) / "owlangs_debug" / "formula_repair" / str(task_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or "", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            LogModule.RESTOR,
            "[FORMULA-REPAIR] Failed to write debug file (path={p}): {err}",
            p=str(path),
            err=str(e)[:200],
        )


def _safe_write_json(path: Path, obj: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            LogModule.RESTOR,
            "[FORMULA-REPAIR] Failed to write debug json (path={p}): {err}",
            p=str(path),
            err=str(e)[:200],
        )


def _build_llm_config_from_dict(cfg: Optional[Dict[str, Any]]) -> Optional[LLMConfig]:
    if not cfg:
        return None
    base_url = cfg.get("base_url")
    model_id = cfg.get("model_id")
    if not base_url or not model_id:
        return None
    return LLMConfig(
        base_url=base_url,
        model_id=model_id,
        api_key=cfg.get("api_key"),
        temperature=float(cfg.get("temperature", 0.1)),
        concurrent=int(cfg.get("concurrent", 1)),
        connect_timeout=int(cfg.get("connect_timeout", 5)),
        timeout=int(cfg.get("timeout", 120)),
        thinking=str(cfg.get("thinking", "default")),
        retry=int(cfg.get("retry", 3)),
        max_tokens=cfg.get("max_tokens"),
        api_type=str(cfg.get("api_type", "openai")),
        platform_key=cfg.get("platform_key"),
    )


# Layout / metadata block types that represent equation segments (not plain text with $ noise).
_FORMULA_BLOCK_TYPES = frozenset({"equation", "formula", "interline_equation"})


def _try_build_layout_block_type_index(layout_doc: Any) -> Optional[Dict[int, str]]:
    """
    Map global layout block index -> normalized block.type for formula gating.
    Returns None when layout_doc is missing or not a LayoutDocument, or when no indexed blocks exist.
    """
    if layout_doc is None:
        return None
    try:
        from layout.base import LayoutDocument as _LayoutDocument
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(layout_doc, _LayoutDocument):
        return None
    out: Dict[int, str] = {}
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        out[int(block.index)] = (getattr(block, "type", None) or "").strip().lower()
    return out if out else None


def _segment_declared_block_types(seg: Dict[str, Any]) -> List[str]:
    types: List[str] = []
    top = (seg.get("block_type") or "").strip().lower()
    if top:
        types.append(top)
    info = seg.get("segment_info")
    if isinstance(info, dict):
        inner = (info.get("block_type") or "").strip().lower()
        if inner:
            types.append(inner)
    return types


def _layout_indices_indicate_formula(
    seg: Dict[str, Any],
    block_type_by_idx: Optional[Dict[int, str]],
) -> bool:
    if not block_type_by_idx:
        return False
    raw = seg.get("layout_block_indices")
    if not raw or not isinstance(raw, (list, tuple)):
        return False
    for x in raw:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        btype = block_type_by_idx.get(i)
        if btype and btype in _FORMULA_BLOCK_TYPES:
            return True
    return False


def _is_formula_segment_for_batch_repair(
    seg: Dict[str, Any],
    block_type_by_idx: Optional[Dict[int, str]],
) -> bool:
    if seg.get("is_equation"):
        return True
    for bt in _segment_declared_block_types(seg):
        if bt in _FORMULA_BLOCK_TYPES:
            return True
    if _layout_indices_indicate_formula(seg, block_type_by_idx):
        return True
    return False


def collect_formula_items(task_state: Dict[str, Any]) -> List[FormulaRepairItem]:
    segs = (task_state.get("translation_segments") or {}).get("segments") or []
    if not isinstance(segs, list):
        return []
    layout_doc = task_state.get("layout_document")
    block_type_by_idx = _try_build_layout_block_type_index(layout_doc)
    # Diagnostics: segments that look like LaTeX under the old heuristic but are not typed as formula blocks.
    from utils.latex_repair_payload import has_latex_content

    skipped_latex_like_indices: List[int] = []
    items: List[FormulaRepairItem] = []
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        if seg.get("is_image"):
            continue
        if not _is_formula_segment_for_batch_repair(seg, block_type_by_idx):
            body = (seg.get("target_text") or seg.get("source_text") or "").strip()
            if body and has_latex_content(body):
                si = seg.get("segment_index")
                if isinstance(si, int) and len(skipped_latex_like_indices) < 12:
                    skipped_latex_like_indices.append(si)
            continue
        idx = seg.get("segment_index")
        if not isinstance(idx, int):
            continue
        source_text = str(seg.get("source_text") or "")
        target_text = str(seg.get("target_text") or "")
        items.append(FormulaRepairItem(segment_index=idx, source_text=source_text, target_text=target_text))
    logger.debug(
        LogModule.RESTOR,
        "[FORMULA-REPAIR] collect_formula_items: selected={n}, layout_index_map={has_map}, "
        "skipped_latex_like_non_formula_sample={sample}",
        n=len(items),
        has_map=bool(block_type_by_idx),
        sample=skipped_latex_like_indices[:8],
    )
    if layout_doc is None:
        logger.debug(
            LogModule.RESTOR,
            "[FORMULA-REPAIR] collect_formula_items: task_state has no layout_document; "
            "formula segments rely on is_equation / block_type / segment_info only.",
        )
    return items


def _chunk_items(items: List[FormulaRepairItem], batch_size: int) -> Iterable[List[FormulaRepairItem]]:
    if batch_size <= 0:
        yield items
        return
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def _build_prompt(items: List[FormulaRepairItem]) -> str:
    # Follow the same SEG-tag structure used by translation to maximize success rate.
    # Input and output MUST preserve marker lines exactly. (Plain string: avoid f-string
    # interpreting LaTeX braces like \\theta_{d} in the instructions.)
    header = """# Task
Normalize and repair LaTeX math formatting inside each segment for PDF export (Pandoc + XeLaTeX).

# Segment Format (CRITICAL)
Input and output are plain text with explicit segment markers:
- Start marker: [SEG n]
- End marker:   [/SEG n]

Rules:
- Keep marker lines EXACTLY as-is. Do NOT translate or modify markers.
- Do NOT add, remove, or reorder segments. Output must contain the same [SEG n] blocks in the same order.
- Operate ONLY within the content of each segment.

# Repair Requirements
- Keep meaning and non-math words exactly; do not drop tokens.
- Fix LaTeX math so it compiles in Pandoc + XeLaTeX.
- Preserve existing delimiter style when already correct. e.g. keep $$...$$ as $$...$$; keep $...$ as $...$; change \\[...\\] to $$...$$.
- Do NOT introduce new LaTeX environments that are not already present in the segment.
- For pseudo-code, keep line numbers and structure; keep control-flow words like if/then/else outside math.
- Output MUST be plain text, NOT Markdown: do NOT use **bold**, lists, headings, tables, or blockquotes.
- Do NOT add layout/spacing commands such as \\hfill, \\quad, \\qquad, \\vspace, \\hspace, or alignment hacks.
- If a segment mixes text/pseudocode and math, wrap ONLY true math parts with $...$ (or keep existing correct delimiters). Keep labels like "Require:", "Ensure:", "while", "do", "then", "else", "end" as plain text.
- Line-numbered pseudo-code handling (CRITICAL):
  - If the input contains line numbers/step markers (formats may vary, e.g. "1:", "1.", "(1)", "Step 1", "①"),
    use them as sentence/line boundaries: split the text so each step becomes its own line.
  - Keep the original line numbers/step markers and their order. Do NOT renumber, reorder, drop, or invent new ones.
  - Normalize placement: move each line number/step marker to the start of its line as much as possible (column 0),
    while keeping the rest of that step's content on the same line (unless a newline already exists).
  - If multiple steps are on one physical line, split them into separate lines at their markers.
- For code/pseudo-code, apply consistent indentation based on control-flow structure (e.g. while/for/if/else/end), without changing the logic or moving tokens into math mode.

# XeLaTeX PDF failures: Missing $ and mangled superscripts
Whole-document PDF often fails with "Missing $ inserted" when superscripts are corrupted after translation
(e.g. nested braces and square brackets inside one ^{...} block, or patterns like superscript{\\{...\\}[}...).
- Rewrite as **clean, balanced** inline math, e.g. $f^\\prime(t,\\theta_d)$ or $f'(t,\\theta_d)$; keep every `^` and `_` **inside** $...$ or $$...$$.
- Do not use raw `[` / `]` as grouping inside a superscript; separate arguments with commas, or use \\left[ ... \\right] for true brackets.
- Use \\prime or ASCII apostrophe for derivatives; avoid garbled `\\{` / `\\}` sequences in superscripts.

# XeLaTeX PDF failures: \\eqno / \\tag inside \\[...\\]
Whole-document compile may fail with `You can't use \\eqno' in math mode` at a closing `\\]` when **\\tag{n}** appears inside **\\[...\\]** (common Pandoc output).
- **Never** leave `\\tag{...}` inside `\\[...\\]`. Rewrite to one of:
  - `\\begin{equation} ... \\end{equation}` (keep `\\tag{n}` if equation numbers are required), or
  - display math **without** `\\tag`, and put `(n)` as plain text after the formula in the same segment.
- Strip Markdown code fences (```) if they leaked into the segment; they are not valid LaTeX.
- Replace corrupted placeholders like `\\textbackslash theta` with valid math, e.g. `$\\theta_0^{*}$`.

# Output
Return ONLY the repaired segments with the SAME [SEG n] / [/SEG n] markers.
"""
    lines: list[str] = [header]
    for it in items:
        # Use target_text as primary input; if missing, use source_text.
        body = it.target_text if (it.target_text or "").strip() else it.source_text
        lines.append(f"[SEG {it.segment_index}]")
        lines.append(body or "")
        lines.append(f"[/SEG {it.segment_index}]")
    return "\n".join(lines).strip() + "\n"


def _parse_seg_tag_output(text: str) -> Dict[int, str]:
    """
    Parse [SEG n] ... [/SEG n] blocks into {n: content}.
    This mirrors the translation SEG-tag parser.
    """
    out: Dict[int, str] = {}
    seg_start_re = re.compile(r"^\[SEG\s+(\d+)\]\s*$")
    seg_end_re = re.compile(r"^\[/SEG\s+(\d+)\]\s*$")
    current_idx: int | None = None
    buffer_lines: list[str] = []
    for line in (text or "").splitlines():
        m_start = seg_start_re.match(line)
        if m_start:
            # Flush previous block defensively
            if current_idx is not None:
                out[current_idx] = "\n".join(buffer_lines)
                buffer_lines = []
            current_idx = int(m_start.group(1))
            continue
        m_end = seg_end_re.match(line)
        if m_end and current_idx is not None:
            end_idx = int(m_end.group(1))
            if end_idx == current_idx:
                out[current_idx] = "\n".join(buffer_lines)
            current_idx = None
            buffer_lines = []
            continue
        if current_idx is not None:
            buffer_lines.append(line)
    if current_idx is not None:
        out[current_idx] = "\n".join(buffer_lines)
    return out


def batch_repair_formulas_with_llm(
    *,
    task_id: str,
    items: List[FormulaRepairItem],
    llm_config_dict: Optional[Dict[str, Any]],
    cfg: Optional[FormulaBatchRepairConfig] = None,
    llm_chat_fn=llm_chat,
    on_progress=None,
) -> Tuple[Dict[int, str], str]:
    """
    Returns:
      (segment_index -> fixed_text (may be empty)), notes
    """
    if not items:
        return {}, "no_items"
    cfg = cfg or FormulaBatchRepairConfig()
    llm_cfg = _build_llm_config_from_dict(llm_config_dict)
    if llm_cfg is None:
        return {}, "llm_config_missing"

    merged: Dict[int, str] = {}
    batches = list(_chunk_items(items, cfg.batch_size))
    max_workers = max(1, int(getattr(llm_cfg, "concurrent", 1) or 1))
    debug_dir = _get_formula_repair_debug_dir(task_id)
    logger.info(
        LogModule.RESTOR,
        "[FORMULA-REPAIR] Auto batch repair start (task_id={tid}, items={n}, batches={b}, batch_size={bs}, concurrent={c})",
        tid=task_id,
        n=len(items),
        b=len(batches),
        bs=cfg.batch_size,
        c=max_workers,
    )
    _safe_write_json(
        debug_dir / "repair_summary.json",
        {
            "task_id": task_id,
            "items": len(items),
            "batches": len(batches),
            "batch_size": cfg.batch_size,
            "concurrent": max_workers,
            "timestamp_ms": int(time.time() * 1000),
        },
    )
    try:
        if on_progress is not None:
            on_progress(
                {
                    "event": "start",
                    "task_id": task_id,
                    "items": len(items),
                    "batches": len(batches),
                    "batch_size": cfg.batch_size,
                    "concurrent": max_workers,
                }
            )
    except Exception:
        pass
    def _process_one_batch(bi: int, batch: List[FormulaRepairItem]) -> Dict[int, str]:
        batch_indices = [it.segment_index for it in batch]
        t0 = time.monotonic()
        try:
            if on_progress is not None:
                on_progress(
                    {
                        "event": "batch_start",
                        "task_id": task_id,
                        "batch_index": bi + 1,
                        "batch_total": len(batches),
                        "segment_indices": batch_indices,
                    }
                )
        except Exception:
            pass
        logger.info(
            LogModule.RESTOR,
            "[FORMULA-REPAIR] Batch start (task_id={tid}, batch={bi}/{bn}, segs={segs})",
            tid=task_id,
            bi=bi + 1,
            bn=len(batches),
            segs=batch_indices[:20] + (["..."] if len(batch_indices) > 20 else []),
        )
        prompt = _build_prompt(batch)
        _safe_write_text(debug_dir / f"batch_{bi + 1:03d}_prompt.txt", prompt)
        raw = llm_chat_fn([LLMMessage(role="user", content=prompt)], llm_cfg)
        _safe_write_text(debug_dir / f"batch_{bi + 1:03d}_raw.txt", raw or "")
        dt_ms = int((time.monotonic() - t0) * 1000)

        parsed_map = _parse_seg_tag_output(raw)
        _safe_write_json(
            debug_dir / f"batch_{bi + 1:03d}_parsed_map.json",
            {str(k): v for k, v in (parsed_map or {}).items()},
        )
        if not parsed_map:
            logger.warning(
                LogModule.RESTOR,
                "[FORMULA-REPAIR] Batch returned no SEG-tag blocks (task_id={tid}, batch={bi}/{bn}), preview={p}",
                tid=task_id,
                bi=bi + 1,
                bn=len(batches),
                p=(raw or "")[:200],
            )
            return {}

        out: Dict[int, str] = {}
        changed = 0
        unchanged = 0
        missing = 0
        batch_compare: List[Dict[str, Any]] = []
        for it in batch:
            in_body = it.target_text if (it.target_text or "").strip() else it.source_text
            out_body = parsed_map.get(it.segment_index)
            if out_body is None:
                missing += 1
                batch_compare.append(
                    {
                        "segment_index": it.segment_index,
                        "status": "missing",
                        "input_text": in_body,
                        "output_text": None,
                    }
                )
                continue
            if (out_body or "").strip() == (in_body or "").strip():
                out[it.segment_index] = ""  # unchanged
                unchanged += 1
                batch_compare.append(
                    {
                        "segment_index": it.segment_index,
                        "status": "unchanged",
                        "input_text": in_body,
                        "output_text": out_body,
                    }
                )
            else:
                out[it.segment_index] = out_body
                changed += 1
                batch_compare.append(
                    {
                        "segment_index": it.segment_index,
                        "status": "changed",
                        "input_text": in_body,
                        "output_text": out_body,
                    }
                )

        _safe_write_json(debug_dir / f"batch_{bi + 1:03d}_compare.json", batch_compare)

        logger.info(
            LogModule.RESTOR,
            "[FORMULA-REPAIR] Batch done (task_id={tid}, batch={bi}/{bn}, latency_ms={ms}, parsed={p}, changed={c}, unchanged={u}, missing={m})",
            tid=task_id,
            bi=bi + 1,
            bn=len(batches),
            ms=dt_ms,
            p=len(parsed_map),
            c=changed,
            u=unchanged,
            m=missing,
        )
        try:
            if on_progress is not None:
                on_progress(
                    {
                        "event": "batch_done",
                        "task_id": task_id,
                        "batch_index": bi + 1,
                        "batch_total": len(batches),
                        "latency_ms": dt_ms,
                        "parsed": len(parsed_map),
                        "changed": changed,
                        "unchanged": unchanged,
                        "missing": missing,
                    }
                )
        except Exception:
            pass
        return out

    # Run sequentially by default; enable parallelism when concurrent > 1.
    if max_workers <= 1 or len(batches) <= 1:
        for bi, batch in enumerate(batches):
            try:
                merged.update(_process_one_batch(bi, batch))
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    LogModule.RESTOR,
                    "[FORMULA-REPAIR] Batch LLM call failed (task_id={tid}, batch={bi}/{bn}): {err}",
                    tid=task_id,
                    bi=bi + 1,
                    bn=len(batches),
                    err=str(e)[:200],
                )
        try:
            if on_progress is not None:
                on_progress(
                    {
                        "event": "done",
                        "task_id": task_id,
                        "notes": "ok",
                        "fixed": len([k for k, v in merged.items() if (v or "").strip()]),
                        "unchanged": len([k for k, v in merged.items() if not (v or "").strip()]),
                    }
                )
        except Exception:
            pass
        return merged, "ok"

    # Parallel batches: match translation settings 'concurrent' (best-effort).
    with ThreadPoolExecutor(max_workers=min(max_workers, len(batches))) as ex:
        futs = {ex.submit(_process_one_batch, bi, batch): bi for bi, batch in enumerate(batches)}
        for fut in as_completed(futs):
            bi = futs[fut]
            try:
                merged.update(fut.result())
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    LogModule.RESTOR,
                    "[FORMULA-REPAIR] Batch LLM call failed (task_id={tid}, batch={bi}/{bn}): {err}",
                    tid=task_id,
                    bi=bi + 1,
                    bn=len(batches),
                    err=str(e)[:200],
                )

    try:
        if on_progress is not None:
            on_progress(
                {
                    "event": "done",
                    "task_id": task_id,
                    "notes": "ok",
                    "fixed": len([k for k, v in merged.items() if (v or "").strip()]),
                    "unchanged": len([k for k, v in merged.items() if not (v or "").strip()]),
                }
            )
    except Exception:
        pass
    return merged, "ok"


def apply_formula_repairs_to_task_state(
    task_state: Dict[str, Any],
    fixes: Dict[int, str],
) -> Dict[str, Any]:
    """
    Mutates task_state['translation_segments']['segments'][i]['target_text'] in-place.
    Fallback rules:
      - if fixed_text is non-empty: use it
      - else if target_text exists: keep it
      - else fallback to source_text
    Returns a small summary dict for logging/telemetry.
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
            # unchanged; keep target if present, else fallback to source
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

