# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Conservative mitex 0.2.6 safety checks for Typst overlay math."""

from __future__ import annotations

import re
from typing import Optional

_BEGIN_ENV_RE = re.compile(r"\\begin\{")
_END_ENV_RE = re.compile(r"\\end\{")
_TAG_RE = re.compile(r"\\tag\{")
_LEFT_RE = re.compile(r"\\left\b")
_RIGHT_RE = re.compile(r"\\right\b")
_RIGHT_TEXT_RE = re.compile(r"\\right\\text\{")
_PAREN_DELIM_RE = re.compile(r"\\\(|\\\)")
# mitex 0.2.6 fails with "unclosed delimiter" when \left\lfloor/\lceil is
# closed with \right. instead of the matching floor/ceil token.
_LEFT_FLOOR_RE = re.compile(r"\\left\\lfloor\b")
_RIGHT_FLOOR_RE = re.compile(r"\\right\\rfloor\b")
_LEFT_CEIL_RE = re.compile(r"\\left\\lceil\b")
_RIGHT_CEIL_RE = re.compile(r"\\right\\rceil\b")
# Bare \not (no operand) → Typst "missing argument: it" via mitex.
_BARE_NOT_RE = re.compile(r"^\\not\s*$")
# Orphan \limits / \nolimits at math start → Typst "missing argument: body"
# via mitex (limits() with no base). Attached forms like \sum\limits stay OK.
_BARE_LIMITS_RE = re.compile(r"^\\(?:no)?limits(?![A-Za-z])")
# Style switch alone → mitex eval fails (empty array / invalid math).
_BARE_MATH_STYLE_RE = re.compile(
    r"^\\(?:displaystyle|textstyle|scriptstyle|scriptscriptstyle)\s*$"
)


def strip_math_delimiters(text: str) -> str:
    """Remove outer $ / $$ / \\(\\) / \\[\\] wrappers when present.

    Peels repeatedly so nested display wrappers (e.g. ``$$\\n$$ x \\n$$`` from
    layout text that already includes ``$$`` plus a second wrap) collapse to
    bare LaTeX. Also drops a leftover leading ``$$`` when the trailing pair was
    consumed by an earlier peel.
    """
    body = str(text or "").strip()
    if not body:
        return ""
    # Bound iterations so malformed input cannot loop forever.
    for _ in range(8):
        prev = body
        if body.startswith("$$") and body.endswith("$$") and len(body) >= 4 and body.count("$$") >= 2:
            body = body[2:-2].strip()
            if body != prev:
                continue
        if body.startswith(r"\[") and body.endswith(r"\]") and len(body) >= 4:
            body = body[2:-2].strip()
            if body != prev:
                continue
        if body.startswith(r"\(") and body.endswith(r"\)") and len(body) >= 4:
            body = body[2:-2].strip()
            if body != prev:
                continue
        if body.startswith("$") and body.endswith("$") and not body.startswith("$$") and len(body) >= 2:
            body = body[1:-1].strip()
            if body != prev:
                continue
        # Orphan leading $$ after peeling a nested outer pair.
        if body.startswith("$$"):
            rest = body[2:].lstrip()
            if rest and not rest.startswith("$"):
                body = rest
                if body != prev:
                    continue
        break
    return body


def format_display_math_block(content: str) -> str:
    """Wrap LaTeX as a markdown display-math block after stripping outer delimiters."""
    body = strip_math_delimiters(content)
    if not body:
        return ""
    return f"$$\n{body}\n$$"


def _brace_depth_balanced(body: str) -> bool:
    depth = 0
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            i += 2 if i + 1 < len(body) else 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def _left_right_balanced(body: str) -> bool:
    return len(_LEFT_RE.findall(body)) == len(_RIGHT_RE.findall(body))


def _floor_ceil_paired(body: str) -> bool:
    """True when \\left\\lfloor/\\lceil counts match matching \\right tokens."""
    return (
        len(_LEFT_FLOOR_RE.findall(body)) == len(_RIGHT_FLOOR_RE.findall(body))
        and len(_LEFT_CEIL_RE.findall(body)) == len(_RIGHT_CEIL_RE.findall(body))
    )


def mitex_unsafe_reason(math_body: str) -> Optional[str]:
    """Return a short reason when LaTeX is likely to break mitex; else None."""
    body = strip_math_delimiters(math_body)
    if not body:
        return None
    if _BEGIN_ENV_RE.search(body) or _END_ENV_RE.search(body):
        return "latex_environment"
    if not _brace_depth_balanced(body):
        return "unbalanced_braces"
    if not _left_right_balanced(body):
        return "unbalanced_left_right"
    if not _floor_ceil_paired(body):
        return "mismatched_floor_ceil"
    if _TAG_RE.search(body):
        return "latex_tag"
    if _RIGHT_TEXT_RE.search(body):
        return "invalid_right_delimiter"
    if _PAREN_DELIM_RE.search(body):
        return "paren_delimiter_artifact"
    stripped = body.strip()
    if _BARE_NOT_RE.match(stripped):
        return "bare_not"
    if _BARE_LIMITS_RE.match(stripped):
        return "bare_limits"
    if _BARE_MATH_STYLE_RE.match(stripped):
        return "bare_math_style"
    # Adjacent $...$$...$ can be scanned as one body containing $$; cmarker
    # still splits them and may emit bare \not.
    if "$$" in body:
        return "embedded_dollar_delimiter"
    return None


def iter_math_spans_in_markdown(text: str) -> list[str]:
    """Extract inline/display math bodies from markdown text."""
    from layout.pdf_renderer.typst_overlay.math_span_utils import iter_math_span_bodies

    return iter_math_span_bodies(text)


def markdown_line_safe_for_mitex(line: str) -> bool:
    """Return False when a preserved line should not use cmarker+mitex."""
    body = str(line or "")
    if not body.strip():
        return True
    spans = iter_math_spans_in_markdown(body)
    if not spans:
        return True
    for span in spans:
        if mitex_unsafe_reason(span):
            return False
    return True


def is_mitex_safe_latex(math_body: str) -> bool:
    """True when math_body is safe to pass through cmarker+mitex."""
    return mitex_unsafe_reason(math_body) is None


def should_fallback_mitex_equation_to_image(
    math_body: str,
    *,
    equation_format: str = "text",
) -> Optional[str]:
    """Return unsafe reason when overlay must use equation-image / source-PDF fallback.

    Applies for ``text`` and ``latex`` equation formats. ``image`` format already
    preserves equation visuals and never routes through mitex.
    """
    eq_fmt = (equation_format or "text").strip().lower()
    if eq_fmt == "image":
        return None
    return mitex_unsafe_reason(math_body)
