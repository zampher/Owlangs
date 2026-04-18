# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Language match detection utilities for exclusion detection.

This module provides functions to detect if text language matches target language,
which can be used for exclusion detection.
"""

from typing import Optional


def is_language_match(text: str, target_lang: Optional[str]) -> Optional[tuple]:
    """
    Check if text language matches target language.
    
    CRITICAL: For mixed-language text (e.g., "PACS：影像归档和通信系统（Picture Archiving and Communication Systems）"),
    if text contains Chinese characters (CJK ideographs) with sufficient ratio (>20%), 
    it should be identified as Chinese, not English, even if English words are present.
    
    Args:
        text: Text to check
        target_lang: Target language code (e.g., 'zh', 'en')
        
    Returns:
        Tuple of (detected_lang, normalized_detected, normalized_target) if match, None otherwise.
        Returns None if target_lang is not provided or language detection fails.
    """
    if not text or not text.strip() or not target_lang:
        return None
    
    text_stripped = text.strip()
    
    # Only detect language for text with sufficient length (at least 3 characters)
    if len(text_stripped) < 3:
        return None
    
    try:
        # Respect global switch: when language_match_exclusion_detection is False,
        # we do not perform language match detection at all.
        try:
            from backend.config.config_loader import get_unified_config
            config = get_unified_config()
            if not getattr(config.exclusion_defaults, "language_match_exclusion_detection", False):
                return None
        except Exception:
            # If config is not available for any reason, fall back to detection logic.
            pass

        from utils.language_detection_utils import detect_language_from_text, _collect_script_language_counts, _count_meaningful_chars
        from utils.translation_segments import _normalize_language_code_for_comparison
        
        # CRITICAL: Check for Chinese characters (CJK ideographs) in mixed-language text
        # If text contains Chinese characters with sufficient ratio, prioritize Chinese detection
        script_lang_counts = _collect_script_language_counts(text_stripped)
        chinese_char_count = script_lang_counts.get('zh', 0)
        meaningful_chars = _count_meaningful_chars(text_stripped)
        
        # If Chinese characters exist and account for >20% of meaningful characters,
        # prioritize Chinese detection (even if langdetect detects English)
        chinese_char_ratio = chinese_char_count / meaningful_chars if meaningful_chars > 0 else 0
        
        detected_lang = detect_language_from_text(text_stripped, sample_size=100)
        
        # CRITICAL: Override detection if Chinese characters dominate
        # This handles cases like "PACS：影像归档和通信系统（Picture Archiving and Communication Systems）"
        # where English words might cause langdetect to detect English, but Chinese characters indicate Chinese content
        if chinese_char_count > 0 and chinese_char_ratio > 0.2:
            # Chinese characters dominate, override to Chinese
            detected_lang = 'zh'
        
        # Normalize both languages for comparison
        normalized_detected = _normalize_language_code_for_comparison(detected_lang)
        normalized_target = _normalize_language_code_for_comparison(target_lang)
        
        if normalized_detected == normalized_target:
            return (detected_lang, normalized_detected, normalized_target)
        
        return None
    except Exception:
        # If language detection fails, return None (don't exclude)
        return None
