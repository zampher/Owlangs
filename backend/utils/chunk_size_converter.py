# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Utility for converting total token limit to text content token limit.

translator_chunk_token_size represents the total token count (text content + system prompt + overhead).
This module helps calculate the maximum text content tokens allowed within that total limit.
All calculations are token-based, not byte-based.
"""

import logging
from typing import Optional

from utils.token_estimator import estimate_tokens

logger = logging.getLogger(__name__)


def get_text_content_token_limit(
    total_token_limit: int,
    system_prompt_tokens: Optional[int] = None,
    api_overhead_tokens: Optional[int] = None,
    safety_margin: float = 0.9
) -> int:
    """
    Calculate available token limit for text content from total token limit.
    
    translator_chunk_token_size = text_tokens + system_prompt_tokens + overhead
    This function calculates: text_tokens = (total_token_limit - system_prompt_tokens - overhead) * safety_margin
    
    Note: For small chunk sizes (e.g., 3000), we use a more conservative safety margin (0.85 instead of 0.9)
    to account for token estimation inaccuracies, especially for JSON format.
    
    Args:
        total_token_limit: Total token count (text + prompt + overhead)
        system_prompt_tokens: Estimated system prompt token count (default: 450)
        api_overhead_tokens: API overhead tokens (default: 50)
        safety_margin: Safety margin to avoid exceeding token limit (default: 0.9 = 90%)
                      For small chunk sizes (< 5000), this is automatically reduced to 0.85
        
    Returns:
        Available token limit for text content (for use in segments2json_chunks)
    """
    if total_token_limit <= 0:
        logger.warning(LogModule.CONVERT, f"Invalid total_token_limit: {total_token_limit}, using default 3000 tokens")
        return 3000
    
    # Default system prompt size (approximately 400-500 tokens for SegmentsTranslateAgent)
    if system_prompt_tokens is None:
        system_prompt_tokens = 450
    
    # API overhead (JSON structure, formatting, etc.)
    if api_overhead_tokens is None:
        api_overhead_tokens = 50
    
    # Use more conservative safety margin for small chunk sizes to account for token estimation inaccuracies
    # Token estimation for JSON format may be less accurate, so we reduce the margin for smaller chunks
    effective_safety_margin = safety_margin
    if total_token_limit < 5000:
        # For small chunk sizes, use 0.85 instead of 0.9 to be more conservative
        effective_safety_margin = min(safety_margin, 0.85)
        if effective_safety_margin < safety_margin:
            logger.debug(
                f"Using more conservative safety_margin={effective_safety_margin} "
                f"(instead of {safety_margin}) for small chunk_size={total_token_limit}"
            )
    
    # Calculate available tokens for text content
    available_text_tokens = int((total_token_limit - system_prompt_tokens - api_overhead_tokens) * effective_safety_margin)
    
    if available_text_tokens <= 0:
        logger.warning(
            f"total_token_limit ({total_token_limit}) is too small after subtracting "
            f"system_prompt_tokens ({system_prompt_tokens}) and overhead ({api_overhead_tokens}). "
            f"Using minimum 500 tokens."
        )
        return 500
    
    logger.debug(
        f"Calculated text_content_token_limit={available_text_tokens} from total_token_limit={total_token_limit} "
        f"(system_prompt={system_prompt_tokens}, overhead={api_overhead_tokens}, "
        f"safety_margin={effective_safety_margin})"
    )
    
    return available_text_tokens


# Deprecated: Keep for backward compatibility, but redirects to new function
def convert_token_chunk_size_to_bytes(
    token_chunk_size: int,
    system_prompt_tokens: Optional[int] = None,
    safety_margin: float = 0.9
) -> int:
    """
    DEPRECATED: Use get_text_content_token_limit instead.
    This function is kept for backward compatibility but now returns token limit instead of bytes.
    """
    logger.warning(
        "convert_token_chunk_size_to_bytes is deprecated. "
        "Use get_text_content_token_limit instead (which returns tokens, not bytes)."
    )
    return get_text_content_token_limit(token_chunk_size, system_prompt_tokens, None, safety_margin)


def estimate_system_prompt_tokens(
    system_prompt: Optional[str] = None,
    language: Optional[str] = None,
    model_id: Optional[str] = None
) -> int:
    """
    Estimate system prompt token count based on actual prompt or defaults.
    
    Args:
        system_prompt: Actual system prompt text (if available)
        language: Target language (affects prompt size)
        model_id: Model ID (some models have different prompt formats)
        
    Returns:
        Estimated system prompt token count
    """
    if system_prompt:
        return estimate_tokens(system_prompt)
    
    # Default estimates based on typical prompt sizes
    # SegmentsTranslateAgent: ~450 tokens
    # MDTranslateAgent: ~400 tokens
    # With glossary: +50-100 tokens
    
    base_tokens = 450  # Default for SegmentsTranslateAgent
    
    # Adjust based on language (some languages have longer prompts)
    if language and language.lower() in ['zh', 'chinese', '中文']:
        base_tokens += 20  # Chinese prompts might be slightly longer
    
    return base_tokens

