from __future__ import annotations

# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Lightweight LaTeX formula checker using Pandoc at snippet level.

Design goals:
- Do NOT modify content; only detect and report potentially broken formulas.
- Work on individual math snippets (inline/display), not whole documents.
- Use Pandoc (if available) as the parser/validator; if Pandoc is missing, skip checks.

This module is intended to be called explicitly (e.g. from a toolbar action in the
frontend) rather than automatically on every export.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class MathSnippet:
    """
    Single math snippet.

    When snippets come from an external caller (e.g. segment classifier),
    start_pos/end_pos can be set to -1 to indicate "not from raw Markdown".
    """

    index: int
    text: str
    start_pos: int = -1
    end_pos: int = -1


@dataclass
class FormulaIssue:
    """Issue detected for a specific math snippet."""

    snippet_index: int
    message: str
    severity: str = "error"  # "error" | "warning"
    raw_stderr: Optional[str] = None


@dataclass
class FormulaCheckResult:
    """Overall result of checking all formulas in a Markdown string."""

    pandoc_available: bool
    snippets: List[MathSnippet]
    issues: List[FormulaIssue]

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


PANDOC_FROM_FOR_SNIPPETS = "markdown+pipe_tables+hard_line_breaks+link_attributes+tex_math_dollars"

# Display math environments that are illegal inside inline math ($...$).
# KaTeX (HTML preview) will reject these; Pandoc/XeLaTeX may silently accept them.
# Display math environments that are illegal inside inline math ($...$).
# NOTE: aligned, cases, matrix/pmatrix/bmatrix/vmatrix/Bmatrix, smallmatrix,
#       and subarray CAN legally appear inside inline math in both LaTeX and KaTeX.
#       Only the following environments are *strictly* display-only.
_DISPLAY_MATH_ENVIRONMENTS: tuple[str, ...] = (
    "align", "alignat", "equation", "eqnarray",
    "gather", "multline", "split",
)

_BROKEN_MATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "split-math-underset",
        re.compile(r"\\\(\s*\\underset\\\)\s*\\\(", re.DOTALL),
    ),
    (
        "split-math-bigl",
        re.compile(r"\\\(\s*\\Bigl\\\)\s*\\\(", re.DOTALL),
    ),
]


def _detect_broken_math_patterns(snippet_text: str) -> Optional[str]:
    """Return a rule name if snippet matches a known broken-math pattern."""
    for rule, pat in _BROKEN_MATH_PATTERNS:
        if pat.search(snippet_text):
            return rule
    return None


_INLINE_MATH_PATTERNS = [
    # $...$
    re.compile(r"\$(.+?)\$", re.DOTALL),
    # \(...\)
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),
]

_DISPLAY_MATH_PATTERNS = [
    # $$...$$
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    # \[...\]
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
]


def _get_pandoc_path() -> Optional[Path]:
    """Resolve pandoc path using existing helper (if available)."""
    try:
        # Import lazily to avoid circular imports at module load time.
        from backend.utils.format_convert_utils import _get_pandoc_path as _inner

        return _inner()
    except Exception:  # noqa: BLE001
        return None


def extract_math_snippets(markdown: str) -> List[MathSnippet]:
    """
    Extract inline and display math snippets from Markdown text.

    This is a best-effort extractor based on simple regexes; it is not a full
    Markdown parser, but good enough for diagnostics and surfacing candidates
    to the user.
    """
    snippets: List[MathSnippet] = []

    def _collect(patterns: List[re.Pattern[str]]) -> None:
        nonlocal snippets
        for pat in patterns:
            for m in pat.finditer(markdown):
                idx = len(snippets)
                snippets.append(
                    MathSnippet(
                        index=idx,
                        text=m.group(0),
                        start_pos=m.start(),
                        end_pos=m.end(),
                    )
                )

    _collect(_INLINE_MATH_PATTERNS)
    _collect(_DISPLAY_MATH_PATTERNS)

    # Sort by start_pos to make indices reflect document order
    snippets.sort(key=lambda s: s.start_pos)
    for i, sn in enumerate(snippets):
        sn.index = i
    return snippets


