import re

from utils.language_utils import get_language_name_from_code


def build_seg_system_prompt(to_lang_code: str, *, mention_markdown: bool = False) -> str:
    """
    Build a shared SEG-tag system prompt using bracket format ([SEG n]:).

    Segment IDs in each request are LOCAL and consecutive: [SEG 0], [SEG 1], ... [SEG n-1].
    They are NOT global document indices and may skip numbers in the source document.

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

IDs are LOCAL to this request: always start at [SEG 0] and increment by 1 ([SEG 0], [SEG 1], ...).
Do NOT invent IDs that were not in the input. Do NOT renumber to fill gaps.

Correct format:
[SEG 0]:
Hello
[SEG 1]:
World

# Requirements
1. Output EVERY input segment with the same LOCAL ID, same count, same order.
2. Start with [SEG 0]: on the first line (or [SEG <first_local_id>] if the input starts elsewhere).
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


def build_seg_user_prompt_from_texts(texts: list[str]) -> str:
    """Build a user prompt with LOCAL consecutive [SEG 0]..[SEG n-1] headers.

    Args:
        texts: Source texts in chunk order.

    Returns:
        Plain-text prompt with segments separated by local [SEG n]: headers.
    """
    lines: list[str] = []
    count = len(texts)
    for local_id, text in enumerate(texts):
        lines.append(f"[SEG {local_id}]:")
        lines.append(text or "")
    if count > 0:
        lines.append("")
        lines.append(
            f"# This request has {count} segment(s): [SEG 0] through [SEG {count - 1}]."
        )
        lines.append(
            f"# Output exactly {count} segment(s) with LOCAL IDs 0 through {count - 1}. Do not skip any."
        )
    return "\n".join(lines)


def build_seg_user_prompt(chunk_dict: dict) -> str:
    """Build a user prompt with LOCAL [SEG 0]..[SEG n-1] headers from a chunk dict.

    Global segment indices in chunk_dict keys are used only for ordering; they are NOT
    sent to the model. Call parse_seg_output_to_global() when parsing the response.

    Args:
        chunk_dict: Dict mapping global segment IDs (str or int keys) to source text.

    Returns:
        Plain-text prompt with local consecutive [SEG n]: headers.
    """
    keys = sorted(chunk_dict.keys(), key=int)
    texts = [chunk_dict[key] or "" for key in keys]
    return build_seg_user_prompt_from_texts(texts)


def global_indices_from_chunk_dict(chunk_dict: dict) -> list[int]:
    """Return global segment indices for a chunk dict, sorted numerically."""
    return [int(k) for k in sorted(chunk_dict.keys(), key=int)]


def map_local_parse_to_global(
    parsed_local: dict[int, str],
    global_indices: list[int],
) -> dict[int, str]:
    """Map parsed LOCAL [SEG n] results to global segment indices.

    Args:
        parsed_local: Dict from parse_seg_output (local segment IDs).
        global_indices: Global document indices in the same order as the prompt texts.

    Returns:
        Dict mapping global segment index to translated text.
    """
    n = len(global_indices)
    if n == 0:
        return {}

    result: dict[int, str] = {}

    for local_id in range(n):
        if local_id in parsed_local:
            result[global_indices[local_id]] = parsed_local[local_id]

    if len(result) == n:
        return result

    for local_id, text in parsed_local.items():
        if 0 <= local_id < n:
            global_idx = global_indices[local_id]
            if global_idx not in result or not (result[global_idx] or "").strip():
                result[global_idx] = text

    if len(result) == n:
        return result

    # Position fallback only when model returned consecutive LOCAL ids starting at 0
    if len(parsed_local) == n:
        sorted_ids = sorted(parsed_local.keys())
        if sorted_ids == list(range(n)):
            for i in range(n):
                if global_indices[i] not in result:
                    result[global_indices[i]] = parsed_local[i]

    return result


def parse_seg_output_to_global(text: str, global_indices: list[int]) -> dict[int, str]:
    """Parse LLM SEG-tag output and map local IDs to global segment indices."""
    parsed_local = parse_seg_output(text)
    return map_local_parse_to_global(parsed_local, global_indices)


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
