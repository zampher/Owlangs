# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Linear-time math delimiter scanning (avoids ReDoS in $...$ regex)."""

from __future__ import annotations

from typing import Callable, Iterable


def transform_latex_bracket_delimiters(text: str) -> str:
    """Replace ``\\[...\\]`` / ``\\(...\\)`` with ``$$...$$`` / ``$...$`` (linear scan)."""
    body = str(text or "")
    if not body:
        return body
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        if i + 1 < n and body[i] == "\\" and body[i + 1] in "[(":
            open_ch = body[i + 1]
            close_seq = "\\" + ("]" if open_ch == "[" else ")")
            inner_start = i + 2
            j = inner_start
            while j < n:
                if body.startswith(close_seq, j):
                    inner = body[inner_start:j]
                    if open_ch == "[":
                        out.append(f"$${inner}$$")
                    else:
                        out.append(f"${inner}$")
                    i = j + len(close_seq)
                    break
                j += 1
            else:
                out.append(body[i])
                i += 1
            continue
        j = i
        while j < n and not (j + 1 < n and body[j] == "\\" and body[j + 1] in "[("):
            j += 1
        out.append(body[i:j])
        i = j
    return "".join(out)


def transform_dollar_math_spans(
    text: str,
    *,
    on_display: Callable[[str], str],
    on_inline: Callable[[str], str],
) -> str:
    """Walk *text* once and rewrite ``$$...$$`` / ``$...$`` spans via callbacks."""
    body = str(text or "")
    if not body:
        return body
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        if body[i] != "$":
            j = i
            while j < n and body[j] != "$":
                j += 1
            out.append(body[i:j])
            i = j
            continue
        if i + 1 < n and body[i + 1] == "$":
            close = body.find("$$", i + 2)
            if close != -1:
                inner = body[i + 2:close]
                out.append(on_display(inner))
                i = close + 2
            else:
                out.append(body[i])
                i += 1
            continue
        j = i + 1
        closed = False
        while j < n:
            if body[j] == "$":
                if j + 1 < n and body[j + 1] == "$":
                    j += 2
                    continue
                inner = body[i + 1:j]
                out.append(on_inline(inner))
                i = j + 1
                closed = True
                break
            j += 1
        if not closed:
            out.append(body[i])
            i += 1
    return "".join(out)


def iter_math_span_bodies(text: str) -> list[str]:
    """Extract inner bodies from ``$$...$$``, ``$...$``, and bracket delimiters."""
    body = str(text or "")
    if not body:
        return []
    spans: list[str] = []

    def _collect_display(inner: str) -> str:
        spans.append(inner)
        return inner

    def _collect_inline(inner: str) -> str:
        spans.append(inner)
        return inner

    transform_dollar_math_spans(
        body,
        on_display=_collect_display,
        on_inline=_collect_inline,
    )

    i = 0
    n = len(body)
    while i < n:
        if i + 1 < n and body[i] == "\\" and body[i + 1] in "[(":
            open_ch = body[i + 1]
            close_seq = "\\" + ("]" if open_ch == "[" else ")")
            inner_start = i + 2
            j = inner_start
            while j < n:
                if body.startswith(close_seq, j):
                    spans.append(body[inner_start:j])
                    i = j + len(close_seq)
                    break
                j += 1
            else:
                i += 1
            continue
        i += 1
    return spans


def walk_math_span_bodies(text: str) -> Iterable[str]:
    """Yield math inner bodies without allocating a full list when possible."""
    for span in iter_math_span_bodies(text):
        yield span
