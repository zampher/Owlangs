# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typst source code emitter.

Generates Typst typesetting source code from a list of RenderPageSpec
objects. The generated Typst code produces a multi-page overlay PDF
with precisely positioned text blocks.

Design principles:
  - Pure string generation, no Typst runtime knowledge required
  - Each block is positioned using #place() at exact bbox coordinates
  - Text that overflows is automatically fit using pdftr_fit utilities
  - Formulas in $...$ (and normalized \\(...\\)) are rendered via cmarker + mitex
"""

import logging
import math
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import List

from layout.pdf_renderer.typst_overlay.math_span_utils import (
    transform_dollar_math_spans,
    transform_latex_bracket_delimiters,
)
from layout.pdf_renderer.typst_overlay.mitex_math_safety import (
    markdown_line_safe_for_mitex,
    mitex_unsafe_reason,
)
from layout.pdf_renderer.typst_overlay.typst_packages import typst_preview_import_lines

from layout.pdf_renderer.shared.table_utils import TableUtils
from layout.pdf_renderer.typst_overlay.formula_safety import formula_safety_insets_pt
from layout.pdf_renderer.typst_overlay.layer_order import background_embed_force_opaque
from logger.logger import LogModule, unified_logger
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    DEFAULT_TABLE_STROKE_PT,
)
from layout.pdf_renderer.typst_overlay.table_border_style import (
    TABLE_BORDER_STYLE_BOOKTABS,
    TABLE_BORDER_STYLE_GRID,
    TABLE_BORDER_STYLE_HORIZONTAL,
    TABLE_BORDER_STYLE_NONE,
    TABLE_BORDER_STYLE_OUTER,
    booktabs_header_row_count,
    group_adjacent_equal_row_cells,
    is_booktabs_border_style,
    resolve_table_border_style,
)
from layout.pdf_renderer.typst_overlay.models import RenderBlock, RenderPageSpec


# ---- Typst code templates ----

TYPST_PRELUDE = '''// Auto-generated Typst overlay source by Owlangs TypstOverlayRenderer
// Do not edit manually

#set page(margin: 0pt, fill: none)
'''

# ---- Utility: Typst string escaping ----

def _escape_typst_string(text: str) -> str:
    """Escape special characters for Typst string literals."""
    return (text
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n"))


def _typst_cmarker_render_expr(var_name: str) -> str:
    """Render user text through cmarker+mitex so LaTeX $...$ math compiles."""
    return f"cmarker.render({var_name}, math: mitex)"


def _typst_cmarker_plain_render_expr(var_name: str) -> str:
    """Render markdown without mitex (fallback for unsafe inline math)."""
    return f"cmarker.render({var_name})"


def _typst_cmarker_render_expr_for_markdown(var_name: str, markdown: str) -> str:
    """Pick cmarker+mitex or plain cmarker based on mitex safety heuristics."""
    if markdown_line_safe_for_mitex(markdown):
        return _typst_cmarker_render_expr(var_name)
    preview = str(markdown or "").replace("\n", " ")[:120]
    unified_logger.warning(
        LogModule.RESTOR,
        "[TYPST_OVERLAY] mitex skipped for block markdown "
        f"(var={var_name}, preview={preview!r})",
    )
    return _typst_cmarker_plain_render_expr(var_name)


@lru_cache(maxsize=8192)
def _prepare_user_text_for_typst(text: str) -> str:
    """Sanitize and escape user-authored text for Typst string bindings."""
    return _escape_typst_string(sanitize_typst_markdown_for_compile(text))


@lru_cache(maxsize=8192)
def _escape_sanitized_text_for_typst(text: str) -> str:
    """Escape already-sanitized markdown for Typst string bindings."""
    return _escape_typst_string(text)


def _typst_rgb(color) -> str:
    """Convert (r, g, b) float tuple to Typst rgb(...) expression."""
    r, g, b = color
    return (f"rgb({int(max(0, min(1, r)) * 255)}, "
            f"{int(max(0, min(1, g)) * 255)}, "
            f"{int(max(0, min(1, b)) * 255)})")


def _typst_place(x_pt: float, y_pt: float, body: str) -> str:
    """Generate a Typst #place() call."""
    return f"#place(top + left, dx: {round(x_pt, 1)}pt, dy: {round(y_pt, 1)}pt, {body})"


def _typst_bool(value: bool) -> str:
    """Convert Python bool to Typst bool literal."""
    return "true" if value else "false"


def _typst_font_style_clause(font_style: str) -> str:
    """Return Typst style clause for set text()."""
    style = (font_style or "normal").strip().lower()
    if style not in ("normal", "italic"):
        style = "normal"
    return f', style: "{style}"'


def _typst_set_text_attrs(
    font_size_pt: float,
    font_weight: str,
    font_style: str,
    text_fill: str,
) -> str:
    """Generate a Typst set text(...) expression with size, weight, style, fill."""
    return (
        f'set text(size: {font_size_pt}pt, weight: "{font_weight or "regular"}"'
        f'{_typst_font_style_clause(font_style)}, fill: {text_fill})'
    )

# ---- Block renderers ----

PLAIN_LINE_FIT_MAX_CHARS = 40
MIN_BLOCK_SIZE_PT = 8.0


def _block_formula_layout_insets_pt(
    block: RenderBlock,
    layout_height_pt: float,
    text: str,
) -> tuple[float, float, float]:
    """Return (top_inset, bottom_inset, content_fit_height) for formula safety padding."""
    formula_insets = formula_safety_insets_pt(
        text,
        block.math_map,
        font_size_pt=block.font_size_pt,
        box_height_pt=layout_height_pt,
    )
    top = formula_insets.top_pt
    bottom = formula_insets.bottom_pt
    content_h = max(
        MIN_BLOCK_SIZE_PT,
        layout_height_pt - top - bottom,
    )
    return top, bottom, content_h


TOC_ENTRY_FONT_PT = 9.6
TOC_ENTRY_MIN_FONT_PT = 6.8
TOC_TITLE_PAGE_GAP_PT = 4.0
TOC_LEADER_DOT_WIDTH_RATIO = 0.26


def _block_fill_arg(block: RenderBlock, *, force_opaque: bool = False) -> str:
    """Generate the fill argument for Typst block based on cover settings."""
    if block.use_cover_fill or force_opaque or getattr(block, 'opaque_fill', False):
        fill = block.cover_fill if block.use_cover_fill else (1.0, 1.0, 1.0)
        return f", fill: {_typst_rgb(fill)}"
    return ""


def _typst_rotate_angle(rotation: int) -> int:
    """Map segment rotation to Typst ``rotate`` angle (counter-clockwise positive)."""
    if rotation in {90, 180, 270}:
        return -rotation
    return 0


def _rotated_reading_dimensions(
    width: float,
    height: float,
    rotation: int,
) -> tuple[float, float]:
    """Return inner layout (width, height) before Typst ``rotate()`` maps into bbox.

    For 90°/270° the PDF bbox is tall and narrow; flow text is composed in swapped
    dimensions so horizontal lines fill the reading-oriented area, then rotated into
    the bbox.
    """
    if rotation in {90, 270}:
        return height, width
    return width, height


# Backward-compatible alias used by table tests.
_table_reading_dimensions = _rotated_reading_dimensions


def _typst_emit_flow_placement_in_context(
    *,
    x0: float,
    y0: float,
    bbox_w: float,
    bbox_h: float,
    inner_var: str,
    outer_var: str,
    rotation: int,
    fill_arg: str = "",
    indent: str = "  ",
) -> list[str]:
    """Emit ``place(...)`` lines for use inside an existing ``#context`` block.

    Required when *inner_var* is bound with ``let`` inside that context (e.g.
    after ``measure()`` for auto-scaled short plain text).
    """
    if rotation in {90, 180, 270}:
        typst_angle = _typst_rotate_angle(rotation)
        return [
            f"{indent}let {outer_var} = block(width: {round(bbox_w, 1)}pt, "
            f"height: {round(bbox_h, 1)}pt, clip: true{fill_arg})[",
            f"{indent}  #align(center + horizon)[",
            f"{indent}    #rotate({typst_angle}deg, origin: center, {inner_var})",
            f"{indent}  ]",
            f"{indent}]",
            f"{indent}place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, "
            f"{outer_var})",
        ]
    return [
        f"{indent}place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, "
        f"{inner_var})",
    ]


def _typst_emit_rotated_placement(
    *,
    x0: float,
    y0: float,
    bbox_w: float,
    bbox_h: float,
    inner_var: str,
    outer_var: str,
    rotation: int,
    fill_arg: str = "",
) -> list[str]:
    """Place *inner_var* inside a clipped bbox, rotating when needed."""
    if rotation in {90, 180, 270}:
        typst_angle = _typst_rotate_angle(rotation)
        return [
            f"#let {outer_var} = block(width: {round(bbox_w, 1)}pt, "
            f"height: {round(bbox_h, 1)}pt, clip: true{fill_arg})[",
            f"  #align(center + horizon)[",
            f"    #rotate({typst_angle}deg, origin: center, {inner_var})",
            f"  ]",
            f"]",
            "#context {",
            f"  place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, "
            f"{outer_var})",
            "}",
        ]
    return [
        "#context {",
        f"  place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, {inner_var})",
        "}",
    ]


def _typst_place_flow_block(
    x0: float,
    y0: float,
    bbox_w: float,
    bbox_h: float,
    inner_var: str,
    var_prefix: str,
    rotation: int,
    *,
    fill_arg: str = "",
    dy_offset: float = 0.0,
) -> str:
    """Place a flow-text inner block, clipping to bbox when rotated."""
    outer_var = f"{var_prefix}_bbox"
    lines = _typst_emit_rotated_placement(
        x0=x0,
        y0=y0 + dy_offset,
        bbox_w=bbox_w,
        bbox_h=bbox_h,
        inner_var=inner_var,
        outer_var=outer_var,
        rotation=rotation,
        fill_arg=fill_arg,
    )
    return "\n".join(lines) + "\n"


def _typst_place_context(x_pt: float, y_pt: float, body_name: str,
                        *, rotation: int = 0) -> str:
    """Generate a Typst #context { place(...) } call for overlay placement.

    Prefer ``_typst_place_flow_block`` for rotated flow text so content stays
    inside the bbox. *rotation* here is legacy and rotates without clipping.
    """
    typst_angle = _typst_rotate_angle(rotation)
    body_ref = (
        f"rotate({typst_angle}deg, origin: center, {body_name})"
        if typst_angle
        else body_name
    )
    return (f"#context {{\n"
            f"  place(top + left, dx: {round(x_pt, 1)}pt, dy: {round(y_pt, 1)}pt, {body_ref})\n"
            f"}}\n")


def _typst_pad_vertical_expr(
    body_expr: str,
    content_top_inset_pt: float,
    content_bottom_inset_pt: float,
) -> str:
    """Wrap *body_expr* with Typst vertical pad for formula safety insets."""
    if content_top_inset_pt <= 0 and content_bottom_inset_pt <= 0:
        return body_expr
    return (
        f"pad(top: {max(0.0, content_top_inset_pt)}pt, "
        f"bottom: {max(0.0, content_bottom_inset_pt)}pt)"
        f"[#{{ {body_expr} }}]"
    )


