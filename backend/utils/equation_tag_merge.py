# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Merge orphan equation-number segments/paragraphs into preceding display math as \\tag{n}.

MinerU often emits the formula body and the right-side number (1)/(2)/… as separate
blocks. Linear markdown rebuild then places the number on the next line; reflow PDF
shows formula and tag on two lines. Pair by layout bbox (same row, number to the right)
or fall back to an immediately following number paragraph after $$...$$.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from logger import unified_logger as logger
from logger.logger import LogModule

# (1), （1）, [11], 【12】
_EQ_NUMBER_RE = re.compile(
    r"^[\(\[（【]\s*(\d+[a-zA-Z]?)\s*[\)\]）】]$"
)

def parse_equation_number_label(text: str) -> Optional[str]:
    """Return equation number label (e.g. '1') if text is solely an eq number tag."""
    if not text or not isinstance(text, str):
        return None
    m = _EQ_NUMBER_RE.match(text.strip())
    return m.group(1) if m else None


def is_display_math_block(text: str) -> bool:
    """True when text is (or is dominated by) a $$...$$ display block."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t.startswith("$$"):
        return False
    return t.count("$$") >= 2


def _normalize_bbox(raw: Any) -> Optional[Tuple[float, float, float, float]]:
    if raw is None:
        return None
    try:
        if isinstance(raw, (list, tuple)) and len(raw) >= 1:
            first = raw[0]
            if isinstance(first, (list, tuple)) and len(first) >= 4:
                x0, y0, x1, y1 = first[:4]
            elif len(raw) >= 4 and all(isinstance(x, (int, float)) for x in raw[:4]):
                x0, y0, x1, y1 = raw[:4]
            else:
                return None
            return (float(x0), float(y0), float(x1), float(y1))
    except (TypeError, ValueError, IndexError):
        return None
    return None


def segment_layout_bbox(segment: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """Best-effort bbox from segment.layout_block_bbox."""
    return _normalize_bbox(segment.get("layout_block_bbox"))


def inject_tag_into_display_math(math_text: str, tag_label: str) -> str:
    """Insert \\tag{label} before the closing $$ of the first display block."""
    if not math_text or not tag_label:
        return math_text
    if r"\tag" in math_text:
        return math_text
    start = math_text.find("$$")
    if start < 0:
        return math_text
    end = math_text.find("$$", start + 2)
    if end < 0:
        return math_text
    body = math_text[start + 2 : end]
    # Keep inner newlines; append tag on the last non-empty line of the body.
    stripped_body = body.rstrip()
    if stripped_body.endswith("\n"):
        new_body = f"{stripped_body} \\tag{{{tag_label}}}\n"
    else:
        new_body = f"{stripped_body} \\tag{{{tag_label}}}"
    return math_text[: start + 2] + new_body + math_text[end:]


def _y_centers_close(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> bool:
    ay = (a[1] + a[3]) / 2.0
    by = (b[1] + b[3]) / 2.0
    ha = max(1.0, a[3] - a[1])
    hb = max(1.0, b[3] - b[1])
    tol = max(12.0, 0.65 * max(ha, hb))
    return abs(ay - by) <= tol


def _math_is_left_of_number(
    math_bb: Tuple[float, float, float, float],
    num_bb: Tuple[float, float, float, float],
) -> bool:
    # Number sits on the right of the formula (typical paper layout).
    return math_bb[0] < num_bb[0] and math_bb[2] <= num_bb[2] + 2.0


def merge_equation_number_tags_in_texts(
    texts: Sequence[str],
    bboxes: Sequence[Optional[Tuple[float, float, float, float]]],
) -> Tuple[List[str], int]:
    """
    Merge orphan eq-number entries into paired display-math entries.

    Returns (new_texts, merge_count). Merged number slots become "".
    """
    n = len(texts)
    if n == 0:
        return [], 0
    out = list(texts)
    bb = list(bboxes) if len(bboxes) == n else [None] * n
    used_math: set[int] = set()
    merge_count = 0

    number_indices = [i for i, t in enumerate(out) if parse_equation_number_label(t)]
    math_indices = [i for i, t in enumerate(out) if is_display_math_block(t)]

    for ni in number_indices:
        label = parse_equation_number_label(out[ni])
        if not label:
            continue
        num_bb = bb[ni]
        best_j: Optional[int] = None
        best_score: Optional[Tuple[float, float]] = None

        if num_bb is not None:
            for j in math_indices:
                if j in used_math:
                    continue
                math_bb = bb[j]
                if math_bb is None:
                    continue
                if not _y_centers_close(math_bb, num_bb):
                    continue
                if not _math_is_left_of_number(math_bb, num_bb):
                    continue
                if r"\tag" in out[j]:
                    continue
                cy_dist = abs((math_bb[1] + math_bb[3]) / 2.0 - (num_bb[1] + num_bb[3]) / 2.0)
                # Prefer closer vertically, then nearer horizontally (larger math.x1).
                score = (cy_dist, -math_bb[2])
                if best_score is None or score < best_score:
                    best_score = score
                    best_j = j

        if best_j is None:
            # Fallback: number immediately after a display-math block without \\tag.
            j = ni - 1
            if (
                j >= 0
                and j not in used_math
                and is_display_math_block(out[j])
                and r"\tag" not in out[j]
            ):
                best_j = j

        if best_j is None:
            continue

        out[best_j] = inject_tag_into_display_math(out[best_j], label)
        out[ni] = ""
        used_math.add(best_j)
        merge_count += 1

    if merge_count:
        logger.info(
            LogModule.RESTOR,
            f"[EQ-TAG-MERGE] Merged {merge_count} orphan equation number(s) into display math as \\tag",
        )
    return out, merge_count


def merge_equation_number_tags_for_segments(
    texts: Sequence[str],
    segments_for_index: Sequence[Optional[Dict[str, Any]]],
) -> Tuple[List[str], int]:
    """Merge using each segment's layout_block_bbox when available."""
    bboxes = [
        segment_layout_bbox(seg) if isinstance(seg, dict) else None
        for seg in segments_for_index
    ]
    return merge_equation_number_tags_in_texts(texts, bboxes)


