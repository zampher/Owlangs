# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Preserve HTML tables when converting to Markdown (XLSX HTML export, EPUB fragments).

- Rectangular tables without merges: GitHub-style pipe tables.
- rowspan/colspan or ragged rows: embed a minimal HTML <table> (GFM / many renderers).
"""

from __future__ import annotations

import re
from typing import Any


def _cell_span_int(cell: Any, key: str) -> int:
    v = cell.get(key)
    if v is None or str(v).strip() == "":
        return 1
    try:
        return max(1, int(str(v).strip()))
    except ValueError:
        return 1


def _table_requires_html_fragment(table: Any) -> bool:
    """Merged or ragged tables cannot be represented as a simple pipe grid."""
    for cell in table.find_all(("td", "th")):
        if _cell_span_int(cell, "rowspan") > 1 or _cell_span_int(cell, "colspan") > 1:
            return True
    rows = table.find_all("tr")
    if not rows:
        return False
    widths: list[int] = []
    for tr in rows:
        w = 0
        for cell in tr.find_all(("td", "th"), recursive=False):
            w += _cell_span_int(cell, "colspan")
        widths.append(w)
    if not widths:
        return False
    return min(widths) != max(widths)


def _strip_layout_noise_from_table_clone(table: Any) -> str:
    """Return HTML string; drop style/class etc. that bloat MD and rarely help readers."""
    from bs4 import BeautifulSoup

    clone = BeautifulSoup(str(table), "html.parser").find("table")
    if not clone:
        return ""
    drop_keys = ("style", "class", "width", "height", "bgcolor", "lang", "xml:lang", "id")
    for tag in clone.find_all(True):
        for k in list(tag.attrs):
            if k in drop_keys or str(k).startswith("data-"):
                del tag[k]
    return str(clone).strip()


def _simple_table_to_pipe_markdown(table: Any) -> str:
    """Convert a simple rectangular table to pipe-style Markdown.

    Preserves inline images inside cells by using _extract_inline_md.
    """
    from workflow.html_to_markdown_export import _extract_inline_md

    rows_out: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(("td", "th"), recursive=False)
        if not cells:
            continue
        row: list[str] = []
        for cell in cells:
            text = (
                _extract_inline_md(cell)
                .replace("\n", " ")
                .replace("|", "\\|")
                .strip()
            )
            row.append(text if text else " ")
        rows_out.append(row)
    if not rows_out:
        return ""
    ncols = max(len(r) for r in rows_out)
    norm = [r + [" "] * (ncols - len(r)) for r in rows_out]
    lines: list[str] = [
        "| " + " | ".join(norm[0]) + " |",
        "| " + " | ".join(["---"] * ncols) + " |",
    ]
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n" + "\n".join(lines) + "\n\n"


def md_table_placeholder_token(index: int) -> str:
    """
    Text-only token inserted where <table> was (before html2text).

    Must not contain '<' or '>' — BeautifulSoup serializes those as entities and
    html2text output then no longer matches angle-bracket markers, so table
    fragments never get restored (MD ends up nearly empty for large XLSX HTML).
    """
    return f"OWLANGSTBL{index:09d}"


def html_table_to_markdown_fragment(table: Any) -> str:
    """One <table> tree -> pipe markdown or embedded HTML."""
    if _table_requires_html_fragment(table):
        inner = _strip_layout_noise_from_table_clone(table)
        return "\n\n" + inner + "\n\n"
    return _simple_table_to_pipe_markdown(table)


def extract_tables_and_insert_placeholders(soup) -> list[str]:
    """
    Replace each <table> with a unique paragraph marker for html2text.

    Returns fragments in the same order as placeholder indices (deepest tables first).
    """
    fragments: list[str] = []
    tables = list(soup.find_all("table"))
    tables.sort(key=lambda t: len(list(t.parents)), reverse=True)
    for i, table in enumerate(tables):
        fragments.append(html_table_to_markdown_fragment(table))
        ph = soup.new_tag("p")
        ph.string = md_table_placeholder_token(i)
        table.replace_with(ph)
    return fragments


def restore_table_placeholders(markdown: str, fragments: list[str]) -> str:
    """Swap html2text-safe markers back to table markdown / HTML."""
    if not fragments:
        return markdown
    out = markdown
    for i, frag in enumerate(fragments):
        token = md_table_placeholder_token(i)
        token_re = re.compile(rf"\s*{re.escape(token)}\s*")
        legacy_re = re.compile(rf"\s*<<<\s*OWLANGS_MD_TABLE_{i}\s*>>>\s*")
        repl = "\n\n" + frag.strip() + "\n\n"
        if token_re.search(out):
            out = token_re.sub(repl, out, count=1)
        elif legacy_re.search(out):
            out = legacy_re.sub(repl, out, count=1)
    return out
