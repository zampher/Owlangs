# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
DOCX export: normalize HTML <sup>/<sub> in Markdown before Pandoc.

Pandoc may not apply inline HTML to Word OMML when raw_html is off, or <sup> may
render inconsistently. We convert typical affiliation-style markup (digits, comma)
to Unicode superscript/subscript outside code fences.
"""

from __future__ import annotations

import re

from utils.math_md_normalize import transform_markdown_outside_fences

_SUP_TRANSLATION = str.maketrans(
    "0123456789+-=()",
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾",
)
_SUB_TRANSLATION = str.maketrans(
    "0123456789+-=()",
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎",
)


def _translate_sup_inner(inner: str) -> str | None:
    """Return Unicode superscript string, or None if inner contains unsupported chars."""
    out: list[str] = []
    for c in inner:
        if c in "0123456789+-=()":
            out.append(c.translate(_SUP_TRANSLATION))
        elif c in ", \t\n\r\v\f":
            out.append("," if c == "," else " ")
        else:
            return None
    return "".join(out)


def _translate_sub_inner(inner: str) -> str | None:
    out: list[str] = []
    for c in inner:
        if c in "0123456789+-=()":
            out.append(c.translate(_SUB_TRANSLATION))
        elif c in ", \t\n\r\v\f":
            out.append("," if c == "," else " ")
        else:
            return None
    return "".join(out)


def _replace_sup_sub_in_text(text: str) -> str:
    def sup_repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        t = _translate_sup_inner(inner)
        return t if t is not None else m.group(0)

    def sub_repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        t = _translate_sub_inner(inner)
        return t if t is not None else m.group(0)

    text = re.sub(r"(?i)<sup>([^<]*)</sup>", sup_repl, text)
    text = re.sub(r"(?i)<sub>([^<]*)</sub>", sub_repl, text)
    return text


def normalize_docx_markdown_sup_sub(md: str) -> str:
    """
    Convert <sup>/<sub> with digit/comma-style content to Unicode (outside code fences).
    Other <sup> fragments are left unchanged for Pandoc raw_html.
    """
    if not md:
        return md
    return transform_markdown_outside_fences(md, _replace_sup_sub_in_text)
