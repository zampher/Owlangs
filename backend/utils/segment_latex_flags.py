# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""LaTeX capability flags for translation segments (orthogonal to chunk/block type)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from layout.block_types import INTERLINE_EQUATION
from utils.latex_repair_payload import has_latex_content
from utils.mixed_formula_text import (
    _has_existing_math_delimiters,
    has_mixed_formula_content,
    mixed_text_to_md,
)

LatexFlags = Dict[str, bool]

_EMPTY_FLAGS: LatexFlags = {
    "present": False,
    "mixed": False,
    "needs_delimiter_wrap": False,
}


def classify_latex_flags(text: str, *, block_type: Optional[str] = None) -> LatexFlags:
    """
    Classify LaTeX rendering needs for a segment body.

    Flags are orthogonal to chunk_type / block_type:
    - present: segment content includes math that downstream should render
    - mixed: natural language and LaTeX coexist (translate prose, preserve math)
    - needs_delimiter_wrap: run mixed_text_to_md before render/export
    """
    normalized_block_type = (block_type or "").strip().lower()
    if normalized_block_type == INTERLINE_EQUATION:
        return {"present": True, "mixed": False, "needs_delimiter_wrap": False}

    if not text or not text.strip():
        return dict(_EMPTY_FLAGS)

    mixed = has_mixed_formula_content(text)
    if mixed:
        delimited = _has_existing_math_delimiters(text)
        return {
            "present": True,
            "mixed": True,
            "needs_delimiter_wrap": not delimited,
        }

    from utils.translation_segments import _is_formula_segment

    if _is_formula_segment(text):
        return {"present": True, "mixed": False, "needs_delimiter_wrap": False}

    delimited = _has_existing_math_delimiters(text)
    present = bool(delimited or has_latex_content(text))

    return {
        "present": present,
        "mixed": False,
        "needs_delimiter_wrap": False,
    }


def normalize_latex_flags(raw: Any) -> LatexFlags:
    """Return a validated latex_flags dict from segment metadata."""
    if not isinstance(raw, dict):
        return dict(_EMPTY_FLAGS)
    return {
        "present": bool(raw.get("present")),
        "mixed": bool(raw.get("mixed")),
        "needs_delimiter_wrap": bool(raw.get("needs_delimiter_wrap")),
    }


def resolve_segment_latex_flags(
    segment: Dict[str, Any],
    *,
    text: Optional[str] = None,
    block_type: Optional[str] = None,
    recompute: bool = False,
) -> LatexFlags:
    """Read stored latex_flags or classify from segment text."""
    if not recompute:
        stored = segment.get("latex_flags")
        if isinstance(stored, dict) and "present" in stored:
            return normalize_latex_flags(stored)

    body = text
    if body is None:
        body = (
            segment.get("modified_text")
            or segment.get("target_text")
            or segment.get("text")
            or segment.get("source_text")
            or ""
        )
    bt = block_type or segment.get("block_type") or segment.get("chunk_type")
    return classify_latex_flags(str(body or ""), block_type=bt)


def attach_latex_flags_to_segment(
    segment: Dict[str, Any],
    *,
    text: Optional[str] = None,
    block_type: Optional[str] = None,
    recompute: bool = False,
) -> LatexFlags:
    """Write latex_flags and has_latex onto segment dict."""
    flags = resolve_segment_latex_flags(
        segment,
        text=text,
        block_type=block_type,
        recompute=recompute,
    )
    segment["latex_flags"] = flags
    segment["has_latex"] = flags["present"]
    return flags


def prepare_text_for_latex_render(text: str, latex_flags: Optional[LatexFlags] = None) -> str:
    """Apply delimiter wrapping when latex_flags.needs_delimiter_wrap is set."""
    if not text:
        return text
    flags = normalize_latex_flags(latex_flags or {})
    if flags.get("needs_delimiter_wrap"):
        return mixed_text_to_md(text)
    return text


def _unwrap_spurious_display_math_wrapper(text: str, flags: LatexFlags) -> str:
    """
    Remove outer $$...$$ when mixed prose was wrongly wrapped as display math.

    cmarker+mitex renders mixed Chinese/English + inline tokens via $...$, not
    a single $$...$$ block around the whole paragraph.
    """
    if not text or not flags.get("mixed"):
        return text
    stripped = text.strip()
    if not (stripped.startswith("$$") and stripped.endswith("$$")):
        return text
    if stripped.count("$$") != 2:
        return text
    inner = stripped[2:-2].strip()
    if not inner:
        return text
    # Mixed paragraphs must not use display-math delimiters for the whole block.
    if has_mixed_formula_content(inner) or _has_existing_math_delimiters(inner):
        return inner
    return text


def normalize_text_for_typst_overlay(
    text: str,
    latex_flags: Optional[LatexFlags] = None,
    *,
    block_type: Optional[str] = None,
) -> str:
    """Prepare segment text for Typst cmarker+mitex overlay rendering."""
    if not text or not text.strip():
        return text
    flags = latex_flags or classify_latex_flags(text, block_type=block_type)
    if not flags.get("present"):
        return text
    prepared = prepare_text_for_latex_render(text, flags)
    return _unwrap_spurious_display_math_wrapper(prepared, flags)


def prepare_segment_export_text(
    segment: Dict[str, Any],
    *,
    text: Optional[str] = None,
    text_field: str = "target_text",
    for_typst: bool = True,
) -> str:
    """Resolve export text and apply LaTeX delimiter normalization when needed."""
    if text is None:
        if text_field == "source_text":
            text = segment.get("source_text") or ""
        else:
            text = segment.get("modified_text") or segment.get("target_text") or ""
    text = (text or "").strip()
    if not text:
        return ""
    flags = resolve_segment_latex_flags(segment, text=text, recompute=True)
    if for_typst:
        return normalize_text_for_typst_overlay(
            text,
            flags,
            block_type=segment.get("block_type") or segment.get("chunk_type"),
        )
    return prepare_text_for_latex_render(text, flags)