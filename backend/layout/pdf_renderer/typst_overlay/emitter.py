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
  - Formulas are rendered through Typst's native $...$ math mode
"""

import re
from pathlib import Path
from typing import List

from layout.pdf_renderer.typst_overlay.formula_safety import formula_safety_insets_pt
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


def _typst_place_context(x_pt: float, y_pt: float, body_name: str) -> str:
    """Generate a Typst #context { place(...) } call for overlay placement."""
    return (f"#context {{\n"
            f"  place(top + left, dx: {round(x_pt, 1)}pt, dy: {round(y_pt, 1)}pt, {body_name})\n"
            f"}}\n")


def _typst_markdown_block(body_name: str, width: float, height: float,
                          block_fill: str, body_expr: str,
                          content_top_inset_pt: float = 0.0,
                          content_bottom_inset_pt: float = 0.0) -> str:
    """Generate a Typst #let body = block(...) expression with optional pad insets."""
    if content_top_inset_pt > 0 or content_bottom_inset_pt > 0:
        body_expr = (
            f"pad(top: {max(0.0, content_top_inset_pt)}pt, "
            f"bottom: {max(0.0, content_bottom_inset_pt)}pt)"
            f"[#{{ {body_expr} }}]"
        )
    return (f"#let {body_name} = block(width: {width}pt, height: {height}pt"
            f"{block_fill})[#{{ {body_expr} }}]\n")


def _typst_markdown_fit_call(md_name: str, max_font_size_pt: float,
                             min_font_size_pt: float, max_leading_em: float,
                             min_leading_em: float, fit_height_pt: float,
                             font_weight: str, font_style: str,
                             first_line_indent_pt: float,
                             justify_text: str) -> str:
    """Generate a pdftr_fit_markdown(...) call expression."""
    indent = f", first_line_indent: {first_line_indent_pt}pt" if first_line_indent_pt > 0 else ""
    style_clause = _typst_font_style_clause(font_style)
    style_arg = f', style: "{font_style or "normal"}"' if style_clause else ""
    return (
        f"pdftr_fit_markdown({md_name}, max_size: {max_font_size_pt}pt, "
        f"min_size: {min_font_size_pt}pt, max_leading: {max_leading_em}em, "
        f"min_leading: {min_leading_em}em, fit_height: {fit_height_pt}pt, "
        f"weight: \"{font_weight}\"{style_arg}{indent}, justify: {justify_text})"
    )


def _typst_single_line_fit_call(md_name: str, max_font_pt: float,
                                min_font_pt: float, width_pt: float,
                                height_pt: float, font_weight: str,
                                font_style: str, justify_text: str) -> str:
    """Generate a pdftr_fit_single_line_markdown(...) call expression."""
    style_arg = f', style: "{font_style or "normal"}"'
    return (
        f"pdftr_fit_single_line_markdown({md_name}, max_size: {max_font_pt}pt, "
        f"min_size: {min_font_pt}pt, fit_width: {width_pt}pt, "
        f"fit_height: {height_pt}pt, weight: \"{font_weight}\"{style_arg}, "
        f"justify: {justify_text})"
    )


def _typst_plain_markdown_expr(md_name: str, font_size_pt: float,
                                leading_em: float, font_weight: str,
                                font_style: str, text_fill: str,
                                first_line_indent_pt: float,
                                justify_text: str) -> str:
    """Generate static markdown rendering expression with line leading."""
    return (
        f"{_typst_set_text_attrs(font_size_pt, font_weight, font_style, text_fill)}; "
        f"set par(leading: {leading_em}em, justify: {justify_text}); "
        f"if {first_line_indent_pt}pt > 0pt {{ h({first_line_indent_pt}pt) }}; "
        f"cmarker.render({md_name}, math: mitex)"
    )


def _typst_plain_text_expr(text_name: str, font_size_pt: float,
                           leading_em: float, font_weight: str,
                           font_style: str, text_fill: str,
                           first_line_indent_pt: float,
                           justify_text: str) -> str:
    """Generate static plain text rendering expression with leading."""
    return (
        f"{_typst_set_text_attrs(font_size_pt, font_weight, font_style, text_fill)}; "
        f"set par(leading: {leading_em}em, justify: {justify_text}); "
        f"if {first_line_indent_pt}pt > 0pt {{ h({first_line_indent_pt}pt) }}; "
        f"{text_name}"
    )