def _typst_first_line_indent_length(block: RenderBlock) -> str:
    """Typst length for first-line indent; prefer em so it tracks text size."""
    em = float(getattr(block, "first_line_indent_em", 0.0) or 0.0)
    if em > 0:
        return f"{em}em"
    pt = float(getattr(block, "first_line_indent_pt", 0.0) or 0.0)
    if pt > 0:
        return f"{pt}pt"
    return ""


def _typst_first_line_indent_h_stmt(indent_length: str) -> str:
    """Emit ``h(indent)`` when *indent_length* is non-empty."""
    if not indent_length:
        return ""
    return f"if {indent_length} > 0pt {{ h({indent_length}) }}; "


def _typst_first_line_indent_arg(indent_length: str) -> str:
    """Emit ``, first_line_indent: <length>`` for fit helpers."""
    if not indent_length:
        return ""
    return f", first_line_indent: {indent_length}"


def _typst_markdown_block(body_name: str, width: float, height: float,
                          block_fill: str, body_expr: str,
                          content_top_inset_pt: float = 0.0,
                          content_bottom_inset_pt: float = 0.0) -> str:
    """Generate a Typst #let body = block(...) expression with optional pad insets."""
    if content_top_inset_pt > 0 or content_bottom_inset_pt > 0:
        body_expr = _typst_pad_vertical_expr(
            body_expr, content_top_inset_pt, content_bottom_inset_pt,
        )
    return (f"#let {body_name} = block(width: {width}pt, height: {height}pt"
            f"{block_fill})[#{{ {body_expr} }}]\n")


def _typst_markdown_fit_call(md_name: str, max_font_size_pt: float,
                             min_font_size_pt: float, max_leading_em: float,
                             min_leading_em: float, fit_height_pt: float,
                             font_weight: str, font_style: str,
                             first_line_indent: str,
                             justify_text: str,
                             *,
                             use_mitex: bool = True) -> str:
    """Generate a pdftr_fit_markdown(...) call expression."""
    indent = _typst_first_line_indent_arg(first_line_indent)
    style_clause = _typst_font_style_clause(font_style)
    style_arg = f', style: "{font_style or "normal"}"' if style_clause else ""
    mitex_arg = ", use_mitex: true" if use_mitex else ", use_mitex: false"
    return (
        f"pdftr_fit_markdown({md_name}, max_size: {max_font_size_pt}pt, "
        f"min_size: {min_font_size_pt}pt, max_leading: {max_leading_em}em, "
        f"min_leading: {min_leading_em}em, fit_height: {fit_height_pt}pt, "
        f"weight: \"{font_weight}\"{style_arg}{indent}, justify: {justify_text}"
        f"{mitex_arg})"
    )


def _typst_markdown_fit_fixed_leading_call(
    md_name: str,
    max_font_size_pt: float,
    min_font_size_pt: float,
    leading_em: float,
    fit_height_pt: float,
    font_weight: str,
    font_style: str,
    first_line_indent: str,
    justify_text: str,
    *,
    use_mitex: bool = True,
) -> str:
    """Generate pdftr_fit_markdown_fixed_leading(...) — font-only fit, locked leading."""
    indent = _typst_first_line_indent_arg(first_line_indent)
    style_clause = _typst_font_style_clause(font_style)
    style_arg = f', style: "{font_style or "normal"}"' if style_clause else ""
    mitex_arg = ", use_mitex: true" if use_mitex else ", use_mitex: false"
    return (
        f"pdftr_fit_markdown_fixed_leading({md_name}, max_size: {max_font_size_pt}pt, "
        f"min_size: {min_font_size_pt}pt, leading: {leading_em}em, "
        f"fit_height: {fit_height_pt}pt, weight: \"{font_weight}\"{style_arg}{indent}, "
        f"justify: {justify_text}{mitex_arg})"
    )


def _block_markdown_fit_call(
    block: RenderBlock,
    md_name: str,
    fit_height_pt: float,
    font_style: str,
    first_line_indent: str,
    justify_text: str,
    *,
    markdown: str = "",
) -> str:
    """Pick fit call: user-locked leading keeps line spacing, auto leading may shrink both."""
    use_mitex = markdown_line_safe_for_mitex(markdown) if markdown else True
    if markdown and not use_mitex:
        preview = str(markdown).replace("\n", " ")[:120]
        unified_logger.warning(
            LogModule.RESTOR,
            "[TYPST_OVERLAY] markdown fit uses plain cmarker "
            f"(block={getattr(block, 'block_id', '?')}, preview={preview!r})",
        )
    if getattr(block, "leading_em_locked", False):
        max_font_pt = block.font_size_pt
        if block.fit_max_font_size_pt and block.fit_max_font_size_pt > 0:
            max_font_pt = min(max_font_pt, block.fit_max_font_size_pt)
        min_font_pt = block.fit_min_font_size_pt
        if not min_font_pt or min_font_pt <= 0:
            min_font_pt = max(1.0, max_font_pt * 0.5)
        return _typst_markdown_fit_fixed_leading_call(
            md_name,
            max_font_pt,
            min_font_pt,
            block.leading_em,
            fit_height_pt,
            block.font_weight,
            font_style,
            first_line_indent,
            justify_text,
            use_mitex=use_mitex,
        )
    return _typst_markdown_fit_call(
        md_name,
        block.font_size_pt,
        block.fit_min_font_size_pt,
        block.leading_em,
        block.fit_min_leading_em,
        fit_height_pt,
        block.font_weight,
        font_style,
        first_line_indent,
        justify_text,
        use_mitex=use_mitex,
    )


def _typst_single_line_fit_call(md_name: str, max_font_pt: float,
                                min_font_pt: float, width_pt: float,
                                height_pt: float, font_weight: str,
                                font_style: str, justify_text: str,
                                *,
                                use_mitex: bool = True) -> str:
    """Generate a pdftr_fit_single_line_markdown(...) call expression."""
    style_arg = f', style: "{font_style or "normal"}"'
    mitex_arg = ", use_mitex: true" if use_mitex else ", use_mitex: false"
    return (
        f"pdftr_fit_single_line_markdown({md_name}, max_size: {max_font_pt}pt, "
        f"min_size: {min_font_pt}pt, fit_width: {width_pt}pt, "
        f"fit_height: {height_pt}pt, weight: \"{font_weight}\"{style_arg}, "
        f"justify: {justify_text}{mitex_arg})"
    )


def _typst_plain_markdown_expr(md_name: str, font_size_pt: float,
                                leading_em: float, font_weight: str,
                                font_style: str, text_fill: str,
                                first_line_indent: str,
                                justify_text: str,
                                *,
                                markdown: str = "") -> str:
    """Generate static markdown rendering expression with line leading."""
    render_expr = (
        _typst_cmarker_render_expr_for_markdown(md_name, markdown)
        if markdown
        else _typst_cmarker_render_expr(md_name)
    )
    indent_stmt = _typst_first_line_indent_h_stmt(first_line_indent)
    return (
        f"{_typst_set_text_attrs(font_size_pt, font_weight, font_style, text_fill)}; "
        f"set par(leading: {leading_em}em, justify: {justify_text}); "
        f"{indent_stmt}{render_expr}"
    )


def _typst_plain_text_expr(text_name: str, font_size_pt: float,
                           leading_em: float, font_weight: str,
                           font_style: str, text_fill: str,
                           first_line_indent: str,
                           justify_text: str,
                           *,
                           markdown: str = "") -> str:
    """Generate static plain text rendering expression with leading."""
    render_expr = (
        _typst_cmarker_render_expr_for_markdown(text_name, markdown)
        if markdown
        else _typst_cmarker_render_expr(text_name)
    )
    indent_stmt = _typst_first_line_indent_h_stmt(first_line_indent)
    return (
        f"{_typst_set_text_attrs(font_size_pt, font_weight, font_style, text_fill)}; "
        f"set par(leading: {leading_em}em, justify: {justify_text}); "
        f"{indent_stmt}{render_expr}"
    )


# LLM/export line-break escapes that are not LaTeX commands (mitex: unknown command \n).
# Keep \nu, \neq, \newline, etc. (\n followed by lowercase letter).
_LITERAL_LINEBREAK_ESCAPE_RE = re.compile(r"\\(?:n|r)(?![a-z])")

# Valid LaTeX command bodies after a literal "\n" (not a newline). Longest first.
_N_PREFIX_LATEX_COMMANDS: tuple[str, ...] = (
    "subseteqq",
    "supseteqq",
    "subseteq",
    "supseteq",
    "shortparallel",
    "shortmid",
    "Leftarrow",
    "Rightarrow",
    "leftarrow",
    "rightarrow",
    "atural",
    "parallel",
    "olimits",
    "ewline",
    "abla",
    "cong",
    "simeq",
    "sim",
    "mid",
    "eq",
    "eg",
    "ot",
    "i",
    "u",
    "e",
)
_N_PREFIX_LATEX_ALTS = "|".join(
    re.escape(prefix)
    for prefix in sorted(_N_PREFIX_LATEX_COMMANDS, key=len, reverse=True)
)
# LLM "\\n" glued to a word inside math (e.g. "\\ndiff") becomes mitex "unknown variable: diff".
_LLM_N_GLUE_WORD_RE = re.compile(
    rf"\\(?:n|r)(?!{_N_PREFIX_LATEX_ALTS})([a-z]{{2,}})"
)


def _neutralize_linebreak_artifacts(text: str) -> str:
    """Replace literal \\n/\\r artifacts with a space; keep \\nu, \\newline, etc."""
    text = _LITERAL_LINEBREAK_ESCAPE_RE.sub(" ", text)
    text = _LLM_N_GLUE_WORD_RE.sub(lambda match: f" {match.group(1)}", text)
    return text


def _clean_math_inner(inner: str) -> str:
    """Sanitize inline/display math before mitex (line breaks + glued LLM tokens)."""
    inner = re.sub(r"[\r\n]+", " ", inner)
    inner = _LITERAL_LINEBREAK_ESCAPE_RE.sub(" ", inner)
    inner = _LLM_N_GLUE_WORD_RE.sub(
        lambda match: f"\\text{{{match.group(1)}}}", inner
    )
    return inner


def _strip_newlines_inside_math_delimiters(text: str) -> str:
    """Replace raw newlines inside $...$ / $$...$$ so mitex does not see unknown \\n."""
    return transform_dollar_math_spans(
        text,
        on_display=lambda inner: f"$${_clean_math_inner(inner)}$$",
        on_inline=lambda inner: f"${_clean_math_inner(inner)}$",
    )


def _log_unsafe_mitex_math_delimiters(text: str) -> str:
    """Log mitex-unsafe math spans; do not mutate content (block-level fallback handles envs)."""

    def _check_inner(inner: str, delimiter: str) -> str:
        reason = mitex_unsafe_reason(inner)
        if reason:
            preview = inner.replace("\n", " ")[:120]
            unified_logger.debug(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] mitex-unsafe math in sanitize "
                f"({reason}, delimiter={delimiter}, preview={preview!r})",
            )
        return inner

    return transform_dollar_math_spans(
        text,
        on_display=lambda inner: f"$${_check_inner(inner, '$$')}$$",
        on_inline=lambda inner: f"${_check_inner(inner, '$')}$",
    )


