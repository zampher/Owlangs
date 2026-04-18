# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unified language detection utilities for translation and anonymization workflows.
Provides consistent language detection across different parts of the application.
"""

import re
import time
import unicodedata
from typing import Optional, List, Dict, Any, Tuple, Callable
from utils.language_detector import LanguageDetector
from logger import unified_logger, LogModule

# Singleton instance for language detector (thread-safe, stateless)
_language_detector_instance: Optional[LanguageDetector] = None


def get_language_detector() -> LanguageDetector:
    """
    Get the singleton LanguageDetector instance.
    
    Returns:
        LanguageDetector instance (shared across the application)
    """
    global _language_detector_instance
    if _language_detector_instance is None:
        _language_detector_instance = LanguageDetector()
    return _language_detector_instance


def detect_language_from_text(
    text: str,
    sample_size: Optional[int] = None,
    log_context: Optional[str] = None
) -> str:
    """
    Detect language from text with optional sampling for performance.
    
    This is a unified wrapper around LanguageDetector.detect_language() that:
    - Uses singleton instance for efficiency
    - Supports text sampling for large documents
    - Provides consistent logging
    
    Args:
        text: Input text to analyze
        sample_size: Optional number of characters/words to sample from text.
                     If None, uses full text. If specified, takes first N characters.
        log_context: Optional context string for logging (e.g., task_id, workflow_id)
    
    Returns:
        Normalized language code (e.g., 'zh', 'en', 'es')
    """
    detector = get_language_detector()
    
    # Sample text if requested
    if sample_size is not None and len(text) > sample_size:
        sampled_text = text[:sample_size]
    else:
        sampled_text = text
    
    # Detect language
    detected_lang = detector.detect_language(sampled_text)
    
    # Log result if context provided
    if log_context:
        unified_logger.info(
            LogModule.DETECT,
            "Language detection completed: {language} (context: {context})",
            language=detected_lang,
            context=log_context
        )
    
    return detected_lang


def detect_language_from_segments(
    segments: List[str],
    max_segments: int = 10,
    log_context: Optional[str] = None
) -> str:
    """
    Detect language from a list of text segments.
    
    This is optimized for translation workflows where content is already split into segments.
    Uses first N segments for faster detection.
    
    Args:
        segments: List of text segments
        max_segments: Maximum number of segments to use for detection (default: 10)
        log_context: Optional context string for logging (e.g., task_id)
    
    Returns:
        Normalized language code (e.g., 'zh', 'en', 'es')
    """
    if not segments:
        return 'en'  # Default to English if no segments
    
    # Join first N segments for detection
    sample_segments = segments[:min(max_segments, len(segments))]
    sample_text = ' '.join(sample_segments)
    
    if not sample_text.strip():
        return 'en'  # Default to English if sample is empty
    
    return detect_language_from_text(sample_text, log_context=log_context)


def detect_language_from_bytes(
    content: bytes,
    encoding: str = 'utf-8',
    sample_size: Optional[int] = None,
    log_context: Optional[str] = None
) -> str:
    """
    Detect language from byte content (e.g., file content).
    
    Args:
        content: Byte content to analyze
        encoding: Text encoding (default: 'utf-8')
        sample_size: Optional number of bytes to sample
        log_context: Optional context string for logging
    
    Returns:
        Normalized language code (e.g., 'zh', 'en', 'es')
    """
    try:
        decoded = content.decode(encoding)
    except UnicodeDecodeError:
        try:
            decoded = content.decode(encoding, errors='replace')
        except Exception:
            # Fallback to English if decoding fails
            return 'en'
    
    return detect_language_from_text(decoded, sample_size=sample_size, log_context=log_context)


def _is_common_char(ch: str) -> bool:
    """
    Determine if a character should be excluded from language statistics.
    Excludes whitespace, digits, punctuation, symbols, and control chars.
    """
    if not ch:
        return True
    if ch.isspace() or ch.isdigit():
        return True
    category = unicodedata.category(ch)
    if category and category[0] in ("Z", "P", "S", "C"):
        return True
    return False


def _count_meaningful_chars(text: str) -> int:
    """Count characters that contribute to language statistics."""
    if not text:
        return 0
    return sum(1 for ch in text if not _is_common_char(ch))


SCRIPT_LANGUAGE_RANGES: Dict[str, List[Tuple[int, int]]] = {
    # Chinese (CJK ranges)
    'zh': [
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0xF900, 0xFAFF),
        (0x20000, 0x2A6DF),
    ],
    # Japanese (Hiragana, Katakana, extensions)
    'ja': [
        (0x3040, 0x309F),
        (0x30A0, 0x30FF),
        (0x31F0, 0x31FF),
    ],
    # Korean (Hangul blocks)
    'ko': [
        (0x1100, 0x11FF),
        (0x3130, 0x318F),
        (0xAC00, 0xD7AF),
    ],
    # Thai
    'th': [
        (0x0E00, 0x0E7F),
    ],
    # Arabic
    'ar': [
        (0x0600, 0x06FF),
        (0x0750, 0x077F),
        (0x08A0, 0x08FF),
    ],
    # Hebrew
    'he': [
        (0x0590, 0x05FF),
    ],
    # Bengali
    'bn': [
        (0x0980, 0x09FF),
    ],
    # Devanagari (Hindi)
    'hi': [
        (0x0900, 0x097F),
    ],
    # Khmer
    'km': [
        (0x1780, 0x17FF),
    ],
    # Greek
    'el': [
        (0x0370, 0x03FF),
    ],
}


def _get_language_for_char(ch: str) -> Optional[str]:
    """
    Map a character to a specific language based on Unicode script ranges.
    
    IMPORTANT: CJK Unified Ideographs (0x4E00-0x9FFF) are shared by Chinese, Japanese, and Korean.
    This function prioritizes language-specific scripts:
    1. Japanese: Hiragana (0x3040-0x309F) and Katakana (0x30A0-0x30FF) - unique to Japanese
    2. Korean: Hangul (0x1100-0x11FF, 0x3130-0x318F, 0xAC00-0xD7AF) - unique to Korean
    3. Chinese: CJK Unified Ideographs (0x4E00-0x9FFF) - shared, but if no Japanese/Korean scripts found, likely Chinese
    
    Returns:
        Language code ('zh', 'ja', 'ko') if character is in a language-specific range, None otherwise.
        Note: CJK Unified Ideographs are marked as 'zh' but may also appear in Japanese/Korean text.
    """
    if not ch or _is_common_char(ch):
        return None
    code = ord(ch)
    
    # Check language-specific scripts first (most reliable)
    # Japanese: Hiragana and Katakana (unique to Japanese)
    if (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF) or (0x31F0 <= code <= 0x31FF):
        return 'ja'
    
    # Korean: Hangul (unique to Korean)
    if (0x1100 <= code <= 0x11FF) or (0x3130 <= code <= 0x318F) or (0xAC00 <= code <= 0xD7AF):
        return 'ko'
    
    # Chinese: CJK Unified Ideographs (shared with Japanese/Korean, but marked as Chinese)
    # Note: This is a heuristic - pure CJK ideographs without Hiragana/Katakana/Hangul
    # are more likely to be Chinese, but could also be Japanese or Korean
    for lang, ranges in SCRIPT_LANGUAGE_RANGES.items():
        for start, end in ranges:
            if start <= code <= end:
                return lang
    
    return None


def _collect_script_language_counts(text: str) -> Dict[str, int]:
    """Count per-language characters for scripts with unique ranges."""
    counts: Dict[str, int] = {}
    if not text:
        return counts
    for ch in text:
        if _is_common_char(ch):
            continue
        lang = _get_language_for_char(ch)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return counts


def _invoke_progress_callback(
    progress_callback: Optional[Callable[..., None]],
    completed: int,
    total: int,
    **kwargs: Any
) -> None:
    """Invoke progress callback with (completed, total) and optional kwargs (e.g. phase='aggregated_short')."""
    if not progress_callback or total <= 0:
        return
    try:
        if kwargs:
            progress_callback(completed, total, **kwargs)
        else:
            progress_callback(completed, total)
    except TypeError:
        progress_callback(completed, total)


def detect_language_per_segment_with_distribution(
    segments: List[str],
    min_length: int = 10,
    log_context: Optional[str] = None,
    progress_callback: Optional[Callable[..., None]] = None,
    progress_interval: int = 500
) -> Dict[str, Any]:
    """
    Detect language for each segment and calculate language distribution.
    
    This function is used for detecting mixed language documents by analyzing
    each segment individually and calculating the percentage of each language.
    
    Args:
        segments: List of text segments
        min_length: Minimum segment length for detection (default: 10 chars)
        log_context: Optional context string for logging (e.g., task_id, workflow_id)
        progress_callback: Optional callback(completed, total, **kwargs). Supports phase="aggregated_short" for short-segment phase.
        progress_interval: Call progress_callback every N segments (default: 500)
    
    Returns:
        Dictionary containing:
        {
            "segment_languages": [
                {"segment_index": 0, "detected_language": "zh"},
                {"segment_index": 1, "detected_language": "en"},
                ...
            ],
            "language_distribution": {
                "zh": 0.85,  # 85% of segments are Chinese
                "en": 0.15   # 15% of segments are English
            },
            "recommended_language": "zh",  # Language with highest percentage
            "is_multilingual": False,  # True if no language >90%
            "total_segments": 100,
            "detected_segments": 95  # Segments that were successfully detected
        }
    """
    detector = get_language_detector()
    segment_languages = []
    language_counts = {}
    language_char_counts: Dict[str, int] = {}
    total_segments = len(segments)
    detected_segments = 0
    short_segments_buffer: List[str] = []
    short_segments_char_sum = 0
    failed_segments_buffer: List[str] = []
    failed_segments_char_sum = 0
    
    # Only log detailed detection info if explicitly requested (reduce log verbosity)
    # For status queries, we cache results to avoid repeated logging
    if log_context:
        # Only log summary, not detailed segment previews (too verbose)
        unified_logger.debug(
            LogModule.DETECT,
            "[LangDetect] Starting language detection for {count} segments (min_length={min_len}, context: {context})",
            count=total_segments,
            min_len=min_length,
            context=log_context
        )

    def _accumulate_chars(lang: Optional[str], char_len: int):
        if not lang or char_len <= 0:
            return
        language_char_counts[lang] = language_char_counts.get(lang, 0) + char_len
    
    # Yield GIL every N segments so the main thread (event loop) can handle getStatus/health requests
    _yield_interval = 10

    for idx, segment in enumerate(segments):
        # Yield GIL periodically so backend can respond to frontend polling (avoid health/status timeouts)
        if idx > 0 and idx % _yield_interval == 0:
            time.sleep(0.001)  # 1ms so main thread gets a real time slice
        # Report progress every progress_interval segments (at start of iteration: completed = idx)
        if progress_callback and total_segments > 0:
            if idx % progress_interval == 0 or idx == 0:
                try:
                    _invoke_progress_callback(progress_callback, idx, total_segments)
                except Exception as e:
                    unified_logger.debug(
                        LogModule.DETECT,
                        "[LangDetect] progress_callback error: %s (context: %s)",
                        e,
                        log_context or "N/A"
                    )
        stripped_segment = segment.strip()
        segment_len = _count_meaningful_chars(stripped_segment)
        raw_len = len(stripped_segment)
        script_lang_counts = _collect_script_language_counts(stripped_segment)
        segment_preview = stripped_segment[:200] if segment_len > 200 else stripped_segment
        
        if segment_len == 0:
            segment_languages.append({
                "segment_index": idx,
                "detected_language": None,
                "skip_reason": "no_meaningful_chars"
            })
            continue

        # Skip very short segments (based on meaningful characters)
        if segment_len < min_length:
            # Check if segment is primarily numbers (which can cause false detection)
            # Count digits in the raw segment
            digit_count = sum(1 for ch in stripped_segment if ch.isdigit())
            
            # Count non-digit, non-whitespace, non-punctuation characters (alphabetic)
            alpha_chars = sum(1 for ch in stripped_segment if ch.isalnum() and not ch.isdigit())
            
            # Check ratio based on meaningful characters, not total length
            # If meaningful chars are primarily digits (>60%), skip it entirely to avoid false positives
            # Lower threshold (60% instead of 70%) to be more strict
            digit_ratio_meaningful = digit_count / segment_len if segment_len > 0 else 0
            
            # Also check if digits significantly outnumber alphabetic characters
            # If digits are >3x more than alphabetic chars, likely numeric content
            digit_vs_alpha_ratio = digit_count / alpha_chars if alpha_chars > 0 else float('inf')
            
            # Also check if total text is primarily digits+whitespace+punctuation (>80%)
            digit_ratio_total = digit_count / raw_len if raw_len > 0 else 0
            
            # Skip if:
            # 1. Meaningful chars are >60% digits, OR
            # 2. Digits are >3x more than alphabetic chars, OR
            # 3. Total text is >80% digits
            # Don't add to short_segments_buffer to prevent aggregation detection
            if digit_ratio_meaningful > 0.6 or digit_vs_alpha_ratio > 3.0 or digit_ratio_total > 0.8:
                segment_languages.append({
                    "segment_index": idx,
                    "detected_language": None,
                    "skip_reason": "too_short_primarily_digits"
                })
                continue
            
            segment_languages.append({
                "segment_index": idx,
                "detected_language": None,
                "skip_reason": "too_short"
            })
            short_segments_buffer.append(stripped_segment)
            short_segments_char_sum += segment_len
            # Commented out per-segment detection log - only keep aggregated detection logs
            # if log_context:
            #     unified_logger.debug(
            #         LogModule.DETECT,
            #         "[LangDetect] Segment {idx}: SKIPPED (too_short, len={len}): {preview}... (context: {context})",
            #         idx=idx,
            #         len=segment_len,
            #         preview=segment_preview.replace('\n', '\\n'),
            #         context=log_context or "N/A"
            #     )
            continue
        
        script_assigned_chars = sum(script_lang_counts.values())
        unassigned_chars = max(segment_len - script_assigned_chars, 0)
        chinese_char_count = script_lang_counts.get('zh', 0)
        chinese_char_ratio = chinese_char_count / segment_len if segment_len > 0 else 0

        # Check if segment is primarily numbers (which can cause false detection)
        # Count digits in the raw segment
        digit_count = sum(1 for ch in stripped_segment if ch.isdigit())
        
        # Count non-digit, non-whitespace, non-punctuation characters (alphabetic)
        alpha_chars = sum(1 for ch in stripped_segment if ch.isalnum() and not ch.isdigit())
        
        # Check ratio based on meaningful characters, not total length
        # If meaningful chars are primarily digits (>60%), skip detection to avoid false positives
        # Lower threshold (60% instead of 70%) to be more strict
        digit_ratio_meaningful = digit_count / segment_len if segment_len > 0 else 0
        
        # Also check if digits significantly outnumber alphabetic characters
        # If digits are >3x more than alphabetic chars, likely numeric content
        digit_vs_alpha_ratio = digit_count / alpha_chars if alpha_chars > 0 else float('inf')
        
        # Also check if total text is primarily digits+whitespace+punctuation (>80%)
        digit_ratio_total = digit_count / raw_len if raw_len > 0 else 0
        
        # Skip if:
        # 1. Meaningful chars are >60% digits, OR
        # 2. Digits are >3x more than alphabetic chars, OR
        # 3. Total text is >80% digits
        if digit_ratio_meaningful > 0.6 or digit_vs_alpha_ratio > 3.0 or digit_ratio_total > 0.8:
            segment_languages.append({
                "segment_index": idx,
                "detected_language": None,
                "skip_reason": "primarily_digits"
            })
            # Don't accumulate chars for digit-only segments
            continue

        dominant_script_lang = None
        dominant_script_ratio = 0.0
        for lang_code, count in script_lang_counts.items():
            ratio = count / segment_len if segment_len > 0 else 0
            if ratio > dominant_script_ratio:
                dominant_script_ratio = ratio
                dominant_script_lang = lang_code

        try:
            detected_lang = detector.detect_language(stripped_segment)
            if dominant_script_lang and dominant_script_ratio >= 0.2 and detected_lang != dominant_script_lang:
                detected_lang = dominant_script_lang

            segment_languages.append({
                "segment_index": idx,
                "detected_language": detected_lang,
                "script_language_counts": script_lang_counts,
                "unassigned_chars": unassigned_chars
            })

            for lang_code, count in script_lang_counts.items():
                _accumulate_chars(lang_code, count)

            if unassigned_chars > 0:
                _accumulate_chars(detected_lang, unassigned_chars)

            language_counts[detected_lang] = language_counts.get(detected_lang, 0) + 1
            detected_segments += 1

            # Commented out per-segment detection log - only keep aggregated detection logs
            # if log_context:
            #     unified_logger.debug(
            #         LogModule.DETECT,
            #         "[LangDetect] Segment {idx}: detected={lang}, eff_len={len}, raw_len={raw}, script_counts={scripts}, unassigned={unassigned}, zh_ratio={ratio:.2%}, chars: {preview}... (context: {context})",
            #         idx=idx,
            #         lang=detected_lang,
            #         len=segment_len,
            #         raw=raw_len,
            #         scripts=script_lang_counts,
            #         unassigned=unassigned_chars,
            #         ratio=chinese_char_ratio,
            #         preview=segment_preview.replace('\n', '\\n'),
            #         context=log_context or "N/A"
            #     )
        except Exception as e:
            segment_languages.append({
                "segment_index": idx,
                "detected_language": None,
                "skip_reason": f"detection_failed: {e}"
            })
            failed_segments_buffer.append(stripped_segment)
            failed_segments_char_sum += segment_len
            # Commented out per-segment detection log - only keep aggregated detection logs
            # if log_context:
            #     unified_logger.debug(
            #         LogModule.DETECT,
            #         "[LangDetect] Segment {idx}: FAILED (error={error}), len={len}: {preview}... (context: {context})",
            #         idx=idx,
            #         error=str(e),
            #         len=segment_len,
            #         preview=segment_preview.replace('\n', '\\n'),
            #         context=log_context or "N/A"
            #     )

    # Final progress: main segment loop done
    if progress_callback and total_segments > 0:
        try:
            _invoke_progress_callback(progress_callback, total_segments, total_segments)
        except Exception as e:
            unified_logger.debug(
                LogModule.DETECT,
                "[LangDetect] progress_callback (final) error: %s (context: %s)",
                e,
                log_context or "N/A"
            )

    # Attempt detection for aggregated short segments (in chunks of progress_interval for progress updates)
    if short_segments_buffer and short_segments_char_sum > 0:
        try:
            combined_short = " ".join(short_segments_buffer)
            combined_preview = combined_short[:300] if len(combined_short) > 300 else combined_short
            
            # Check if aggregated short segments are primarily numbers
            # Count meaningful characters (excluding whitespace, punctuation, etc.)
            # NOTE: _count_meaningful_chars excludes digits, so if text is all digits+whitespace, this will be 0
            combined_meaningful_chars = _count_meaningful_chars(combined_short)
            combined_digit_count = sum(1 for ch in combined_short if ch.isdigit())
            
            # Count non-digit, non-whitespace, non-punctuation characters (alphabetic)
            combined_alpha_chars = sum(1 for ch in combined_short if ch.isalnum() and not ch.isdigit())
            
            # Count total non-whitespace characters (digits + alphabetic + punctuation)
            combined_non_whitespace = sum(1 for ch in combined_short if not ch.isspace())
            
            # Check ratio based on meaningful characters (non-digit, non-whitespace, non-punctuation)
            # If meaningful chars are primarily digits (>50%), skip detection to avoid false positives
            # Lower threshold (50% instead of 60%) to be more strict
            combined_digit_ratio = combined_digit_count / combined_meaningful_chars if combined_meaningful_chars > 0 else 0
            
            # Also check ratio based on non-whitespace characters (includes digits)
            # If non-whitespace chars are primarily digits (>70%), skip detection
            combined_digit_ratio_non_ws = combined_digit_count / combined_non_whitespace if combined_non_whitespace > 0 else 0
            
            # Also check if digits significantly outnumber alphabetic characters
            # If digits are >3x more than alphabetic chars, likely numeric content
            digit_vs_alpha_ratio = combined_digit_count / combined_alpha_chars if combined_alpha_chars > 0 else float('inf')
            
            # Also check if total text is primarily digits+whitespace+punctuation (>80%)
            combined_total_digit_ratio = combined_digit_count / len(combined_short) if len(combined_short) > 0 else 0
            
            # Skip if:
            # 1. If meaningful chars are 0 but there are digits, likely all digits+whitespace (most common case for ISBN/prices)
            # 2. Non-whitespace chars are >70% digits, OR
            # 3. Meaningful chars are >50% digits (if meaningful chars exist), OR
            # 4. Digits are >2x more than alphabetic chars, OR
            # 5. Total text is >75% digits
            should_skip = False
            skip_reason = ""
            
            if combined_meaningful_chars == 0 and combined_digit_count > 0:
                # All non-whitespace chars are digits (meaningful_chars excludes digits, so if 0 and digits exist, it's all digits+whitespace)
                # This is the most common case for ISBN codes, prices, etc.
                should_skip = True
                skip_reason = "all_digits_whitespace"
            elif combined_digit_ratio_non_ws > 0.7:
                # Non-whitespace chars are >70% digits
                should_skip = True
                skip_reason = f"non_ws_ratio_{combined_digit_ratio_non_ws:.2%}"
            elif combined_meaningful_chars > 0 and combined_digit_ratio > 0.5:
                # Meaningful chars exist and are >50% digits
                should_skip = True
                skip_reason = f"meaningful_ratio_{combined_digit_ratio:.2%}"
            elif digit_vs_alpha_ratio > 2.0:
                # Digits are >2x more than alphabetic chars
                should_skip = True
                skip_reason = f"digit_vs_alpha_{digit_vs_alpha_ratio:.2f}"
            elif combined_total_digit_ratio > 0.75:
                # Total text is >75% digits
                should_skip = True
                skip_reason = f"total_ratio_{combined_total_digit_ratio:.2%}"
            
            if should_skip:
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Aggregated {count} short segments skipped (primarily digits, reason={reason}, meaningful_ratio={ratio:.2%}, non_ws_ratio={nws_ratio:.2%}, total_ratio={total_ratio:.2%}, digit_vs_alpha={dva_ratio:.2f}, meaningful_chars={mchars}, digits={digits}, alpha={alpha}, non_ws={nws}) (context: {context})",
                    count=len(short_segments_buffer),
                    reason=skip_reason,
                    ratio=combined_digit_ratio,
                    nws_ratio=combined_digit_ratio_non_ws,
                    total_ratio=combined_total_digit_ratio,
                    dva_ratio=digit_vs_alpha_ratio if digit_vs_alpha_ratio != float('inf') else 999.0,
                    mchars=combined_meaningful_chars,
                    digits=combined_digit_count,
                    alpha=combined_alpha_chars,
                    nws=combined_non_whitespace,
                    context=log_context or "N/A"
                )
            else:
                # Log detailed info before detection to debug why digits are not being filtered
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Aggregated {count} short segments will be detected (meaningful_ratio={ratio:.2%}, non_ws_ratio={nws_ratio:.2%}, total_ratio={total_ratio:.2%}, digit_vs_alpha={dva_ratio:.2f}, meaningful_chars={mchars}, digits={digits}, alpha={alpha}, non_ws={nws}, preview={preview}) (context: {context})",
                    count=len(short_segments_buffer),
                    ratio=combined_digit_ratio,
                    nws_ratio=combined_digit_ratio_non_ws,
                    total_ratio=combined_total_digit_ratio,
                    dva_ratio=digit_vs_alpha_ratio if digit_vs_alpha_ratio != float('inf') else 999.0,
                    mchars=combined_meaningful_chars,
                    digits=combined_digit_count,
                    alpha=combined_alpha_chars,
                    nws=combined_non_whitespace,
                    preview=combined_preview[:200].replace('\n', '\\n'),
                    context=log_context or "N/A"
                )
                
                # Log first 20 short segments for debugging
                sample_segments = short_segments_buffer[:20]
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Sample of {count} short segments (first 20 of {total}): {segments} (context: {context})",
                    count=len(sample_segments),
                    total=len(short_segments_buffer),
                    segments=" | ".join([f"[{i}]:{s[:50]}" for i, s in enumerate(sample_segments)]),
                    context=log_context or "N/A"
                )
                
                # Process in chunks of progress_interval so we can report progress every 500 segments (frontend progress bar)
                num_chunks = (len(short_segments_buffer) + progress_interval - 1) // progress_interval
                _invoke_progress_callback(
                    progress_callback, 0, num_chunks, phase="aggregated_short"
                )
                for chunk_idx in range(num_chunks):
                    start = chunk_idx * progress_interval
                    end = min(start + progress_interval, len(short_segments_buffer))
                    chunk_list = short_segments_buffer[start:end]
                    combined_chunk = " ".join(chunk_list)
                    chunk_char_sum = sum(_count_meaningful_chars(s) for s in chunk_list)
                    if not combined_chunk.strip() or chunk_char_sum <= 0:
                        _invoke_progress_callback(
                            progress_callback, chunk_idx + 1, num_chunks, phase="aggregated_short"
                        )
                        time.sleep(0.001)  # Yield GIL so main thread can handle getStatus/health
                        continue
                    chunk_meaningful = _count_meaningful_chars(combined_chunk)
                    script_lang_counts_combined = _collect_script_language_counts(combined_chunk)
                    chinese_char_count_combined = script_lang_counts_combined.get('zh', 0)
                    japanese_char_count_combined = script_lang_counts_combined.get('ja', 0)
                    korean_char_count_combined = script_lang_counts_combined.get('ko', 0)
                    if japanese_char_count_combined > 0:
                        short_lang = 'ja'
                    elif korean_char_count_combined > 0:
                        short_lang = 'ko'
                    elif chinese_char_count_combined > 0:
                        chinese_ratio = chinese_char_count_combined / chunk_meaningful if chunk_meaningful > 0 else 0
                        short_lang = 'zh' if chinese_ratio > 0.3 else detector.detect_language(combined_chunk)
                    else:
                        short_lang = detector.detect_language(combined_chunk)
                    if short_lang == 'ko' and chinese_char_count_combined > 0 and korean_char_count_combined == 0:
                        short_lang = 'zh'
                    _accumulate_chars(short_lang, chunk_char_sum)
                    _invoke_progress_callback(
                        progress_callback, chunk_idx + 1, num_chunks, phase="aggregated_short"
                    )
                    time.sleep(0.001)  # Yield GIL so main thread can handle getStatus/health
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Aggregated {count} short segments processed in {chunks} chunks (context: {context})",
                    count=len(short_segments_buffer),
                    chunks=num_chunks,
                    context=log_context or "N/A"
                )
        except Exception as e:
            combined_preview = " ".join(short_segments_buffer)[:300]
            unified_logger.debug(
                LogModule.DETECT,
                "[LangDetect] Aggregated {count} short segments detection failed: {error}, content: {preview}... (context: {context})",
                count=len(short_segments_buffer),
                error=str(e),
                preview=combined_preview.replace('\n', '\\n'),
                context=log_context or "N/A"
            )

    # Attempt detection for aggregated failed segments
    if failed_segments_buffer and failed_segments_char_sum > 0:
        try:
            combined_failed = " ".join(failed_segments_buffer)
            combined_preview = combined_failed[:300] if len(combined_failed) > 300 else combined_failed
            
            # Check if aggregated failed segments are primarily numbers
            # Count meaningful characters (excluding whitespace, punctuation, etc.)
            combined_meaningful_chars = _count_meaningful_chars(combined_failed)
            combined_digit_count = sum(1 for ch in combined_failed if ch.isdigit())
            
            # Count non-digit, non-whitespace, non-punctuation characters
            combined_alpha_chars = sum(1 for ch in combined_failed if ch.isalnum() and not ch.isdigit())
            
            # Check ratio based on meaningful characters
            # If meaningful chars are primarily digits (>60%), skip detection to avoid false positives
            # Lower threshold (60% instead of 70%) to be more strict
            combined_digit_ratio = combined_digit_count / combined_meaningful_chars if combined_meaningful_chars > 0 else 0
            
            # Also check if digits significantly outnumber alphabetic characters
            # If digits are >3x more than alphabetic chars, likely numeric content
            digit_vs_alpha_ratio = combined_digit_count / combined_alpha_chars if combined_alpha_chars > 0 else float('inf')
            
            # Also check if total text is primarily digits+whitespace+punctuation (>80%)
            combined_total_digit_ratio = combined_digit_count / len(combined_failed) if len(combined_failed) > 0 else 0
            
            # Skip if:
            # 1. Meaningful chars are >60% digits, OR
            # 2. Digits are >3x more than alphabetic chars, OR
            # 3. Total text is >80% digits
            if combined_digit_ratio > 0.6 or digit_vs_alpha_ratio > 3.0 or combined_total_digit_ratio > 0.8:
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Aggregated {count} failed segments skipped (primarily digits, meaningful_ratio={ratio:.2%}, total_ratio={total_ratio:.2%}, digit_vs_alpha={dva_ratio:.2f}) (context: {context})",
                    count=len(failed_segments_buffer),
                    ratio=combined_digit_ratio,
                    total_ratio=combined_total_digit_ratio,
                    dva_ratio=digit_vs_alpha_ratio if digit_vs_alpha_ratio != float('inf') else 999.0,
                    context=log_context or "N/A"
                )
            else:
                failed_lang = detector.detect_language(combined_failed)
                _accumulate_chars(failed_lang, failed_segments_char_sum)
                unified_logger.debug(
                    LogModule.DETECT,
                    "[LangDetect] Aggregated {count} failed segments detected as {lang} (chars={chars}): {preview}... (context: {context})",
                    count=len(failed_segments_buffer),
                    lang=failed_lang,
                    chars=failed_segments_char_sum,
                    preview=combined_preview.replace('\n', '\\n'),
                    context=log_context or "N/A"
                )
        except Exception as e:
            combined_preview = " ".join(failed_segments_buffer)[:300]
            unified_logger.debug(
                LogModule.DETECT,
                "[LangDetect] Aggregated {count} failed segments detection failed: {error}, content: {preview}... (context: {context})",
                count=len(failed_segments_buffer),
                error=str(e),
                preview=combined_preview.replace('\n', '\\n'),
                context=log_context or "N/A"
            )
    
    # Calculate distribution
    language_distribution = {}
    recommended_language = 'en'  # Default
    is_multilingual = False
    total_characters = sum(language_char_counts.values())
    
    if total_characters > 0:
        for lang, char_count in language_char_counts.items():
            language_distribution[lang] = char_count / total_characters
        
        # Find language with highest percentage
        if language_distribution:
            recommended_language, max_percentage = max(
                language_distribution.items(),
                key=lambda x: x[1]
            )
            # If no language has >90%, it's multilingual
            is_multilingual = max_percentage < 0.9
    elif detected_segments > 0:
        # Fallback to segment count distribution
        for lang, count in language_counts.items():
            language_distribution[lang] = count / detected_segments
        if language_distribution:
            recommended_language, max_percentage = max(
                language_distribution.items(),
                key=lambda x: x[1]
            )
            is_multilingual = max_percentage < 0.9
    
    if log_context:
        unified_logger.info(
            LogModule.DETECT,
            "Language distribution detected (char_weights={chars}): {distribution}, "
            "recommended: {recommended}, multilingual: {multilingual} (context: {context})",
            chars=language_char_counts,
            distribution=language_distribution,
            recommended=recommended_language,
            multilingual=is_multilingual,
            context=log_context
        )
    
    return {
        "segment_languages": segment_languages,
        "language_distribution": language_distribution,
        "recommended_language": recommended_language,
        "is_multilingual": is_multilingual,
        "total_segments": total_segments,
        "detected_segments": detected_segments
    }


def select_anonymize_model(
    language_distribution: Dict[str, float],
    threshold: float = 0.9
) -> Tuple[str, bool]:
    """
    Select anonymization model based on language distribution.
    
    Args:
        language_distribution: Dict of {language: percentage}
        threshold: Threshold for single language dominance (default: 0.9)
    
    Returns:
        Tuple of (selected_language, use_multilingual)
        - selected_language: Language code or 'xx' for multilingual
        - use_multilingual: True if should use multilingual model
    """
    if not language_distribution:
        return 'en', False  # Default to English
    
    # Find language with highest percentage
    max_lang, max_percentage = max(
        language_distribution.items(),
        key=lambda x: x[1]
    )
    
    if max_percentage >= threshold:
        # Single language dominant (>=90%)
        return max_lang, False
    else:
        # Mixed language (<90% for any language)
        return 'xx', True  # Use multilingual model