def sanitize_typst_markdown_for_compile(markdown: str) -> str:
    """Sanitize markdown to avoid common Typst compilation errors in overlay blocks."""
    text = str(markdown or "")
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:circled|textcircled)\s*R\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:circled|textcircled)\s*\{\s*R\s*\}\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*\\(?:textregistered|registered)\s*\}\s*\$", "®", text)
    text = re.sub(r"\$\s*\^\s*\{\s*®\s*\}\s*\$", "®", text)
    text = text.replace("$^®$", "®").replace("$^{®}$", "®")
    text = text.replace(r"$^\circled{R}$", "®").replace(r"$^\textcircled{R}$", "®")
    text = re.sub(r"\\langlen\b", r"\\langle n", text)
    text = text.replace(r"\circled{\times}", r"\otimes")
    text = text.replace(r"\circled{\parallel}", r"\circ")
    text = text.replace(r"\textcircled{\times}", r"\otimes")
    text = text.replace(r"\textcircled{\parallel}", r"\circ")
    # Remove Markdown image references (e.g., ![alt](path)) to avoid Typst compilation errors
    # when image files are not available. For overlay rendering, image/table/chart visuals
    # should remain on the original PDF, not re-rendered through Typst.
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
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
            f'#let {title_name} = "{_escape_typst_string(prefix_title)}"',
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
        f"set par(leading: {leading_em}em, justify: {justify_text}); line }}]))"
    )