def _strip_paren_delimiter_artifacts_inside_math(text: str) -> str:
    """Remove stray \\( / \\) tokens inside $...$ / $$...$$ spans."""

    def _clean_inner(inner: str) -> str:
        return inner.replace(r"\(", "").replace(r"\)", "").strip()

    return transform_dollar_math_spans(
        text,
        on_display=lambda inner: f"$${_clean_inner(inner)}$$",
        on_inline=lambda inner: f"${_clean_inner(inner)}$",
    )


EMIT_SLOW_BLOCK_THRESHOLD_S = 0.5

_HEAVY_SANITIZE_MARKERS = (
    "$",
    r"\(",
    r"\[",
    r"\circled",
    r"\diff",
    r"\partial",
    r"\not",
    r"\argmin",
    r"\argmax",
    "![",
    r"\langlen",
    r"\right\text",
    r"\textcircled",
)

# Translation artifact: $\not$$\perp$ (or $X \not$$\perp$) is split by cmarker
# into bare $\not$ which breaks mitex 0.2.6 with "missing argument: it".
_SPLIT_NOT_MATH_RE = re.compile(r"\$([^$]*\\not)\$\s*\$([^$]+)\$")


def _needs_heavy_markdown_sanitize(text: str) -> bool:
    """True when text needs the full mitex/math sanitize pipeline."""
    if not text:
        return False
    return any(marker in text for marker in _HEAVY_SANITIZE_MARKERS)


@lru_cache(maxsize=16384)
def _prepare_table_cell_for_typst(text: str) -> str:
    """Fast-path Typst binding for table cells (mostly plain text)."""
    body = str(text or "")
    if not _needs_heavy_markdown_sanitize(body):
        return _escape_typst_string(body)
    return _escape_typst_string(_sanitize_typst_markdown_core(body))


class _TableCellVarCache:
    """Deduplicate identical table cell strings into shared #let bindings."""

    def __init__(self, var_prefix: str) -> None:
        self._var_prefix = var_prefix
        self._text_to_var: dict[str, str] = {}
        self._let_lines: list[str] = []
        self._counter = 0

    def bind(self, cell_text: str) -> str:
        key = str(cell_text or "")
        cached = self._text_to_var.get(key)
        if cached is not None:
            return cached
        var = f"{self._var_prefix}_cell_{self._counter}"
        self._counter += 1
        self._text_to_var[key] = var
        self._let_lines.append(
            f'#let {var} = "{_prepare_table_cell_for_typst(key)}"'
        )
        return var

    @property
    def let_lines(self) -> list[str]:
        return self._let_lines


@lru_cache(maxsize=8192)
def _sanitize_typst_markdown_core(markdown: str) -> str:
    """Cached markdown sanitization for Typst overlay emit (hot path)."""
    text = str(markdown or "")
    if not _needs_heavy_markdown_sanitize(text):
        return text
    # Normalize LaTeX math delimiters to $...$ / $$...$$ for cmarker+mitex.
    text = transform_latex_bracket_delimiters(text)
    text = _strip_paren_delimiter_artifacts_inside_math(text)
    text = _strip_newlines_inside_math_delimiters(text)
    text = _neutralize_linebreak_artifacts(text)
    # Merge split negation: $\not$$\perp$ -> $\not\perp$
    text = _SPLIT_NOT_MATH_RE.sub(r"$\1\2$", text)
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:circled|textcircled)\s*R\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:circled|textcircled)\s*\{\s*R\s*\}\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:textregistered|registered)\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*®\s*\}\s*\$", "®", text)
    text = text.replace("$^®$", "®").replace("$^{®}$", "®")
    text = text.replace(r"$^\circled{R}$", "®").replace(r"$^\textcircled{R}$", "®")
    text = re.sub(r"\\langlen\b", r"\\langle n", text)
    # mitex 0.2.6 does not define \\diff (physics package); map to upright d.
    text = re.sub(r"\\diff\b", r"\\mathrm{d}", text)
    # mitex 0.2.6 does not define \\argmin/\\argmax (amsmath); map to operatorname.
    # Use (?![A-Za-z]) so \\argmin_{x} still matches (\\b fails before '_').
    text = re.sub(r"\\argmin(?![A-Za-z])", r"\\operatorname{argmin}", text)
    text = re.sub(r"\\argmax(?![A-Za-z])", r"\\operatorname{argmax}", text)
    # mitex 0.2.6 mis-parses \\partial as unknown variable "diff"; use Unicode ∂.
    text = text.replace(r"\partial", "∂")
    # OCR/translation corruption: \right\text{ceil} is not a valid delimiter.
    text = re.sub(r"\\right\\text\{ceil\}", r"\\right\\rfloor", text)
    text = re.sub(r"\\right\\text\{floor\}", r"\\right\\rfloor", text)
    text = text.replace(r"\circled{\times}", r"\otimes")
    text = text.replace(r"\circled{\parallel}", r"\circ")
    text = text.replace(r"\textcircled{\times}", r"\otimes")
    text = text.replace(r"\textcircled{\parallel}", r"\circ")
    # Remove Markdown image references (e.g., ![alt](path)) to avoid Typst compilation errors
    # when image files are not available. For overlay rendering, image/table/chart visuals
    # should remain on the original PDF, not re-rendered through Typst.
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
    return text


def sanitize_typst_markdown_for_compile(markdown: str) -> str:
    """Sanitize markdown to avoid common Typst compilation errors in overlay blocks."""
    text = _sanitize_typst_markdown_core(markdown)
    if unified_logger.isEnabledFor(logging.DEBUG):
        return _log_unsafe_mitex_math_delimiters(text)
    return text


# ---- TOC entry rendering helpers ----

def _toc_text_units(text: str) -> float:
    """Estimate text width in character units for TOC leader dot calculation."""
    units = 0.0
    for char in str(text or ""):
        if char.isspace():
            units += 0.35
        elif "\u4e00" <= char <= "\u9fff":
            units += 1.08
        elif char.isascii() and char.isalnum():
            units += 0.62
        elif char == ".":
            units += 0.34
        else:
            units += 0.56
    return units


def _toc_leader_text(prefix_title: str, page_label: str, *,
                     width_pt: float, font_size_pt: float) -> str:
    """Generate leader dot string between title and page label."""
    if not str(page_label or "").strip():
        return ""
    available_units = max(8.0, (width_pt / max(font_size_pt, 1.0)) * 0.84)
    used_units = _toc_text_units(prefix_title) + _toc_text_units(page_label)
    spare_units = available_units - used_units
    if spare_units <= 1.4:
        return "..."
    dot_count = int(spare_units / 0.34)
    return "." * max(3, min(48, dot_count))


def _render_toc_entries(block_id: str, block: RenderBlock,
                        text_fill: str) -> str:
    """Render TOC (table-of-contents) entries with layout/measure/place."""
    parts: list[str] = []
    font_weight = block.font_weight or "regular"
    var_prefix = block_id.replace("-", "_")

    for index, entry in enumerate(block.toc_entries or []):
        if len(entry.bbox) != 4 or not str(entry.title or "").strip():
            continue
        ex0, ey0, ex1, ey1 = entry.bbox
        ew = max(MIN_BLOCK_SIZE_PT, ex1 - ex0)
        eh = max(MIN_BLOCK_SIZE_PT, ey1 - ey0)
        indent = round(max(0, int(entry.level or 1) - 1) * min(18.0, ew * 0.06), 2)
        max_font_pt = round(max(1.0, min(TOC_ENTRY_FONT_PT, eh * 0.82)), 2)
        min_font_pt = round(max(1.0, min(max_font_pt, TOC_ENTRY_MIN_FONT_PT, eh * 0.58)), 2)
        prefix = f"{entry.number} " if str(entry.number or "").strip() else ""
        line_width = round(max(8.0, ew - indent), 2)
        # Use sanitized title text directly (no build_direct_typst_passthrough_text dependency)
        prefix_title = sanitize_typst_markdown_for_compile(f"{prefix}{entry.title}")
        page_label = str(entry.page_label or "").strip()
        title_name = f"{var_prefix}_toc_{index}_title"
        page_name = f"{var_prefix}_toc_{index}_page"
        body_name = f"{var_prefix}_toc_{index}_body"
        title_y = round(max(0.0, eh * 0.08), 2)
        leader_y = round(eh * 0.55, 2)
        parts.extend([
            f'#let {title_name} = "{_prepare_user_text_for_typst(prefix_title)}"',
            f'#let {page_name} = "{_escape_typst_string(page_label)}"',
            f"#let {body_name} = block(width: {line_width}pt, height: {eh}pt)[#{{ "
            f"set text(size: {max_font_pt}pt, weight: \"{font_weight}\", fill: {text_fill}); "
            "set par(leading: 0.15em, justify: false); "
            "layout(size => { "
            f"let page-body = box[#{{ {page_name} }}]; "
            "let page-size = measure(page-body); "
            f"let title-body = box[#{{ cmarker.render({title_name}, math: mitex) }}]; "
            "let title-size = measure(title-body); "
            "let title-max = calc.max(8pt, size.width - page-size.width - 8pt); "
            "let title-width = calc.min(title-size.width, title-max); "
            "let leader-start = title-width + 2pt; "
            "let leader-end = size.width - page-size.width - 4pt; "
            "let leader-len = calc.max(0pt, leader-end - leader-start); "
            f"place(top + left, dx: 0pt, dy: {title_y}pt, box(width: title-width, clip: false)[#{{ title-body }}]); "
            f"if leader-len > 2pt {{ place(top + left, dx: leader-start, dy: {leader_y}pt, "
            "line(length: leader-len, stroke: (paint: rgb(120, 120, 120), thickness: 0.45pt, dash: (1pt, 2pt)))) }; "
            f"place(top + left, dx: size.width - page-size.width, dy: {title_y}pt, page-body) "
            "}) }}]",
            _typst_place_context(ex0 + indent, ey0, body_name).rstrip(),
        ])
    return "\n".join(parts) + ("\n" if parts else "")


def _typst_preserved_lines_expr(lines_name: str, font_size_pt: float,
                                 leading_em: float, font_weight: str,
                                 font_style: str, text_fill: str,
                                 justify_text: str,
                                 width_pt: float) -> str:
    """Generate preserved line breaks rendering expression."""
    # Each logical \\n segment sits in a width-constrained block so long lines
    # (USPC lists) wrap with par(leading). Stack spacing separates segments.
    return (
        f"{_typst_set_text_attrs(font_size_pt, font_weight, font_style, text_fill)}; "
        f"stack(dir: ttb, spacing: {leading_em}em, ..{lines_name}.map(line => "
        f"block(width: {width_pt}pt)[#{{ "
        f"set par(leading: {leading_em}em, justify: {justify_text}); cmarker.render(line, math: mitex) }}]))"
    )


