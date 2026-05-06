# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Normalize LaTeX fragments inside Markdown before Pandoc (DOCX/PDF).

Pandoc's texmath reader is stricter than full XeLaTeX. Common issues:
- \\tag {n} (space before brace) -> parse failures
- Display $$...$$ with ", t \\in ..." or ", \\forall ..." before \\tag -> unexpected \\tag
- Bare "s. t.:" (subject to) prefix confusing the math lexer before \\sum
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Optional

from logger import unified_logger as logger
from logger.logger import LogModule

# ```tex / ```latex (or ~~~): when body is exactly one $$...$$, unwrap for Pandoc math (PDF/DOCX pipeline).
TEX_LATEX_FENCE_LANGS = frozenset({"tex", "latex"})


def parse_opening_markdown_fence_language(line: str) -> str:
    """First info word on an opening ``` or ~~~ line, lowercased; empty if bare fence."""
    stripped = line.strip()
    if stripped.startswith("```"):
        after = stripped[3:].strip()
    elif stripped.startswith("~~~"):
        after = stripped[3:].strip()
    else:
        return ""
    if not after:
        return ""
    return after.split()[0].lower()


def extract_display_math_inner_from_tex_fence_body(body: str) -> Optional[str]:
    """If fenced body is exactly one $$...$$ display block, return inner LaTeX; else None."""
    t = body.strip()
    if not t.startswith("$$"):
        return None
    parts = t.split("$$")
    if len(parts) != 3:
        return None
    if parts[0].strip() or parts[2].strip():
        return None
    inner = parts[1].strip()
    return inner if inner else None


def unwrap_tex_latex_fences_to_display_math(md: str) -> str:
    """Replace ```tex / ```latex / ~~~ blocks whose body is a single $$...$$ with bare display math.

    Pandoc treats fenced blocks as code; $$ inside ```tex is not math until the fence is removed.
    """
    if not md or ("```" not in md and "~~~" not in md):
        return md
    lines = md.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        lang = parse_opening_markdown_fence_language(line)
        if lang in TEX_LATEX_FENCE_LANGS:
            j = i + 1
            while j < n:
                st = lines[j].strip()
                if st.startswith("```") or st.startswith("~~~"):
                    break
                j += 1
            if j >= n:
                out.append(line)
                i += 1
                continue
            body = "".join(lines[i + 1 : j])
            inner = extract_display_math_inner_from_tex_fence_body(body)
            if inner is not None:
                prev = inner[:120] + ("..." if len(inner) > 120 else "")
                logger.info(
                    LogModule.RESTOR,
                    f"[MD-NORMALIZE] Unwrapped tex/latex fence to $$ display math for Pandoc (preview={prev!r})",
                )
                out.append("$$\n")
                out.append(inner)
                if not inner.endswith("\n"):
                    out.append("\n")
                out.append("$$\n")
                i = j + 1
                continue
            out.extend(lines[i : j + 1])
            i = j + 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def transform_markdown_outside_fences(md: str, fn: Callable[[str], str]) -> str:
    """Apply fn to each region of md that is outside ```/~~~ code fences."""
    if not md:
        return md
    return _normalize_outside_fences(md, fn)


def normalize_md_math_for_pandoc_export(md: str) -> str:
    """
    Apply deterministic fixes so Pandoc is more likely to parse display math and OMML.

    Safe to run on full Markdown: code fences are skipped so literals are unchanged.
    """
    if not md:
        return md
    md = unwrap_tex_latex_fences_to_display_math(md)
    return _normalize_outside_fences(md, _normalize_math_segment_plain)


def _normalize_math_segment_plain(text: str) -> str:
    """Normalize one contiguous region outside code fences."""
    t = _normalize_tag_spacing(text)
    t = _normalize_display_dollar_blocks(t)
    t = _normalize_bracket_display_blocks(t)
    return t


def _normalize_tag_spacing(text: str) -> str:
    # \\tag {23} -> \\tag{23} (texmath / OMML path)
    return re.sub(r"\\tag\s+\{", r"\\tag{", text)


def _apply_tag_body_texmath_fixes(body: str) -> str:
    """
    When a display block uses \\tag{...}, texmath often rejects \\tag if the main
    formula ends with ", ..." plus another clause (t \\in, \\forall, etc.).
    """
    if r"\tag" not in body:
        return body
    body = re.sub(r",\s*t\s*\\in\b", r" \\quad t \\in", body)
    # "X, X \\in" (e.g. "t \\in T_R, T_R \\in T_C \\tag") — same identifier twice before \\in
    body = re.sub(
        r"((?:[A-Za-z]+(?:_\{[^}]+\}|_[A-Za-z0-9]+)*))\s*,\s*\1\s*\\in\b",
        r"\1 \\quad \1 \\in",
        body,
    )
    # ", \\forall" after `}`, `]`, `)` — not commas inside "\\left[ A, B \\right]"
    body = re.sub(r"([}\])])\s*,\s*\\forall\b", r"\1 \\quad \\forall", body)
    # Bare subscript before ", \\forall" (e.g. "R_d, \\forall m" has no closing `}` on R_d)
    body = re.sub(r"(_[A-Za-z0-9]+)\s*,\s*\\forall\b", r"\1 \\quad \\forall", body)
    # "s. t.," / "s. t.:" — not inside \\mathrm{s.t.:} (avoid double-wrapping)
    body = re.sub(r"(?i)(?<!\{)s\.\s*t\.\s*,", r"\\mathrm{s.t.:},", body)
    body = re.sub(r"(?i)(?<!\{)s\.\s*t\.:", r"\\mathrm{s.t.:}", body)
    return body


def _normalize_display_dollar_blocks(text: str) -> str:
    """Process each $$...$$ block: texmath-friendly tweaks when \\tag is present."""
    out: list[str] = []
    pos = 0
    while True:
        start = text.find("$$", pos)
        if start < 0:
            out.append(text[pos:])
            break
        out.append(text[pos:start])
        end = text.find("$$", start + 2)
        if end < 0:
            out.append(text[start:])
            break
        body = _apply_tag_body_texmath_fixes(text[start + 2 : end])
        out.append("$$")
        out.append(body)
        out.append("$$")
        pos = end + 2
    return "".join(out)


def _normalize_bracket_display_blocks(text: str) -> str:
    """Process each \\[...\\] block like $$ blocks."""
    out: list[str] = []
    pos = 0
    while True:
        start = text.find("\\[", pos)
        if start < 0:
            out.append(text[pos:])
            break
        out.append(text[pos:start])
        end = text.find("\\]", start + 2)
        if end < 0:
            out.append(text[start:])
            break
        body = _apply_tag_body_texmath_fixes(text[start + 2 : end])
        out.append("\\[")
        out.append(body)
        out.append("\\]")
        pos = end + 2
    return "".join(out)


def _normalize_outside_fences(md: str, fn) -> str:
    """
    Apply fn(text) to each region outside fenced code blocks (``` / ~~~).
    """
    lines = md.splitlines(keepends=True)
    out: list[str] = []
    buf: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.lstrip()
        is_fence = stripped.startswith("```") or stripped.startswith("~~~")
        if is_fence:
            if not in_fence:
                if buf:
                    out.append(fn("".join(buf)))
                    buf = []
                in_fence = True
                out.append(line)
            else:
                in_fence = False
                out.append(line)
            continue
        if in_fence:
            out.append(line)
        else:
            buf.append(line)
    if buf:
        out.append(fn("".join(buf)))
    return "".join(out)
