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
    user_prompt: Optional[str] = None


@dataclass
class LatexRepairResult:
    fixed_md_snippet: str
    notes: str | None = None


_ERROR_TYPE_GUIDANCE: dict[str, str] = {
    "math_bold_outside_math_mode": (
        "- This error means commands like `\\mathbf{...}`, `\\mathit{...}`, `\\mathcal{...}`, or other math fonts are used in normal text without `$...$` or other math delimiters.\n"
        "- Locate where bold/math fonts are intended and **wrap those parts in proper LaTeX math**: e.g. `$\\mathbf{x}$`, `$\\mathcal{C}$`.\n"
        "- Do NOT convert formulas into plain text; keep them as LaTeX math so they render as equations in the final PDF.\n"
        "- Control-flow keywords and plain-language words (if, then, else, while, for, comments) **must remain outside** math delimiters."
    ),
    "bad_math_environment_delimiter": (
        "- This error means math delimiters are mismatched, such as `\\( ... $$`, `\\[ ... $`, or stray pieces like `\\(\\underset\\) \\(`.\n"
        "- Repair delimiters so every math expression has a consistent pair: `$...$`, `$$...$$`, `\\(...\\)` or `\\[...\\]`.\n"
        "- Prefer to **keep the same block style** as the input: inline stays inline, display stays display.\n"
        "- Keep all non-math words as plain text outside `$...$`. Do not wrap whole sentences inside math."
    ),
    "missing_dollar_inserted": (
        "- This error means XeLaTeX hit `^`, `_`, or a math-only command where it could not open math mode, or the **superscript/subscript "
        "argument is syntactically broken** (very common after translation/OCR).\n"
        "- **Wrap** any expression using `^`, `_`, `\\theta`, `\\sum`, Greek letters, etc. in **balanced** inline math `$...$` or display `$$...$$`.\n"
        "- **Mangled superscripts (CRITICAL)**: If you see patterns like `^{\\{\\prime\\}{[}...` or mixed `{`, `}`, `[`, `]` inside one `^{...}`, the braces are wrong. "
        "Rewrite as valid math, e.g. prime + arguments: `$x^{\\prime}(t,\\theta_d)$` or `$x'(t,\\theta_d)$` — use **one** balanced `{...}` for the whole superscript, or split into separate factors.\n"
        "- Do **not** use `[` / `]` as fake grouping inside `^{...}`; use commas, `\\,`, or `\\left[ ... \\right]` only when you mean brackets.\n"
        "- Subscripts: use `\\theta_{d}` **inside** `$...$`, not a corrupted mix like `\\theta\\_\\{d\\}` with stray backslashes or braces.\n"
        "- Ensure display math (`$$...$$` / `\\[...\\]`) is fully closed before the next paragraph."
    ),
    "undefined_control_sequence": (
        "- This error means a `\\command` is not recognized by XeLaTeX.\n"
        "- Common causes: typos (`\\ailgn` instead of `\\align`), commands from packages not loaded, or commands invented by translation.\n"
        "- **Fix typos**: correct misspelled commands to their proper names (`\\align`, `\\frac`, `\\mathbf`, etc.).\n"
        "- **Replace unsupported commands** with standard LaTeX equivalents.\n"
        "- If a command is plain text that happens to start with `\\` (e.g. `\\hline` as a word), escape it as `\\\\hline` so it is treated as text.\n"
        "- Do NOT remove the content; replace the broken command with a valid one or wrap it in `\\text{...}` if it is meant to be text."
    ),
    "environment_undefined": (
        "- This error means a `\\begin{env}...\\end{env}` environment is not recognized.\n"
        "- Common causes: `\\begin{align}` without `amsmath` package, `\\begin{equation}` typos, or invented environment names.\n"
        "- **Replace with supported environments**: `align` → `aligned` (if inline) or keep `align` but ensure it is inside `$$...$$`.\n"
        "- For simple aligned math, use `$$ \\begin{aligned} ... \\end{aligned} $$` instead of raw `\\begin{align}`.\n"
        "- If the environment is not needed, remove `\\begin{...}` / `\\end{...}` and keep the inner content in `$...$` or `$$...$$`."
    ),
    "missing_end_environment": (
        "- This error means a `\\begin{...}` is missing its matching `\\end{...}`.\n"
        "- Find the unclosed environment and add the missing `\\end{env}` at the correct position.\n"
        "- If the `\\begin{...}` itself is accidental (e.g. from corrupted text), remove it and keep the inner content in proper math delimiters."
    ),
    "missing_begin_environment": (
        "- This error means a `\\end{...}` appears without a matching `\\begin{...}`.\n"
        "- Either remove the stray `\\end{...}` or add the missing `\\begin{...}` before it.\n"
        "- If the environment is not needed, convert the content to inline math `$...$` or display math `$$...$$`."
    ),
    "brace_mismatch": (
        "- This error means braces `{` and `}` are mismatched.\n"
        "- Carefully balance every opening `{` with a closing `}`.\n"
        "- Common cause: nested commands like `\\frac{a}{b}` where one brace is missing.\n"
        "- Do not add or remove content; only fix brace balance."
    ),
    "runaway_argument": (
        "- This error means a command argument (inside `{...}`) was not properly closed.\n"
        "- Find the command with the unclosed argument and add the missing `}`.\n"
        "- Common cause: `\\frac{a{b}` or `\\mathbf{x` missing closing brace."
    ),
    "missing_file": (
        "- This error means a required file or package is missing.\n"
        "- Since we cannot install packages, remove or replace the command that requires the missing file.\n"
        "- Use standard LaTeX commands that do not require external packages."
    ),
    "double_subscript": (
        "- This error means a subscript `_` appears twice in a row, e.g. `x_{i_j_k}`.\n"
        "- Use braces to group nested subscripts: `x_{i_{j_k}}` instead of `x_i_j_k`."
    ),
    "double_superscript": (
        "- This error means a superscript `^` appears twice in a row.\n"
        "- Use braces to group nested superscripts: `x^{a^{b}}` instead of `x^a^b`."
    ),
    "manual_segment_repair": (
        "- This is a user-initiated formula repair. Inspect the snippet carefully for any LaTeX issues.\n"
        "- Common problems to watch for:\n"
        "  * **Unclosed environments**: every `\\begin{xxx}` MUST have a matching `\\end{xxx}`. If `\\end` is missing, add it at the correct position.\n"
        "  * **Environment in wrong math mode**: environments like `align`, `equation`, `gather` MUST be in display math (`$$...$$` or `\\[...\\]`), NOT in inline math (`$...$`). Either move them to display mode or remove the environment wrapper.\n"
        "  * **Empty environments**: `\\begin{align}\\end{align}` with nothing inside is useless and often causes renderer errors. Remove it or add meaningful content.\n"
        "  * **Math commands outside math mode**: commands like `\\sum`, `\\frac`, `\\mathbf` must be inside `$...$` or another math delimiter.\n"
        "  * **Missing $ / broken `^{...}`**: PDF export often fails with `Missing $ inserted` when superscripts nest `\\{`, `}`, `[` incorrectly. "
        "Rewrite to clean math (e.g. `$f^{\\prime}(t,\\theta_d)$`); never leave `[` as an unescaped delimiter inside a superscript block.\n"
        "  * **\\tag vs \\[...\\]**: Do **not** use `\\tag{n}` inside `\\[...\\]`. Use `\\begin{equation}...\\end{equation}`, or remove `\\tag` and write `(n)` in text.\n"
        "  * **Markdown leakage**: Remove stray ``` fences; fix corrupted theta like `$\\textbackslash theta` → `$\\theta_0^{*}$` or equivalent valid math.\n"
        "- Do NOT over-correct: if `\\begin{aligned}...\\end{aligned}` is properly closed and inside correct delimiters, leave it alone."
    ),
    "environment_in_wrong_mode": (
        "- A display-only environment (`align`, `equation`, `gather`, etc.) was found inside inline math (`$...$`).\n"
        "- **Fix**: Move the environment to display math by changing `$...$` to `$$...$$` (or `\\[...\\]`).\n"
        "- **Alternative**: If the environment is not needed, remove `\\begin{...}` and `\\end{...}` and keep only the inner math content in `$...$`.\n"
        "- Do NOT leave display environments inside inline delimiters; both KaTeX (HTML) and XeLaTeX (PDF) will reject this."
    ),
    "pre_check_failed": (
        "- This segment failed a pre-export PDF compatibility check.\n"
        "- Review the segment for broken LaTeX: unmatched delimiters, undefined commands, missing braces, or environment issues.\n"
        "- Ensure all math is properly wrapped in `$...$`, `$$...$$`, `\\(...\\)`, or `\\[...\\]`.\n"
        "- Pay special attention to **corrupted superscripts** (`^{...}` with mixed brackets) that pass HTML preview but break XeLaTeX.\n"
        "- **\\tag + \\[...\\] (CRITICAL for PDF)**: If you see `\\[ ... \\tag{n} ... \\]`, rewrite: use `\\begin{equation}...\\end{equation}` with `\\tag` **or** drop `\\tag` and keep `(n)` in the surrounding text. Do **not** leave `\\tag` inside raw `\\[...\\]`.\n"
        "- Remove or fix any commands that are not standard LaTeX."
    ),
    "docx_texmath_failure": (
        "- Pandoc converted this Markdown fragment to DOCX but **texmath** (OMML) reported errors on **display math**.\n"
        "- Typical causes: `\\tag{...}` preceded by comma-separated clauses (`unexpected control sequence \\tag`), "
        "unbalanced `{` `}` (often inside `\\mathrm{...}` or `\\triangleright{...}`), "
        "or `\\begin{array}` / `\\left\\{` without matching `\\end{array}` / `\\right.`.\n"
        "- **If stderr mentions `unexpected \\tag`**: rewrite comma-separated constraints before `\\tag` using `\\quad` between clauses, "
        "or split into separate display blocks; ensure nothing after the last comma looks like an unfinished subformula.\n"
        "- **Brace mismatch**: balance every `{`/`}`; close environments before `\\tag`.\n"
        "- Goal: the same segment text, processed like DOCX export (normalized Markdown math), must convert to DOCX **without** "
        "`Could not convert TeX math` warnings in Pandoc stderr.\n"
        "- Preserve segment meaning and non-math wording; fix LaTeX structure only.\n"
        "- **CRITICAL — single segment boundary**: stderr may mention several equations or line numbers from Pandoc's trace; "
        "**only repair math that appears in the snippet** between the markers above. Do **not** prepend or paste another equation "
        "(e.g. an objective `\\min ... \\tag{56}`) unless that exact equation text is already part of the snippet. "
        "Do **not** output multiple distinct `\\tag{n}` blocks whose numbers were not all present in the original snippet.\n"
    ),
    "eqno_in_math_mode": (
        "- XeLaTeX: `! You can't use \\eqno' in math mode` (often reported at a closing `\\]`).\n"
        "- **Cause**: `\\tag{...}` inside **unnumbered** display `\\[...\\]`; the kernel then hits `\\eqno` in an illegal position.\n"
        "- **Fix** (pick one): (1) Replace the block with `\\begin{equation} ... \\end{equation}` and keep `\\tag{n}` if numbering is required; "
        "(2) Remove `\\tag{n}` from inside display math and write the label as plain text `(n)` after the equation; "
        "(3) Use `$$\\begin{aligned} ... \\end{aligned}$$` without `\\tag` when numbering is optional.\n"
        "- After fixing, ensure **no** `\\tag` remains inside `\\[...\\]`."
    ),
}