def _render_preserved_line_breaks_block(
    block_id: str,
    block: RenderBlock,
    *,
    line_values: list[str],
    text_fill: str,
    block_fill: str,
    font_style: str,
    justify: str,
    layout_width: float,
    layout_height: float,
    content_top: float,
    content_bottom: float,
    x0: float,
    y0: float,
    width: float,
    height: float,
    rotation: int,
    rotate_fill: str,
) -> str:
    """Emit preserved lines with per-line mitex safety fallback."""
    var_prefix = block_id.replace("-", "_")
    body_var = f"{var_prefix}_body"
    width_pt = round(layout_width, 2)
    leading_em = block.leading_em
    stack_items: list[str] = []
    let_lines: list[str] = []
    fallback_count = 0

    for index, line in enumerate(line_values):
        line_var = f"{var_prefix}_line_{index}"
        let_lines.append(
            f'#let {line_var} = "{_prepare_user_text_for_typst(line)}"',
        )
        if markdown_line_safe_for_mitex(line):
            render_expr = _typst_cmarker_render_expr(line_var)
        else:
            fallback_count += 1
            preview = line.replace("\n", " ")[:120]
            unified_logger.warning(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] Preserved line mitex fallback "
                f"(block={block_id}, line={index}, preview={preview!r})",
            )
            render_expr = _typst_cmarker_plain_render_expr(line_var)
        stack_items.append(
            "block(width: "
            f"{width_pt}pt)[#{{ set par(leading: {leading_em}em, justify: {justify}); "
            f"{render_expr} }}]",
        )

    if fallback_count:
        unified_logger.info(
            LogModule.RESTOR,
            "[TYPST_OVERLAY] Preserved line block "
            f"{block_id}: {fallback_count}/{len(line_values)} line(s) "
            "use plain cmarker (mitex skipped)",
        )

    body_expr = (
        f"{_typst_set_text_attrs(block.font_size_pt, block.font_weight, font_style, text_fill)}; "
        f"stack(dir: ttb, spacing: {leading_em}em, {', '.join(stack_items)})"
    )
    parts = [
        *let_lines,
        _typst_markdown_block(
            body_var,
            layout_width,
            layout_height,
            block_fill,
            body_expr,
            content_top_inset_pt=content_top,
            content_bottom_inset_pt=content_bottom,
        ),
        _typst_place_flow_block(
            x0, y0, width, height, body_var, var_prefix, rotation,
            fill_arg=rotate_fill,
        ).rstrip(),
    ]
    return "\n".join(parts) + "\n"


def _render_plain_block(block_id: str, block: RenderBlock,
                        *, force_opaque: bool = False) -> str:
    """Render a simple plain-text block (short text, no markdown)."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    rotation = getattr(block, "rotation", 0) or 0
    layout_width, layout_height = _rotated_reading_dimensions(width, height, rotation)
    text_fill = _typst_rgb(block.text_color)
    var_prefix = block_id.replace("-", "_")
    block_fill = _block_fill_arg(block, force_opaque=force_opaque)

    text = block.plain_text or block.markdown_text
    if not text.strip():
        return ""

    font_style = getattr(block, "font_style", None) or "normal"
    content_top, content_bottom, content_fit_height = _block_formula_layout_insets_pt(
        block, layout_height, text,
    )

    # Long plain text: use markdown fit rendering (> 40 chars)
    if len(text) > PLAIN_LINE_FIT_MAX_CHARS:
        text_var = f"{var_prefix}_txt"
        body_var = f"{var_prefix}_body"
        sanitized = sanitize_typst_markdown_for_compile(text)
        justify = _typst_bool(block.justify_text)
        first_indent = _typst_first_line_indent_length(block)

        if block.fit_to_box and not block.font_size_locked:
            fit_call = _block_markdown_fit_call(
                block,
                text_var,
                min(content_fit_height, block.fit_max_height_pt or content_fit_height),
                font_style,
                first_indent,
                justify,
                markdown=sanitized,
            )
            body_expr = f"set text(fill: {text_fill}); {fit_call}"
        else:
            body_expr = _typst_plain_text_expr(
                text_var, block.font_size_pt, block.leading_em,
                block.font_weight, font_style, text_fill, first_indent, justify,
                markdown=sanitized,
            )

        parts = [
            f"#let {text_var} = \"{_escape_sanitized_text_for_typst(sanitized)}\"",
            _typst_markdown_block(
                body_var, layout_width, layout_height, block_fill, body_expr,
                content_top_inset_pt=content_top,
                content_bottom_inset_pt=content_bottom),
            _typst_place_flow_block(
                x0, y0, width, height, body_var, var_prefix, rotation,
                fill_arg=block_fill if rotation in {90, 180, 270} else "",
            ).rstrip(),
        ]
        return "\n".join(parts) + "\n"

    # User-locked font: render at exact size (no width auto-scaling).
    if block.font_size_locked:
        text_var = f"{var_prefix}_txt"
        box_var = f"{var_prefix}_box"
        sanitized_locked = sanitize_typst_markdown_for_compile(text)
        render_expr = _typst_cmarker_render_expr_for_markdown(text_var, sanitized_locked)
        indent_prefix = _typst_first_line_indent_h_stmt(
            _typst_first_line_indent_length(block),
        )
        body_inner = (
            f"{{ {_typst_set_text_attrs(block.font_size_pt, block.font_weight, font_style, text_fill)}; "
            f"{indent_prefix}{render_expr} }}"
        )
        body_expr = _typst_pad_vertical_expr(body_inner, content_top, content_bottom)
        lines = [
            f"#let {text_var} = \"{_escape_sanitized_text_for_typst(sanitized_locked)}\"",
            f"#let {box_var} = block(width: {layout_width}pt, height: {layout_height}pt{block_fill})"
            f"[#{{ {body_expr} }}]",
            _typst_place_flow_block(
                x0, y0, width, height, box_var, var_prefix, rotation,
                fill_arg=block_fill if rotation in {90, 180, 270} else "",
            ).rstrip(),
        ]
        return "\n".join(lines) + "\n"

    # Short text: use a simple box with auto-scaling (measure + place in one context).
    text_var = f"{var_prefix}_txt"
    base_var = f"{var_prefix}_base"
    inner_var = f"{var_prefix}_inner"
    outer_var = f"{var_prefix}_bbox"
    rotate_fill = block_fill if rotation in {90, 180, 270} else ""
    sanitized_short = sanitize_typst_markdown_for_compile(text)
    render_expr = _typst_cmarker_render_expr_for_markdown(text_var, sanitized_short)
    indent_prefix = _typst_first_line_indent_h_stmt(
        _typst_first_line_indent_length(block),
    )
    short_body_inner = (
        "set text(size: scaled-font, weight: "
        f"\"{block.font_weight}\"{_typst_font_style_clause(font_style)}, fill: {text_fill}); "
        f"{indent_prefix}{render_expr}"
    )
    short_body_expr = _typst_pad_vertical_expr(
        short_body_inner, content_top, content_bottom,
    )

    lines = [
        f"#let {text_var} = \"{_escape_sanitized_text_for_typst(sanitized_short)}\"",
        f"#let {base_var} = box[#{{ {_typst_set_text_attrs(block.font_size_pt, block.font_weight, font_style, text_fill)}; "
        f"{indent_prefix}{render_expr} }}]",
        "#context {",
        f"  let base-size = measure({base_var})",
        f"  let scaled-font = if base-size.width > {layout_width}pt "
        f"{{ {block.font_size_pt}pt * ({layout_width}pt / base-size.width) }} "
        f"else {{ {block.font_size_pt}pt }}",
        f"  let {inner_var} = block(width: {layout_width}pt, height: {layout_height}pt{block_fill})"
        f"[#{{ {short_body_expr} }}]",
        *_typst_emit_flow_placement_in_context(
            x0=x0,
            y0=y0,
            bbox_w=width,
            bbox_h=height,
            inner_var=inner_var,
            outer_var=outer_var,
            rotation=rotation,
            fill_arg=rotate_fill,
        ),
        "}",
    ]
    return "\n".join(lines) + "\n"


def _render_preserved_line_boxes(block_id: str, block: RenderBlock,
                                  text_fill: str, block_fill: str) -> str:
    """Render blocks with preserved line breaks using per-line fit."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    parts: list[str] = []
    font_weight = block.font_weight or "regular"
    font_style = getattr(block, "font_style", None) or "normal"
    rotation = getattr(block, "rotation", 0) or 0
    var_prefix = block_id.replace("-", "_")

    # Render cover rect if present (preserved line box overlay)
    if block.use_cover_fill and block.cover_bbox and len(block.cover_bbox) == 4:
        cover_name = f"{var_prefix}_cover"
        cx0, cy0, cx1, cy1 = block.cover_bbox
        cw = max(MIN_BLOCK_SIZE_PT, cx1 - cx0)
        ch = max(MIN_BLOCK_SIZE_PT, cy1 - cy0)
        parts.extend([
            f"#let {cover_name} = rect(width: {cw}pt, height: {ch}pt, fill: {_typst_rgb(block.cover_fill)})",
            _typst_place_context(cx0, cy0, cover_name).rstrip(),
        ])

    line_placements: list[str] = []
    for index, line in enumerate(block.preserved_line_boxes or []):
        if len(line.bbox) != 4 or not str(line.text or "").strip():
            continue
        lx0, ly0, lx1, ly1 = line.bbox
        lw = max(MIN_BLOCK_SIZE_PT, lx1 - lx0)
        lh = max(MIN_BLOCK_SIZE_PT, ly1 - ly0)
        line_name = f"{var_prefix}_line_{index}_md"
        body_name = f"{var_prefix}_line_{index}_body"
        if block.font_size_locked or getattr(block, "leading_em_locked", False):
            line_md = sanitize_typst_markdown_for_compile(str(line.text or ""))
            body_expr = _typst_plain_markdown_expr(
                line_name,
                block.font_size_pt,
                block.leading_em,
                font_weight,
                font_style,
                text_fill,
                0.0,
                "false",
                markdown=line_md,
            )
            parts.append(f"#let {line_name} = \"{_escape_sanitized_text_for_typst(line_md)}\"")
            parts.append(
                _typst_markdown_block(body_name, lw, lh, block_fill, body_expr).rstrip())
            if rotation in {90, 180, 270}:
                line_placements.append(
                    f"  place(top + left, dx: {round(lx0 - x0, 1)}pt, "
                    f"dy: {round(ly0 - y0, 1)}pt, {body_name})"
                )
            else:
                parts.append(
                    _typst_place_context(lx0, ly0, body_name).rstrip())
            continue
        max_font_pt = round(max(1.0, min(block.font_size_pt, lh * 0.86)), 2)
        min_font_pt = round(max(1.0, min(max_font_pt, lh * 0.58)), 2)
        line_md = sanitize_typst_markdown_for_compile(str(line.text or ""))
        parts.extend([
            f"#let {line_name} = \"{_escape_sanitized_text_for_typst(line_md)}\"",
            _typst_markdown_block(
                body_name, lw, lh, block_fill,
                f"set text(fill: {text_fill}); "
                f"{_typst_single_line_fit_call(line_name, max_font_pt, min_font_pt, lw, lh, font_weight, font_style, 'false', use_mitex=markdown_line_safe_for_mitex(line_md))}").rstrip(),
        ])
        if rotation in {90, 180, 270}:
            line_placements.append(
                f"  place(top + left, dx: {round(lx0 - x0, 1)}pt, "
                f"dy: {round(ly0 - y0, 1)}pt, {body_name})"
            )
        else:
            parts.append(_typst_place_context(lx0, ly0, body_name).rstrip())

    if rotation in {90, 180, 270} and line_placements:
        inner_var = f"{var_prefix}_inner"
        parts.extend([
            f"#let {inner_var} = block(width: {round(width, 1)}pt, "
            f"height: {round(height, 1)}pt{block_fill})[",
            "#context {",
            *line_placements,
            "}]",
            _typst_place_flow_block(
                x0, y0, width, height, inner_var, var_prefix, rotation,
                fill_arg=block_fill,
            ).rstrip(),
        ])

    return "\n".join(parts) + ("\n" if parts else "")