def check_snippets_with_pandoc(snippet_data: List[Dict[str, Any]]) -> FormulaCheckResult:
    """
    Check a pre-classified list of formula snippets using Pandoc.

    Args:
        snippet_data: List of {"segment_index": int, "text": str} dicts.
                      segment_index is the REAL segment index (not a list position).

    This是推荐的入口：调用方自己决定哪些片段属于“公式”，本函数只负责
    调用 Pandoc 做解析校验，不从 Markdown 里再去猜测公式位置。
    """
    pandoc_path = _get_pandoc_path()
    snippets: List[MathSnippet] = [
        MathSnippet(index=item.get("segment_index", i), text=item["text"])
        for i, item in enumerate(snippet_data)
    ]

    if not pandoc_path:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Pandoc not available; skipping formula checks (snippets={count})",
            count=len(snippets),
        )
        return FormulaCheckResult(
            pandoc_available=False,
            snippets=snippets,
            issues=[],
        )

    all_issues: List[FormulaIssue] = []
    for sn in snippets:
        all_issues.extend(_check_snippet_with_pandoc(sn, pandoc_path))

    if all_issues:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Completed formula checks (pre-classified): snippets={snips}, issues={issues}",
            snips=len(snippets),
            issues=len(all_issues),
        )
    else:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Formula checks passed (pre-classified): snippets={snips}, no issues detected",
            snips=len(snippets),
        )

    return FormulaCheckResult(
        pandoc_available=True,
        snippets=snippets,
        issues=all_issues,
    )


