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



# Valid LaTeX command bodies after a literal "\n" (not a newline). Longest-first match.

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





def _is_latex_letter(ch: str) -> bool:

    return ch.isalpha() or ch == "@"





def _is_literal_linebreak_escape(text: str, pos: int) -> bool:

    """True for LLM \\n/\\r artifacts, not for \\nu, \\neq, \\newline, etc."""

    if pos >= len(text) or text[pos] != "\\":

        return False

    if pos + 1 >= len(text):

        return False

    marker = text[pos + 1]

    if marker not in "nr":

        return False

    if pos + 2 < len(text) and text[pos + 2].islower():

        for prefix in sorted(_N_PREFIX_LATEX_COMMANDS, key=len, reverse=True):

            if text.startswith(prefix, pos + 2):

                return False

    return True





def _consume_brace_group(text: str, pos: int) -> int:

    if pos >= len(text) or text[pos] != "{":

        return pos

    depth = 0

    i = pos

    while i < len(text):

        ch = text[i]

        if ch == "{":

            depth += 1

        elif ch == "}":

            depth -= 1

            if depth == 0:

                return i + 1

        elif ch == "\\":

            i += 1

            while i < len(text) and _is_latex_letter(text[i]):

                i += 1

            continue

        i += 1

    return pos





def _consume_paren_group(text: str, pos: int) -> int:

    if pos >= len(text) or text[pos] != "(":

        return pos

    depth = 0

    i = pos

    while i < len(text):

        ch = text[i]

        if ch == "(":

            depth += 1

        elif ch == ")":

            depth -= 1

            if depth == 0:

                return i + 1

        elif ch == "{":

            nxt = _consume_brace_group(text, i)

            if nxt == i:

                break

            i = nxt

            continue

        elif ch == "\\":

            if _is_literal_linebreak_escape(text, i):

                break

            nxt = _scan_latex_command_span_end(text, i)

            if nxt <= i:

                break

            i = nxt

            continue

        i += 1

    return pos if depth != 0 else i





def _consume_script_group(text: str, pos: int) -> int:

    if pos >= len(text) or text[pos] not in "^_":

        return pos

    i = pos + 1

    if i < len(text) and text[i] == "{":

        return _consume_brace_group(text, i)

    if i < len(text):

        return i + 1

    return pos





def _scan_latex_command_span_end(text: str, start: int) -> int:

    if start >= len(text) or text[start] != "\\":

        return start

    if _is_literal_linebreak_escape(text, start):

        return start

    i = start + 1

    if i >= len(text):

        return start

    if not _is_latex_letter(text[i]):

        return i + 1

    while i < len(text) and _is_latex_letter(text[i]):

        i += 1

    while i < len(text):

        if text[i] == "{":

            nxt = _consume_brace_group(text, i)

            if nxt == i:

                break

            i = nxt

        elif text[i] in "^_":

            nxt = _consume_script_group(text, i)

            if nxt == i:

                break

            i = nxt

        elif text[i] == "(":

            nxt = _consume_paren_group(text, i)

            if nxt == i:

                break

            i = nxt

        else:

            break

    return i if i > start + 1 else start





def _scan_identifier_math_span_end(text: str, start: int) -> int:

    if start >= len(text) or not text[start].isalpha():

        return start

    i = start

    while i < len(text) and (text[i].isalnum() or text[i] == "."):

        i += 1

    script_start = i

    while i < len(text) and text[i] in "^_":

        nxt = _consume_script_group(text, i)

        if nxt == i:

            break

        i = nxt

    return i if i > script_start else start





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

    i = 0

    while i < len(text):

        end = 0

        if text[i] == "\\" and not _is_literal_linebreak_escape(text, i):

            end = _scan_latex_command_span_end(text, i)

        elif text[i].isalpha():

            end = _scan_identifier_math_span_end(text, i)

        if end > i:

            if i > last:

                segments.append((False, text[last:i]))

            segments.append((True, text[i:end]))

            last = end

            i = end

            continue

        i += 1

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