def _render_markdown_block(block_id: str, block: RenderBlock,
                           *, force_opaque: bool = False) -> str:
    """Render a markdown/formula block using Typst's cmarker package."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    rotation = getattr(block, "rotation", 0) or 0
    layout_width, layout_height = _rotated_reading_dimensions(width, height, rotation)
    text_fill = _typst_rgb(block.text_color)
    var_prefix = block_id.replace("-", "_")
    block_fill = _block_fill_arg(block, force_opaque=force_opaque)
    rotate_fill = block_fill if rotation in {90, 180, 270} else ""

    text = block.markdown_text or block.plain_text
    if not text.strip():
        return ""

    # Sanitize markdown to avoid known Typst compilation pitfalls
    text = sanitize_typst_markdown_for_compile(text)

    md_var = f"{var_prefix}_md"
    body_var = f"{var_prefix}_body"
    justify = _typst_bool(block.justify_text)
    first_indent = _typst_first_line_indent_length(block)
    font_style = getattr(block, "font_style", None) or "normal"

    # Formula safety vertical insets (multi-line edge margin lives in shrunk inner_bbox)
    content_top, content_bottom, content_fit_height = _block_formula_layout_insets_pt(
        block, layout_height, text,
    )

    # TOC entries (dedicated TOC entry dispatch)
    if block.toc_entries:
        return _render_toc_entries(block_id, block, text_fill)

    # Preserved line boxes
    if block.preserve_line_breaks and block.preserved_line_boxes:
        return _render_preserved_line_boxes(block_id, block, text_fill, block_fill)

    # Preserved line breaks with newlines
    if block.preserve_line_breaks and "\n" in text:
        line_values = [line.strip() for line in text.splitlines() if line.strip()]
        return _render_preserved_line_breaks_block(
            block_id,
            block,
            line_values=line_values,
            text_fill=text_fill,
            block_fill=block_fill,
            font_style=font_style,
            justify=justify,
            layout_width=layout_width,
            layout_height=layout_height,
            content_top=content_top,
            content_bottom=content_bottom,
            x0=x0,
            y0=y0,
            width=width,
            height=height,
            rotation=rotation,
            rotate_fill=rotate_fill,
        )

    if block.fit_to_box and not block.font_size_locked:
        if block.fit_single_line:
            # Single-line fit mode (block renderer path)
            max_font_pt = max(block.font_size_pt, block.fit_max_font_size_pt or block.font_size_pt)
            min_font_pt = max(1.0, min(block.fit_min_font_size_pt or block.font_size_pt, block.font_size_pt))
            fit_w = max(layout_width, block.fit_target_width_pt) if block.fit_target_width_pt > 0 else layout_width
            fit_h = max(MIN_BLOCK_SIZE_PT, min(content_fit_height, block.fit_max_height_pt or content_fit_height))
            shift_up = max(0.0, block.fit_shift_up_pt)
            fit_call = _typst_single_line_fit_call(
                md_var, max_font_pt, min_font_pt, fit_w, fit_h,
                block.font_weight, font_style, justify,
                use_mitex=markdown_line_safe_for_mitex(text),
            )
            parts = [
                f"#let {md_var} = \"{_escape_sanitized_text_for_typst(text)}\"",
                _typst_markdown_block(
                    body_var, fit_w, layout_height, block_fill,
                    f"set text(fill: {text_fill}); {fit_call}",
                    content_top_inset_pt=content_top,
                    content_bottom_inset_pt=content_bottom),
                _typst_place_flow_block(
                    x0, y0, width, height, body_var, var_prefix, rotation,
                    fill_arg=rotate_fill, dy_offset=-shift_up,
                ).rstrip(),
            ]
            return "\n".join(parts) + "\n"

        # Multi-line fit mode
        fit_call = _block_markdown_fit_call(
            block,
            md_var,
            content_fit_height,
            font_style,
            first_indent,
            justify,
            markdown=text,
        )
        parts = [
            f"#let {md_var} = \"{_escape_sanitized_text_for_typst(text)}\"",
            _typst_markdown_block(
                body_var, layout_width, layout_height, block_fill,
                f"set text(fill: {text_fill}); {fit_call}",
                content_top_inset_pt=content_top,
                content_bottom_inset_pt=content_bottom),
            _typst_place_flow_block(
                x0, y0, width, height, body_var, var_prefix, rotation,
                fill_arg=rotate_fill,
            ).rstrip(),
        ]
        return "\n".join(parts) + "\n"
    else:
        # Static rendering with leading (_typst_plain_markdown_expr)
        body_expr = _typst_plain_markdown_expr(
            md_var, block.font_size_pt, block.leading_em,
            block.font_weight, font_style, text_fill, first_indent, justify,
            markdown=text,
        )
        parts = [
            f"#let {md_var} = \"{_escape_sanitized_text_for_typst(text)}\"",
            _typst_markdown_block(
                body_var, layout_width, layout_height, block_fill, body_expr,
                content_top_inset_pt=content_top,
                content_bottom_inset_pt=content_bottom),
            _typst_place_flow_block(
                x0, y0, width, height, body_var, var_prefix, rotation,
                fill_arg=rotate_fill,
            ).rstrip(),
        ]
        return "\n".join(parts) + "\n"


def _render_cover_block(block_id: str, block: RenderBlock) -> str:
    """Render a white cover rect to hide original text visually."""
    var_prefix = block_id.replace("-", "_")

    # Use cover_bbox if available, otherwise fall back to inner_bbox
    if hasattr(block, 'cover_bbox') and block.cover_bbox and len(block.cover_bbox) == 4:
        x0, y0, x1, y1 = block.cover_bbox
    else:
        x0, y0, x1, y1 = block.inner_bbox

    width = max(4.0, x1 - x0)
    height = max(4.0, y1 - y0)
    fill = _typst_rgb(block.cover_fill)
    cover_var = f"{var_prefix}_cover"

    parts = [
        f"#let {cover_var} = rect(width: {width}pt, height: {height}pt, fill: {fill})",
        _typst_place_context(x0, y0, cover_var),
    ]
    return "\n".join(parts) + "\n"


def _render_image_block(block_id: str, block: RenderBlock) -> str:
    """Render an embedded chart/table body image at the layout bbox."""
    if not block.image_rel_path:
        return ""

    x0, y0, x1, y1 = block.inner_bbox
    width = max(4.0, x1 - x0)
    height = max(4.0, y1 - y0)
    rel_path = block.image_rel_path.replace("\\", "/")
    var_prefix = block_id.replace("-", "_")
    img_var = f"{var_prefix}_img"

    parts = [
        f'#let {img_var} = image("{rel_path}", width: {round(width, 1)}pt, '
        f"height: {round(height, 1)}pt, fit: \"contain\")",
        _typst_place_context(x0, y0, img_var),
    ]
    return "\n".join(parts) + "\n"


def parse_table_rows_for_render(table_text: str) -> list:
    """Parse markdown, HTML, or TSV table text into a 2D cell grid."""
    rows = _parse_markdown_table(table_text)
    if rows:
        return rows
    if "<table" in table_text.lower():
        html_rows, _ = TableUtils.parse_html_table(table_text)
        if html_rows:
            return html_rows
    return TableUtils.parse_markdown_table(table_text)


def _parse_table_rows(table_text: str) -> list:
    """Backward-compatible alias for table row parsing."""
    return parse_table_rows_for_render(table_text)


def _parse_markdown_table(table_text: str) -> list:
    """Parse markdown table text into a 2D list of cell strings.

    Returns a list of rows, where each row is a list of cell strings.
    The header separator row (|---|---|) is excluded.
    Returns empty list if parsing fails.
    """
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []

    rows: list = []
    for i, line in enumerate(lines):
        if not line.startswith("|") and not line.endswith("|"):
            continue
        # Strip leading/trailing pipe
        line = line[1:] if line.startswith("|") else line
        line = line[:-1] if line.endswith("|") else line
        # Split cells, respecting escaped pipes
        cells = _split_table_cells(line)
        # Skip separator rows (e.g. ---, :---, ---:) at any position.
        if cells and all(
            re.match(r"^:?-{2,}:?$", c.strip()) for c in cells if c.strip()
        ):
            continue
        rows.append([c.strip() for c in cells])
    return rows


def _split_table_cells(cell_line: str) -> list:
    """Split a table row string into cells, respecting escaped pipes."""
    cells: list = []
    current: list = []
    i = 0
    while i < len(cell_line):
        if cell_line[i] == "\\" and i + 1 < len(cell_line) and cell_line[i + 1] == "|":
            current.append("|")
            i += 2
        elif cell_line[i] == "|":
            cells.append("".join(current))
            current = []
            i += 1
        else:
            current.append(cell_line[i])
            i += 1
    cells.append("".join(current))
    return cells


TABLE_CELL_PAD_PT = 4.0
TABLE_HEADER_FONT_SCALE = 0.95
TABLE_MIN_FONT_PT = 5.5
TABLE_MAX_FONT_PT = 12.0
TABLE_ROW_HEIGHT_FACTOR = 1.55
TABLE_HEADER_COLOR = (0.95, 0.95, 0.98)
TABLE_STROKE_COLOR = (0.45, 0.45, 0.45)
TABLE_LATIN_CHAR_WIDTH_RATIO = 0.55
TABLE_CJK_CHAR_WIDTH_RATIO = 1.0
TABLE_COLUMN_MIN_WIDTH_PT = 8.0
TABLE_COLUMN_FILL_THRESHOLD = 0.92
TABLE_ROW_MIN_HEIGHT_PT = 6.0
TABLE_ROW_LINE_HEIGHT_FACTOR = 1.35


def _typst_table_stroke_arg(stroke_pt: float) -> str:
    """Return Typst table stroke argument for full grid lines."""
    if stroke_pt <= 0:
        return "stroke: none,"
    return (
        f"stroke: {round(stroke_pt, 2)}pt + {_typst_rgb(TABLE_STROKE_COLOR)},"
    )


def _typst_table_stroke_color_expr(stroke_pt: float) -> str:
    """Return a Typst stroke expression for partial table borders."""
    return f"{round(stroke_pt, 2)}pt + {_typst_rgb(TABLE_STROKE_COLOR)}"


def _typst_table_stroke_callback(
    style: str,
    *,
    stroke_pt: float,
    row_count: int,
    col_count: int,
) -> str:
    """Return Typst stroke rule for horizontal-only or outer border styles."""
    stroke = _typst_table_stroke_color_expr(stroke_pt)
    last_row = max(0, row_count - 1)
    last_col = max(0, col_count - 1)
    if style == TABLE_BORDER_STYLE_HORIZONTAL:
        return (
            f"stroke: (x, y) => ("
            f"top: {stroke}, bottom: {stroke}, left: none, right: none),"
        )
    if style == TABLE_BORDER_STYLE_OUTER:
        return (
            f"stroke: (x, y) => ("
            f"top: if y == 0 {{ {stroke} }} else {{ none }}, "
            f"bottom: if y == {last_row} {{ {stroke} }} else {{ none }}, "
            f"left: if x == 0 {{ {stroke} }} else {{ none }}, "
            f"right: if x == {last_col} {{ {stroke} }} else {{ none }}),"
        )
    return "stroke: none,"


def _is_cjk_char(ch: str) -> bool:
    """True for common CJK unified ideographs used in table width estimates."""
    if not ch:
        return False
    code = ord(ch)
    return (
        0x2E80 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x3400 <= code <= 0x4DBF
    )


def _strip_math_delimiters_for_width_estimate(text: str) -> str:
    """Remove $...$ wrappers so width heuristics use visible characters only."""
    body = str(text or "")
    body = re.sub(r"\$\$([^$]+)\$\$", r"\1", body)
    body = re.sub(r"\$([^$]+)\$", r"\1", body)
    return body.strip()


def _estimate_table_cell_width_pt(text: str, font_pt: float) -> float:
    """Heuristic cell content width (pt) for column sizing."""
    if font_pt <= 0:
        font_pt = TABLE_MIN_FONT_PT
    visible = _strip_math_delimiters_for_width_estimate(text)
    if not visible:
        return TABLE_COLUMN_MIN_WIDTH_PT

    cjk_count = sum(1 for ch in visible if _is_cjk_char(ch))
    latin_count = max(0, len(visible) - cjk_count)
    text_width = (
        latin_count * font_pt * TABLE_LATIN_CHAR_WIDTH_RATIO
        + cjk_count * font_pt * TABLE_CJK_CHAR_WIDTH_RATIO
    )
    return max(TABLE_COLUMN_MIN_WIDTH_PT, text_width + TABLE_CELL_PAD_PT * 2)


def _estimate_table_column_widths_pt(
    rows: list,
    col_count: int,
    font_pt: float,
) -> list[float]:
    """Return per-column natural width (pt) from the widest cell in each column."""
    widths = [TABLE_COLUMN_MIN_WIDTH_PT] * col_count
    for row in rows:
        for col_idx in range(min(col_count, len(row))):
            cell_w = _estimate_table_cell_width_pt(row[col_idx], font_pt)
            widths[col_idx] = max(widths[col_idx], cell_w)
    return widths


def _column_fr_weights(widths: list[float]) -> list[int]:
    """Convert column natural widths to integer Typst fr weights."""
    total = sum(widths)
    if total <= 0:
        return [1] * len(widths)
    scale = 100.0 / total
    return [max(1, int(round(width * scale))) for width in widths]


def _resolve_table_column_widths_pt(
    rows: list,
    col_count: int,
    layout_width: float,
    font_pt: float,
    *,
    inset_pt: float = TABLE_CELL_PAD_PT,
) -> list[float]:
    """Resolve per-column widths (pt) so the table spans the layout bbox width."""
    avail_width = max(MIN_BLOCK_SIZE_PT, layout_width - inset_pt * 2)
    natural = _estimate_table_column_widths_pt(rows, col_count, font_pt)
    total = sum(natural)
    if total <= 0:
        even = avail_width / max(1, col_count)
        return [even] * col_count

    if total < avail_width * TABLE_COLUMN_FILL_THRESHOLD:
        scale = avail_width / total
        scaled = [
            max(TABLE_COLUMN_MIN_WIDTH_PT, width * scale)
            for width in natural
        ]
        drift = avail_width - sum(scaled)
        if abs(drift) > 0.05:
            scaled[-1] = max(TABLE_COLUMN_MIN_WIDTH_PT, scaled[-1] + drift)
        return scaled

    fr_weights = _column_fr_weights(natural)
    fr_total = sum(fr_weights)
    return [avail_width * weight / fr_total for weight in fr_weights]


def _table_extra_vertical_stroke_budget_pt(
    border_style: str,
    row_count: int,
    stroke_pt: float,
) -> float:
    """Reserve vertical space consumed by table.hline / outer rules outside row tracks."""
    if stroke_pt <= 0:
        return 0.0
    if is_booktabs_border_style(border_style):
        return 3.0 * stroke_pt
    if border_style == TABLE_BORDER_STYLE_HORIZONTAL:
        return max(0, row_count + 1) * stroke_pt
    if border_style == TABLE_BORDER_STYLE_OUTER:
        return 2.0 * stroke_pt
    return 0.0


def _estimate_table_row_natural_heights_pt(
    rows: list,
    col_count: int,
    column_widths_pt: list[float],
    font_pt: float,
    header_font_pt: float,
    *,
    inset_pt: float = TABLE_CELL_PAD_PT,
    header_row_count: int = 1,
) -> list[float]:
    """Estimate per-row natural height (pt) from wrapped cell content."""
    heights: list[float] = []
    for row_idx, row in enumerate(rows):
        row_font = header_font_pt if row_idx < header_row_count else font_pt
        line_h = row_font * TABLE_ROW_LINE_HEIGHT_FACTOR
        row_h = TABLE_ROW_MIN_HEIGHT_PT
        for col_idx in range(min(col_count, len(row))):
            col_w = column_widths_pt[min(col_idx, len(column_widths_pt) - 1)]
            inner_w = max(1.0, col_w - inset_pt * 2)
            cell_w = _estimate_table_cell_width_pt(row[col_idx], row_font)
            wrap_lines = max(1, int(math.ceil(cell_w / inner_w)))
            cell_h = wrap_lines * line_h + inset_pt * 2
            row_h = max(row_h, cell_h)
        heights.append(row_h)
    return heights


def _resolve_table_row_heights_pt(
    rows: list,
    col_count: int,
    layout_height: float,
    column_widths_pt: list[float],
    font_pt: float,
    header_font_pt: float,
    *,
    inset_pt: float = TABLE_CELL_PAD_PT,
    border_style: str = TABLE_BORDER_STYLE_GRID,
    stroke_pt: float = 0.0,
) -> list[float]:
    """Resolve per-row heights (pt) so the table spans the layout bbox height."""
    row_count = len(rows)
    stroke_budget = _table_extra_vertical_stroke_budget_pt(
        border_style, row_count, stroke_pt,
    )
    avail_height = max(
        MIN_BLOCK_SIZE_PT,
        layout_height - inset_pt * 2 - stroke_budget,
    )
    header_row_count = (
        min(booktabs_header_row_count(border_style), row_count)
        if is_booktabs_border_style(border_style)
        else 1
    )
    natural = _estimate_table_row_natural_heights_pt(
        rows,
        col_count,
        column_widths_pt,
        font_pt,
        header_font_pt,
        inset_pt=inset_pt,
        header_row_count=header_row_count,
    )
    total = sum(natural)
    if total <= 0:
        even = avail_height / max(1, row_count)
        return [even] * row_count

    scale = avail_height / total
    scaled = [
        max(TABLE_ROW_MIN_HEIGHT_PT, height * scale)
        for height in natural
    ]
    drift = avail_height - sum(scaled)
    if abs(drift) > 0.05:
        scaled[-1] = max(TABLE_ROW_MIN_HEIGHT_PT, scaled[-1] + drift)
    return scaled


def _typst_table_columns_spec(
    rows: list,
    col_count: int,
    layout_width: float,
    font_pt: float,
    *,
    inset_pt: float = TABLE_CELL_PAD_PT,
) -> str:
    """Build Typst table column sizing that fills the layout bbox width."""
    widths = _resolve_table_column_widths_pt(
        rows, col_count, layout_width, font_pt, inset_pt=inset_pt,
    )
    return "(" + ", ".join(f"{round(width, 1)}pt" for width in widths) + ")"


def _typst_table_rows_spec(
    rows: list,
    col_count: int,
    layout_height: float,
    column_widths_pt: list[float],
    font_pt: float,
    header_font_pt: float,
    *,
    inset_pt: float = TABLE_CELL_PAD_PT,
    border_style: str = TABLE_BORDER_STYLE_GRID,
    stroke_pt: float = 0.0,
) -> str:
    """Build Typst table row sizing that fills the layout bbox height."""
    heights = _resolve_table_row_heights_pt(
        rows,
        col_count,
        layout_height,
        column_widths_pt,
        font_pt,
        header_font_pt,
        inset_pt=inset_pt,
        border_style=border_style,
        stroke_pt=stroke_pt,
    )
    return "(" + ", ".join(f"{round(height, 1)}pt" for height in heights) + ")"


def _typst_table_cell_content(
    cell_var: str,
    *,
    row_idx: int,
    font_pt: float,
    header_font_pt: float,
    text_fill: str,
    border_style: str,
    is_header_row: bool,
) -> str:
    """Build one Typst table cell body expression."""
    body_expr = _typst_cmarker_render_expr(cell_var)
    use_header_fill = (
        is_header_row and border_style == TABLE_BORDER_STYLE_GRID
    )
    weight = "bold" if is_header_row else "regular"
    size_pt = header_font_pt if is_header_row else font_pt
    inner = (
        f"set text(size: {size_pt}pt, weight: \"{weight}\""
        f", fill: {text_fill}); {body_expr}"
    )
    if use_header_fill:
        return (
            f"table.cell(fill: {_typst_rgb(TABLE_HEADER_COLOR)})"
            f"[#{{ {inner} }}]"
        )
    return f"[#{{ {inner} }}]"


def _typst_booktabs_title_cell_expr(
    cell_var: str,
    *,
    row_idx: int,
    colspan: int,
    header_font_pt: float,
    data_font_pt: float,
    text_fill: str,
    stroke_pt: float,
    draw_bottom_rule: bool,
) -> str:
    """Build one booktabs title cell, merging colspan and optional bottom rule."""
    inner_content = _typst_table_cell_content(
        cell_var,
        row_idx=row_idx,
        font_pt=data_font_pt,
        header_font_pt=header_font_pt,
        text_fill=text_fill,
        border_style=TABLE_BORDER_STYLE_BOOKTABS,
        is_header_row=True,
    )
    if colspan <= 1 and not draw_bottom_rule:
        return inner_content

    cell_args: list[str] = []
    if colspan > 1:
        cell_args.append(f"colspan: {colspan}")
    if draw_bottom_rule and stroke_pt > 0:
        stroke = _typst_table_stroke_color_expr(stroke_pt)
        cell_args.append(f"stroke: (bottom: {stroke})")
    if not cell_args:
        return inner_content
    return f"table.cell({', '.join(cell_args)}){inner_content}"


def _typst_table_booktabs_items(
    rows: list,
    *,
    var_prefix: str,
    stroke_pt: float,
    header_font_pt: float,
    data_font_pt: float,
    text_fill: str,
    cell_cache: _TableCellVarCache,
    header_row_count: int = 1,
) -> list:
    """Emit booktabs-style table items: toprule, header, midrule, body, bottomrule."""
    stroke = _typst_table_stroke_color_expr(stroke_pt)
    items: list = []
    if stroke_pt > 0:
        items.append(f"  table.hline(stroke: {stroke}),")

    effective_header_rows = max(1, min(header_row_count, len(rows)))
    header_parts: list = []
    for row_idx in range(effective_header_rows):
        title_groups = group_adjacent_equal_row_cells(rows[row_idx])
        draw_bottom_rule = row_idx < effective_header_rows - 1
        for text, colspan in title_groups:
            cell_var = cell_cache.bind(text)
            header_parts.append(
                _typst_booktabs_title_cell_expr(
                    cell_var,
                    row_idx=row_idx,
                    colspan=colspan,
                    header_font_pt=header_font_pt,
                    data_font_pt=data_font_pt,
                    text_fill=text_fill,
                    stroke_pt=stroke_pt,
                    draw_bottom_rule=draw_bottom_rule and colspan > 1,
                )
            )
    items.append("  table.header(")
    items.append("    " + ", ".join(header_parts) + ",")
    items.append("  ),")

    if stroke_pt > 0:
        items.append(f"  table.hline(stroke: {stroke}),")

    body_cells: list = []
    for row_idx, row in enumerate(rows[effective_header_rows:], start=effective_header_rows):
        for cell in row:
            cell_var = cell_cache.bind(cell)
            body_cells.append(
                _typst_table_cell_content(
                    cell_var,
                    row_idx=row_idx,
                    font_pt=data_font_pt,
                    header_font_pt=header_font_pt,
                    text_fill=text_fill,
                    border_style=TABLE_BORDER_STYLE_BOOKTABS,
                    is_header_row=False,
                )
            )
    if body_cells:
        items.append("  " + ", ".join(body_cells) + ",")

    if stroke_pt > 0:
        items.append(f"  table.hline(stroke: {stroke}),")
    return items


def _estimate_table_font_pt(
    *,
    layout_width: float,
    layout_height: float,
    row_count: int,
    col_count: int,
    rows: list,
    block_font_pt: float,
    border_style: str,
) -> float:
    """Estimate a table font size that uses the reading-oriented bbox."""
    total_chars = sum(len(c) for r in rows for c in r)
    avg_chars_per_cell = max(1, total_chars / max(1, row_count * col_count))
    pad = TABLE_CELL_PAD_PT * 2
    avail_width = max(MIN_BLOCK_SIZE_PT, layout_width - pad * col_count)
    avail_height = max(MIN_BLOCK_SIZE_PT, layout_height - pad * row_count)
    font_from_width = avail_width / max(1, avg_chars_per_cell * 0.55)
    row_factor = (
        1.35
        if is_booktabs_border_style(border_style)
        or border_style
        in {
            TABLE_BORDER_STYLE_HORIZONTAL,
            TABLE_BORDER_STYLE_OUTER,
            TABLE_BORDER_STYLE_NONE,
        }
        else TABLE_ROW_HEIGHT_FACTOR
    )
    font_from_height = avail_height / max(1, row_count * row_factor)
    return max(
        TABLE_MIN_FONT_PT,
        min(
            TABLE_MAX_FONT_PT,
            block_font_pt,
            font_from_width,
            font_from_height,
        ),
    )


def _render_table_block(block_id: str, block: RenderBlock) -> str:
    """Render a translated table using Typst #table() at the block bbox."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    rotation = getattr(block, "rotation", 0) or 0
    layout_width, layout_height = _rotated_reading_dimensions(width, height, rotation)
    text_fill = _typst_rgb(block.text_color)
    var_prefix = block_id.replace("-", "_")

    table_text = block.markdown_text or block.plain_text
    if not table_text.strip():
        return ""

    rows = block.table_rows if block.table_rows else _parse_table_rows(table_text)
    if not rows or not rows[0]:
        snippet = table_text.strip().replace("\n", " ")[:120]
        unified_logger.warning(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Table block {block_id}: failed to parse table body "
            f"(chars={len(table_text)}, snippet={snippet!r})",
        )
        return ""

    col_count = max(len(r) for r in rows)
    if col_count == 0:
        return ""

    for r in rows:
        while len(r) < col_count:
            r.append("")

    row_count = len(rows)
    table_stroke_pt = max(
        0.0,
        float(getattr(block, "table_stroke_pt", DEFAULT_TABLE_STROKE_PT)),
    )
    border_style = resolve_table_border_style(
        getattr(block, "table_border_style", TABLE_BORDER_STYLE_GRID),
        stroke_pt=table_stroke_pt,
    )

    target_font_pt = _estimate_table_font_pt(
        layout_width=layout_width,
        layout_height=layout_height,
        row_count=row_count,
        col_count=col_count,
        rows=rows,
        block_font_pt=block.font_size_pt,
        border_style=border_style,
    )

    header_font_pt = round(target_font_pt * TABLE_HEADER_FONT_SCALE, 1)
    data_font_pt = round(target_font_pt, 1)

    cell_cache = _TableCellVarCache(var_prefix)
    cell_lines: list = []
    if is_booktabs_border_style(border_style):
        cell_lines = _typst_table_booktabs_items(
            rows,
            var_prefix=var_prefix,
            stroke_pt=table_stroke_pt,
            header_font_pt=header_font_pt,
            data_font_pt=data_font_pt,
            text_fill=text_fill,
            cell_cache=cell_cache,
            header_row_count=booktabs_header_row_count(border_style),
        )
    else:
        total_cells = sum(len(r) for r in rows)
        cell_index = 0
        for row_idx, row in enumerate(rows):
            for cell in row:
                cell_var = cell_cache.bind(cell)
                comma = "," if cell_index < total_cells - 1 else ""
                cell_index += 1
                cell_lines.append(
                    "  "
                    + _typst_table_cell_content(
                        cell_var,
                        row_idx=row_idx,
                        font_pt=data_font_pt,
                        header_font_pt=header_font_pt,
                        text_fill=text_fill,
                        border_style=border_style,
                        is_header_row=row_idx == 0,
                    )
                    + comma
                )
    cell_let_lines = cell_cache.let_lines

    provisional_inset = TABLE_CELL_PAD_PT
    column_widths_pt = _resolve_table_column_widths_pt(
        rows,
        col_count,
        layout_width,
        data_font_pt,
        inset_pt=provisional_inset,
    )
    row_heights_pt = _resolve_table_row_heights_pt(
        rows,
        col_count,
        layout_height,
        column_widths_pt,
        data_font_pt,
        header_font_pt,
        inset_pt=provisional_inset,
        border_style=border_style,
        stroke_pt=table_stroke_pt,
    )
    avg_row_h = sum(row_heights_pt) / max(1, len(row_heights_pt))
    inset_pt = round(
        min(
            TABLE_CELL_PAD_PT,
            max(0.25, (avg_row_h - data_font_pt) / 2 - 0.25),
        ),
        2,
    )
    column_widths_pt = _resolve_table_column_widths_pt(
        rows,
        col_count,
        layout_width,
        data_font_pt,
        inset_pt=inset_pt,
    )
    row_heights_pt = _resolve_table_row_heights_pt(
        rows,
        col_count,
        layout_height,
        column_widths_pt,
        data_font_pt,
        header_font_pt,
        inset_pt=inset_pt,
        border_style=border_style,
        stroke_pt=table_stroke_pt,
    )
    columns_str = "(" + ", ".join(
        f"{round(width, 1)}pt" for width in column_widths_pt
    ) + ")"
    rows_spec = "(" + ", ".join(
        f"{round(height, 1)}pt" for height in row_heights_pt
    ) + ")"

    if border_style == TABLE_BORDER_STYLE_GRID:
        stroke_arg = _typst_table_stroke_arg(table_stroke_pt)
    elif border_style == TABLE_BORDER_STYLE_NONE:
        stroke_arg = "stroke: none,"
    else:
        stroke_arg = _typst_table_stroke_callback(
            border_style,
            stroke_pt=table_stroke_pt,
            row_count=row_count,
            col_count=col_count,
        )

    table_var = f"{var_prefix}_table"
    inner_var = f"{var_prefix}_inner"

    parts: list = [
        *cell_let_lines,
        f"#let {table_var} = table(",
        f"  columns: {columns_str},",
        f"  rows: {rows_spec},",
    ]
    parts.extend([
        f"  {stroke_arg}",
        f"  inset: {inset_pt}pt,",
        f"  align: (left + horizon,) * {col_count},",
    ])
    parts.extend(cell_lines)
    parts.append(")")

    fill_arg = _block_fill_arg(block, force_opaque=block.opaque_fill)
    bbox_w = round(width, 1)
    bbox_h = round(height, 1)
    layout_w = round(layout_width, 1)
    layout_h = round(layout_height, 1)

    outer_var = f"{var_prefix}_bbox"
    parts.append(
        f"#let {inner_var} = block(width: {layout_w}pt, height: {layout_h}pt)"
        f"[#{{ {table_var} }}]"
    )
    if rotation in {90, 180, 270}:
        parts.extend(
            _typst_emit_rotated_placement(
                x0=x0,
                y0=y0,
                bbox_w=bbox_w,
                bbox_h=bbox_h,
                inner_var=inner_var,
                outer_var=outer_var,
                rotation=rotation,
                fill_arg=fill_arg,
            )
        )
    else:
        parts.extend([
            f"#let {outer_var} = block(width: {bbox_w}pt, height: {bbox_h}pt"
            f"{fill_arg})[#{{ {table_var} }}]",
            "#context {",
            f"  place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, "
            f"{outer_var})",
            "}",
        ])

    return "\n".join(parts) + "\n"