def _pre_check_math_patterns(snippet: MathSnippet) -> List[FormulaIssue]:
    """
    Static pre-check for math-mode errors that Pandoc/XeLaTeX may silently
    accept but KaTeX (HTML preview) will reject.

    These checks run *before* Pandoc so we catch problems that would otherwise
    be hidden by Pandoc's lenient conversion.
    """
    md_doc = snippet.text
    issues: List[FormulaIssue] = []

    # 1. Check $$...$$ display math first (so we can exclude it from $...$ checks)
    display_blocks: list[tuple[int, int]] = []
    for m in re.finditer(r"\$\$(.+?)\$\$", md_doc, re.DOTALL):
        display_content = m.group(1)
        if "$" in display_content:
            issues.append(
                FormulaIssue(
                    snippet_index=snippet.index,
                    message="Inline math ($...$) nested inside display math ($$...$$).",
                    severity="error",
                )
            )
        display_blocks.append((m.start(), m.end()))

    # Build a version with $$...$$ replaced by placeholders so $...$ regex
    # does not accidentally cross display-math boundaries.
    stripped_for_inline = md_doc
    for i, (start, end) in enumerate(reversed(display_blocks)):
        placeholder = f"##DISP{i}##"
        stripped_for_inline = stripped_for_inline[:start] + placeholder + stripped_for_inline[end:]

    # 2. Display math environments inside inline math ($...$)
    for m in re.finditer(r"\$([^$\n]+?)\$", stripped_for_inline):
        inline_content = m.group(1)
        for env in _DISPLAY_MATH_ENVIRONMENTS:
            if f"\\begin{{{env}}}" in inline_content:
                issues.append(
                    FormulaIssue(
                        snippet_index=snippet.index,
                        message=(
                            f"Display math environment '\\begin{{{env}}}' "
                            f"found inside inline math ($...$). "
                            f"Move it to display math ($$...$$ or \\[...\\])."
                        ),
                        severity="error",
                    )
                )
        # Nested $$ inside $
        if "$$" in inline_content:
            issues.append(
                FormulaIssue(
                    snippet_index=snippet.index,
                    message="Nested display math ($$...$$) inside inline math ($...$).",
                    severity="error",
                )
            )
        # \[ or \] inside inline math
        if r"\[" in inline_content or r"\]" in inline_content:
            issues.append(
                FormulaIssue(
                    snippet_index=snippet.index,
                    message="Display math delimiters (\\[ or \\]) inside inline math ($...$).",
                    severity="error",
                )
            )

    # 3. Check for unpaired $ (simple heuristic, excluding $$)
    normalized = md_doc.replace("$$", "##DISPLAY##")
    single_dollar_count = normalized.count("$")
    if single_dollar_count % 2 != 0:
        issues.append(
            FormulaIssue(
                snippet_index=snippet.index,
                message="Unpaired inline math delimiter ($). Every opening $ must have a matching closing $.",
                severity="error",
            )
        )

    # 4. Check for unclosed math environments (\begin{xxx} without matching \end{xxx})
    #    and empty environments (\begin{xxx}\end{xxx} with nothing useful inside).
    #    ONLY check inside math blocks ($...$, $$...$$, \(...\), \[...\]).
    #    \begin outside math delimiters is treated as plain text by Pandoc/KaTeX
    #    and should NOT be flagged.
    math_blocks_to_check: List[str] = []

    # $$...$$
    for m in re.finditer(r"\$\$(.+?)\$\$", md_doc, re.DOTALL):
        math_blocks_to_check.append(m.group(1))
    # $...$ (after stripping $$)
    temp = md_doc
    for m in reversed(list(re.finditer(r"\$\$(.+?)\$\$", temp, re.DOTALL))):
        temp = temp[:m.start()] + "##DISP##" + temp[m.end():]
    for m in re.finditer(r"\$(.+?)\$", temp):
        math_blocks_to_check.append(m.group(1))
    # \[...\]
    for m in re.finditer(r"\\\[(.+?)\\\]", md_doc, re.DOTALL):
        math_blocks_to_check.append(m.group(1))
    # \(...\)
    for m in re.finditer(r"\\\((.+?)\\\)", md_doc, re.DOTALL):
        math_blocks_to_check.append(m.group(1))

    for block in math_blocks_to_check:
        for m in re.finditer(r"\\begin\{([A-Za-z]+)\}", block):
            env_name = m.group(1)
            start_pos = m.start()
            end_pattern = f"\\end{{{env_name}}}"
            end_match = re.search(re.escape(end_pattern), block[start_pos:])
            if not end_match:
                issues.append(
                    FormulaIssue(
                        snippet_index=snippet.index,
                        message=(
                            f"Unclosed math environment '\\begin{{{env_name}}}' "
                            f"inside math block without matching '\\end{{{env_name}}}'."
                        ),
                        severity="error",
                    )
                )
            else:
                inner = block[start_pos + len(m.group(0)) : start_pos + end_match.start()]
                if not inner.strip() or inner.strip() in (")", ",", ".", ";", ":", " ", "\\"
                ):
                    issues.append(
                        FormulaIssue(
                            snippet_index=snippet.index,
                            message=(
                                f"Empty or near-empty math environment '\\begin{{{env_name}}}...\\end{{{env_name}}}' "
                                f"inside math block. Consider removing it or adding content."
                            ),
                            severity="warning",
                        )
                    )

    return issues


