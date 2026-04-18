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


@dataclass
class LatexErrorContext:
    error_type: str
    line_no: int
    tex_snippet: str
    md_snippet: str
    error_token: str
    debug_md_path: Optional[Path]
    debug_tex_path: Path


def extract_latex_error_context(
    stderr: str,
    debug_tex_path: Path,
    debug_md_path: Optional[Path],
) -> Optional[LatexErrorContext]:
    """Parse XeLaTeX stderr + debug .tex to locate the first LaTeX error."""
    try:
        if not debug_tex_path.exists():
            return None

        # Detect error type from stderr
        lowered = stderr.lower()
        if "bad math environment delimiter" in lowered:
            error_type = "bad_math_environment_delimiter"
        elif r"\mathbf allowed only in math mode".lower() in lowered:
            error_type = "math_bold_outside_math_mode"
        else:
            error_type = "unknown_latex_error"

        # Try to locate the first "l.<num> " pattern in stderr (XeLaTeX style)
        m = re.search(r"l\.(\d+)\s", stderr)
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
        tex_snippet = f"{line_no}: {error_line}" if error_line else ""

        # Extract a representative token from the error line (if possible).
        # Keep this conservative; downstream uses it for best-effort segment matching.
        token_match = re.search(r"(\\underset|\\mathbf|\$[^$]+\$)", error_line)
        error_token = token_match.group(0) if token_match else ""

        return LatexErrorContext(
            error_type=error_type,
            line_no=line_no,
            tex_snippet=tex_snippet,
            md_snippet="",
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