def render_block_to_typst(block_id: str, block: RenderBlock,
                          *, force_opaque: bool = False) -> str:
    """Generate the Typst source lines for a single RenderBlock (overlay dispatch logic)."""
    if block.skip_reason:
        return ""
    if block.render_kind == "image":
        return _render_image_block(block_id, block)
    if block.use_cover_fill:
        return _render_cover_block(block_id, block)
    if block.render_kind == "table":
        return _render_table_block(block_id, block)
    if block.render_kind in ("plain", "plain_line"):
        return _render_plain_block(block_id, block, force_opaque=force_opaque)
    return _render_markdown_block(block_id, block, force_opaque=force_opaque)


# --- Helper functions for Typst source ---

# ---- Typst helper functions for preserve-layout overlay ----

FIT_SIZE_FN = '''
#let pdftr_fit_size(lo, hi, eps, fits) = {
  if hi - lo <= eps {
    lo
  } else {
    let mid = lo + (hi - lo) / 2
    if fits(mid) {
      pdftr_fit_size(mid, hi, eps, fits)
    } else {
      pdftr_fit_size(lo, mid, eps, fits)
    }
  }
}
'''

FIT_LEADING_FN = '''
#let pdftr_fit_leading(lo, hi, eps, fits) = {
  if hi - lo <= eps {
    lo
  } else {
    let mid = lo + (hi - lo) / 2
    if fits(mid) {
      pdftr_fit_leading(mid, hi, eps, fits)
    } else {
      pdftr_fit_leading(lo, mid, eps, fits)
    }
  }
}
'''