def _check_snippet_with_pandoc(snippet: MathSnippet, pandoc_path: Path) -> List[FormulaIssue]:
    """
    Check a single math snippet via Pandoc + XeLaTeX (dry-run).

    Strategy:
    - Run static pre-checks first (catches KaTeX-only errors).
    - Invoke Pandoc with --pdf-engine=xelatex to run the same toolchain as export.
    - If XeLaTeX fails (non-zero exit or LaTeX Error in stderr), record an issue.

    IMPORTANT:
    - This checker is ONLY used for short formula snippets, not full documents.
    - It is expected that some snippets will not be valid standalone LaTeX; in that
      case, we surface the error so the frontend can decide whether to use AI repair.
    """
    md_doc = snippet.text
    issues: List[FormulaIssue] = []

    # --- Static pre-checks (catches errors Pandoc/XeLaTeX may hide) ---
    pre_issues = _pre_check_math_patterns(snippet)
    if pre_issues:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Snippet {idx}: pre-check found {count} issue(s), preview={preview}",
            idx=snippet.index,
            count=len(pre_issues),
            preview=md_doc.replace("\n", " ")[:200],
        )
        issues.extend(pre_issues)
        # Continue to Pandoc checks so we collect *all* issues, not just pre-check ones.

    broken_rule = _detect_broken_math_patterns(md_doc)
    if broken_rule:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Snippet {idx}: matched broken-math rule={rule}, preview={preview}",
            idx=snippet.index,
            rule=broken_rule,
            preview=md_doc.replace("\n", " ")[:200],
        )
        issues.append(
            FormulaIssue(
                snippet_index=snippet.index,
                message=f"Detected broken math pattern: {broken_rule}",
                severity="error",
            )
        )
        # Return early if a broken pattern is matched; pre-checks are already included.
        return issues

    # First, sanity-check that Pandoc can parse the snippet as Markdown/TeX,
    # and at the same time write the intermediate LaTeX it generates to a
    # debug .tex file for further analysis.
    try:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Snippet {idx}: running Pandoc parse check (len={length}, preview={preview})",
            idx=snippet.index,
            length=len(md_doc),
            preview=md_doc.replace("\n", " ")[:160],
        )
        # Write snippet markdown to a temporary .md file so we can ask Pandoc
        # to emit a LaTeX .tex file on disk.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp_md:
            tmp_md.write(md_doc)
            tmp_md_path = Path(tmp_md.name)

        debug_root = Path(tempfile.gettempdir()) / "owlangs_latex_snippets"
        debug_root.mkdir(parents=True, exist_ok=True)
        debug_tex_path = debug_root / f"snippet_{snippet.index}.tex"

        proc = subprocess.run(  # noqa: S603
            [
                str(pandoc_path),
                "-f",
                PANDOC_FROM_FOR_SNIPPETS,
                str(tmp_md_path),
                "-t",
                "latex",
                "-o",
                str(debug_tex_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Snippet {idx}: wrote debug LaTeX to {path}",
            idx=snippet.index,
            path=str(debug_tex_path),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            LogModule.RESTOR,
            "[LATEX-CHECK] Pandoc invocation failed for snippet {idx}: {err}",
            idx=snippet.index,
            err=str(e),
        )
        return [
            FormulaIssue(
                snippet_index=snippet.index,
                message=f"Pandoc invocation failed: {e}",
                severity="error",
            )
        ]

    stderr = proc.stderr.decode("utf-8", errors="ignore")
    logger.info(
        LogModule.RESTOR,
        "[LATEX-CHECK] Snippet {idx}: Pandoc parse exit={code}, stderr_snippet={stderr}",
        idx=snippet.index,
        code=proc.returncode,
        stderr=(stderr or "")[:200],
    )
    if proc.returncode != 0 or ("error" in stderr.lower() or "Error" in stderr):
        # Keep message concise but include raw stderr for debugging.
        msg = "Pandoc reported an error while parsing this formula snippet."
        issues.append(
            FormulaIssue(
                snippet_index=snippet.index,
                message=msg,
                severity="error",
                raw_stderr=stderr.strip() or None,
            )
        )

    # Then run a XeLaTeX dry-run via Pandoc's PDF engine to detect LaTeX-level errors.
    # Use a temporary PDF path; we do not care about the actual file, only stderr.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_pdf:
        try:
            logger.info(
                LogModule.RESTOR,
                "[LATEX-CHECK] Snippet {idx}: running Pandoc+XeLaTeX dry-run to {out}",
                idx=snippet.index,
                out=tmp_pdf.name,
            )
            proc_pdf = subprocess.run(  # noqa: S603
                [
                    str(pandoc_path),
                    "-f",
                    PANDOC_FROM_FOR_SNIPPETS,
                    "--pdf-engine=xelatex",
                    "-o",
                    str(tmp_pdf.name),
                ],
                input=md_doc.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                LogModule.RESTOR,
                "[LATEX-CHECK] Pandoc+XeLaTeX invocation failed for snippet {idx}: {err}",
                idx=snippet.index,
                err=str(e),
            )
            issues.append(
                FormulaIssue(
                    snippet_index=snippet.index,
                    message=f"Pandoc+XeLaTeX invocation failed: {e}",
                    severity="error",
                )
            )
            return issues

        stderr_pdf = proc_pdf.stderr.decode("utf-8", errors="ignore")
        # Heuristic: only surface *math-related* LaTeX errors that我们在整篇导出时
        # 也会真正关心。扩展后的签名覆盖了常见的公式/数学模式错误，同时仍然
        # 忽略因为片段缺少上下文而导致的文档结构、引用等非 math 报错。
        lower = stderr_pdf.lower()
        math_error_signatures = (
            # Original 3 signatures
            r"latex error: \mathbf allowed only in math mode",
            "missing $ inserted",
            "bad math environment delimiter",
            # Extended: command and environment errors
            "! undefined control sequence",
            "! missing \\end",
            "! missing \\begin",
            "! environment",
            # Extended: math-mode only errors
            "can be used only in math mode",
            "allowed only in math mode",
            # Extended: subscript/superscript errors
            "! double subscript",
            "! double superscript",
            # Extended: brace/argument errors (very common in math fragments)
            "! runaway argument",
            "! too many",
            "! extra",
            "! missing {",
            "mismatched braces",
        )
        matched = [sig for sig in math_error_signatures if sig in lower]
        has_latex_error = bool(matched)

        if has_latex_error:
            msg = "XeLaTeX reported an error while typesetting this formula snippet."
            logger.info(
                LogModule.RESTOR,
                "[LATEX-CHECK] Snippet {idx}: XeLaTeX math errors matched={matched}, stderr_snippet={stderr}",
                idx=snippet.index,
                matched=matched,
                stderr=(stderr_pdf or "")[:300],
            )
            issues.append(
                FormulaIssue(
                    snippet_index=snippet.index,
                    message=msg,
                    severity="error",
                    raw_stderr=stderr_pdf.strip() or None,
                )
            )
        else:
            logger.info(
                LogModule.RESTOR,
                "[LATEX-CHECK] Snippet {idx}: XeLaTeX dry-run completed without targeted math errors.",
                idx=snippet.index,
            )

    return issues


def check_formulas_with_pandoc(markdown: str) -> FormulaCheckResult:
    """
    Check all math snippets in the given Markdown using Pandoc.

    - If Pandoc is not available, returns pandoc_available=False and empty issues list.
    - Otherwise, returns all snippets and those with detected issues.
    """
    # 兼容旧接口：从 Markdown 粗略提取公式片段，再复用统一的 snippet 检查逻辑。
    snippets = extract_math_snippets(markdown)
    snippet_data = [{"segment_index": sn.index, "text": sn.text} for sn in snippets]

    result = check_snippets_with_pandoc(snippet_data)
    # 保留原先的位置信息（start_pos/end_pos），方便调用方在纯 Markdown 模式下高亮。
    # 此时 result.snippets 中只包含 index 和 text，我们用已有的 snippets 覆盖。
    result.snippets = snippets
    return result


@dataclass
class SegmentPdfCompatResult:
    """Result of checking a single translation segment for PDF compatibility."""

    passed: bool
    has_latex: bool
    pandoc_available: bool
    issues: List[FormulaIssue]
    stderr: Optional[str] = None
    message: str = ""


def check_segment_pdf_compat(segment_text: str, segment_index: int = 0) -> SegmentPdfCompatResult:
    """
    Check whether a single translation segment can be compiled to PDF via Pandoc + XeLaTeX.

    This is a thin wrapper around _check_snippet_with_pandoc that:
    - Skips segments with no LaTeX content (fast path)
    - Returns a SegmentPdfCompatResult with a clear passed/failed flag
    - Surfaces the raw stderr so callers can show detailed error messages

    Args:
        segment_text: The segment's target_text (may contain Markdown + LaTeX math).
        segment_index: Segment index (for logging/issue reporting).

    Returns:
        SegmentPdfCompatResult with passed=True if no issues found.
    """
    if not segment_text or not segment_text.strip():
        return SegmentPdfCompatResult(
            passed=True,
            has_latex=False,
            pandoc_available=False,
            issues=[],
            message="Segment text is empty; nothing to check.",
        )

    from utils.latex_repair_payload import has_latex_content

    if not has_latex_content(segment_text):
        return SegmentPdfCompatResult(
            passed=True,
            has_latex=False,
            pandoc_available=False,
            issues=[],
            message="No LaTeX content detected; PDF compatibility is assumed OK.",
        )

    pandoc_path = _get_pandoc_path()
    if not pandoc_path:
        return SegmentPdfCompatResult(
            passed=True,
            has_latex=True,
            pandoc_available=False,
            issues=[],
            message="Pandoc not available; skipping PDF compatibility check.",
        )

    snippet = MathSnippet(index=segment_index, text=segment_text)
    issues = _check_snippet_with_pandoc(snippet, pandoc_path)

    # Collect stderr from issues for the caller
    stderr_parts = [
        issue.raw_stderr for issue in issues if issue.raw_stderr
    ]
    stderr_combined = "\n".join(stderr_parts) if stderr_parts else None

    if issues:
        return SegmentPdfCompatResult(
            passed=False,
            has_latex=True,
            pandoc_available=True,
            issues=issues,
            stderr=stderr_combined,
            message=f"Found {len(issues)} PDF compatibility issue(s) in this segment.",
        )

    return SegmentPdfCompatResult(
        passed=True,
        has_latex=True,
        pandoc_available=True,
        issues=[],
        message="PDF compatibility check passed.",
    )



# ---------------------------------------------------------------------------
# KaTeX checker (HTML preview compatibility)
# ---------------------------------------------------------------------------

def extract_math_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Extract math blocks from Markdown text for KaTeX rendering.

    Supports:
      - $$...$$  (display math)
      - $...$    (inline math)
      - \\[...\\] (display math)
      - \\(...\\) (inline math)

    Returns a list of dicts: [{"content": str, "display": bool}, ...]
    """
    blocks: List[Dict[str, Any]] = []
    if not text:
        return blocks

    # We extract $$...$$ first, then $...$ from the remaining text,
    # so that $$ does not interfere with $ matching.
    placeholders: List[Dict[str, Any]] = []
    temp = text

    # Extract $$...$$ (display math) — process from end to start so indices
    # remain valid as we replace.
    for m in reversed(list(re.finditer(r"\$\$(.+?)\$\$", temp, re.DOTALL))):
        content = m.group(1).strip()
        if content:
            placeholders.append({"content": content, "display": True})
        placeholder = f"##KD{len(placeholders)}##"
        temp = temp[: m.start()] + placeholder + temp[m.end() :]

    # Extract $...$ (inline math) from the stripped text.
    for m in re.finditer(r"\$(.+?)\$", temp):
        content = m.group(1).strip()
        if content:
            blocks.append({"content": content, "display": False})

    # Restore display-math placeholders.
    for ph in reversed(placeholders):
        blocks.append(ph)

    # Extract \\[...\\] (display math)
    for m in re.finditer(r"\\\[(.+?)\\\]", text, re.DOTALL):
        content = m.group(1).strip()
        if content:
            blocks.append({"content": content, "display": True})

    # Extract \\(...\\) (inline math)
    for m in re.finditer(r"\\\((.+?)\\\)", text, re.DOTALL):
        content = m.group(1).strip()
        if content:
            blocks.append({"content": content, "display": False})

    return blocks


_KATEX_CHECKER_JS_PATH: Optional[Path] = None


def _get_katex_checker_js_path() -> Optional[Path]:
    """Resolve the KaTeX checker JS script path."""
    global _KATEX_CHECKER_JS_PATH
    if _KATEX_CHECKER_JS_PATH is not None:
        return _KATEX_CHECKER_JS_PATH

    # Look relative to this file: ../static/katex/katex_checker.js
    candidate = Path(__file__).parent.parent / "static" / "katex" / "katex_checker.js"
    if candidate.exists():
        _KATEX_CHECKER_JS_PATH = candidate
        return candidate

    # Fallback: search under backend/static/katex
    alt = Path.cwd() / "backend" / "static" / "katex" / "katex_checker.js"
    if alt.exists():
        _KATEX_CHECKER_JS_PATH = alt
        return alt

    _KATEX_CHECKER_JS_PATH = Path("").resolve()  # sentinel for "not found"
    return None


@dataclass
class KaTeXCheckResult:
    """Result of KaTeX checking a batch of segments."""

    katex_available: bool
    issues: List[FormulaIssue]
    checked_segments: int
    checked_blocks: int


def check_segments_with_katex(
    segments_data: List[Dict[str, Any]],
) -> KaTeXCheckResult:
    """
    Check a batch of segments for KaTeX (HTML preview) compatibility.

    Args:
        segments_data: List of {"segment_index": int, "text": str} dicts.

    Returns:
        KaTeXCheckResult with issues found.
    """
    js_path = _get_katex_checker_js_path()
    if js_path is None or not js_path.exists():
        logger.warning(
            LogModule.RESTOR,
            "[KATEX-CHECK] katex_checker.js not found; skipping KaTeX checks",
        )
        return KaTeXCheckResult(
            katex_available=False,
            issues=[],
            checked_segments=0,
            checked_blocks=0,
        )

    # Build payload: one entry per segment that has math blocks.
    payload: List[Dict[str, Any]] = []
    total_blocks = 0
    for seg in segments_data:
        idx = seg.get("segment_index")
        text = seg.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        blocks = extract_math_blocks(text)
        if not blocks:
            continue
        payload.append({"segment_index": idx, "math_blocks": blocks})
        total_blocks += len(blocks)

    if not payload:
        return KaTeXCheckResult(
            katex_available=True,
            issues=[],
            checked_segments=len(segments_data),
            checked_blocks=0,
        )

    logger.info(
        LogModule.RESTOR,
        "[KATEX-CHECK] Running KaTeX check for {segments} segments, {blocks} math blocks",
        segments=len(payload),
        blocks=total_blocks,
    )

    try:
        proc = subprocess.run(  # noqa: S603
            ["node", str(js_path), json.dumps(payload)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            LogModule.RESTOR,
            "[KATEX-CHECK] Node.js/KaTeX invocation failed: {err}",
            err=str(e),
        )
        return KaTeXCheckResult(
            katex_available=False,
            issues=[],
            checked_segments=len(payload),
            checked_blocks=total_blocks,
        )

    stderr = proc.stderr.decode("utf-8", errors="ignore")
    if stderr:
        logger.info(
            LogModule.RESTOR,
            "[KATEX-CHECK] Node.js stderr: {stderr}",
            stderr=stderr[:300],
        )

    if proc.returncode != 0:
        logger.warning(
            LogModule.RESTOR,
            "[KATEX-CHECK] Node.js exited with code {code}",
            code=proc.returncode,
        )

    stdout = proc.stdout.decode("utf-8", errors="ignore")
    issues: List[FormulaIssue] = []
    try:
        results = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning(
            LogModule.RESTOR,
            "[KATEX-CHECK] Failed to parse Node.js output: {out}",
            out=stdout[:200],
        )
        return KaTeXCheckResult(
            katex_available=True,
            issues=[],
            checked_segments=len(payload),
            checked_blocks=total_blocks,
        )

    for seg_result in results:
        seg_idx = seg_result.get("segment_index")
        for err in seg_result.get("errors", []):
            content = err.get("content", "")
            display = err.get("display", False)
            error_msg = err.get("error", "Unknown KaTeX error")
            mode_str = "display" if display else "inline"
            issues.append(
                FormulaIssue(
                    snippet_index=seg_idx,
                    message=(
                        f"KaTeX HTML preview error in {mode_str} math: {error_msg}. "
                        f"Problematic content: {content[:120]}{'...' if len(content) > 120 else ''}"
                    ),
                    severity="error",
                    raw_stderr=error_msg,
                )
            )

    logger.info(
        LogModule.RESTOR,
        "[KATEX-CHECK] Completed: segments={segs}, blocks={blocks}, issues={issues}",
        segs=len(payload),
        blocks=total_blocks,
        issues=len(issues),
    )

    return KaTeXCheckResult(
        katex_available=True,
        issues=issues,
        checked_segments=len(payload),
        checked_blocks=total_blocks,
    )
