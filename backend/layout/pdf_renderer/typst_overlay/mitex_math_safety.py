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


def strip_math_delimiters(text: str) -> str:
    """Remove outer $ / $$ / \\(\\) / \\[\\] wrappers when present."""
    body = str(text or "").strip()
    if not body:
        return ""
    if body.startswith("$$") and body.endswith("$$") and body.count("$$") >= 2:
        return body[2:-2].strip()
    if body.startswith(r"\[") and body.endswith(r"\]"):
        return body[2:-2].strip()
    if body.startswith(r"\(") and body.endswith(r"\)"):
        return body[2:-2].strip()
    if body.startswith("$") and body.endswith("$") and not body.startswith("$$"):
        return body[1:-1].strip()
    return body


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
    if _TAG_RE.search(body):
        return "latex_tag"
    return None


def is_mitex_safe_latex(math_body: str) -> bool:
    """True when math_body is safe to pass through cmarker+mitex."""
    return mitex_unsafe_reason(math_body) is None
