# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""
HTML inline-tag sanitization utilities.

Closes unclosed <del>, <s>, <ins> tags in HTML fragments to prevent
strikethrough/underline bleeding into subsequent content (e.g. in exported HTML).
"""

import re
from typing import Optional

from logger import unified_logger as logger
from logger.logger import LogModule


# Inline tags that can cause strikethrough/underline if unclosed when injected into HTML export
# CRITICAL: Match only actual HTML tags, not text content like "（<s>, <e>）".
# A valid HTML tag must have <tag> or <tag followed by space/attributes. We use lookahead
# to ensure <s> is followed by ">" or space, not other characters like comma or parenthesis.
_UNCLOSED_OPEN_PATTERNS = [
    (re.compile(r"<del(?=\s|>)", re.IGNORECASE), "</del>"),
    (re.compile(r"<s(?=\s|>)", re.IGNORECASE), "</s>"),
    (re.compile(r"<ins(?=\s|>)", re.IGNORECASE), "</ins>"),
]
_UNCLOSED_CLOSE_PATTERNS = [
    re.compile(r"</del\s*>", re.IGNORECASE),
    re.compile(r"</s\s*>", re.IGNORECASE),
    re.compile(r"</ins\s*>", re.IGNORECASE),
]

# Literal marker pattern for things like "（<s>, <e>）" which should be rendered as text,
# not treated as real HTML tags.
_LITERAL_SE_MARKER_PATTERN = re.compile(
    r"(?P<prefix>[（(])\s*<s>\s*,\s*<e>\s*(?P<suffix>[）)])",
    re.IGNORECASE,
)


def _close_unclosed_inline_tags(
    html_fragment: str,
    log_context: Optional[dict] = None,
) -> str:
    """
    Close any unclosed <del>, <s>, <ins> in an HTML fragment to prevent
    strikethrough/underline bleeding into content that follows (e.g. in exported HTML).

    When log_context is provided, logs diagnostic info for each tag type that had
    unclosed opens: tag name, open/close counts, position of first unclosed open,
    and a short snippet so the start/end of the strikethrough region can be identified.
    log_context may include e.g. segment_index, block_index, context="table_cell" or "full_markdown".
    """
    if not html_fragment or not html_fragment.strip():
        return html_fragment

    # Normalize known literal marker patterns like "（<s>, <e>）" so they are treated as text,
    # not as real HTML <s>/<e> tags. Otherwise they will be counted as unclosed <s> and cause
    # strikethrough to bleed to the end of the document.
    def _escape_literal_markers(match: re.Match) -> str:
        prefix = match.group("prefix")
        suffix = match.group("suffix")
        return f"{prefix}&lt;s&gt;, &lt;e&gt;{suffix}"

    new_fragment, n_subs = _LITERAL_SE_MARKER_PATTERN.subn(
        _escape_literal_markers, html_fragment
    )

    if n_subs > 0 and log_context is not None:
        msg = (
            "[STRIKETHROUGH-FIX] Escaped %d literal <s>, <e> marker pairs "
            "inside parentheses to avoid treating them as HTML tags | context=%s"
        ) % (n_subs, log_context)
        logger.warning(LogModule.RESTOR, msg)

    html_fragment = new_fragment

    closers = []
    tag_names = ("del", "s", "ins")
    for idx, ((open_pat, close_tag), close_pat) in enumerate(
        zip(_UNCLOSED_OPEN_PATTERNS, _UNCLOSED_CLOSE_PATTERNS)
    ):
        n_open = len(open_pat.findall(html_fragment))
        n_close = len(close_pat.findall(html_fragment))
        to_add = max(0, n_open - n_close)
        for _ in range(to_add):
            closers.append(close_tag)
        if to_add > 0 and log_context is not None:
            first_open = open_pat.search(html_fragment)
            pos = first_open.start() if first_open else 0
            snippet_start = max(0, pos - 40)
            snippet_end = min(len(html_fragment), pos + 80)
            snippet = html_fragment[snippet_start:snippet_end].replace("\n", " ")
            msg = (
                "[STRIKETHROUGH-FIX] Unclosed <%s>: opens=%d closes=%d, added %d closers; "
                "first open at char %d, snippet: %s | context=%s"
            ) % (tag_names[idx], n_open, n_close, to_add, pos, repr(snippet), log_context)
            logger.warning(LogModule.RESTOR, msg)
    if not closers:
        return html_fragment
    end_pos = len(html_fragment.rstrip())
    result = html_fragment.rstrip() + "".join(closers)
    if log_context is not None:
        snippet_end_start = max(0, end_pos - 60)
        snippet_end = html_fragment[snippet_end_start:end_pos].replace("\n", " ")
        msg = (
            "[STRIKETHROUGH-FIX] Appended %d closers at end of fragment (char %d); "
            "snippet before append: %s | context=%s"
        ) % (len(closers), end_pos, repr(snippet_end), log_context)
        logger.warning(LogModule.RESTOR, msg)
    return result
