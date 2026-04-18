from __future__ import annotations

"""
Thin wrapper for LLM-based LaTeX / Markdown formula repair.

This module is designed to be a single integration point with the underlying
LLM provider so that routing/business logic does not depend on vendor details.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.llm_client import LLMMessage, LLMConfig, llm_chat


@dataclass
class LatexRepairRequest:
    error_type: str
    tex_context: str
    md_context: str
    original_md_snippet: str
    task_id: str
    segment_index: int | None = None
    snippet_index: int | None = None
    llm_config: Optional[Dict[str, Any]] = None


@dataclass
class LatexRepairResult:
    fixed_md_snippet: str
    notes: str | None = None


def _build_prompt(req: LatexRepairRequest) -> str:
    # Add targeted guidance for specific error types so the model focuses on the real root cause.
    extra_guidance_parts: list[str] = []
    if req.error_type == "math_bold_outside_math_mode":
        extra_guidance_parts.append(
            "- This error usually means commands like `\\mathbf{...}`, `\\mathit{...}`, or other math fonts are used in normal text without `$...$` or other math delimiters.\n"
            "- In the snippet, locate where bold math is intended (for example short variable names, vectors, or symbols) and **wrap those parts in proper LaTeX math**:\n"
            "  - e.g. `$\\mathbf{x}$`, `$\\mathbf{v}$`, or similar.\n"
            "- Do not convert formulas into plain text; keep them as LaTeX math so they can be rendered as equations in the final PDF.\n"
            "- **Do not introduce new Markdown formatting** (no new `**bold**`, bullet lists, or numbered lists) unless it is already present in the input snippet.\n"
            "- Keep the overall line structure and pseudo-code style (such as algorithm numbering and step descriptions) as close to the original as possible; only adjust the minimal LaTeX spans needed to fix the error.\n"
            "- Control-flow keywords and plain-language words such as `if`, `then`, `else`, `while`, `end while`, `for`, and any natural-language comments **must remain outside** math delimiters. Do not move them into `$...$`."
        )
    elif req.error_type == "bad_math_environment_delimiter":
        extra_guidance_parts.append(
            "- This error usually means math delimiters are opened/closed in a mismatched way, such as `\\( ... $$`, `\\[ ... $`, or stray pieces like `\\(\\underset\\) \\(`.\n"
            "- Carefully repair the math delimiters so every math expression has a consistent opening and closing pair: either `$...$`, `$$...$$`, `\\(...\\)` or `\\[...\\]`.\n"
            "- When you rewrite the problematic part, express the math as valid LaTeX (e.g. `$...$`, `\\(...\\)` or `\\[...\\]`), not as plain descriptive text.\n"
            "- Prefer to **keep the same block style** as the input: if the original used inline math, keep it inline; if it used display math (`$$...$$`), keep display math.\n"
            "- **Do not reformat the algorithm or paragraph layout** (no extra line breaks, no new list markers); only change the LaTeX around the broken delimiters.\n"
            "- Keep all non-math words (e.g. natural-language descriptions, comments, and explanations) exactly as plain text outside `$...$`. Do not wrap whole sentences or comments inside math."
        )

    extra_guidance = "\n\n".join(extra_guidance_parts) if extra_guidance_parts else ""

    return f"""You are a LaTeX typesetting expert.
The following snippet comes from a document that may contain **formulas or pseudo-code (algorithms with line numbers)**.
A PDF export failed with a LaTeX error.

Error type: {req.error_type}

LaTeX context (around the error):
```tex
{req.tex_context}
```

The following snippet is the part we want to repair.
Treat it as a small LaTeX fragment (it may currently contain a mix of plain text, line numbers like `1:`, separators like `|`, and LaTeX commands):
```tex
{req.original_md_snippet}
```

