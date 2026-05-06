from __future__ import annotations

"""
Helpers for extracting minimal LaTeX error context from debug files.

This module used to extract rich Markdown/TeX snippets for an automatic LLM repair flow.
We now keep it lean: only extract what we need to locate the likely bad segment
(error type, error line number, and a representative token).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import re

from logger import unified_logger as logger
from logger.logger import LogModule


# LaTeX hints used to quickly detect whether a text fragment contains math/commands.
# Kept in one place so callers (segment checker, formula batch repair, etc.) can reuse it.
_LATEX_HINTS = (
    "$",
    r"\(",
    r"\[",
    r"\frac",
    r"\sum",
    r"\int",
    r"\mathbf",
    r"\mathcal",
    r"\underset",
    r"\overset",
    r"\begin{",
    r"\end{",
    r"\alpha",
    r"\beta",
    r"\gamma",
    r"\delta",
    r"\theta",
    r"\lambda",
    r"\mu",
    r"\nu",
    r"\pi",
    r"\sigma",
    r"\tau",
    r"\phi",
    r"\chi",
    r"\psi",
    r"\omega",
    r"\Gamma",
    r"\Delta",
    r"\Theta",
    r"\Lambda",
    r"\Pi",
    r"\Sigma",
    r"\Phi",
    r"\Psi",
    r"\Omega",
    r"\times",
    r"\div",
    r"\pm",
    r"\cdot",
    r"\sqrt",
    r"\leq",
    r"\geq",
    r"\neq",
    r"\approx",
    r"\equiv",
    r"\infty",
    r"\partial",
    r"\nabla",
    r"\forall",
    r"\exists",
    r"\in",
    r"\notin",
    r"\subset",
    r"\cup",
    r"\cap",
    r"\emptyset",
    r"\rightarrow",
    r"\leftarrow",
    r"\Rightarrow",
    r"\Leftarrow",
    r"\to",
    r"\mapsto",
    r"\hat",
    r"\bar",
    r"\tilde",
    r"\vec",
    r"\dot",
    r"\ddot",
    r"\overline",
    r"\underline",
    r"\text",
    r"\mbox",
    r"\operatorname",
    r"\mathop",
    r"\limits",
    r"\prod",
    r"\coprod",
    r"\bigcup",
    r"\bigcap",
    r"\bigoplus",
    r"\bigotimes",
    r"\oint",
    r"\iint",
    r"\iiint",
    r"\idotsint",
    r"\binom",
    r"\tbinom",
    r"\dbinom",
    r"\genfrac",
    r"\mathbb",
    r"\mathfrak",
    r"\mathsf",
    r"\mathrm",
    r"\mathit",
    r"\mathnormal",
    r"\boldsymbol",
    r"\bm",
    r"\cfrac",
    r"\dfrac",
    r"\tfrac",
    r"\binom",
    r"\pmatrix",
    r"\bmatrix",
    r"\vmatrix",
    r"\matrix",
    r"\cases",
    r"\align",
    r"\aligned",
    r"\gather",
    r"\gathered",
    r"\split",
    r"\multline",
    r"\equation",
    r"\item",
    r"\label",
    r"\ref",
    r"\cite",
    r"\footnote",
)


def has_latex_content(text: str) -> bool:
    """Return True if *text* contains any LaTeX math or command hints."""
    if not text:
        return False
    return any(hint in text for hint in _LATEX_HINTS)


@dataclass
class LatexErrorContext:
    error_type: str
    line_no: int
    tex_snippet: str
    md_snippet: str
    error_token: str
    debug_md_path: Optional[Path]
    debug_tex_path: Path


def _detect_error_type(stderr: str) -> str:
    """Detect error type from XeLaTeX stderr."""
    lowered = stderr.lower()

    if "bad math environment delimiter" in lowered:
        return "bad_math_environment_delimiter"
    if r"\mathbf allowed only in math mode".lower() in lowered:
        return "math_bold_outside_math_mode"
    if "missing $ inserted" in lowered:
        return "missing_dollar_inserted"
    # e.g. "! You can't use \eqno' in math mode" at \] when \tag is inside \[...\]
    if "eqno" in lowered and "math mode" in lowered:
        return "eqno_in_math_mode"
    if "undefined control sequence" in lowered:
        return "undefined_control_sequence"
    if "environment" in lowered and "undefined" in lowered:
        return "environment_undefined"
    if r"missing \endcsname" in lowered:
        return "missing_endcsname"
    if "extra }, or forgotten endgroup" in lowered or "missing endgroup" in lowered:
        return "brace_mismatch"
    if "missing endgroup" in lowered:
        return "missing_endgroup"
    if "argument of" in lowered and "has an extra }" in lowered:
        return "argument_extra_brace"
    if "runaway argument" in lowered:
        return "runaway_argument"
    if "file `" in lowered and "not found" in lowered:
        return "missing_file"
    if "double subscript" in lowered:
        return "double_subscript"
    if "double superscript" in lowered:
        return "double_superscript"
    if "missing { inserted" in lowered:
        return "missing_open_brace"
    if "missing } inserted" in lowered:
        return "missing_close_brace"
    if "begin{" in lowered and ("end{" not in lowered or "missing" in lowered):
        return "missing_end_environment"
    if "end{" in lowered and ("begin{" not in lowered or "missing" in lowered):
        return "missing_begin_environment"
    if "inserted" in lowered and "missing" in lowered:
        return "missing_token"
    if "paragraph ended before" in lowered:
        return "paragraph_ended_early"
    if "too many }'s" in lowered:
        return "extra_close_brace"
    if "dimension too large" in lowered:
        return "dimension_too_large"
    if "overflow" in lowered:
        return "overflow"
    if "fatal error" in lowered:
        return "fatal_error"

    return "unknown_latex_error"


def _extract_error_token(error_line: str, stderr: str, error_type: str) -> str:
    """Extract a representative LaTeX token from the error line or stderr."""

    # Priority 1: match environments in the error line (most specific)
    if error_line:
        token_match = re.search(
            r"(\\begin\{[^}]+\}|\\end\{[^}]+\}|\\\w+|\$\$[^$]+\$\$|\$[^$]+\$)",
            error_line,
        )
        if token_match:
            return token_match.group(0)

    # Priority 2: for undefined control sequence, extract from stderr message
    if error_type == "undefined_control_sequence":
        m = re.search(r"Undefined control sequence[.\s]*\\(\w+)", stderr, re.IGNORECASE)
        if m:
            return "\\" + m.group(1)
        m = re.search(r"l\.\d+\s+.*?(\\\w+)", stderr, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)

    # Priority 3: for environment undefined, extract env name
    if error_type == "environment_undefined":
        if error_line:
            m = re.search(r"\\begin\{([^}]+)\}", error_line)
            if m:
                return "\\begin{" + m.group(1) + "}"
        m = re.search(r"LaTeX Error:\s*Environment `?([^'`\s]+)'?", stderr, re.IGNORECASE)
        if m:
            return "\\begin{" + m.group(1) + "}"

    # Priority 4: match any backslash command in the error line (broader)
    if error_line:
        token_match = re.search(r"\\[a-zA-Z@]+", error_line)
        if token_match:
            return token_match.group(0)

        # Priority 5: match math delimiters
        token_match = re.search(r"\$\$.*?\$\$|\$[^$]*\$", error_line)
        if token_match:
            return token_match.group(0)

    return ""


def _build_md_snippet(
    debug_md_path: Optional[Path],
    error_token: str,
    error_line: str,
) -> str:
    """Find the corresponding markdown snippet by searching for the error token in the debug MD file."""
    if not debug_md_path or not debug_md_path.exists():
        return ""

    try:
        md_text = debug_md_path.read_text(encoding="utf-8", errors="replace")
        md_lines = md_text.splitlines()
    except Exception:
        return ""

    # Strategy 1: exact match of error_token
    if error_token:
        for i, line in enumerate(md_lines):
            if error_token in line:
                start = max(0, i - 2)
                end = min(len(md_lines), i + 3)
                return "\n".join(f"{j + 1}: {md_lines[j]}" for j in range(start, end))

    # Strategy 2: for environment tokens, search by environment name
    env_match = re.search(r"\\(begin|end)\{([^}]+)\}", error_token)
    if env_match:
        env_name = env_match.group(2)
        for i, line in enumerate(md_lines):
            if f"\\begin{{{env_name}}}" in line or f"\\end{{{env_name}}}" in line:
                start = max(0, i - 2)
                end = min(len(md_lines), i + 3)
                return "\n".join(f"{j + 1}: {md_lines[j]}" for j in range(start, end))

    # Strategy 3: fallback — search for a substantial substring from the error line
    # (cleaned of LaTeX line-number prefix like "l.123 ")
    clean_err = re.sub(r"^l\.\d+\s*", "", error_line).strip()
    if len(clean_err) >= 8:
        for i, line in enumerate(md_lines):
            # Try to find a significant chunk of the error line in markdown
            if clean_err[:40] in line or clean_err[-40:] in line:
                start = max(0, i - 2)
                end = min(len(md_lines), i + 3)
                return "\n".join(f"{j + 1}: {md_lines[j]}" for j in range(start, end))

    return ""


def extract_latex_error_context(
    stderr: str,
    debug_tex_path: Path,
    debug_md_path: Optional[Path],
) -> Optional[LatexErrorContext]:
    """Parse XeLaTeX stderr + debug .tex to locate the first LaTeX error."""
    try:
        if not debug_tex_path.exists():
            return None

        error_type = _detect_error_type(stderr)

        # Try to locate the first "l.<num> " pattern in stderr (XeLaTeX style)
        m = re.search(r"l\.(\d+)\s", stderr)
        if not m:
            # Fallback: look for "<filename>:<num>:" pattern
            m = re.search(r":(\d+):\s", stderr)
        if not m:
            return None
        line_no = int(m.group(1))

        try:
            tex_lines = debug_tex_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as tex_err:  # noqa: BLE001
            logger.debug(
                LogModule.RESTOR,
                f"[LATEX-REPAIR] Failed to read debug LaTeX for context: {tex_err}",
            )
            return None

        error_line = tex_lines[line_no - 1] if 0 <= line_no - 1 < len(tex_lines) else ""
        # Also include a few surrounding lines for richer context
        ctx_start = max(0, line_no - 2)
        ctx_end = min(len(tex_lines), line_no + 2)
        tex_snippet = "\n".join(
            f"{j + 1}: {tex_lines[j]}" for j in range(ctx_start, ctx_end)
        )

        error_token = _extract_error_token(error_line, stderr, error_type)
        md_snippet = _build_md_snippet(debug_md_path, error_token, error_line)

        return LatexErrorContext(
            error_type=error_type,
            line_no=line_no,
            tex_snippet=tex_snippet,
            md_snippet=md_snippet,
            error_token=error_token,
            debug_md_path=debug_md_path,
            debug_tex_path=debug_tex_path,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(
            LogModule.RESTOR,
            f"[LATEX-REPAIR] extract_latex_error_context failed: {e}",
        )
        return None
