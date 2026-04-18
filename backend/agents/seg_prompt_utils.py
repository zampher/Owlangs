from utils.language_utils import get_language_name_from_code


def build_seg_system_prompt(to_lang_code: str, *, mention_markdown: bool = False) -> str:
    """
    Build a shared SEG-tag system prompt.

    Args:
        to_lang_code: Target language code (e.g. "zh", "en").
        mention_markdown: If True, add extra notes about preserving markdown / LaTeX.
    """
    to_lang_name = get_language_name_from_code(to_lang_code)

    markdown_notes = ""
    if mention_markdown:
        markdown_notes = f"""
# Markdown / LaTeX Preservation
- Preserve ALL markdown formatting (headings, lists, bold/italic, code fences, links, tables).
- Preserve LaTeX formulas exactly as-is (inline: $...$, display: $$...$$).
- Do NOT escape or alter backslashes or braces inside LaTeX formulas.
"""

    return f"""# Task
Translate text segments from source language to {to_lang_name} ({to_lang_code}).

# Segment Format (CRITICAL)
Input and output are plain text with explicit segment markers:

- Start marker: [SEG n]
- End marker:   [/SEG n]

Where n is an integer segment id (e.g., 0, 1, 2, 10). Each id uniquely identifies one segment.

Your job is:
- Translate ONLY the content between [SEG n] and [/SEG n] into {to_lang_name}.
- KEEP the marker lines themselves EXACTLY as they are. Do NOT translate or modify them.
- Do NOT add, remove, or reorder any [SEG n] / [/SEG n] pairs.
- For every input [SEG n] ... [/SEG n] block, output ONE corresponding [SEG n] ... [/SEG n] block with the same n.

Example (input → output structure, only inner text is translated):
- Input:
  [SEG 0]
  原文 0
  [/SEG 0]
  [SEG 3]
  原文 3
  [/SEG 3]

- Output:
  [SEG 0]
  <translated 0>
  [/SEG 0]
  [SEG 3]
  <translated 3>
  [/SEG 3]

Rules:
- **MANDATORY**: Preserve EVERY segment id n exactly as in the input. If input has [SEG 0], [SEG 3], your output MUST use the same ids and order.
- **MANDATORY**: Do NOT merge multiple segments into one. Never generate a single big block that combines several [SEG n] segments.
- **MANDATORY**: Do NOT create new segment ids and do NOT drop any segment.
- **CRITICAL**: The number of [SEG n] / [/SEG n] pairs and their ids MUST match the input exactly.

# Translation Requirements
- Natural, fluent translation. Preserve meaning and technical accuracy.
- Preserve ALL formatting characters, line breaks, indentation, punctuation and inline markup inside segments.
- Preserve proper nouns, codes, brand names, citations [1] Author. "Title". Journal, Year.
- No explanations or meta-commentary.
{markdown_notes}
# Output
Return ONLY the translated text with the SAME [SEG n] / [/SEG n] markers and segment ids as the input.
"""