Task: Return a corrected **LaTeX snippet** that:
1. Keeps the original meaning and surrounding non-math text as much as possible (do not drop words like control-flow keywords, comments, or English phrases).
2. Fixes LaTeX math syntax so that Pandoc + XeLaTeX can compile it successfully.
3. Uses proper LaTeX math for formulas (`$...$`, `$$...$$`, `\\(...\\)`, or `\\[...\\]`) and does **not** turn formulas into plain descriptive text.
4. Uses consistent math delimiters without mixing them incorrectly. **Preserve the existing math delimiter style whenever it is already correct** (e.g. keep `$$...$$` as `$$...$$`; keep `\\[...\\]` as `\\[...\\]`; do not rewrite one correct style into another).
5. Avoids constructs that cause \"Bad math environment delimiter\" or `\\mathbf` outside of math mode.
6. Preserves the original structural style (including algorithm lines, any leading line numbers like `1:`, separators such as `|`, and line breaks) as much as possible. Do **not** add Markdown constructs such as lists, headings, or `**bold**`.
7. Do **not** introduce new LaTeX environments that are not already present in the snippet (for example do not wrap the code in `\\begin{{algorithm}}...\\end{{algorithm}}` or other algorithm/align environments if they were not in the input).
8. If the snippet contains line numbers (for example a pattern like `<integer>:` at the start of logical steps), normalize them so that there is at most **one line number per logical step** and the numbering is monotonic and consistent across the snippet. Do not invent new steps or skip existing ones.
9. If the snippet represents pseudo-code or an algorithm, apply consistent indentation using a simple, language-agnostic rule: increase indentation level by two spaces after opening a control-flow block (such as lines that clearly start a block with words like `if`, `while`, `for`, or similar), decrease indentation back when the block is closed (lines starting with phrases like `end` or equivalent), and keep `else`-style lines aligned with their matching `if`. Do not guess a specific programming language; just apply indentation based on the visible structure in this snippet.
10. Keeps every non-math token from the input snippet (including numbers, colons, pipes, words like `then`, `else`, comments, and punctuation) unless it is obviously duplicated or part of a broken LaTeX control sequence. Do **not** drop or hide such tokens inside math.
11. Does not modify surrounding sections outside this snippet.

{extra_guidance}

Output **only** the corrected LaTeX snippet (pure LaTeX/text lines, no Markdown fences, no explanations).
"""


def _build_llm_config_from_dict(cfg: Optional[Dict[str, Any]]) -> Optional[LLMConfig]:
    if not cfg:
        return None
    base_url = cfg.get("base_url")
    model_id = cfg.get("model_id")
    if not base_url or not model_id:
        return None
    return LLMConfig(
        base_url=base_url,
        model_id=model_id,
        api_key=cfg.get("api_key"),
        temperature=float(cfg.get("temperature", 0.1)),
        concurrent=int(cfg.get("concurrent", 1)),
        connect_timeout=int(cfg.get("connect_timeout", 5)),
        timeout=int(cfg.get("timeout", 30)),
        thinking=str(cfg.get("thinking", "default")),
        retry=int(cfg.get("retry", 3)),
        max_tokens=cfg.get("max_tokens"),
        api_type=str(cfg.get("api_type", "openai")),
        platform_key=cfg.get("platform_key"),
    )


def repair_latex_snippet_with_llm(req: LatexRepairRequest) -> LatexRepairResult:
    """
    Call the configured LLM provider to suggest a repaired Markdown snippet.

    - If llm_config is missing or invalid, falls back to echoing original snippet.
    - Any runtime errors are swallowed and reported via notes to avoid breaking export.
    """
    prompt = _build_prompt(req)
    llm_cfg = _build_llm_config_from_dict(req.llm_config)
    if llm_cfg is None:
        return LatexRepairResult(
            fixed_md_snippet=req.original_md_snippet,
            notes="LLM config missing or incomplete; returning original snippet.",
        )

    try:
        messages = [LLMMessage(role="user", content=prompt)]
        fixed = llm_chat(messages, llm_cfg).strip()
        if not fixed:
            fixed = req.original_md_snippet
        return LatexRepairResult(
            fixed_md_snippet=fixed,
            notes="LLM repair executed successfully.",
        )
    except Exception as e:  # noqa: BLE001
        return LatexRepairResult(
            fixed_md_snippet=req.original_md_snippet,
            notes=f"LLM repair failed: {e}",
        )