FIT_FLOOR_SIZE_FN = '''
#let pdftr_floor_size(value, floor) = if value < floor { floor } else { value }
'''

FIT_FLOOR_LEADING_FN = '''
#let pdftr_floor_leading(value, floor) = if value < floor { floor } else { value }
'''

FIT_SINGLE_LINE_FN = '''
#let pdftr_fit_single_line_markdown(markdown, max_size: 10pt, min_size: 9pt, fit_width: none, fit_height: none, weight: "regular", style: "normal", justify: false, eps: 0.08pt, use_mitex: true) = {
  layout(size => {
    let render-md() = if use_mitex { cmarker.render(markdown, math: mitex) } else { cmarker.render(markdown) }
    let allowed-width = if fit_width == none { size.width } else { calc.min(size.width, fit_width) }
    let allowed-height = if fit_height == none { size.height } else { calc.min(size.height, fit_height) }
    let render(text_size) = box(inset: 0pt, clip: false)[#{
      set text(size: text_size, weight: weight, style: style)
      set par(leading: 1em, justify: justify)
      render-md()
    }]
    let fits(text_size) = {
      let measured = measure(render(text_size))
      measured.width <= allowed-width and measured.height <= allowed-height
    }
    let chosen-size = if fits(max_size) {
      max_size
    } else {
      pdftr_fit_size(min_size, max_size, eps, size_pt => fits(size_pt))
    }
    box(width: allowed-width, height: allowed-height, inset: 0pt, clip: false)[#{
      set text(size: chosen-size, weight: weight, style: style)
      set par(leading: 1em, justify: justify)
      render-md()
    }]
  })
}
'''

