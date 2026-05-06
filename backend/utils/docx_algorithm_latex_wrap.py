# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Wrap bare LaTeX in Markdown so Pandoc emits OMML (Word equations) for DOCX.

Pseudo-code / algorithm lines often contain \\mathrm, \\gets, subscripts but no $...$.
We only run outside code fences; heuristics are conservative (skip uncertain lines).
"""

from __future__ import annotations

import re

from utils.math_md_normalize import transform_markdown_outside_fences

# Lines that mix plain English control words with math: only partial wrap (see below).
_CONTROL_SKIP_FULL_WRAP = re.compile(
    r"\b(else)\b|^\s*\d+\s*:\s*(end\s+(if|while))\b",
    re.I | re.M,
)


def _wrap_require_ensure_header(head: str) -> str:
    if "$" in head or "Require:" not in head or "Ensure:" not in head:
        return head
    mr = re.match(r"(Require:\s*)(.+?)(\s+Ensure:\s*)(.+)$", head.strip(), re.DOTALL)
    if not mr:
        return head
    r, e = mr.group(2).strip(), mr.group(4).strip()
    return f"{mr.group(1)}${r}${mr.group(3)}${e}$"


def _wrap_numbered_body(prefix: str, body: str) -> str:
    """prefix ends with 'N: '; body is the rest of the line."""
    body = body.strip()
    if not body or "$" in body:
        return prefix + body
    if "\\" not in body and "_" not in body:
        return prefix + body

    # while <math> do [comment]
    m = re.match(r"while\s+(.+?)\s+do(\s+.*)?$", body, re.I | re.DOTALL)
    if m and ("\\" in m.group(1) or "_" in m.group(1)):
        mid, tail = m.group(1).strip(), m.group(2) or ""
        return f"{prefix}while ${mid}$ do{tail}"

    # if <math> then [comment]
    m = re.match(r"if\s+(.+?)\s+then(\s+.*)?$", body, re.I | re.DOTALL)
    if m and ("\\" in m.group(1) or "_" in m.group(1)):
        mid, tail = m.group(1).strip(), m.group(2) or ""
        return f"{prefix}if ${mid}$ then{tail}"

    if _CONTROL_SKIP_FULL_WRAP.search(body):
        return prefix + body

    # Plain numbered LaTeX line (no leading while/if we matched above)
    if re.search(r"\b(while|if)\b", body, re.I):
        return prefix + body

    return prefix + f"${body}$"


def _split_require_ensure_and_step(line: str) -> str | None:
    """
    If line contains Require:/Ensure: and a trailing ' N: ...' step, split and wrap both parts.
    Returns new multi-line string or None if not applicable.
    """
    if "Require:" not in line or "$" in line:
        return None
    m = re.search(r"\s+(?=\d+\s*:\s)", line)
    if not m:
        return None
    if m.start() <= line.index("Require:"):
        return None
    head = line[: m.start()].rstrip()
    tail = line[m.start() :].lstrip()
    if "Ensure:" not in head:
        return None
    hw = _wrap_require_ensure_header(head)
    tm = re.match(r"^(\s*\d+\s*:\s*)(.*)$", tail)
    if not tm:
        return hw
    tw = _wrap_numbered_body(tm.group(1), tm.group(2))
    return hw + "\n" + tw


def _process_one_line(line: str) -> str:
    split = _split_require_ensure_and_step(line)
    if split is not None:
        return split
    st = line.strip()
    if st.startswith("Require:") and "Ensure:" in st and "$" not in line:
        return _wrap_require_ensure_header(st)

    m = re.match(r"^(\s*\d+\s*:\s*)(.*)$", line)
    if not m:
        return line
    return _wrap_numbered_body(m.group(1), m.group(2))


def _wrap_algorithm_segment(text: str) -> str:
    # Only process segments that look like LaTeX-heavy algorithm text
    if "\\" not in text and "_" not in text:
        return text
    if not re.search(
        r"(?i)ALGORITHM|\\gets|\\mathrm|\\mathbf|\\triangleright|\\theta|\\sum|\\underset",
        text,
    ):
        if not re.search(r"\d+\s*:\s*.*\\", text):
            return text

    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        out.append(_process_one_line(line))
    return "\n".join(out)


def wrap_bare_latex_for_docx_algorithms(md: str) -> str:
    """
    Wrap bare LaTeX on algorithm-style lines so Pandoc DOCX uses equation objects where possible.
    """
    if not md:
        return md
    return transform_markdown_outside_fences(md, _wrap_algorithm_segment)