def _build_prompt(req: LatexRepairRequest) -> str:
    extra_guidance = _ERROR_TYPE_GUIDANCE.get(req.error_type, "")
    if not extra_guidance:
        extra_guidance = (
            "- Review the segment for common LaTeX issues: unmatched delimiters, undefined commands, missing braces, or environment mismatches.\n"
            "- Ensure all math is properly wrapped in `$...$`, `$$...$$`, `\\(...\\)`, or `\\[...\\]`.\n"
            "- **If stderr mentions \\eqno / \\tag with \\]**: never keep `\\tag{...}` inside `\\[...\\]`; use `equation`/`gather` or drop `\\tag`.\n"
            "- Remove Markdown artifacts (` ``` ` fences) and literal `\\textbackslash` placeholders where real math was intended.\n"
            "- Remove or fix any commands that are not standard LaTeX."
        )

    prompt = rf"""You are a LaTeX typesetting expert.
The following snippet comes from a document that may contain **formulas or pseudo-code (algorithms with line numbers)**.
A PDF export failed with a LaTeX error.

Error type: {req.error_type}

Diagnostic context (LaTeX log around the error, or Pandoc/texmath stderr for DOCX):
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
5. Preserves the original structural style (including algorithm lines, any leading line numbers like `1:`, separators such as `|`, and line breaks) as much as possible. Do **not** add Markdown constructs such as lists, headings, or `**bold**`.
6. Do **not** introduce new LaTeX environments that are not already present in the snippet (for example do not wrap the code in `\\begin{{algorithm}}...\\end{{algorithm}}` or other algorithm/align environments if they were not in the input).
7. If the snippet contains line numbers, normalize them so there is at most **one line number per logical step** and numbering is monotonic. Do not invent new steps.
8. If the snippet represents pseudo-code, apply consistent indentation based on control-flow structure (if/while/for/else/end). Do not guess a programming language.
9. Keeps every non-math token (numbers, colons, pipes, words like then/else, punctuation) unless it is obviously duplicated or part of a broken control sequence. Do **not** drop or hide such tokens inside math.
10. Does not modify surrounding sections outside this snippet.
11. **CRITICAL — Environment closure**: Every `\begin{{xxx}}` MUST have a matching `\end{{xxx}}` at the correct nesting level. If `\end` is missing, add it. If `\begin` is stray, remove it. Do NOT leave environments half-open.
12. **CRITICAL — Environment math mode**: Display-only environments (`align`, `equation`, `gather`, `eqnarray`, `multline`, `split`) MUST NOT appear inside inline math (`$...$`). Either change the delimiters to display mode (`$$...$$` or `\[...\]`) or remove the environment wrapper entirely.
13. **CRITICAL — Empty environments**: An environment with no meaningful content between `\begin` and `\end` (e.g. `\begin{{align}}\end{{align}}`) is broken. Remove it or add the intended math content inside it.
14. **CRITICAL — Superscript/bracket corruption (XeLaTeX)**: If superscripts contain mangled brace/bracket mixes (common after translation), **rewrite the entire formula** as standard balanced math inside one pair of dollar signs (derivative style: x with prime and arguments such as t and theta sub d). Never use raw square brackets as grouping inside a superscript; use commas or proper `` \\left[ ... \\right] `` for brackets.
15. **CRITICAL — \\tag and display math (PDF / \\eqno errors)**: Do **not** put `\\tag{{...}}` inside `\\[...\\]`. Pandoc often emits that shape; XeLaTeX may then fail with `You can't use \\eqno' in math mode` at the closing `\\]`. Rewrite as `\\begin{{equation}}...\\end{{equation}}` (with `\\tag` if needed), or use `$$...$$` / `\\[...\\]` **without** `\\tag` and add the number as plain text `(n)` in the sentence.

{extra_guidance}

Output **only** the corrected LaTeX snippet (pure LaTeX/text lines, no Markdown fences, no explanations).
"""

    # Append user's custom guidance if provided
    if req.user_prompt:
        prompt += (
            f"\n\nAdditional instructions from the user (follow these carefully):\n"
            f"{req.user_prompt}\n"
        )

    return prompt


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
        timeout=int(cfg.get("timeout", 120)),
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
