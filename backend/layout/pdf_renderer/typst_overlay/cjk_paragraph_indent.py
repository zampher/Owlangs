# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Owlangs Authors.
"""CJK body first-line indent for Typst overlay PDF export."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from layout.block_types import CAPTION_SUB_TYPES

# Block types that must never receive Chinese body first-line indent.
_NON_BODY_BLOCK_TYPES = frozenset(
    {
        "title",
        "doc_title",
        "header",
        "footer",
        "page_number",
        "page_footer",
        "number",
        "aside_text",
        "ref_text",
        "reference",
        "equation",
        "formula",
        "display_formula",
        "inline_formula",
        "list",
        "list_item",
        "figure_title",
        "table_title",
        "chart_title",
        *CAPTION_SUB_TYPES,
        "caption",
        "footnote",
        "vision_footnote",
    }
)

_BLOCK_INDEX_RE = re.compile(r"^block-(\d+)(?:-|$)", re.IGNORECASE)

_CJK_LANG_ALIASES = frozenset(
    {
        "zh",
        "zh-cn",
        "zh-hans",
        "zh-hant",
        "zh-tw",
        "zh-hk",
        "zh_cn",
        "zh_tw",
        "chinese",
        "chinese_simplified",
        "chinese_traditional",
        "simplified_chinese",
        "traditional_chinese",
        "cn",
    }
)


def is_cjk_target_language(lang: Optional[str]) -> bool:
    """Return True when *lang* denotes Chinese (simplified or traditional)."""
    if not lang or not isinstance(lang, str):
        return False
    key = lang.strip().lower().replace(" ", "_")
    if not key:
        return False
    if key in _CJK_LANG_ALIASES:
        return True
    # zh-CN / zh_CN / zh-Hans-CN style tags
    if key.startswith("zh-") or key.startswith("zh_"):
        return True
    return False


# Two CJK character widths as Typst em (tracks fitted/scaled font size).
CJK_BODY_FIRST_LINE_INDENT_EM = 2.0


def cjk_body_first_line_indent_em() -> float:
    """Two CJK character widths in em (relative to the rendered text size)."""
    return CJK_BODY_FIRST_LINE_INDENT_EM


def cjk_body_first_line_indent_pt(font_size_pt: float) -> float:
    """Approximate two CJK widths in pt at *font_size_pt* (diagnostics / legacy)."""
    size = float(font_size_pt) if font_size_pt and font_size_pt > 0 else 1.0
    return CJK_BODY_FIRST_LINE_INDENT_EM * max(size, 1.0)


def should_apply_cjk_body_indent(
    *,
    block_id: Optional[str],
    block_type: Optional[str],
    render_kind: Optional[str],
) -> bool:
    """Whether a render block should get Chinese body first-line indent."""
    kind = (render_kind or "text").strip().lower()
    if kind in {"image", "table", "skip"}:
        return False

    bid = (block_id or "").strip().lower()
    if bid.startswith("caption-") or bid.startswith("footnote-"):
        return False

    btype = (block_type or "").strip().lower()
    if btype in _NON_BODY_BLOCK_TYPES:
        return False
    if btype.endswith("_caption") or btype.endswith("_title"):
        return False

    # Body paragraphs and layout-group companion text only.
    if btype in {"", "text", "paragraph", "content"}:
        return True
    # Unknown non-caption types: do not indent (safer than over-indenting).
    return False


def resolve_target_language(
    config_lang: Optional[str] = None,
    task_state: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Prefer config.target_language, then task_state to_lang / target_language."""
    if config_lang and str(config_lang).strip():
        return str(config_lang).strip()
    if not task_state:
        return None
    for key in ("to_lang", "target_language", "target_lang"):
        val = task_state.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return None


def infer_layout_block_type(
    block_id: Optional[str],
    type_by_index: Mapping[int, str],
) -> Optional[str]:
    """Map a RenderBlock.block_id to the layout document block type."""
    bid = (block_id or "").strip()
    if not bid:
        return None
    lower = bid.lower()
    if lower.startswith("caption-"):
        return "caption"
    if lower.startswith("footnote-"):
        return "footnote"
    m = _BLOCK_INDEX_RE.match(bid)
    if not m:
        return None
    try:
        idx = int(m.group(1))
    except ValueError:
        return None
    return type_by_index.get(idx)


def apply_cjk_body_indent_to_block(
    rb: Any,
    *,
    target_language: Optional[str],
    layout_block_type: Optional[str] = None,
) -> float:
    """
    Set Chinese body first-line indent as ``first_line_indent_em`` (2em).

    Em units track the rendered (possibly fitted/scaled) font size so the
    visual indent stays ≈ two CJK characters. Absolute pt is cleared.

    Returns the em indent applied (0.0 when skipped).
    """
    if not is_cjk_target_language(target_language):
        rb.first_line_indent_em = 0.0
        rb.first_line_indent_pt = 0.0
        return 0.0

    if not should_apply_cjk_body_indent(
        block_id=getattr(rb, "block_id", None),
        block_type=layout_block_type,
        render_kind=getattr(rb, "render_kind", None),
    ):
        rb.first_line_indent_em = 0.0
        rb.first_line_indent_pt = 0.0
        return 0.0

    indent_em = cjk_body_first_line_indent_em()
    rb.first_line_indent_em = indent_em
    # Prefer em in the emitter; clear absolute pt to avoid double-counting.
    rb.first_line_indent_pt = 0.0
    return indent_em