def merge_orphan_equation_number_paragraphs(md: str) -> str:
    """
    Merge markdown paragraphs that are solely (n) into the preceding $$...$$ block.

    Example:
        $$\\n x=1\\n$$\\n\\n(1)  ->  $$\\n x=1 \\tag{1}\\n$$
    """
    if not md or not re.search(r"[\(\[（【]\s*\d+", md):
        return md

    parts = re.split(r"(\n\s*\n)", md)
    # parts alternates: text, sep, text, sep, ...
    out_parts: List[str] = []
    i = 0
    merges = 0
    while i < len(parts):
        part = parts[i]
        if i + 2 < len(parts):
            sep = parts[i + 1]
            nxt = parts[i + 2]
            label = parse_equation_number_label(nxt)
            if label and is_display_math_block(part) and r"\tag" not in part:
                out_parts.append(inject_tag_into_display_math(part, label))
                merges += 1
                i += 3  # skip sep + number paragraph
                continue
        out_parts.append(part)
        i += 1

    if merges:
        logger.info(
            LogModule.RESTOR,
            f"[EQ-TAG-MERGE] Merged {merges} orphan equation number paragraph(s) in markdown",
        )
    return "".join(out_parts)


def promote_tagged_display_math_to_equation(md: str) -> str:
    """
    Rewrite $$...\\tag{n}...$$ (and \\[...\\tag...\\]) to equation environments.

    Not used by convert_md_to_pdf: that path omits raw_tex and _sanitize_md_for_pdf
    only protects $$/$ math, so equation envs get backslash-doubled (Missing $).
    Kept for callers that feed raw TeX / raw_tex-enabled Pandoc.
    """
    if not md or r"\tag" not in md:
        return md

    def _rewrite_dollar(m: re.Match[str]) -> str:
        body = m.group(1)
        if r"\tag" not in body:
            return m.group(0)
        inner = body.strip()
        return f"\\begin{{equation}}\n{inner}\n\\end{{equation}}"

    def _rewrite_bracket(m: re.Match[str]) -> str:
        body = m.group(1)
        if r"\tag" not in body:
            return m.group(0)
        inner = body.strip()
        return f"\\begin{{equation}}\n{inner}\n\\end{{equation}}"

    # Non-greedy across newlines for display blocks.
    out = re.sub(r"\$\$(.*?)\$\$", _rewrite_dollar, md, flags=re.DOTALL)
    out = re.sub(r"\\\[(.*?)\\\]", _rewrite_bracket, out, flags=re.DOTALL)
    return out
