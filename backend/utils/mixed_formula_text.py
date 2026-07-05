# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""
Utilities to handle mixed plain text + LaTeX (no $ delimiters) for MD and DOCX export.

Used when a segment is identified as containing formulas but the content mixes
ordinary text and LaTeX (e.g. algorithm lines: "Require: a_{C},a_{R} Ensure: f^{*}").
Produces Markdown with $...$ around formula parts so downstream export can render them.
"""

import re
from typing import List, Tuple

# Inline math spans: LaTeX commands and identifier sub/superscripts (e.g. R_{m}, C_{d}).
# Scan the full string instead of whitespace tokens so CJK punctuation glued to a
# subscript (``C_{d}，都是...``) does not swallow the rest of the paragraph as math.
# Exclude \n, \r, \t artifacts (LLM line breaks) — not valid LaTeX; mitex rejects \n.
# Keep \nu, \neq, \newline (\n followed by lowercase continues the command name).
_MATH_SPAN_RE = re.compile(
    r"(?:\\(?:mathrm|mathbf|mathit|operatorname|text)\{[^{}]*\}"
    r"|\\(?!(?:n|r|t)(?![a-z]))[a-zA-Z]+(?:\{[^{}]*\})*"
    r"|[A-Za-z]+(?:_\{[^{}]*\}|\^\{[^{}]*\})+)"
)


def segment_mixed_text_into_md_segments(text: str) -> List[Tuple[bool, str]]:
    """
    Split mixed plain text + LaTeX (no $ delimiters) into (is_math, segment) list.
    Used to produce MD with $...$ around formula parts.

    Returns:
        List of (is_math, segment_text). is_math True means the segment is LaTeX to wrap in $...$.
    """
    if not text:
        return []
    segments: List[Tuple[bool, str]] = []
    last = 0
    for match in _MATH_SPAN_RE.finditer(text):
        if match.start() > last:
            segments.append((False, text[last : match.start()]))
        segments.append((True, match.group()))
        last = match.end()
    if last < len(text):
        segments.append((False, text[last:]))
    return segments


def _has_existing_math_delimiters(text: str) -> bool:
    """
    True if text already contains LaTeX math delimiters ($$ or $).
    Do NOT run mixed_text_to_md on such content - it would corrupt the structure.
    """
    if not text or not text.strip():
        return False
    return "$$" in text or ("$" in text and text.count("$") >= 2)


def mixed_text_to_md(text: str) -> str:
    """
    Build Markdown string from mixed text by wrapping math segments in $...$.
    Safe for pure LaTeX (single math segment) and pure text (no change).
    For multi-line content, processes each line separately so newlines are preserved.
    Skips processing when content already has $$ or $ delimiters to avoid corrupting LaTeX.
    """
    if not text:
        return text
    if _has_existing_math_delimiters(text):
        return text
    if "\n" in text:
        lines = text.split("\n")
        return "\n".join(_mixed_text_to_md_single_line(line) for line in lines)
    return _mixed_text_to_md_single_line(text)


def _mixed_text_to_md_single_line(text: str) -> str:
    """Single-line mixed text to MD (no newline handling)."""
    segments = segment_mixed_text_into_md_segments(text)
    return "".join(("$" + s + "$" if is_math else s) for is_math, s in segments)


def extract_formula_fragments_from_mixed_text(text: str) -> List[str]:
    """Return list of LaTeX formula strings (each math segment). For OMML or other use."""
    segments = segment_mixed_text_into_md_segments(text)
    return [s for is_math, s in segments if is_math]


def has_mixed_formula_content(text: str) -> bool:
    """
    True if text contains both non-math and math-like parts (optional fast path).
    If False, caller may skip mixed_text_to_md (pure text or pure LaTeX).
    """
    if not text or not text.strip():
        return False
    segments = segment_mixed_text_into_md_segments(text)
    math_count = sum(1 for is_math, _ in segments if is_math)
    plain_count = sum(1 for is_math, s in segments if not is_math and s.strip())
    return math_count >= 1 and plain_count >= 1
