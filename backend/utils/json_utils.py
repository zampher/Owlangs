# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import json
import re
from typing import Optional
from utils.token_estimator import estimate_chunk_tokens_from_json_dict, estimate_json_tokens

# Re-export for backward compatibility (deprecated, use estimate_json_tokens from token_estimator instead)
get_json_tokens = estimate_json_tokens


def segments2json_chunks(
    segments: list[str],
    chunk_size_max: int,
    estimate_tokens: bool = False,
    segment_indices: Optional[list[int]] = None,
    max_segments_per_chunk: Optional[int] = None,
) -> tuple[dict[str, str], list[dict[str, str]], list[tuple[int, int]], Optional[list[int]]]:
    """
    Convert text segment list (segments) to multiple JSON chunks.

    Args:
        segments: List of text segments
        chunk_size_max: Maximum chunk size in tokens (text content only, excluding system prompt and overhead)
        estimate_tokens: If True, also estimate input tokens for each chunk (including system prompt)
        segment_indices: Optional list of original segment indices for each segment.
                        If provided, uses these indices (may be non-continuous, e.g., [0, 1, 3, 5, 6]).
                        If None, uses enumerate (0, 1, 2, ...) for backward compatibility.
        max_segments_per_chunk: If set (e.g. 1), never merge more than this many segments per chunk.
                               Use 1 for segment-per-request to avoid one bad segment breaking a whole chunk.

    Returns:
        Tuple containing:
        - indexed_originals: Dict mapping segment index to original text
        - json_chunks_list: List of chunk dictionaries
        - merged_indices_list: List of tuples indicating merged segments
        - chunk_tokens: Optional list of estimated input tokens for each chunk (if estimate_tokens=True)
    """
    # Validate segment_indices if provided
    if segment_indices is not None and len(segment_indices) != len(segments):
        raise ValueError(
            f"segment_indices length ({len(segment_indices)}) must match segments length ({len(segments)})"
        )
    
    # Use provided segment indices or fallback to enumerate
    use_original_indices = segment_indices is not None and len(segment_indices) == len(segments)
    
    # === Part 1: Preprocessing - split segments that exceed token limit ===
    new_segments = []
    new_segment_indices = []  # Track indices for split segments
    merged_indices_list = []

    for list_idx, segment in enumerate(segments):
        # Get original segment index (if provided) or use list index
        original_seg_idx = segment_indices[list_idx] if use_original_indices else list_idx
        
        # Check if a single segment (as a JSON object value) exceeds the token limit
        # Use actual segment index as key to accurately estimate tokens including the index number
        # The index number (e.g., "0", "1", "1234") is part of the JSON format and must be included in token estimation
        test_dict = {str(original_seg_idx): segment}
        segment_tokens = estimate_json_tokens(test_dict)
        
        if segment_tokens > chunk_size_max:
            sub_segments = []
            lines = segment.splitlines(keepends=True)
            current_sub_segment = ""
            for line in lines:
                next_sub_segment = current_sub_segment + line
                # Use actual segment index for accurate token estimation (index is part of JSON format)
                next_test_dict = {str(original_seg_idx): next_sub_segment}
                next_tokens = estimate_json_tokens(next_test_dict)

                if next_tokens > chunk_size_max:
                    if current_sub_segment:
                        sub_segments.append(current_sub_segment)

                    # Even if a single line exceeds the limit, it must be added as an independent sub-segment
                    sub_segments.append(line)
                    current_sub_segment = ""
                else:
                    current_sub_segment = next_sub_segment

            if current_sub_segment:
                sub_segments.append(current_sub_segment)

            if not sub_segments and segment == "":
                sub_segments.append("")

            start_index = len(new_segments)
            new_segments.extend(sub_segments)
            # For split segments, all sub-segments use the same original segment index
            new_segment_indices.extend([original_seg_idx] * len(sub_segments))
            end_index = len(new_segments)
            if end_index - start_index > 1:
                merged_indices_list.append((start_index, end_index))
        else:
            new_segments.append(segment)
            new_segment_indices.append(original_seg_idx)

    # === Part 2: Combine into JSON chunks using token-based limit (or max_segments_per_chunk) ===
    json_chunks_list = []
    if not new_segments:
        return ({}, [], [], None) if estimate_tokens else ({}, [], [])

    chunk = {}
    for list_idx, val in enumerate(new_segments):
        # Get segment index (original if provided, otherwise use list index)
        seg_idx = new_segment_indices[list_idx] if use_original_indices else list_idx
        # When max_segments_per_chunk is set (e.g. 1), flush current chunk before adding if at limit
        if max_segments_per_chunk is not None and len(chunk) >= max_segments_per_chunk and chunk:
            json_chunks_list.append(chunk)
            chunk = {}
        prospective_chunk = chunk.copy()
        prospective_chunk[str(seg_idx)] = val

        # Estimate tokens for prospective chunk (JSON format)
        # Note: The segment index (key) is included in token estimation, as it's part of the JSON structure
        # sent to the LLM. This ensures accurate token counting including all JSON formatting overhead.
        prospective_tokens = estimate_json_tokens(prospective_chunk)

        # Fix bug: Even if chunk is empty, if prospective_chunk (i.e., single element) exceeds limit,
        # should submit old chunk first.
        if prospective_tokens > chunk_size_max and chunk:
            json_chunks_list.append(chunk)
            chunk = {str(seg_idx): val}
        else:
            chunk = prospective_chunk

    if chunk:
        json_chunks_list.append(chunk)

    # ==================== Core Fix ====================
    # Build final, complete js dictionary based on complete new_segments list
    # Use original segment indices if provided, otherwise use enumerate
    if use_original_indices:
        js = {str(seg_idx): segment for seg_idx, segment in zip(new_segment_indices, new_segments)}
    else:
        js = {str(i): segment for i, segment in enumerate(new_segments)}
    # ================================================

    # Estimate tokens for each chunk if requested
    chunk_tokens = None
    if estimate_tokens:
        chunk_tokens = []
        for chunk_dict in json_chunks_list:
            tokens = estimate_chunk_tokens_from_json_dict(chunk_dict)
            chunk_tokens.append(tokens)
        return js, json_chunks_list, merged_indices_list, chunk_tokens
    else:
        return js, json_chunks_list, merged_indices_list


def fix_json_string(json_string):
    def repl(m:re.Match):
        return f"""{'"' if m.group(1) else ""},\n"{m.group(2)}":{'"' if m.group(3) else ""}"""
    fixed_json = re.sub(
        r"""([“”"])?\s*[，,]\s*["“”]\s*(\d+)\s*["“”]\s*[：:]\s*(["“”])?""",
        repl,
        json_string,
        re.MULTILINE
    )
    return fixed_json


if __name__ == '__main__':
    print(estimate_json_tokens({"0": ""}))
