# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""
Translation result validation utilities.

This module provides functions to validate translation results and determine
if a translation should be considered as failed or if it's just untranslatable content
(e.g., numbers, punctuation, symbols).
"""

import re
import logging
from typing import Any, Dict, Tuple

from logger import unified_logger as unified_logger
from logger.logger import LogModule

logger = logging.getLogger(__name__)


def should_treat_as_failure(source: str, translated: str) -> Tuple[bool, str]:
    """
    Determine if translation result should be treated as failure.
    
    This function checks if a translation result (same as source) represents
    a real translation failure or just untranslatable content (e.g., "1、2").
    
    Args:
        source: Original source text
        translated: Translated text
        
    Returns:
        Tuple of (is_failure: bool, reason: str)
        - is_failure: True if should be marked as failed, False otherwise
        - reason: Explanation of the decision
    """
    source = source.strip()
    translated = translated.strip()
    
    # Empty translation is always failure
    if not translated:
        logger.debug(
            f"[TRANSLATION_FAILURE] Translation failed: empty response from AI platform\n"
            f"  Source text: {source[:500]!r}\n"
            f"  Translated text: (empty)"
        )
        return True, "Translation failed: empty response from AI platform"
    
    # If different, it's a successful translation (no need to check)
    if source != translated:
        return False, "Translation successful"
    
    # Same text - need to check if it's actually translatable content
    translatable_ratio = calculate_translatable_ratio(source)
    source_length = len(source)
    
    # Check if source contains CJK characters (Chinese, Japanese, Korean)
    # If source contains CJK and target is same, it's definitely a failure
    has_cjk = any(is_cjk_char(c) for c in source)
    
    
    # If source has significant translatable content (>30%), it's a failure
    # OR if source contains CJK characters (which should always be translated), it's a failure
    if translatable_ratio > 0.3 or (has_cjk and source_length > 3):
        logger.debug(
            f"[TRANSLATION_FAILURE] Translation failed: response same as source\n"
            f"  Source text: {source[:500]!r}\n"
            f"  Translated text: {translated[:500]!r}\n"
            f"  Source length: {source_length}, Translatable ratio: {translatable_ratio:.2%}, Has CJK: {has_cjk}"
        )
        return True, "Translation failed: platform returned untranslated content"
    
    # If source is very short (<=3 chars) and mostly numbers/punctuation,
    # it might not need translation (e.g., "1、2", "①", "A.")
    if source_length <= 3:
        if translatable_ratio < 0.3:
            return False, "Content likely doesn't need translation (short numeric/punctuation)"
        # Even short texts with translatable content should be translated
        logger.debug(
            f"[TRANSLATION_FAILURE] Translation failed: response same as source\n"
            f"  Source text: {source[:500]!r}\n"
            f"  Translated text: {translated[:500]!r}\n"
            f"  Source length: {source_length}, Translatable ratio: {translatable_ratio:.2%}"
        )
        return True, "Translation failed: platform returned untranslated content"
    
    # For longer texts (4+ chars), if same but has some translatable content (>10%),
    # it's likely a failure
    if translatable_ratio > 0.1:
        logger.debug(
            f"[TRANSLATION_FAILURE] Translation failed: response same as source\n"
            f"  Source text: {source[:500]!r}\n"
            f"  Translated text: {translated[:500]!r}\n"
            f"  Source length: {source_length}, Translatable ratio: {translatable_ratio:.2%}"
        )
        return True, "Translation failed: platform returned untranslated content"
    
    # Very long text with low translatable ratio might be special cases
    # (e.g., code, special formatting), but we'll be conservative and mark as failure
    if source_length > 10:
        logger.debug(
            f"[TRANSLATION_FAILURE] Translation failed: response same as source (long text)\n"
            f"  Source text: {source[:500]!r}\n"
            f"  Translated text: {translated[:500]!r}\n"
            f"  Source length: {source_length}, Translatable ratio: {translatable_ratio:.2%}"
        )
        return True, "Translation failed: platform returned untranslated content"
    
    # Default: if same text and low translatable ratio, probably doesn't need translation
    logger.debug(
        f"[TRANSLATION_FAILURE] NOT marking as failure: "
        f"source='{source[:100]}...', length={source_length}, "
        f"translatable_ratio={translatable_ratio:.2%}"
    )
    return False, "Content likely doesn't need translation (mostly non-translatable characters)"


def refresh_task_state_segment_failure_flags(task_state: Dict[str, Any]) -> int:
    """
    Recompute is_failed, needs_retry, and failure_reason from source_text vs target_text
    using should_treat_as_failure for each segment.

    Skips excluded, image, and user-cleared segments (same rules as batch retranslate).

    Used by queued translation auto-retry so collection matches immersive / RECORD_SEGMENTS
    semantics: flags may be missing after initial recording, or cleared incorrectly when
    the LLM returns same-as-source but the validator would still treat it as untranslated.

    Returns:
        Count of segments with is_failed True after refresh.
    """
    data = task_state.get("translation_segments") or {}
    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list):
        return 0
    failed_count = 0
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if seg.get("is_excluded") or seg.get("is_image"):
            continue
        if seg.get("status") == "cleared":
            continue
        src = (seg.get("source_text") or "").strip()
        tgt = (seg.get("target_text") or "").strip()
        is_failed, reason = should_treat_as_failure(src, tgt)
        seg["is_failed"] = is_failed
        seg["failure_reason"] = reason if is_failed else None
        seg["needs_retry"] = bool(is_failed)
        if is_failed:
            failed_count += 1
    return failed_count


def summarize_segment_translation_stats(task_state: Dict[str, Any]) -> Dict[str, int]:
    """
    Count segments by outcome using should_treat_as_failure on source vs target.

    - eligible: not excluded, not image, not cleared — same population as auto-retry eligibility.
    - success / failed: split among eligible only.
    """
    data = task_state.get("translation_segments") or {}
    segments = data.get("segments") if isinstance(data, dict) else None
    out = {
        "total": 0,
        "eligible": 0,
        "success": 0,
        "failed": 0,
        "excluded": 0,
        "image": 0,
        "cleared": 0,
    }
    if not isinstance(segments, list):
        return out
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        out["total"] += 1
        if seg.get("is_excluded"):
            out["excluded"] += 1
            continue
        if seg.get("is_image"):
            out["image"] += 1
            continue
        if seg.get("status") == "cleared":
            out["cleared"] += 1
            continue
        src = (seg.get("source_text") or "").strip()
        tgt = (seg.get("target_text") or "").strip()
        out["eligible"] += 1
        is_failed, _reason = should_treat_as_failure(src, tgt)
        if is_failed:
            out["failed"] += 1
        else:
            out["success"] += 1
    return out


def log_segment_translation_stats(task_id: str, task_state: Dict[str, Any], context: str) -> None:
    """Emit one INFO line with success/failed/eligible counts for operators."""
    s = summarize_segment_translation_stats(task_state)
    unified_logger.info(
        LogModule.TRANS,
        f"[SEGMENT-STATS] task={task_id} {context}: "
        f"total={s['total']} eligible={s['eligible']} success={s['success']} failed={s['failed']} "
        f"(excluded={s['excluded']} image={s['image']} cleared={s['cleared']})",
    )


def calculate_translatable_ratio(text: str) -> float:
    """
    Calculate the ratio of translatable characters in text.
    
    Translatable characters include:
    - Letters (alphabetic characters)
    - Chinese/Japanese/Korean characters (CJK)
    - Characters that are not pure digits, punctuation, or whitespace
    
    Args:
        text: Text to analyze
        
    Returns:
        Ratio of translatable characters (0.0 to 1.0)
    """
    if not text:
        return 0.0
    
    translatable_count = 0
    total_chars = len(text)
    
    for char in text:
        # Count letters (alphabetic characters)
        if char.isalpha():
            translatable_count += 1
        # Count CJK characters (Chinese, Japanese, Korean)
        elif is_cjk_char(char):
            translatable_count += 1
        # Count other non-ASCII characters that might be translatable
        # (excluding common punctuation and symbols)
        elif ord(char) > 127 and char not in _COMMON_NON_TRANSLATABLE:
            translatable_count += 1
    
    return translatable_count / total_chars if total_chars > 0 else 0.0


def is_cjk_char(char: str) -> bool:
    """
    Check if a character is a CJK (Chinese, Japanese, Korean) character.
    
    Args:
        char: Single character to check
        
    Returns:
        True if character is CJK, False otherwise
    """
    if not char:
        return False
    
    code = ord(char)
    # CJK Unified Ideographs: U+4E00 to U+9FFF
    # CJK Extension A: U+3400 to U+4DBF
    # CJK Extension B: U+20000 to U+2A6DF
    # Hiragana: U+3040 to U+309F
    # Katakana: U+30A0 to U+30FF
    # Hangul: U+AC00 to U+D7AF
    return (
        (0x4E00 <= code <= 0x9FFF) or      # CJK Unified Ideographs
        (0x3400 <= code <= 0x4DBF) or      # CJK Extension A
        (0x3040 <= code <= 0x309F) or      # Hiragana
        (0x30A0 <= code <= 0x30FF) or      # Katakana
        (0xAC00 <= code <= 0xD7AF)         # Hangul
    )


# Common non-translatable characters (punctuation, symbols, etc.)
_COMMON_NON_TRANSLATABLE = {
    '、', '，', '。', '：', '；', '！', '？',  # Chinese punctuation
    ',', '.', ':', ';', '!', '?',  # English punctuation
    '(', ')', '[', ']', '{', '}',  # Brackets
    '-', '_', '+', '=', '*', '/', '\\',  # Symbols
    '@', '#', '$', '%', '^', '&',  # Special symbols
    ' ', '\t', '\n', '\r',  # Whitespace
    '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩',  # Circled numbers
    '❶', '❷', '❸', '❹', '❺', '❻', '❼', '❽', '❾', '❿',  # Dingbats
}

