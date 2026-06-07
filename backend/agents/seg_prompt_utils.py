import re

from utils.language_utils import get_language_name_from_code


def build_seg_system_prompt(to_lang_code: str, *, mention_markdown: bool = False) -> str:
    """
    Build a shared SEG-tag system prompt using bracket format ([SEG n]:).

    Args:
        to_lang_code: Target language code (e.g. "zh", "en").
        mention_markdown: If True, add extra notes about preserving markdown / LaTeX.
    """
    to_lang_name = get_language_name_from_code(to_lang_code)

    markdown_notes = ""
    if mention_markdown:
        markdown_notes = """
# Markdown / LaTeX Preservation
- Preserve ALL markdown formatting (headings, lists, bold/italic, code fences, links, tables).
- Preserve LaTeX formulas exactly as-is (inline: $...$, display: $$...$$).
- Do NOT escape or alter backslashes or braces inside LaTeX formulas.
"""

    return f"""# Role
You are a translation engine. Output is parsed by code. Produce only the translation.

# Task
Translate each segment below into {to_lang_name} ({to_lang_code}).

# Output Format
Each segment uses a [SEG n]: header followed by the translated text.
The next [SEG n]: header (or end of response) marks the segment boundary.

Correct format:
[SEG 0]:
Hello
[SEG 1]:
World

# Requirements
1. Output EVERY input segment with the same ID, same count, same order.
2. Start with [SEG <first_id>]: on the first line.
3. End immediately after the last segment; no extra text.
4. Preserve spaces, line breaks, punctuation, and formatting inside each segment.
5. Keep [SEG n]: headers plain — no bold, no headings, no code fences around the entire output.
{markdown_notes}
# Example
Input:
[SEG 0]:
销售合同
[SEG 1]:
甲方：某某公司

Output:
[SEG 0]:
Sales Contract
[SEG 1]:
Party A: XX Company
"""


def build_seg_user_prompt(chunk_dict: dict) -> str:
    """Build a user prompt with [SEG n]: headers from a dict of {{segment_id: text}}.

    Args:
        chunk_dict: Dict mapping segment IDs (str or int keys) to source text.

    Returns:
        Plain-text prompt with segments separated by [SEG n]: headers.
    """
    lines: list[str] = []
    keys = sorted(chunk_dict.keys(), key=int)
    for key in keys:
        text = chunk_dict[key] or ""
        lines.append(f"[SEG {key}]:")
        lines.append(text)
    if keys:
        first_id = keys[0]
        last_id = keys[-1]
        count = len(keys)
        lines.append("")
        lines.append(
            f"# This request has {count} segment(s): [SEG {first_id}] through [SEG {last_id}]."
        )
        lines.append(f"# Output exactly {count} segment(s) with the same IDs. Do not skip any.")
    return "\n".join(lines)


def parse_seg_output(text: str) -> dict[int, str]:
    """Parse LLM output in [SEG n]: format into {{segment_id: translated_text}}.

    Handles common small-model artifacts:
    - Code fence wrapping (``` ... ```)
    - Preamble text before the first [SEG n] header
    - Trailing commentary after the last segment
    - Colon omitted from header (tolerates [SEG n] without colon)
    - Markdown-bold headers like **[SEG 34]**

    Args:
        text: Raw LLM response string.

    Returns:
        Dict mapping integer segment IDs to their translated content.
    """
    if not text:
        return {}

    text = text.strip()

    # Strip code fences if the model wrapped output in ``` or ```markdown
    text = re.sub(r'^```\w*\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)

    # Normalize markdown-bold segment headers: **[SEG 34]** -> [SEG 34]:
    text = re.sub(
        r'\*\*\[SEG\s+(\d+)\]\*\*',
        r'[SEG \1]:',
        text,
        flags=re.IGNORECASE,
    )

    # Strip preamble/commentary before the first [SEG n]: header
    m_first = re.search(r'\[SEG\s+\d+\]', text, flags=re.IGNORECASE)
    if m_first:
        text = text[m_first.start():]

    # Split on [SEG n]: or [SEG n] (colon optional for small-model tolerance)
    parts = re.split(r'^\[SEG\s+(\d+)\]:?\s*$', text, flags=re.MULTILINE | re.IGNORECASE)
    result: dict[int, str] = {}
    for i in range(1, len(parts) - 1, 2):
        seg_id = int(parts[i])
        content = parts[i + 1].strip()
        result[seg_id] = content

    return result
