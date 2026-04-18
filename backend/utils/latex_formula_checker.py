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


PANDOC_FROM_FOR_SNIPPETS = "markdown+pipe_tables+hard_line_breaks+link_attributes"

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


def check_snippets_with_pandoc(snippet_texts: List[str]) -> FormulaCheckResult:
    """
    Check a pre-classified list of formula snippets using Pandoc.

    This是推荐的入口：调用方自己决定哪些片段属于“公式”，本函数只负责
    调用 Pandoc 做解析校验，不从 Markdown 里再去猜测公式位置。
    """
    pandoc_path = _get_pandoc_path()
    snippets: List[MathSnippet] = [
        MathSnippet(index=i, text=text) for i, text in enumerate(snippet_texts)
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


def _check_snippet_with_pandoc(snippet: MathSnippet, pandoc_path: Path) -> List[FormulaIssue]:
    """
    Check a single math snippet via Pandoc + XeLaTeX (dry-run).

    Strategy:
    - Wrap the snippet text in a minimal Markdown document.
    - Invoke Pandoc with --pdf-engine=xelatex to run the same toolchain as export.
    - If XeLaTeX fails (non-zero exit or LaTeX Error in stderr), record an issue.

    IMPORTANT:
    - This checker is ONLY used for short formula snippets, not full documents.
    - It is expected that some snippets will not be valid standalone LaTeX; in that
      case, we surface the error so the frontend can decide whether to use AI repair.
    """
    md_doc = snippet.text
    issues: List[FormulaIssue] = []

    broken_rule = _detect_broken_math_patterns(md_doc)
    if broken_rule:
        logger.info(
            LogModule.RESTOR,
            "[LATEX-CHECK] Snippet {idx}: matched broken-math rule={rule}, preview={preview}",
            idx=snippet.index,
            rule=broken_rule,
            preview=md_doc.replace("\n", " ")[:200],
        )
        return [
            FormulaIssue(
                snippet_index=snippet.index,
                message=f"Detected broken math pattern: {broken_rule}",
                severity="error",
            )
        ]

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

        debug_root = Path.cwd() / "backend" / "debug" / "latex_snippets"
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
        # 也会真正关心，例如：
        # - \mathbf allowed only in math mode
        # - Missing $ inserted
        # - Bad math environment delimiter
        #
        # 其他因为片段缺少上下文而导致的 LaTeX 报错（例如文档结构、引用等）在这里忽略，
        # 避免把所有公式都标成有问题。
        lower = stderr_pdf.lower()
        math_error_signatures = (
            r"latex error: \mathbf allowed only in math mode",
            "missing $ inserted",
            "bad math environment delimiter",
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
    snippet_texts = [sn.text for sn in snippets]

    result = check_snippets_with_pandoc(snippet_texts)
    # 保留原先的位置信息（start_pos/end_pos），方便调用方在纯 Markdown 模式下高亮。
    # 此时 result.snippets 中只包含 index 和 text，我们用已有的 snippets 覆盖。
    result.snippets = snippets
    return result