def _render_plain_block(block_id: str, block: RenderBlock,
                        *, force_opaque: bool = False) -> str:
    """Render a simple plain-text block (short text, no markdown)."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    text_fill = _typst_rgb(block.text_color)
    var_prefix = block_id.replace("-", "_")
    block_fill = _block_fill_arg(block, force_opaque=force_opaque)

    text = block.plain_text or block.markdown_text
    if not text.strip():
        return ""

    font_style = getattr(block, "font_style", None) or "normal"

    # Long plain text: use markdown fit rendering (> 40 chars)
    if len(text) > PLAIN_LINE_FIT_MAX_CHARS:
        text_var = f"{var_prefix}_txt"
        body_var = f"{var_prefix}_body"
        sanitized = sanitize_typst_markdown_for_compile(text)
        justify = _typst_bool(block.justify_text)
        first_indent = max(0.0, block.first_line_indent_pt)
        indent_arg = f", first_line_indent: {first_indent}pt" if first_indent > 0 else ""

        if block.fit_to_box and not block.font_size_locked:
            style_arg = f', style: "{font_style}"'
            fit_call = (
                f"pdftr_fit_markdown({text_var}, "
                f"max_size: {block.font_size_pt}pt, "
                f"min_size: {block.fit_min_font_size_pt}pt, "
                f"max_leading: {block.leading_em}em, "
                f"min_leading: {block.fit_min_leading_em}em, "
                f"fit_height: {min(height * 0.9, block.fit_max_height_pt or height)}pt, "
                f"weight: \"{block.font_weight}\"{style_arg}{indent_arg}, "
                f"justify: {justify})"
            )
            body_expr = f"set text(fill: {text_fill}); {fit_call}"
        else:
            body_expr = _typst_plain_text_expr(
                text_var, block.font_size_pt, block.leading_em,
                block.font_weight, font_style, text_fill, first_indent, justify)

        parts = [
            f"#let {text_var} = \"{_escape_typst_string(sanitized)}\"",
            _typst_markdown_block(body_var, width, height, block_fill, body_expr),
            _typst_place_context(x0, y0, body_var),
        ]
        return "\n".join(parts) + "\n"

    # User-locked font: render at exact size (no width auto-scaling).
    if block.font_size_locked:
        text_var = f"{var_prefix}_txt"
        box_var = f"{var_prefix}_box"
        lines = [
            f"#let {text_var} = \"{_escape_typst_string(text)}\"",
            f"#let {box_var} = block(width: {width}pt, height: {height}pt{block_fill})"
            f"[#{{ {_typst_set_text_attrs(block.font_size_pt, block.font_weight, font_style, text_fill)}; {text_var} }}]",
            _typst_place_context(x0, y0, box_var),
        ]
        return "\n".join(lines) + "\n"

    # Short text: use a simple box with auto-scaling
    text_var = f"{var_prefix}_txt"
    base_var = f"{var_prefix}_base"
    scaled_var = f"{var_prefix}_scaled"

    lines = [
        f"#let {text_var} = \"{_escape_typst_string(text)}\"",
        f"#let {base_var} = box[#{{ {_typst_set_text_attrs(block.font_size_pt, block.font_weight, font_style, text_fill)}; {text_var} }}]",
        "#context {",
        f"  let base-size = measure({base_var})",
        f"  let scaled-font = if base-size.width > {width}pt "
        f"{{ {block.font_size_pt}pt * ({width}pt / base-size.width) }} "
        f"else {{ {block.font_size_pt}pt }}",
        f"  let {scaled_var} = block(width: {width}pt, height: {height}pt{block_fill})"
        f"[#{{ set text(size: scaled-font, weight: "
        f"\"{block.font_weight}\"{_typst_font_style_clause(font_style)}, fill: {text_fill}); {text_var} }}]",
        f"  place(top + left, dx: {round(x0, 1)}pt, dy: {round(y0, 1)}pt, "
        f"{scaled_var})",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _render_preserved_line_boxes(block_id: str, block: RenderBlock,
                                  text_fill: str, block_fill: str) -> str:
    """Render blocks with preserved line breaks using per-line fit."""
    parts: list[str] = []
    font_weight = block.font_weight or "regular"
    font_style = getattr(block, "font_style", None) or "normal"
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

    for index, line in enumerate(block.preserved_line_boxes or []):
        if len(line.bbox) != 4 or not str(line.text or "").strip():
            continue
        lx0, ly0, lx1, ly1 = line.bbox
        lw = max(MIN_BLOCK_SIZE_PT, lx1 - lx0)
        lh = max(MIN_BLOCK_SIZE_PT, ly1 - ly0)
        line_name = f"{var_prefix}_line_{index}_md"
        body_name = f"{var_prefix}_line_{index}_body"
        if block.font_size_locked:
            body_expr = _typst_plain_markdown_expr(
                line_name,
                block.font_size_pt,
                block.leading_em,
                font_weight,
                font_style,
                text_fill,
                0.0,
                "false",
            )
            parts.extend([
                f"#let {line_name} = \"{_escape_typst_string(line.text)}\"",
                _typst_markdown_block(body_name, lw, lh, block_fill, body_expr),
                _typst_place_context(lx0, ly0, body_name).rstrip(),
            ])
            continue
        max_font_pt = round(max(1.0, min(block.font_size_pt, lh * 0.86)), 2)
        min_font_pt = round(max(1.0, min(max_font_pt, lh * 0.58)), 2)
        parts.extend([
            f"#let {line_name} = \"{_escape_typst_string(line.text)}\"",
            _typst_markdown_block(
                body_name, lw, lh, block_fill,
                f"set text(fill: {text_fill}); "
                f"{_typst_single_line_fit_call(line_name, max_font_pt, min_font_pt, lw, lh, font_weight, font_style, 'false')}"),
            _typst_place_context(lx0, ly0, body_name).rstrip(),
        ])
    return "\n".join(parts) + ("\n" if parts else "")


def _render_markdown_block(block_id: str, block: RenderBlock,
                           *, force_opaque: bool = False) -> str:
    """Render a markdown/formula block using Typst's cmarker package."""
    x0, y0, x1, y1 = block.inner_bbox
    width = max(MIN_BLOCK_SIZE_PT, x1 - x0)
    height = max(MIN_BLOCK_SIZE_PT, y1 - y0)
    text_fill = _typst_rgb(block.text_color)
    var_prefix = block_id.replace("-", "_")
    block_fill = _block_fill_arg(block, force_opaque=force_opaque)

    text = block.markdown_text or block.plain_text
    if not text.strip():
        return ""

    # Sanitize markdown to avoid known Typst compilation pitfalls
    text = sanitize_typst_markdown_for_compile(text)

    md_var = f"{var_prefix}_md"
    body_var = f"{var_prefix}_body"
    justify = _typst_bool(block.justify_text)
    first_indent = max(0.0, block.first_line_indent_pt)
    font_style = getattr(block, "font_style", None) or "normal"

    # Calculate formula safety insets (block renderer path)
    formula_insets = formula_safety_insets_pt(
        text,
        block.math_map,
        font_size_pt=block.font_size_pt,
        box_height_pt=height,
    )
    content_fit_height = max(MIN_BLOCK_SIZE_PT, height - formula_insets.total_pt)

    # TOC entries (dedicated TOC entry dispatch)
    if block.toc_entries:
        return _render_toc_entries(block_id, block, text_fill)

    # Preserved line boxes
    if block.preserve_line_breaks and block.preserved_line_boxes:
        return _render_preserved_line_boxes(block_id, block, text_fill, block_fill)

    # Preserved line breaks with newlines
    if block.preserve_line_breaks and "\n" in text:
        lines_name = f"{var_prefix}_lines"
        line_values = [line.strip() for line in text.splitlines() if line.strip()]
        body_expr = _typst_preserved_lines_expr(
            lines_name, block.font_size_pt, block.leading_em,
            block.font_weight, font_style, text_fill, justify, width)
        parts = [
            f"#let {lines_name} = (" + ", ".join(
                f"\"{_escape_typst_string(v)}\"" for v in line_values) + ("," if len(line_values) == 1 else "") + ")",
            _typst_markdown_block(
                body_var, width, height, block_fill, body_expr,
                content_top_inset_pt=formula_insets.top_pt,
                content_bottom_inset_pt=formula_insets.bottom_pt),
            _typst_place_context(x0, y0, body_var),
        ]
        return "\n".join(parts) + "\n"

    if block.fit_to_box and not block.font_size_locked:
        if block.fit_single_line:
            # Single-line fit mode (block renderer path)
            max_font_pt = max(block.font_size_pt, block.fit_max_font_size_pt or block.font_size_pt)
            min_font_pt = max(1.0, min(block.fit_min_font_size_pt or block.font_size_pt, block.font_size_pt))
            fit_w = max(width, block.fit_target_width_pt) if block.fit_target_width_pt > 0 else width
            fit_h = max(MIN_BLOCK_SIZE_PT, min(content_fit_height, block.fit_max_height_pt or content_fit_height))
            shift_up = max(0.0, block.fit_shift_up_pt)
            fit_call = _typst_single_line_fit_call(
                md_var, max_font_pt, min_font_pt, fit_w, fit_h,
                block.font_weight, font_style, justify)
            parts = [
                f"#let {md_var} = \"{_escape_typst_string(text)}\"",
                _typst_markdown_block(
                    body_var, fit_w, height, block_fill,
                    f"set text(fill: {text_fill}); {fit_call}",
                    content_top_inset_pt=formula_insets.top_pt,
                    content_bottom_inset_pt=formula_insets.bottom_pt),
                _typst_place_context(x0, y0 - shift_up, body_var),
            ]
            return "\n".join(parts) + "\n"

        # Multi-line fit mode
        fit_call = _typst_markdown_fit_call(
            md_var, block.font_size_pt, block.fit_min_font_size_pt,
            block.leading_em, block.fit_min_leading_em,
            content_fit_height, block.font_weight, font_style,
            first_indent, justify)
        parts = [
            f"#let {md_var} = \"{_escape_typst_string(text)}\"",
            _typst_markdown_block(
                body_var, width, height, block_fill,
                f"set text(fill: {text_fill}); {fit_call}",
                content_top_inset_pt=formula_insets.top_pt,
                content_bottom_inset_pt=formula_insets.bottom_pt),
            _typst_place_context(x0, y0, body_var),
        ]
        return "\n".join(parts) + "\n"
    else:
        # Static rendering with leading (_typst_plain_markdown_expr)
        body_expr = _typst_plain_markdown_expr(
            md_var, block.font_size_pt, block.leading_em,
            block.font_weight, font_style, text_fill, first_indent, justify)
        parts = [
            f"#let {md_var} = \"{_escape_typst_string(text)}\"",
            _typst_markdown_block(
                body_var, width, height, block_fill, body_expr,
                content_top_inset_pt=formula_insets.top_pt,
                content_bottom_inset_pt=formula_insets.bottom_pt),
            _typst_place_context(x0, y0, body_var),
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


def render_block_to_typst(block_id: str, block: RenderBlock,
                          *, force_opaque: bool = False) -> str:
    """Generate the Typst source lines for a single RenderBlock (overlay dispatch logic)."""
    if block.skip_reason:
        return ""
    if block.render_kind == "image":
        return _render_image_block(block_id, block)
    if block.use_cover_fill:
        return _render_cover_block(block_id, block)
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
#let pdftr_fit_single_line_markdown(markdown, max_size: 10pt, min_size: 9pt, fit_width: none, fit_height: none, weight: "regular", style: "normal", justify: false, eps: 0.08pt) = {
  layout(size => {
    let allowed-width = if fit_width == none { size.width } else { calc.min(size.width, fit_width) }
    let allowed-height = if fit_height == none { size.height } else { calc.min(size.height, fit_height) }
    let render(text_size) = box(inset: 0pt, clip: false)[#{
      set text(size: text_size, weight: weight, style: style)
      set par(leading: 1em, justify: justify)
      cmarker.render(markdown, math: mitex)
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
      cmarker.render(markdown, math: mitex)
    }]
  })
}
'''

FIT_MARKDOWN_FN = '''
#let pdftr_fit_markdown(markdown, max_size: 10pt, min_size: 9pt, max_leading: 0.66em, min_leading: 0.54em, fit_height: none, weight: "regular", style: "normal", first_line_indent: 0pt, justify: false, eps: 0.08pt) = {
  layout(size => {
    let allowed-height = if fit_height == none { size.height } else { calc.min(size.height, fit_height) }
    let render(text_size, leading) = block(width: size.width)[#{
      set text(size: text_size, weight: weight, style: style)
      set par(leading: leading, justify: justify)
      if first_line_indent > 0pt { h(first_line_indent) }
      cmarker.render(markdown, math: mitex)
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
    lines.append("#import \"@preview/cmarker:0.1.8\"")
    lines.append("#import \"@preview/mitex:0.2.6\": mitex")
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
    lines.append("")

    total_pages = len(page_specs)
    for page_idx, spec in enumerate(page_specs):
        lines.append(
            f"#set page(width: {spec.page_width_pt}pt, "
            f"height: {spec.page_height_pt}pt, "
            f"margin: 0pt, fill: none)"
        )

        for block_idx, block in enumerate(spec.blocks):
            block_id = f"p{page_idx}_{block.block_id}_{block_idx}"
            block_source = render_block_to_typst(block_id, block)
            if block_source.strip():
                lines.append(block_source)

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
    lines.append("#import \"@preview/cmarker:0.1.8\"")
    lines.append("#import \"@preview/mitex:0.2.6\": mitex")
    lines.append("")
    lines.append(f'#set text(font: "{font_family}", size: 10pt, fallback: true)')
    lines.append("")
    lines.append(FIT_SIZE_FN)
    lines.append(FIT_LEADING_FN)
    lines.append(FIT_FLOOR_SIZE_FN)
    lines.append(FIT_FLOOR_LEADING_FN)
    lines.append(FIT_SINGLE_LINE_FN)
    lines.append(FIT_MARKDOWN_FN)
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
            block_source = render_block_to_typst(block_id, block, force_opaque=True)
            if block_source.strip():
                lines.append(block_source)

        if page_idx + 1 < total_pages:
            lines.append("#pagebreak()")
            lines.append("")

    return "\n".join(lines) + "\n"
