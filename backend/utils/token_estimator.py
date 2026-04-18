# SPDX-FileCopyrightText: 2026 Zampherssss
# SPDX-License-Identifier: MPL-2.0

"""
Token estimation utilities for calculating input token counts including system prompts.
"""

import json
from typing import Optional


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.
    
    Uses a simple approximation:
    - Chinese/Japanese/Korean: ~1.0-1.2 characters per token (typically 1 token per CJK character)
    - English and other characters: ~3.5-4 characters per token
    
    Note: For GPT models, Chinese characters typically map to 1-1.2 tokens each.
    This is more accurate than the previous 1.5 chars/token estimate.
    
    For JSON format, actual tokens may be higher due to special characters.
    Consider using a more accurate tokenizer (like tiktoken) for production use.
    
    Args:
        text: Text string to estimate
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Count Chinese/Japanese/Korean characters (CJK)
    cjk_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff' or 
                    '\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' or
                    '\uac00' <= char <= '\ud7af')
    
    # Count JSON special characters (quotes, commas, colons, braces, brackets)
    # These characters typically consume more tokens than regular characters
    json_special_chars = sum(1 for char in text if char in '{}[]",:')
    
    # Count escaped characters (e.g., \" in JSON)
    escaped_chars = text.count('\\"') + text.count('\\n') + text.count('\\t') + text.count('\\\\')
    
    # Count other characters (excluding CJK and JSON special chars)
    other_count = len(text) - cjk_count - json_special_chars
    
    # Estimate: CJK ~1.0 chars/token (typically 1 token per Chinese character for GPT models)
    # This matches actual GPT tokenizer behavior: 1 Chinese character ≈ 1 token
    # Using 1.0 instead of 1.1 to be more conservative and avoid underestimation
    cjk_tokens = int(cjk_count / 1.0) if cjk_count > 0 else 0
    
    # JSON special characters typically consume ~1 token per character (they're punctuation)
    # Quotes, commas, colons, braces are all single tokens in most tokenizers
    json_special_tokens = json_special_chars
    
    # Escaped characters (e.g., \") typically consume 2 tokens (backslash + character)
    # But since we're counting the escaped sequence as 2 chars, we need to account for the extra token
    escaped_tokens = escaped_chars  # Each escape sequence adds ~1 extra token
    
    # For other characters (English, numbers, punctuation): ~3.5 chars/token
    # Reduced from 4.0 to account for JSON special characters if applicable
    other_tokens = int(other_count / 3.5) if other_count > 0 else 0
    
    return cjk_tokens + json_special_tokens + escaped_tokens + other_tokens + 1  # +1 for safety margin


def estimate_chunk_input_tokens(
    chunk_text: str,
    system_prompt: Optional[str] = None,
    system_prompt_approx: Optional[int] = None
) -> int:
    """
    Estimate total input tokens for a chunk including system prompt.
    
    Args:
        chunk_text: The chunk text content (JSON format for segments)
        system_prompt: Optional system prompt text (if provided, will be used for exact calculation)
        system_prompt_approx: Optional approximate system prompt token count (if system_prompt not provided)
        
    Returns:
        Estimated total input tokens (chunk + system prompt)
    """
    chunk_tokens = estimate_tokens(chunk_text)
    
    # Estimate system prompt tokens
    if system_prompt:
        system_tokens = estimate_tokens(system_prompt)
    elif system_prompt_approx:
        system_tokens = system_prompt_approx
    else:
        # Default system prompt size for SegmentsTranslateAgent (approximately 400-500 tokens)
        system_tokens = 450
    
    # Add overhead for JSON structure and API formatting (~50 tokens)
    overhead = 50
    
    return chunk_tokens + system_tokens + overhead


def estimate_json_tokens(js: dict) -> int:
    """
    Estimate token count for a dictionary converted to JSON string.
    
    This is a general-purpose function for estimating tokens in JSON format.
    It includes:
    - All keys (e.g., segment indices like "0", "1", "1234")
    - All values (e.g., segment text content)
    - JSON formatting characters (quotes, commas, colons, braces)
    
    The keys are part of the JSON structure and must be included in token estimation.
    
    Args:
        js: Dictionary to estimate tokens for
        
    Returns:
        Estimated token count for the JSON string representation
    """
    json_str = json.dumps(js, ensure_ascii=False)
    return estimate_tokens(json_str)


def estimate_chunk_tokens_from_json_dict(chunk_dict: dict, system_prompt_approx: int = 450) -> int:
    """
    Estimate input tokens for a chunk in JSON dict format (as used by segments2json_chunks).
    
    The token estimation includes:
    - Segment indices (keys) as strings (e.g., "0", "1", "1234") - these are part of the JSON structure
    - Segment text content (values)
    - JSON formatting characters (quotes, commas, colons, braces)
    - System prompt tokens
    - API overhead tokens
    
    Note: Segment indices are included in token estimation because they are part of the JSON
    structure sent to the LLM, even though they are not displayed to users in the UI.
    
    Args:
        chunk_dict: Dictionary with segment indices as keys and segment texts as values
                   Example: {"0": "text1", "1": "text2", "1234": "text3"}
        system_prompt_approx: Approximate system prompt token count (default: 450 for SegmentsTranslateAgent)
        
    Returns:
        Estimated total input tokens (including segment indices, text content, system prompt, and overhead)
    """
    # Convert dict to JSON string (includes segment indices as keys)
    chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
    return estimate_chunk_input_tokens(chunk_json, system_prompt_approx=system_prompt_approx)