FIT_MARKDOWN_FN = '''
#let pdftr_fit_markdown(markdown, max_size: 10pt, min_size: 9pt, max_leading: 0.66em, min_leading: 0.54em, fit_height: none, weight: "regular", style: "normal", first_line_indent: 0pt, justify: false, eps: 0.08pt, use_mitex: true) = {
  layout(size => {
    let render-md() = if use_mitex { cmarker.render(markdown, math: mitex) } else { cmarker.render(markdown) }
    let allowed-height = if fit_height == none { size.height } else { calc.min(size.height, fit_height) }
    let render(text_size, leading) = block(width: size.width)[#{
      set text(size: text_size, weight: weight, style: style)
      set par(leading: leading, justify: justify)
      if first_line_indent > 0pt { h(first_line_indent) }
      render-md()
    }]
    let fits(text_size, leading) = measure(width: size.width, render(text_size, leading)).height <= allowed-height
    if fits(max_size, max_leading) {
      render(max_size, max_leading)
    } else {
      let fallback_min_size = min_size
      let fallback_min_leading = min_leading
      let emergency_min_size = calc.max(4.2pt, min_size * 0.65)
      let emergency_min_leading = calc.max(0.20em, min_leading * 0.75)
      let chosen_leading = if fits(min_size, max_leading) { max_leading } else { min_leading }
      let chosen_size = if not fits(min_size, chosen_leading) {
        let fallback_leading = fallback_min_leading
        let emergency_leading = emergency_min_leading
        if not fits(fallback_min_size, fallback_leading) {
          pdftr_fit_size(emergency_min_size, fallback_min_size, eps, size_pt => fits(size_pt, emergency_leading))
        } else {
          pdftr_fit_size(fallback_min_size, min_size, eps, size_pt => fits(size_pt, fallback_leading))
        }
      } else {
        pdftr_fit_size(min_size, max_size, eps, size_pt => fits(size_pt, chosen_leading))
      }
      let leading_floor = if fits(chosen_size, min_leading) { min_leading } else if fits(chosen_size, emergency_min_leading) { emergency_min_leading } else { emergency_min_leading }
      let leading_cap = if fits(chosen_size, max_leading) { max_leading } else { chosen_leading }
      let final_leading = if fits(chosen_size, leading_cap) {
        leading_cap
      } else {
        pdftr_fit_leading(leading_floor, leading_cap, 0.01em, leading => fits(chosen_size, leading))
      }
      render(chosen_size, final_leading)
    }
  })
}
'''

FIT_MARKDOWN_FIXED_LEADING_FN = '''
#let pdftr_fit_markdown_fixed_leading(markdown, max_size: 10pt, min_size: 9pt, leading: 1.25em, fit_height: none, weight: "regular", style: "normal", first_line_indent: 0pt, justify: false, eps: 0.08pt, use_mitex: true) = {
  layout(size => {
    let render-md() = if use_mitex { cmarker.render(markdown, math: mitex) } else { cmarker.render(markdown) }
    let allowed-height = if fit_height == none { size.height } else { calc.min(size.height, fit_height) }
    let render(text_size) = block(width: size.width)[#{
      set text(size: text_size, weight: weight, style: style)
      set par(leading: leading, justify: justify)
      if first_line_indent > 0pt { h(first_line_indent) }
      render-md()
    }]
    let fits(text_size) = measure(width: size.width, render(text_size)).height <= allowed-height
    let chosen_size = if fits(max_size) {
      max_size
    } else {
      let fallback_min_size = min_size
      let emergency_min_size = calc.max(4.2pt, min_size * 0.65)
      if not fits(fallback_min_size) {
        pdftr_fit_size(emergency_min_size, fallback_min_size, eps, fits)
      } else {
        pdftr_fit_size(fallback_min_size, max_size, eps, fits)
      }
    }
    render(chosen_size)
  })
}
'''


def build_typst_overlay_source(
    page_specs: List[RenderPageSpec],
    font_family: str = "Noto Sans CJK SC",
) -> str:
    """
    Build complete Typst source for a multi-page overlay document.

    Args:
        page_specs: List of page specifications with blocks to render
        font_family: Typst font family name for text rendering

    Returns:
        Complete Typst source code as a string
    """
    lines = [TYPST_PRELUDE]
    lines.append("// Typst packages for markdown and math rendering")
    lines.extend(typst_preview_import_lines())
    lines.append("")

    lines.append(f'#set text(font: "{font_family}", size: 10pt, fallback: true)')
    lines.append("")

    lines.append("// Fit-to-box helper functions")
    lines.append(FIT_SIZE_FN)
    lines.append(FIT_LEADING_FN)
    lines.append(FIT_FLOOR_SIZE_FN)
    lines.append(FIT_FLOOR_LEADING_FN)
    lines.append(FIT_SINGLE_LINE_FN)
    lines.append(FIT_MARKDOWN_FN)
    lines.append(FIT_MARKDOWN_FIXED_LEADING_FN)
    lines.append("")

    total_pages = len(page_specs)
    total_blocks = sum(len(spec.blocks) for spec in page_specs)
    unified_logger.info(
        LogModule.RESTOR,
        f"[TYPST_OVERLAY] Emitting Typst source for {total_blocks} block(s) "
        f"across {total_pages} page(s)",
    )
    page_emit_started = time.perf_counter()
    for page_idx, spec in enumerate(page_specs):
        page_block_count = 0
        lines.append(
            f"#set page(width: {spec.page_width_pt}pt, "
            f"height: {spec.page_height_pt}pt, "
            f"margin: 0pt, fill: none)"
        )

        for block_idx, block in enumerate(spec.blocks):
            block_id = f"p{page_idx}_{block.block_id}_{block_idx}"
            block_started = time.perf_counter()
            block_source = render_block_to_typst(block_id, block)
            block_elapsed = time.perf_counter() - block_started
            if block_elapsed >= EMIT_SLOW_BLOCK_THRESHOLD_S:
                cell_count = 0
                if block.table_rows:
                    cell_count = sum(len(row) for row in block.table_rows)
                raw_text = block.markdown_text or block.plain_text or ""
                text_len = len(raw_text)
                preview = raw_text.replace("\n", " ")[:80]
                unified_logger.info(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] Slow emit block {block.block_id} "
                    f"(kind={block.render_kind}, chars={text_len}, "
                    f"cells={cell_count}, fit_to_box={block.fit_to_box}, "
                    f"preserve_line_breaks={block.preserve_line_breaks}, "
                    f"preview={preview!r}) took {block_elapsed:.2f}s "
                    f"on page {page_idx + 1}",
                )
            if block_source.strip():
                lines.append(block_source)
                page_block_count += 1

        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Emitted page {page_idx + 1}/{total_pages} "
            f"({page_block_count} block(s)) in "
            f"{time.perf_counter() - page_emit_started:.2f}s",
        )
        page_emit_started = time.perf_counter()

        # Page break between pages
        if page_idx + 1 < total_pages:
            lines.append("#pagebreak()")
            lines.append("")

    return "\n".join(lines) + "\n"


def build_typst_background_source(
    page_specs: List[RenderPageSpec],
    background_pdf_path: Path,
    font_family: str = "Noto Sans CJK SC",
    work_dir: Path | None = None,
) -> str:
    """
    Build Typst source for background rendering mode.

    In this mode, each page embeds the original PDF page as a background
    image, then overlays translated text on top. This preserves all
    original visual elements (charts, lines, decorative graphics).

    Args:
        page_specs: List of page specifications
        background_pdf_path: Path to the cleaned source PDF
        font_family: Typst font family name
        work_dir: Working directory for relative path calculation

    Returns:
        Complete Typst source code as a string
    """
    import os
    if work_dir is None:
        work_dir = background_pdf_path.parent
    source_rel = os.path.relpath(background_pdf_path, work_dir)

    lines = [TYPST_PRELUDE]
    lines.extend(typst_preview_import_lines())
    lines.append("")
    lines.append(f'#set text(font: "{font_family}", size: 10pt, fallback: true)')
    lines.append("")
    lines.append(FIT_SIZE_FN)
    lines.append(FIT_LEADING_FN)
    lines.append(FIT_FLOOR_SIZE_FN)
    lines.append(FIT_FLOOR_LEADING_FN)
    lines.append(FIT_SINGLE_LINE_FN)
    lines.append(FIT_MARKDOWN_FN)
    lines.append(FIT_MARKDOWN_FIXED_LEADING_FN)
    lines.append("")

    total_pages = len(page_specs)
    for page_idx, spec in enumerate(page_specs):
        lines.append(
            f"#set page(width: {spec.page_width_pt}pt, "
            f"height: {spec.page_height_pt}pt, "
            f"margin: 0pt, fill: none)"
        )

        # Embed the original page as background image
        source_page_idx = spec.page_index + 1  # Typst uses 1-based page indexing
        lines.append(
            f'#place(top + left, dx: 0pt, dy: 0pt, '
            f'image("{source_rel}", page: {source_page_idx}, '
            f'width: {spec.page_width_pt}pt))'
        )

        for block_idx, block in enumerate(spec.blocks):
            block_id = f"bgp{page_idx}_{block.block_id}_{block_idx}"
            force_opaque = background_embed_force_opaque(block, spec.blocks)
            block_source = render_block_to_typst(
                block_id, block, force_opaque=force_opaque,
            )
            if block_source.strip():
                lines.append(block_source)

        if page_idx + 1 < total_pages:
            lines.append("#pagebreak()")
            lines.append("")

    return "\n".join(lines) + "\n"
