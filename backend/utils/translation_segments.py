# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""
Utility functions for recording and managing translation segments.
"""

import asyncio
import codecs
import json
import logging
import re
import time
from typing import List, Optional, Dict, Tuple, Any
from pathlib import Path

# Delayed import to avoid circular import issues in PyInstaller frozen builds
# from app.models.translation_segment import TranslationSegment, TranslationSegmentsMetadata
from agents.seg_prompt_utils import parse_seg_output
from logger import unified_logger as logger
from logger.logger import LogModule


# Lazy import helper for PyInstaller compatibility
_imported_models = None

def _get_translation_models():
    """Lazy import TranslationSegment and TranslationSegmentsMetadata for PyInstaller compatibility."""
    global _imported_models
    if _imported_models is None:
        try:
            from app.models.translation_segment import TranslationSegment, TranslationSegmentsMetadata
        except ModuleNotFoundError:
            # Defensive fallback: if the app alias isn't set up yet, import directly
            # from backend.app.models and register the alias in sys.modules.
            import sys as _sys
            from backend.app.models.translation_segment import TranslationSegment, TranslationSegmentsMetadata
            _sys.modules.setdefault("app.models.translation_segment", _sys.modules["backend.app.models.translation_segment"])
            _sys.modules.setdefault("app.models", _sys.modules["backend.app.models"])
            _sys.modules.setdefault("app", _sys.modules["backend.app"])
        _imported_models = (TranslationSegment, TranslationSegmentsMetadata)
    return _imported_models


def _normalize_language_code_for_comparison(lang_code: str) -> str:
    """
    Normalize language code for comparison.
    Maps various language code formats to a standard format.
    Also handles full language names (e.g., 'Chinese', 'English') and converts them to codes.
    
    Args:
        lang_code: Language code (e.g., 'zh', 'zh-CN', 'en', 'en-US') or full name (e.g., 'Chinese', 'English')
        
    Returns:
        Normalized language code (e.g., 'zh', 'en')
    """
    if not lang_code:
        return ''
    
    normalized = lang_code.lower().strip()
    
    # Map full language names to codes (for API compatibility)
    full_name_map = {
        'chinese': 'zh',
        'english': 'en',
        'japanese': 'ja',
        'korean': 'ko',
        'french': 'fr',
        'german': 'de',
        'spanish': 'es',
        'russian': 'ru',
        'italian': 'it',
        'portuguese': 'pt',
        'arabic': 'ar',
        'bengali': 'bn',
        'catalan': 'ca',
        'czech': 'cs',
        'croatian': 'hr',
        'danish': 'da',
        'dutch': 'nl',
        'filipino': 'fil',
        'finnish': 'fi',
        'greek': 'el',
        'hebrew': 'he',
        'hindi': 'hi',
        'khmer': 'km',
        'lithuanian': 'lt',
        'macedonian': 'mk',
        'malay': 'ms',
        'norwegian bokmål': 'nb',
        'norwegian': 'nb',
        'polish': 'pl',
        'romanian': 'ro',
        'slovenian': 'sl',
        'swedish': 'sv',
        'thai': 'th',
        'turkish': 'tr',
        'ukrainian': 'uk',
        'urdu': 'ur',
        'vietnamese': 'vi',
    }
    
    # Check if it's a full language name first
    if normalized in full_name_map:
        return full_name_map[normalized]
    
    # Map common variations to standard codes
    lang_map = {
        'zh-cn': 'zh',
        'zh-tw': 'zh',
        'zh-hans': 'zh',
        'zh-hant': 'zh',
        'en-us': 'en',
        'en-gb': 'en',
        'ja-jp': 'ja',
        'ko-kr': 'ko',
    }
    
    return lang_map.get(normalized, normalized.split('-')[0])


def _normalize_text_for_matching(text: str) -> str:
    """
    Normalize text for matching between markdown and layout blocks.
    
    Removes markdown syntax, image references, and normalizes whitespace
    to improve matching accuracy.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text for matching
    """
    if not text:
        return ""
    
    # Remove markdown image references: ![](path) or ![alt](path)
    text = re.sub(r'!\[.*?\]\([^)]+\)', '', text)
    
    # Remove markdown headers: # Title -> Title
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # Remove markdown bold/italic: **text** -> text, *text* -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Remove markdown links: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Normalize LaTeX: $^{1}$ -> ^{1}, \(^{1}\) -> ^{1}
    # Keep the content but remove $ and \( \) wrappers
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    text = re.sub(r'\\\(([^)]+)\\\)', r'\1', text)
    
    # Normalize whitespace: multiple spaces/newlines to single space
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def _extract_separators_from_source(source_chunks: List[str], original_content: Optional[str] = None) -> List[Optional[str]]:
    """
    Extract separators between chunks from original content.
    Returns a list of separators, where separators[i] is the separator after chunk[i].
    
    Args:
        source_chunks: List of source text chunks
        original_content: Original document content (before translation)
        
    Returns:
        List of separators (None if not found, empty string for last chunk)
    """
    separators: List[Optional[str]] = []
    
    if original_content is None or not source_chunks:
        # If no original content, use intelligent defaults based on chunk content
        # This will be handled by join_markdown_texts in rebuild function
        return [None] * len(source_chunks)
    
    # Find the position of each chunk in the original content sequentially
    # This ensures we find chunks in order even if they appear multiple times
    current_pos = 0
    for i, chunk in enumerate(source_chunks):
        if i == len(source_chunks) - 1:
            # Last chunk: no separator after it
            separators.append("")
            break
        
        # Find the chunk in original content starting from current position
        chunk_pos = original_content.find(chunk, current_pos)
        if chunk_pos == -1:
            # Chunk not found, use default
            separators.append(None)
            logger.warning(LogModule.TRANS, f"Chunk {i} not found in original content for separator extraction")
            continue
        
        # Find the end of this chunk
        chunk_end = chunk_pos + len(chunk)
        
        # Find the start of next chunk (must be after current chunk)
        next_chunk = source_chunks[i + 1]
        next_chunk_pos = original_content.find(next_chunk, chunk_end)
        
        if next_chunk_pos == -1:
            # Next chunk not found, use default
            separators.append(None)
            logger.warning(LogModule.TRANS, f"Next chunk {i + 1} not found after chunk {i} for separator extraction")
            continue
        
        # Extract the separator between chunks (preserves whitespace, newlines, etc.)
        separator = original_content[chunk_end:next_chunk_pos]
        separators.append(separator)
        current_pos = next_chunk_pos
    
    return separators


def _is_image_segment(text: str) -> bool:
    """
    Check if a segment is an image segment (contains only placeholder).
    
    Image segments are identified by:
    - Containing only <ph-...> placeholder(s)
    - Or containing base64 image data (data:image/...;base64,...)
    - Or containing markdown image syntax (![alt](path))
    
    Args:
        text: Segment text to check
        
    Returns:
        True if segment is an image segment, False otherwise
    """
    if not text:
        return False
    
    text_stripped = text.strip()
    
    # Check if segment contains only placeholder(s)
    # Pattern: <ph-xxxxx> (possibly with whitespace)
    ph_pattern = r"^<ph-[a-zA-Z0-9]+>\s*$"
    if re.match(ph_pattern, text_stripped):
        return True
    
    # Check if segment contains base64 image data
    # Pattern: data:image/...;base64,...
    base64_image_pattern = r"data:image/[^;]+;base64,"
    if re.search(base64_image_pattern, text_stripped):
        return True
    
    # Check if segment is a markdown image with base64
    # Pattern: ![alt](data:image/...;base64,...)
    markdown_base64_image_pattern = r"!\[.*?\]\(data:image/[^;]+;base64,[^)]+\)"
    if re.match(rf"^{markdown_base64_image_pattern}\s*$", text_stripped):
        return True
    
    # Check if segment is a markdown image (without base64)
    # Pattern: ![alt](path) - only if it's the only content
    markdown_image_pattern = r"!\[.*?\]\([^)]+\)"
    if re.match(rf"^{markdown_image_pattern}\s*$", text_stripped):
        return True
    
    return False


def _is_formula_segment(text: str) -> bool:
    """
    Check if a segment is a formula segment (LaTeX/math formula).
    
    Formula segments are identified by:
    - Containing LaTeX inline math: $...$ or \\(...\\)
    - Containing LaTeX display math: $$...$$ or \\[...\\]
    - Being primarily LaTeX content (more than 50% LaTeX syntax)
    
    Args:
        text: Segment text to check
        
    Returns:
        True if segment is a formula segment, False otherwise
    """
    if not text:
        return False
    
    text_stripped = text.strip()
    total_chars = len(text_stripped)  # CRITICAL: Initialize total_chars before any conditional blocks
    
    # Check for LaTeX inline math: $...$ or \(...\)
    inline_math_pattern = r'\$[^$]+\$|\\\([^)]+\\\)'
    if re.search(inline_math_pattern, text_stripped):
        # If the segment is primarily math (more than 50% is math), consider it a formula segment
        math_chars = len(re.findall(inline_math_pattern, text_stripped))
        if math_chars > 0 and (math_chars * 2) > total_chars * 0.5:
            return True
    
    # Check for LaTeX display math: $$...$$ or \[...\]
    display_math_pattern = r'\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]'
    if re.search(display_math_pattern, text_stripped):
        return True
    
    # Check if segment is primarily LaTeX content (contains many LaTeX commands)
    latex_command_pattern = r'\\[a-zA-Z]+\{?[^}]*\}?'
    latex_commands = re.findall(latex_command_pattern, text_stripped)
    if len(latex_commands) > 0:
        # If more than 30% of the text is LaTeX commands, consider it a formula
        latex_chars = sum(len(cmd) for cmd in latex_commands)
        if latex_chars > total_chars * 0.3:
            return True
    
    return False


def _is_table_segment(text: str) -> bool:
    """
    Check if a segment is a table segment (markdown table).
    
    Table segments are identified by:
    - Containing markdown table syntax: lines starting and ending with |
    - Having at least 2 rows (header + separator + data)
    - Fallback: tables with newlines inside cells (separator not at line 1)
      use the same heuristic as document_rebuild so they are not mis-detected
      as IDENTIFIER (e.g. tables containing URLs/emails).
    
    Args:
        text: Segment text to check
        
    Returns:
        True if segment is a table segment, False otherwise
    """
    if not text:
        return False
    
    text_stripped = text.strip()
    lines = text_stripped.split('\n')
    
    # Filter out empty lines
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    if len(non_empty_lines) < 2:
        return False
    
    # Check if at least 2 lines start and end with |
    table_line_count = 0
    for line in non_empty_lines:
        stripped_line = line.strip()
        if stripped_line.startswith('|') and stripped_line.endswith('|'):
            table_line_count += 1
    
    # A markdown table should have at least 2 rows (header + separator or header + data)
    # And at least 50% of non-empty lines should be table rows
    if table_line_count >= 2 and table_line_count >= len(non_empty_lines) * 0.5:
        return True
    
    # Fallback: tables with newlines in cells (separator not at line 1) so that
    # exclusion detection treats them as TABLE, not IDENTIFIER (e.g. table with URLs/emails)
    from utils.document_rebuild.table_layout_utils import _is_markdown_table
    return _is_markdown_table(text_stripped)


def record_translation_segments(
    task_id: str,
    source_chunks: List[str],
    target_chunks: List[str],
    original_filename: Optional[str] = None,
    workflow_type: Optional[str] = None,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    platform_key: Optional[str] = None,  # AI platform key used for translation
    task_state: Optional[dict] = None,
    original_content: Optional[str] = None,  # Original document content for format preservation
    excluded_segments: Optional[List[int]] = None,  # List of segment indices to exclude from translation
    layout_chunk_block_map: Optional[List[List[int]]] = None,  # Precomputed layout indices per chunk
    chunk_to_segment_map: Optional[List[List[int]]] = None,  # Precomputed chunk to segment mapping
    arb_metadata_indices: Optional[List[int]] = None,  # Indices of ARB metadata segments (e.g., @@locale) for JSON/ARB workflows
) -> None:
    """
    Record translation segments to task state.
    
    Args:
        task_id: Task identifier
        source_chunks: List of source text chunks
        target_chunks: List of translated text chunks (must match source_chunks length)
        original_filename: Original file name
        workflow_type: Workflow type used (e.g., 'markdown_based', 'docx')
        source_lang: Source language code
        target_lang: Target language code
        task_state: Task state dictionary (if None, will be imported from app_routes_service)
        original_content: Original document content for format preservation (optional)
    """
    # Import models with lazy loading for PyInstaller compatibility
    TranslationSegment, TranslationSegmentsMetadata = _get_translation_models()
    
    if task_state is None:
        # Import here to avoid circular dependency
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            logger.warning(LogModule.TRANS, f"Task {task_id} not found in tasks_state, cannot record segments")
            return
    
    # CRITICAL: Get platform_key from task_state if not provided as parameter
    # This ensures platform_used is set correctly for frontend display
    if platform_key is None and task_state:
        platform_key = task_state.get("platform_key")
        if platform_key:
            logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Task {task_id}: Retrieved platform_key={platform_key} from task_state")
    
    if len(source_chunks) != len(target_chunks):
        logger.error(LogModule.TRANS,
            f"Source chunks ({len(source_chunks)}) and target chunks ({len(target_chunks)}) "
            f"count mismatch for task {task_id}"
        )
        return
    
    if not source_chunks:
        logger.warning(LogModule.TRANS, f"No source chunks to record for task {task_id}")
        return
    
    # CRITICAL: Pre-fill target segments with source text before translation
    # This ensures that even if translation fails or segments are missing, we have the original text
    # This is especially important for excluded segments and image segments
    # Strategy: Initialize all segments with source text, then update with translated text
    # TranslationSegment is imported via _get_translation_models() at function start
    
    # Get or create translation_segments in task_state
    # CRITICAL: Use dict format for consistency (new format)
    # Handle backward compatibility if it's already a list
    if "translation_segments" not in task_state:
        task_state["translation_segments"] = {
            "segments": [],
            "metadata": {}
        }
    elif isinstance(task_state.get("translation_segments"), list):
        # Convert old list format to new dict format
        old_segments = task_state["translation_segments"]
        task_state["translation_segments"] = {
            "segments": old_segments,
            "metadata": {}
        }
    
    # CRITICAL: Initialize excluded_segments_with_reasons BEFORE pre-fill stage
    # This must be done early because it's used in pre-fill stage
    from exclusion.core import ExclusionManager, ExclusionReason
    
    # Get excluded segments from task_state (unified source)
    # This is the SINGLE SOURCE OF TRUTH for exclusion information
    # It reads from segments_metadata.excluded_segments (Extract phase) and
    # translation_segments[].is_excluded (Translate phase, for backward compatibility)
    excluded_segments_with_reasons = {}
    if task_state:
        excluded_segments_with_reasons = ExclusionManager.get_excluded_segments(task_state)
        
        # CRITICAL: Log excluded segments from Extract phase for debugging
        segments_metadata = task_state.get("segments_metadata", {})
        extract_excluded = segments_metadata.get("excluded_segments", {})
        if extract_excluded:
            logger.info(
                LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: Found {len(extract_excluded)} excluded segments "
                f"from Extract phase (segments_metadata.excluded_segments): "
                f"{sorted([int(k) for k in extract_excluded.keys()])[:10]}{'...' if len(extract_excluded) > 10 else ''}",
            )
        
        # Log what we actually got from ExclusionManager
        if excluded_segments_with_reasons:
            logger.info(
                LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: ExclusionManager returned {len(excluded_segments_with_reasons)} excluded segments: "
                f"{sorted(excluded_segments_with_reasons.keys())[:10]}{'...' if len(excluded_segments_with_reasons) > 10 else ''}",
            )
        else:
            logger.debug(
                LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: No excluded segments found from ExclusionManager",
            )
    
    # CRITICAL: excluded_segments parameter (from MDTranslator) should already be included
    # in excluded_segments_with_reasons (from ExclusionManager.get_excluded_segments)
    # because MDTranslator uses the same source (ExclusionManager.get_excluded_segments)
    # So we should NOT add segments from excluded_segments parameter as UNKNOWN
    # This would overwrite existing reasons (e.g., user_selected, reference, identifier)
    # 
    # However, if there are segments in excluded_segments that are NOT in excluded_segments_with_reasons,
    # this indicates a data inconsistency. We should log a warning but NOT add them as UNKNOWN
    # because Translate phase is READ-ONLY and should not modify exclusion data.
    excluded_set = set(excluded_segments) if excluded_segments else set()
    if excluded_set:
        missing_in_excluded_segments_with_reasons = excluded_set - set(excluded_segments_with_reasons.keys())
        if missing_in_excluded_segments_with_reasons:
            logger.warning(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: Found {len(missing_in_excluded_segments_with_reasons)} segments "
                f"in excluded_segments parameter that are NOT in excluded_segments_with_reasons: "
                f"{sorted(missing_in_excluded_segments_with_reasons)[:10]}... "
                f"This indicates a data inconsistency. These segments will NOT be excluded in translation. "
                f"Exclusion data should be fixed in Extract phase."
            )
        # Do NOT add missing segments as UNKNOWN - Translate phase is READ-ONLY
    # Optional: ARB metadata indices (only for JSON/ARB workflows that pass them)
    arb_metadata_index_set = set(arb_metadata_indices) if arb_metadata_indices else set()

    # Get segments list for iteration
    translation_segments_data = task_state["translation_segments"]
    if isinstance(translation_segments_data, dict):
        existing_segments_list = translation_segments_data.get("segments", [])
    else:
        existing_segments_list = []
    
    # Get cached segments if available (for accurate segment indexing)
    source_segments = None
    if task_state:
        cache_info = task_state.get("source_chunks_cache")
        if cache_info:
            cached_segments = cache_info.get("segments", [])
            if cached_segments:
                source_segments = [str(s) for s in cached_segments]
    
    # Pre-fill segments with source text
    # If source_segments is available, use it; otherwise use source_chunks
    segments_to_prefill = source_segments if source_segments else source_chunks
    
    # CRITICAL: Build index map for O(1) lookup instead of O(n) linear search
    # This dramatically improves performance when pre-filling many segments
    existing_segments_map = {}
    for seg in existing_segments_list:
        if isinstance(seg, dict):
            seg_idx = seg.get("segment_index")
            if seg_idx is not None:
                existing_segments_map[seg_idx] = seg
        elif hasattr(seg, "segment_index"):
            seg_idx = seg.segment_index
            if seg_idx is not None:
                existing_segments_map[seg_idx] = seg.to_dict() if hasattr(seg, "to_dict") else seg
    
    # Track statistics for batch logging (avoid per-segment logging for performance)
    prefill_stats = {
        "total": 0,
        "excluded": 0,
        "images": 0,
        "new": 0,
        "existing": 0
    }
    
    for seg_idx, source_text in enumerate(segments_to_prefill):
        prefill_stats["total"] += 1
        # Check if segment already exists - use O(1) dictionary lookup
        existing_segment = existing_segments_map.get(seg_idx)
        
        if existing_segment is None:
            prefill_stats["new"] += 1
            # Create new segment with source text as target (will be updated after translation)
            # Use unified ExclusionManager to check exclusion
            exclusion_reason = excluded_segments_with_reasons.get(seg_idx)
            is_excluded = exclusion_reason is not None
            exclusion_metadata = {}
            
            # CRITICAL: Translate phase does NOT detect new exclusions
            # If segment is not in excluded_segments_with_reasons, it should NOT be excluded
            # This ensures that exclusion data is managed only in Extract phase
            # NOTE: Removed per-segment logging for non-excluded segments to improve performance
            # Only log first few segments for debugging purposes
            if not is_excluded and seg_idx < 3:
                logger.debug(
                    LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Segment {seg_idx} (pre-fill) is NOT excluded "
                    f"(not in excluded_segments_with_reasons, will be marked as not excluded)",
                )
            
            is_image = _is_image_segment(str(source_text))
            
            # CRITICAL: Image segments should always be marked as excluded
            if is_image and not is_excluded:
                is_excluded = True
                exclusion_reason = ExclusionReason.IMAGE
                exclusion_metadata = {}
                excluded_segments_with_reasons[seg_idx] = exclusion_reason
            
            # For excluded and image segments, target_text should be source_text
            # For other segments, also pre-fill with source_text (will be updated after translation)
            target_text = str(source_text)
            
            segment = TranslationSegment.create(
                task_id=task_id,
                segment_index=seg_idx,
                source_text=str(source_text),
                target_text=target_text,  # Pre-fill with source text
                source_format=None,
                workflow_type=workflow_type,
            )
            segment_dict = segment.to_dict()
            
            if is_excluded:
                prefill_stats["excluded"] += 1
                segment_dict['is_excluded'] = True
                segment_dict['excluded_at'] = time.time()
                segment_dict['exclusion_reason'] = exclusion_reason.value if exclusion_reason else None
                segment_dict['exclusion_metadata'] = exclusion_metadata if exclusion_reason else None
                # Log excluded segments for debugging (only first few to avoid performance impact)
                if seg_idx < 20 or seg_idx in [8, 12, 31, 40, 42, 53, 56, 77, 82, 85, 87, 89, 91, 93, 95]:
                    logger.debug(
                        LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Pre-fill segment {seg_idx} marked as excluded "
                        f"(exclusion_reason={exclusion_reason.value if exclusion_reason else None})",
                    )
            
            if is_image:
                prefill_stats["images"] += 1
                segment_dict['is_image'] = True
                if not segment_dict.get('is_excluded'):
                    segment_dict['is_excluded'] = True
                    segment_dict['excluded_at'] = time.time()
                    segment_dict['exclusion_reason'] = ExclusionReason.IMAGE.value
                    segment_dict['exclusion_metadata'] = {}
            
            # CRITICAL: Set platform_used if platform_key is available
            # This allows frontend to display correct platform/model information
            if platform_key:
                segment_dict["platform_used"] = platform_key
                # Initialize used_platforms list if not already set
                if "used_platforms" not in segment_dict:
                    segment_dict["used_platforms"] = [platform_key] if platform_key else []
            
            # Add to segments list (maintain dict format)
            if isinstance(task_state["translation_segments"], dict):
                task_state["translation_segments"].setdefault("segments", []).append(segment_dict)
            else:
                # Fallback for old format
                task_state["translation_segments"].append(segment_dict)
            if seg_idx < 3:
                logger.trace(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Pre-filled segment {seg_idx} with source text: '{str(source_text)[:50]}...' "
                    f"(is_image={is_image}, is_excluded={is_excluded})"
                )
        else:
            prefill_stats["existing"] += 1
    
    # Log pre-fill statistics in batch (avoid per-segment logging for performance)
    if prefill_stats["total"] > 0:
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: Pre-fill completed - "
            f"total={prefill_stats['total']}, new={prefill_stats['new']}, existing={prefill_stats['existing']}, "
            f"excluded={prefill_stats['excluded']}, images={prefill_stats['images']}"
        )
    
    # CRITICAL: Validate and fix source_chunks if they appear to contain translated text
    # If source_chunks and target_chunks are identical and contain non-ASCII characters,
    # it might indicate that source_chunks was incorrectly filled with translated text
    # In this case, try to recover original text from source_chunks_cache
    if task_state and len(source_chunks) == len(target_chunks):
        # Check if source and target are suspiciously similar (might indicate data corruption)
        # This can happen if source_chunks was incorrectly populated with translated text
        identical_count = sum(1 for s, t in zip(source_chunks, target_chunks) if s == t)
        if identical_count > len(source_chunks) * 0.8:  # More than 80% identical
            logger.warning(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Warning: {identical_count}/{len(source_chunks)} segments have identical source and target text. "
                f"This might indicate source_chunks contains translated text instead of original text."
            )
            # Try to recover from source_chunks_cache if available
            cache_info = task_state.get("source_chunks_cache", {})
            cached_segments = cache_info.get("segments", [])
            if cached_segments and len(cached_segments) == len(source_chunks):
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Attempting to recover original text from source_chunks_cache "
                    f"({len(cached_segments)} cached segments available)"
                )
                # Use cached segments as source_chunks (they should be original text)
                # Convert to list to avoid modifying the original
                source_chunks = [str(s) for s in cached_segments]
                logger.info(LogModule.TRANS, f"[RECORD_SEGMENTS] Recovered source_chunks from cache")
            else:
                logger.warning(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Cannot recover: cache_info exists={bool(cache_info)}, "
                    f"cached_segments count={len(cached_segments) if cached_segments else 0}, "
                    f"source_chunks count={len(source_chunks)}"
                )
    
    # Determine original format from filename
    source_format = None
    if original_filename:
        ext = Path(original_filename).suffix.lower().lstrip('.')
        if ext:
            source_format = ext
    
    # Extract separators from original content to preserve format
    separators = _extract_separators_from_source(source_chunks, original_content)
    
    # Log excluded segments info (excluded_segments_with_reasons is already initialized above)
    if excluded_segments_with_reasons:
        # Group by reason for logging
        reason_counts = {}
        for reason in excluded_segments_with_reasons.values():
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: Found {len(excluded_segments_with_reasons)} excluded segments: "
            f"{', '.join(f'{count} {reason.value}' for reason, count in sorted(reason_counts.items()))}"
        )
    else:
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: No excluded segments found in task_state"
        )
    
    # CRITICAL: Map chunks to segments for correct segment_index assignment
    # Chunks may contain multiple segments, so we need to map them correctly
    chunk_to_segment_map_computed: List[List[int]] = []  # Maps chunk index to list of segment indices
    source_segments: List[str] = []  # Original segments from source_chunks_cache
    
    # Check if source_chunks and target_chunks are actually segments (not chunks)
    # This happens when translate_segments_with_agent returns segments directly
    # We can detect this by checking if len(source_chunks) matches the number of segments in cache
    # CRITICAL: For PPTX workflow, if chunk_to_segment_map=None, we know input is segments
    is_actually_segments = False
    source_segments: List[str] = []
    
    # Force segment-level processing for PPTX when chunk_to_segment_map is explicitly None
    if workflow_type == "pptx" and chunk_to_segment_map is None:
        is_actually_segments = True
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] PPTX workflow with chunk_to_segment_map=None, "
            f"forcing segment-level processing: source_chunks={len(source_chunks)}, target_chunks={len(target_chunks)}"
        )
    
    # CRITICAL: For XLSX workflow, send_segments_async already splits chunks back to segments
    # So source_chunks and target_chunks are actually segments, not chunks
    # We should treat them as segments if:
    # 1. workflow_type is xlsx OR filename ends with .xlsx
    # 2. AND source_chunks length matches cached_segments length (indicating segments, not chunks)
    is_xlsx_workflow = workflow_type == "xlsx" or (original_filename and original_filename.lower().endswith('.xlsx'))
    if is_xlsx_workflow:
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] XLSX workflow detected: workflow_type={workflow_type}, "
            f"source_chunks={len(source_chunks)}, target_chunks={len(target_chunks)}, "
            f"chunk_to_segment_map provided={chunk_to_segment_map is not None}"
        )
        if task_state:
            cache_info = task_state.get("source_chunks_cache", {})
            cached_segments = cache_info.get("segments", [])
            if cached_segments and len(source_chunks) == len(cached_segments):
                # For XLSX, if source_chunks length matches cached_segments, they are segments
                # send_segments_async already split chunks back to segments
                is_actually_segments = True
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] XLSX workflow: source_chunks length ({len(source_chunks)}) "
                    f"matches cached_segments length ({len(cached_segments)}), "
                    f"treating input as segments (send_segments_async already split chunks)"
                )
            elif chunk_to_segment_map is not None:
                # Log chunk_to_segment_map structure for debugging
                total_segments_in_map = sum(len(seg_indices) for seg_indices in chunk_to_segment_map)
                is_one_to_one = all(len(seg_indices) == 1 for seg_indices in chunk_to_segment_map)
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] XLSX workflow: chunk_to_segment_map has {len(chunk_to_segment_map)} chunks, "
                    f"total segments in map: {total_segments_in_map}, is_one_to_one: {is_one_to_one}, "
                    f"source_chunks length: {len(source_chunks)}"
                )
                # If chunk_to_segment_map segments count matches source_chunks, they are segments
                if total_segments_in_map == len(source_chunks):
                    is_actually_segments = True
                    logger.info(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] XLSX workflow: chunk_to_segment_map total segments ({total_segments_in_map}) "
                        f"matches source_chunks length ({len(source_chunks)}), treating input as segments"
                    )
    
    # CRITICAL: For PDF workflow, chunks and segments are one-to-one
    # We should NOT treat them as segments just because lengths match
    is_pdf_workflow = workflow_type == "markdown_based" or (original_filename and original_filename.lower().endswith('.pdf'))
    
    if task_state:
        cache_info = task_state.get("source_chunks_cache", {})
        cached_segments = cache_info.get("segments", [])
        if cached_segments:
            source_segments = [str(s) for s in cached_segments]
            
            # When caller passes chunk_to_segment_map=None and lengths match cache, input is segment-level.
            # This includes markdown_based/PDF: md_translator expands JSON chunk results to segment-level
            # and passes segment arrays with chunk_to_segment_map=None (pure segments).
            if not is_actually_segments and len(source_chunks) == len(cached_segments):
                if chunk_to_segment_map is None:
                    # Explicitly None means "treat as segments" (PPTX, or markdown_based segment-level result)
                    is_actually_segments = True
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] chunk_to_segment_map=None and len matches cache: treating as segments. "
                        f"source_chunks={len(source_chunks)}, cached_segments={len(cached_segments)}, workflow={workflow_type}"
                    )
                else:
                    # Caller provided a chunk map - use it (chunk-level input)
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Length match but chunk_to_segment_map provided: treating as chunks. "
                        f"source_chunks={len(source_chunks)}, cached_segments={len(cached_segments)}"
                    )
            elif not is_actually_segments:
                # Cache exists but lengths don't match - use cached segments for mapping
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Using cached segments for mapping: "
                    f"source_chunks={len(source_chunks)}, cached_segments={len(cached_segments)}"
                )
    
    # CRITICAL: For PDF workflow, prioritize chunk_to_segment_map if provided
    # PDF workflow has one-to-one chunks/segments, so we should use the provided map
    # Priority 1: If we detected that input is actually segments, force one-to-one mapping
    # This must be checked FIRST, before using chunk_to_segment_map
    # CRITICAL: When is_actually_segments=True, we MUST use one-to-one mapping and ignore any chunk_to_segment_map
    if is_actually_segments:
        # Create one-to-one mapping: each "chunk" (actually segment) maps to itself
        chunk_to_segment_map_computed = [[i] for i in range(len(source_chunks))]
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Input is segments (not chunks), created one-to-one mapping: "
            f"{len(chunk_to_segment_map_computed)} entries (workflow={workflow_type}, "
            f"source_chunks={len(source_chunks)}, target_chunks={len(target_chunks)})"
        )
    # Priority 2: Use precomputed chunk_to_segment_map if provided (for chunks, not segments)
    # This must be checked AFTER is_actually_segments detection to avoid incorrect mapping
    # If chunk_to_segment_map is explicitly provided (e.g., full_chunk_to_segment_map from PDF workflow),
    # we should use it even if lengths match (PDF workflow has one-to-one chunks/segments)
    elif chunk_to_segment_map is not None:
        chunk_to_segment_map_computed = chunk_to_segment_map
        logger.info(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Using precomputed chunk_to_segment_map: {len(chunk_to_segment_map_computed)} chunks. "
            f"First few mappings: {chunk_to_segment_map_computed[:5] if len(chunk_to_segment_map_computed) > 5 else chunk_to_segment_map_computed}, "
            f"is_pdf_workflow={is_pdf_workflow}"
        )
        
        # For PDF workflow, chunks may be merged (like DOCX), so mapping may not be one-to-one
        # This is expected and correct - it reduces token consumption
        if is_pdf_workflow:
            # Log mapping info for debugging
            merged_chunks_count = sum(1 for seg_indices in chunk_to_segment_map_computed if len(seg_indices) > 1)
            if merged_chunks_count > 0:
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] PDF workflow: {merged_chunks_count} chunks are merged "
                    f"(contain multiple segments). This is expected and reduces token consumption."
                )
    # Priority 3: If we detected that input is actually segments (fallback check)
    # This should not be needed if Priority 1 worked correctly, but keep for safety
    elif is_actually_segments:
        # Create one-to-one mapping: each "chunk" (actually segment) maps to itself
        chunk_to_segment_map_computed = [[i] for i in range(len(source_chunks))]
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Input is segments (not chunks), created one-to-one mapping: "
            f"{len(chunk_to_segment_map_computed)} entries (workflow={workflow_type}, "
            f"source_chunks={len(source_chunks)}, target_chunks={len(target_chunks)})"
        )
    # Priority 3: Try to get from task_state (saved by translate_segments_with_agent)
    # BUT: Only if we haven't detected segments AND chunk_to_segment_map was not explicitly set to None
    elif not is_actually_segments and chunk_to_segment_map is None and task_state:
        # chunk_to_segment_map=None might indicate segments, but we didn't detect it above
        # Check if we should still use task_state's map or force one-to-one
        # For PPTX, we already handled this above, so this is for other workflows
        chunk_to_segment_map_from_state = task_state.get("chunk_to_segment_map")
        if chunk_to_segment_map_from_state:
            chunk_to_segment_map_computed = chunk_to_segment_map_from_state
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Using chunk_to_segment_map from task_state: {len(chunk_to_segment_map_computed)} chunks"
            )
    
    # Legacy check (should not be needed now, but keep for backward compatibility)
    if is_actually_segments and not chunk_to_segment_map_computed:
        # Create one-to-one mapping: each "chunk" (actually segment) maps to itself
        chunk_to_segment_map_computed = [[i] for i in range(len(source_chunks))]
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Created one-to-one mapping for segments: {len(chunk_to_segment_map_computed)} entries"
        )
    
    # Priority 4: Build chunk_to_segment_map by matching chunk content to segments (fallback)
    # CRITICAL: Only if we haven't detected segments - never build map for segments!
    if not is_actually_segments and not chunk_to_segment_map_computed and task_state:
        cache_info = task_state.get("source_chunks_cache", {})
        cached_segments = cache_info.get("segments", [])
        if cached_segments:
            source_segments = [str(s) for s in cached_segments]
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Found {len(source_segments)} cached segments, "
                f"building chunk_to_segment_map by content matching"
            )
            
            # Build chunk_to_segment_map by matching chunk content to segments
            # This ensures correct segment_index assignment when chunks contain multiple segments
            # Strategy: For each chunk, find which segments it contains by matching content
            current_segment_idx = 0
            for chunk_idx, chunk_text in enumerate(source_chunks):
                chunk_text_stripped = chunk_text.strip()
                
                if not chunk_text_stripped:
                    # Empty chunk - no segments
                    chunk_to_segment_map.append([])
                    continue
                
                # Normalize chunk text for matching (remove extra whitespace, newlines)
                chunk_normalized = ' '.join(chunk_text_stripped.split())
                chunk_normalized_lower = chunk_normalized.lower()
                
                # Try to find segments that this chunk contains
                # A chunk may contain one or more segments concatenated together
                matched_segments = []
                accumulated_text = ""
                search_start = current_segment_idx
                
                # Try to match segments sequentially until we've matched the entire chunk
                for seg_idx in range(search_start, len(source_segments)):
                    seg_text = str(source_segments[seg_idx]).strip()
                    if not seg_text:
                        # Skip empty segments
                        continue
                    
                    # Normalize segment text for matching
                    seg_normalized = ' '.join(seg_text.split())
                    seg_normalized_lower = seg_normalized.lower()
                    
                    # Check if this segment is part of the chunk
                    # Strategy: accumulate segments until we match the chunk content
                    test_accumulated = accumulated_text + (" " if accumulated_text else "") + seg_normalized
                    test_accumulated_normalized = ' '.join(test_accumulated.split())
                    test_accumulated_lower = test_accumulated_normalized.lower()
                    
                    # Check if accumulated text matches chunk (allowing for some flexibility)
                    if (chunk_normalized_lower.startswith(test_accumulated_lower) or 
                        test_accumulated_lower in chunk_normalized_lower or
                        chunk_normalized_lower in test_accumulated_lower):
                        matched_segments.append(seg_idx)
                        accumulated_text = test_accumulated_normalized
                        
                        # If we've matched the entire chunk, stop
                        if (len(test_accumulated_normalized) >= len(chunk_normalized) * 0.9 or
                            chunk_normalized_lower == test_accumulated_lower):
                            break
                    elif matched_segments:
                        # We've started matching but this segment doesn't fit
                        # Stop here - we've found the segments for this chunk
                        break
                    elif seg_idx - search_start > 20:
                        # Too many segments checked without a match - give up
                        break
                
                if matched_segments:
                    # Found matching segments
                    chunk_to_segment_map_computed.append(matched_segments)
                    current_segment_idx = max(matched_segments) + 1
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Chunk {chunk_idx} mapped to segments {matched_segments} "
                        f"(chunk length: {len(chunk_text)}, segments: {len(matched_segments)})"
                    )
                else:
                    # No match found - use chunk index as segment index (fallback)
                    # This happens when chunks don't match segments (e.g., different splitting)
                    if current_segment_idx < len(source_segments):
                        chunk_to_segment_map_computed.append([current_segment_idx])
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx} no match found, using segment index {current_segment_idx} as fallback"
                        )
                        current_segment_idx += 1
                    else:
                        chunk_to_segment_map_computed.append([chunk_idx])
                        logger.warning(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx} no match found and segment index out of bounds, "
                            f"using chunk index {chunk_idx} as fallback"
                        )
            
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Built chunk_to_segment_map: {len(chunk_to_segment_map_computed)} chunks mapped to segments"
            )
        else:
            # No cached segments - use chunk index as segment index (original behavior)
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] No cached segments found, using chunk index as segment index"
            )
            chunk_to_segment_map_computed = [[i] for i in range(len(source_chunks))]
    else:
        # No task_state - use chunk index as segment index (original behavior)
        if not chunk_to_segment_map_computed:
            chunk_to_segment_map_computed = [[i] for i in range(len(source_chunks))]
    
    # Create segments - now with correct segment_index mapping
    # CRITICAL: Start with existing segments from pre-fill stage (if any) to preserve exclusion_reason
    segments = []
    if isinstance(task_state.get("translation_segments"), dict):
        existing_segments_from_prefill = task_state["translation_segments"].get("segments", [])
        if existing_segments_from_prefill:
            # Copy existing segments to preserve exclusion_reason and other metadata from pre-fill stage
            segments = [seg.copy() if isinstance(seg, dict) else seg for seg in existing_segments_from_prefill]
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: Starting with {len(segments)} segments from pre-fill stage"
            )
    
    seen_segment_indices = set()  # Track which segment indices we've already created
    # Initialize seen_segment_indices with existing segments from pre-fill stage
    for seg in segments:
        if isinstance(seg, dict):
            seg_idx = seg.get("segment_index")
            if seg_idx is not None:
                seen_segment_indices.add(seg_idx)
    
    # CRITICAL: ExclusionManager already handles existing segments from translation_segments
    # No need to build separate existing_segments_excluded_map - use excluded_segments_with_reasons instead
    # This provides unified exclusion management with reason tracking
    
    # If input is actually segments (not chunks), process them directly
    if is_actually_segments:
        logger.debug(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Processing {len(source_chunks)} segments directly (not chunks). "
            f"source_chunks length: {len(source_chunks)}, target_chunks length: {len(target_chunks)}"
        )
        # Ensure we process all segments, even if target_chunks is shorter
        max_len = max(len(source_chunks), len(target_chunks))
        if len(source_chunks) != len(target_chunks):
            logger.warning(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Length mismatch: source_chunks={len(source_chunks)}, "
                f"target_chunks={len(target_chunks)}. Will process {max_len} segments."
            )
        
        # Track excluded segments for batch logging
        excluded_segment_indices = []
        
        # CRITICAL: Build index map for O(1) lookup instead of O(n) linear search
        # This dramatically improves performance when updating many existing segments
        # Map segment_index -> segment_dict for fast lookup
        segment_index_map = {}
        for seg in segments:
            if isinstance(seg, dict):
                seg_idx = seg.get("segment_index")
                if seg_idx is not None:
                    segment_index_map[seg_idx] = seg
            elif hasattr(seg, "segment_index"):
                seg_idx = seg.segment_index
                if seg_idx is not None:
                    segment_index_map[seg_idx] = seg.to_dict() if hasattr(seg, "to_dict") else seg
        
        # For segments passed directly, we need to map them to their original indices
        # The source_chunks should match the cached segments in task_state
        # Use sequential indices (0, 1, 2, ...) as segment_index, which should match
        # the original source_segments list indices since they're passed in order
        for segment_idx in range(max_len):
            # Get source and target texts, handling length mismatch
            source_text = source_chunks[segment_idx] if segment_idx < len(source_chunks) else ""
            target_text = target_chunks[segment_idx] if segment_idx < len(target_chunks) else source_text
            
            # Debug: Log when target_text equals source_text for first 3 segments (for troubleshooting)
            if segment_idx < 3 and target_text == source_text:
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Segment {segment_idx} has target_text==source_text: "
                    f"source='{source_text[:50]}...'"
                )
            
            # Use segment index directly - it should match the original source_segments list index
            # since source_chunks is passed as source_segments[:n] which preserves original order
            actual_segment_index = segment_idx
            
            # CRITICAL: Check if segment already exists from pre-fill stage
            # If it exists, update it instead of creating a new one (preserves exclusion_reason)
            # Use O(1) dictionary lookup instead of O(n) linear search
            existing_segment_dict = None
            if actual_segment_index in seen_segment_indices:
                # Fast O(1) lookup using index map
                existing_segment_dict = segment_index_map.get(actual_segment_index)
                
                if existing_segment_dict:
                    # Update existing segment with translated text, but preserve exclusion_reason
                    # CRITICAL: Only update target_text if segment is not excluded
                    exclusion_reason_existing = excluded_segments_with_reasons.get(actual_segment_index)
                    is_excluded_existing = exclusion_reason_existing is not None
                    
                    # Check if this is an image segment
                    is_image_existing = _is_image_segment(source_text) or _is_image_segment(target_text)
                    
                    if not is_excluded_existing and not is_image_existing:
                        # Not excluded and not image - update target_text with translation
                        existing_segment_dict["target_text"] = target_text
                        
                        # CRITICAL: Check if translation failed using should_treat_as_failure
                        # This ensures that segments with target_text == source_text are marked as failed
                        from utils.translation_validator import should_treat_as_failure
                        source_text_stripped = source_text.strip()
                        target_text_stripped = (target_text or '').strip()
                        
                        is_failed_existing, failure_reason_existing = should_treat_as_failure(
                            source_text_stripped, target_text_stripped
                        )
                        
                        existing_segment_dict["is_failed"] = is_failed_existing
                        existing_segment_dict["failure_reason"] = failure_reason_existing
                        existing_segment_dict["needs_retry"] = is_failed_existing
                        
                        # Log failed segments (only log first 5 for brevity)
                        if is_failed_existing and actual_segment_index < 5:
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} translation failed: "
                                f"reason={failure_reason_existing}"
                            )
                    else:
                        # Excluded or image - check if translation result exists before overwriting
                        # CRITICAL: For language_match and user_selected exclusions, if translation result exists and is different from source,
                        # preserve the translation result instead of overwriting with source_text.
                        # This handles cases where segment was translated before being marked as excluded.
                        # For user_selected exclusions, user may have excluded segments after translation, but we should still show the translation.
                        from exclusion.core import ExclusionReason
                        is_language_match = exclusion_reason_existing == ExclusionReason.LANGUAGE_MATCH
                        is_user_selected = exclusion_reason_existing == ExclusionReason.USER_SELECTED
                        
                        # Check if translation exists and differs from source for language_match or user_selected exclusions
                        if (is_language_match or is_user_selected) and target_text and target_text.strip():
                            # Check if translation result is different from source (actual translation exists)
                            source_text_stripped = source_text.strip()
                            target_text_stripped = (target_text or '').strip()
                            if target_text_stripped != source_text_stripped:
                                # Translation exists and is different - preserve it
                                existing_segment_dict["target_text"] = target_text
                                logger.info(LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} is {exclusion_reason_existing.value if exclusion_reason_existing else 'UNKNOWN'} excluded, "
                                    f"but translation exists and differs from source. Preserving translation: "
                                    f"source='{source_text_stripped[:50]}...', target='{target_text_stripped[:50]}...'"
                                )
                            else:
                                # Translation same as source - use source_text
                                existing_segment_dict["target_text"] = source_text
                                logger.debug(LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} is {exclusion_reason_existing.value if exclusion_reason_existing else 'UNKNOWN'} excluded, "
                                    f"and translation same as source. Using source_text: '{source_text_stripped[:50]}...'"
                                )
                        else:
                            # For other exclusions (e.g., IDENTIFIER, IMAGE, FORMULA, REFERENCE, STRUCTURAL), always use source_text
                            # These are content-based exclusions that should not be translated
                            existing_segment_dict["target_text"] = source_text
                        
                        existing_segment_dict["is_excluded"] = True
                        existing_segment_dict["exclusion_reason"] = exclusion_reason_existing.value if exclusion_reason_existing else None
                        existing_segment_dict["is_failed"] = False
                        existing_segment_dict["failure_reason"] = None
                        existing_segment_dict["needs_retry"] = False
                    
                    # Log update for debugging (only first 3 segments to reduce log verbosity)
                    if actual_segment_index < 3:
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Updated existing segment {actual_segment_index} "
                            f"from pre-fill stage (is_excluded={is_excluded_existing}, "
                            f"exclusion_reason={existing_segment_dict.get('exclusion_reason')})"
                        )
                    continue
            
            seen_segment_indices.add(actual_segment_index)
            
            # Use source and target texts directly
            segment_source_text = source_text
            segment_target_text = target_text
            
            # Log first few segments for debugging
            if segment_idx < 3:
                source_preview = segment_source_text[:100] if len(segment_source_text) > 100 else segment_source_text
                target_preview = segment_target_text[:100] if len(segment_target_text) > 100 else segment_target_text
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Segment idx={segment_idx}, actual_index={actual_segment_index}: "
                    f"source_text (first 100 chars)='{source_preview}...', "
                    f"target_text (first 100 chars)='{target_preview}...'"
                )
            # Also log a few segments in the middle and end to verify indices are correct
            elif segment_idx == len(source_chunks) // 2 or segment_idx == len(source_chunks) - 1:
                source_preview = segment_source_text[:50] if len(segment_source_text) > 50 else segment_source_text
                target_preview = segment_target_text[:50] if len(segment_target_text) > 50 else segment_target_text
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Segment idx={segment_idx}, actual_index={actual_segment_index}: "
                    f"source_text (first 50 chars)='{source_preview}...', "
                    f"target_text (first 50 chars)='{target_preview}...'"
                )
            
            # Check if this segment is excluded using unified ExclusionManager
            # excluded_segments_with_reasons already contains all excluded segments from task_state
            exclusion_reason = excluded_segments_with_reasons.get(actual_segment_index)
            is_excluded = exclusion_reason is not None
            exclusion_metadata = {}
            
            # CRITICAL: Translate phase does NOT detect new exclusions
            # If segment is not in excluded_segments_with_reasons, it should NOT be excluded
            # This ensures that exclusion data is managed only in Extract phase
            if not is_excluded:
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} (is_actually_segments path) is NOT excluded "
                    f"(not in excluded_segments_with_reasons, will be marked as not excluded)"
                )
            
            # If excluded, check if translation result exists before overwriting
            # CRITICAL: For language_match exclusions, if translation result exists and is different from source,
            # preserve the translation result instead of overwriting with source_text.
            # This handles cases where segment was translated before being marked as language_match excluded.
            if is_excluded:
                from exclusion.core import ExclusionReason
                is_language_match = exclusion_reason == ExclusionReason.LANGUAGE_MATCH
                
                if is_language_match and segment_target_text and segment_target_text.strip():
                    # Check if translation result is different from source (actual translation exists)
                    if segment_target_text.strip() != segment_source_text.strip():
                        # Translation exists and is different - preserve it
                        logger.info(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is LANGUAGE_MATCH excluded, "
                            f"but translation exists and differs from source. Preserving translation: "
                            f"source='{segment_source_text[:50]}...', target='{segment_target_text[:50]}...'"
                        )
                        # Keep segment_target_text as is (don't overwrite with source_text)
                    else:
                        # Translation same as source - use source_text
                        segment_target_text = segment_source_text
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is LANGUAGE_MATCH excluded, "
                            f"and translation same as source. Using source_text: '{segment_source_text[:50]}...'"
                        )
                else:
                    # For non-language_match exclusions (e.g., IDENTIFIER, IMAGE), always use source_text
                    segment_target_text = segment_source_text
                
                excluded_segment_indices.append(actual_segment_index)
            
            # Check if this is an image segment (should not be marked as failed)
            # CRITICAL: Check both source_text and target_text for image segments
            # This ensures images are detected even if they appear in different formats
            # segment_target_text should already be initialized at this point (from line 835 or 865)
            # But we add a safety check to avoid UnboundLocalError
            segment_target_text_for_check = segment_target_text if 'segment_target_text' in locals() else target_text
            is_image = _is_image_segment(segment_source_text) or _is_image_segment(segment_target_text_for_check)
            
            # CRITICAL: If this is an image segment, ensure it's marked as excluded
            # Image segments should always be excluded from translation
            if is_image and not is_excluded:
                is_excluded = True
                exclusion_reason = ExclusionReason.IMAGE
                exclusion_metadata = {}
                excluded_segments_with_reasons[actual_segment_index] = exclusion_reason
                excluded_segment_indices.append(actual_segment_index)
                # Use source_text as target_text for image segments
                segment_target_text = segment_source_text
                if actual_segment_index < 3:  # Log first few for debugging
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Segment {actual_segment_index} is image, "
                        f"marking as excluded and using source_text as target_text: '{segment_source_text[:50]}...'"
                    )
            
            # Check if translation failed using validation utility
            from utils.translation_validator import should_treat_as_failure
            
            source_text_stripped = segment_source_text.strip()
            target_text_stripped = (segment_target_text or '').strip()
            
            is_failed = False
            failure_reason = None
            
            # CRITICAL: Excluded segments and image segments should never be marked as failed
            # Check is_excluded FIRST before checking for translation failure
            # This ensures that segments marked as excluded in Extract phase (e.g., formulas)
            # are not incorrectly marked as failed during translation phase
            if not is_excluded and not is_image:
                # ARB metadata segments (e.g., @@locale, @settingsGeneralTitle descriptions)
                # should not be counted as failed translations, even if target == source.
                is_arb_metadata_segment = (
                    bool(arb_metadata_index_set)
                    and actual_segment_index in arb_metadata_index_set
                )
                if not is_arb_metadata_segment:
                    is_failed, failure_reason = should_treat_as_failure(
                        source_text_stripped, target_text_stripped
                    )
                    
                    # CRITICAL: For failed translations, use source_text as target_text (fill with original text)
                    # This ensures failed segments display the original text, not empty or incorrect translation
                    if is_failed:
                        segment_target_text = segment_source_text
                        # Log failed segments (only log first 5 for brevity)
                        if actual_segment_index < 5:
                            logger.debug(
                                LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} translation failed: "
                                f"reason={failure_reason}"
                            )
            
            # CRITICAL: Final safety check - if segment is excluded, clear is_failed flag
            # This prevents excluded segments (e.g., formulas from Extract phase) from being marked as failed
            # even if should_treat_as_failure was called before is_excluded was properly set
            if is_excluded or is_image:
                if is_failed:
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Segment {actual_segment_index} is excluded/image, "
                        f"clearing is_failed flag (was set to True, reason={failure_reason})"
                    )
                is_failed = False
                failure_reason = None
            
            # Create segment record
            # CRITICAL: If translation failed, automatically mark as needs_retry
            # This allows the "Translate Failed" feature to show these segments for retranslation
            needs_retry = is_failed and not is_excluded and not is_image
            
            # Debug: Log segment creation for first 3 segments or failed segments (for troubleshooting)
            if actual_segment_index < 3 or (is_failed and actual_segment_index < 10):
                logger.debug(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Creating segment {actual_segment_index}: "
                    f"is_failed={is_failed}, is_excluded={is_excluded}, is_image={is_image}"
                )
            
            segment_dict = {
                "segment_index": actual_segment_index,
                "source_text": segment_source_text,
                "target_text": segment_target_text,
                "modified": False,
                "separator_after": "",
                "is_excluded": is_excluded,
                "is_image": is_image,
                "is_failed": is_failed,
                "failure_reason": failure_reason,
                "needs_retry": needs_retry,
                "exclusion_reason": exclusion_reason.value if exclusion_reason else None,
                "exclusion_metadata": exclusion_metadata if exclusion_reason else None,
            }
            
            # CRITICAL: Set platform_used if platform_key is available
            # This allows frontend to display correct platform/model information
            if platform_key:
                segment_dict["platform_used"] = platform_key
                # Initialize used_platforms list if not already set
                if "used_platforms" not in segment_dict:
                    segment_dict["used_platforms"] = [platform_key] if platform_key else []
            
            # Log final state for excluded segments (for debugging)
            if is_excluded:
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} final state - "
                    f"is_excluded={is_excluded}, exclusion_reason={exclusion_reason.value if exclusion_reason else None}, "
                    f"is_image={is_image}, is_failed={is_failed}, "
                    f"needs_retry={needs_retry}, failure_reason={failure_reason}"
                )
            
            segments.append(segment_dict)
        
        # Batch log excluded segments (only if there are any)
        if excluded_segment_indices:
            if len(excluded_segment_indices) <= 10:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Excluded {len(excluded_segment_indices)} segments: {excluded_segment_indices}")
            else:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Excluded {len(excluded_segment_indices)} segments: {excluded_segment_indices[:10]}... (and {len(excluded_segment_indices) - 10} more)")
    else:
        # Original logic: process chunks and map to segments
        # If a chunk contains multiple segments, create one segment record per segment
        # Track excluded segments for batch logging
        excluded_segment_indices_chunks = []
        
        # Diagnostic: log map vs chunk lengths once to trace chunk-segment mapping errors
        map_len = len(chunk_to_segment_map_computed)
        src_len = len(source_chunks)
        tgt_len = len(target_chunks)
        seg_len = len(source_segments) if source_segments else 0
        logger.info(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Chunks path: chunk_to_segment_map_computed len={map_len}, "
            f"source_chunks len={src_len}, target_chunks len={tgt_len}, source_segments len={seg_len}"
        )
        if map_len != src_len:
            logger.warning(LogModule.TRANS,
                f"[RECORD_SEGMENTS] chunk_to_segment_map length ({map_len}) != source_chunks length ({src_len}). "
                f"This will cause wrong chunk-segment mapping. Expect map length to match source_chunks."
            )
        if map_len >= 7 and map_len <= 30:
            sample_indices = [chunk_to_segment_map_computed[i] for i in (0, 1, 6)]
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] chunk_to_segment_map_computed sample (chunk 0,1,6): {sample_indices}"
            )
        
        for chunk_idx, (source_text, target_text) in enumerate(zip(source_chunks, target_chunks)):
            # Get segment indices for this chunk
            chunk_segment_indices = chunk_to_segment_map_computed[chunk_idx] if chunk_idx < len(chunk_to_segment_map_computed) else [chunk_idx]
            
            # Validate segment indices against cached segments (out-of-range indicates wrong map)
            if source_segments and chunk_segment_indices:
                invalid = [s for s in chunk_segment_indices if s < 0 or s >= len(source_segments)]
                if invalid:
                    logger.warning(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Chunk {chunk_idx} has segment indices out of range [0, {len(source_segments)-1}]: "
                        f"invalid={invalid[:10]}{'...' if len(invalid) > 10 else ''}, "
                        f"chunk_segment_indices_sample={chunk_segment_indices[:5]}..."
                    )
            
            # If chunk contains multiple segments, create one segment record per segment
            # Each segment will use the chunk's target_text (since we can't reliably split it back)
            # But at least the segment_index will be correct, and source_text will be segment-specific
            if not chunk_segment_indices:
                # No segments mapped - skip this chunk or use chunk_idx as fallback
                logger.warning(LogModule.TRANS, f"[RECORD_SEGMENTS] Chunk {chunk_idx} has no mapped segments, using chunk_idx as fallback")
                chunk_segment_indices = [chunk_idx]
            
            # CRITICAL: For PDF workflow, check if this chunk is an image or excluded chunk at chunk level
            # This ensures correct handling of image/excluded chunks before segment-level processing
            is_chunk_image = _is_image_segment(source_text)
            is_chunk_excluded = False
            if excluded_set and chunk_segment_indices:
                # Check if any segment in this chunk is excluded
                # BUT: If chunk contains actual text (not just placeholder), it should not be treated as excluded
                # This handles image_caption chunks which have image block indices but contain actual text
                is_placeholder_only = _is_image_segment(source_text)
                if not is_placeholder_only:
                    # Chunk has actual text content - don't treat as excluded even if segment is in excluded_set
                    # This ensures image_caption chunks are translated
                    is_chunk_excluded = False
                else:
                    # Chunk is placeholder-only - check if segments are excluded
                    is_chunk_excluded = any(seg_idx in excluded_set for seg_idx in chunk_segment_indices)
            
            # CRITICAL: For image chunks and excluded chunks, ensure target_text matches source_text
            # This is especially important for PDF workflow where chunks and segments are one-to-one
            if is_chunk_image:
                target_text = source_text  # Use source placeholder as target
                if chunk_idx < 3:
                    logger.trace(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Chunk {chunk_idx} is image chunk, "
                        f"ensuring target_text matches source_text: '{source_text[:50]}...'"
                    )
            elif is_chunk_excluded:
                # For excluded chunks, ensure target_text matches source_text
                target_text = source_text
                if chunk_idx < 3:
                    logger.trace(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Chunk {chunk_idx} is excluded chunk, "
                        f"ensuring target_text matches source_text: '{source_text[:50]}...'"
                    )
            
            # Get source segment texts for this chunk (if available)
            chunk_source_segments = []
            if source_segments and chunk_segment_indices:
                chunk_source_segments = [
                    str(source_segments[seg_idx]) if seg_idx < len(source_segments) else ""
                    for seg_idx in chunk_segment_indices
                ]
            
            # CRITICAL: For image chunks and excluded chunks, ensure we use the chunk's source_text directly
            # Don't try to get from source_segments which may not include images or may have incorrect text
            # CRITICAL: For excluded chunks, if chunk maps to multiple segments, we need to get each segment's source_text
            # from source_segments, not use the chunk's source_text for all segments
            if is_chunk_image:
                # Image chunk: use chunk's source_text directly (it's the placeholder)
                # Image chunks typically map to a single segment, so this is safe
                chunk_source_segments = [source_text]  # Override with chunk's source_text
            elif is_chunk_excluded:
                # Excluded chunk: get individual segment source texts from source_segments
                # This ensures each excluded segment uses its own source_text, not the chunk's combined text
                # CRITICAL: For PDF workflow, source_segments should always be available from Extract phase
                if not source_segments:
                    logger.error(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Excluded chunk {chunk_idx}: source_segments not available! "
                        f"This should not happen for PDF workflow. Using chunk source_text as fallback."
                    )
                    chunk_source_segments = [source_text] * len(chunk_segment_indices) if chunk_segment_indices else [source_text]
                elif not chunk_segment_indices:
                    logger.error(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Excluded chunk {chunk_idx}: chunk_segment_indices is empty! "
                        f"Using chunk source_text as fallback."
                    )
                    chunk_source_segments = [source_text]
                else:
                    # Get source text for each segment in this chunk
                    chunk_source_segments = []
                    for seg_idx in chunk_segment_indices:
                        if seg_idx < len(source_segments):
                            seg_text = str(source_segments[seg_idx])
                            chunk_source_segments.append(seg_text)
                        else:
                            # Index out of bounds - this should not happen if source_chunks_cache is correct
                            logger.error(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Excluded chunk {chunk_idx}, segment {seg_idx}: "
                                f"index {seg_idx} >= source_segments length {len(source_segments)}. "
                                f"This indicates source_chunks_cache is incorrect. Using chunk source_text."
                            )
                            chunk_source_segments.append(source_text)
            
            # CRITICAL: For multi-segment chunks, try to parse indexed format from target_text first
            # This ensures each segment gets its own translation (markdown_based / image workflows),
            # not the entire chunk filled into every segment. PDF workflow unchanged (often 1 segment per chunk).
            indexed_segments_map = {}
            normalized_target = (target_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
            if len(chunk_segment_indices) > 1:
                text_to_parse = target_text or ""
                raw = text_to_parse.strip()
                # Prefer direct mapping when LLM returns [{"index": i, "text": "..."}, ...] (per-segment JSON)
                if raw.startswith("[") and '"text"' in raw:
                    try:
                        data = json.loads(raw)
                        if isinstance(data, list) and data:
                            # If every item has "index" and "text", build indexed_segments_map directly
                            if all(isinstance(item, dict) and "index" in item and "text" in item for item in data):
                                for item in data:
                                    idx = int(item["index"])
                                    indexed_segments_map[idx] = str(item.get("text", "")).strip()
                                logger.debug(
                                    LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Chunk {chunk_idx}: Built indexed map from JSON array "
                                    f"(count={len(indexed_segments_map)}, indices={sorted(indexed_segments_map.keys())[:10]}...).",
                                )
                            else:
                                # Single element or missing index: unwrap "text" and parse as "0: ...\n1: ..."
                                parts = []
                                for item in data:
                                    if isinstance(item, dict) and "text" in item:
                                        parts.append(str(item["text"]).strip())
                                if parts:
                                    text_to_parse = "\n\n".join(parts)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.debug(
                            LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx}: JSON parse failed ({e!s}); "
                            "will try to extract \"text\" field and then indexed line parse.",
                        )
                        # When LLM returns malformed JSON like [{"index":0,"text":"0: ...\n1: ..."}],
                        # extract the first "text" value so line-based "N: " parsing can run on it.
                        text_extracted = None
                        if '"text"' in raw or "'text'" in raw:
                            # Match "text"\s*:\s*" then capture string value (handle \", \\, \n inside)
                            for pat in (r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', r"'text'\s*:\s*'((?:[^'\\]|\\.)*)'"):
                                m = re.search(pat, raw)
                                if m:
                                    try:
                                        text_extracted = codecs.decode(m.group(1), "unicode_escape")
                                    except Exception:
                                        text_extracted = m.group(1).replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
                                    break
                            # Fallback for unterminated string: capture from "text":" to end of raw
                            if text_extracted is None and '"text"' in raw:
                                m = re.search(r'"text"\s*:\s*"(.*)', raw)
                                if m:
                                    s = m.group(1)
                                    try:
                                        text_extracted = codecs.decode(s, "unicode_escape")
                                    except Exception:
                                        text_extracted = s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
                        if text_extracted is not None and text_extracted.strip():
                            text_to_parse = text_extracted.strip()
                            logger.debug(
                                LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Chunk {chunk_idx}: Extracted \"text\" from malformed JSON, length={len(text_to_parse)}; will run indexed line parse.",
                            )
                        else:
                            text_to_parse = raw
                # Only run line-based "0: ...\n1: ..." parsing when we did not already build map from JSON array
                if not indexed_segments_map:
                    # Normalize: line endings and strip so line-by-line and fallback parse are reliable
                    normalized_target = text_to_parse.replace("\r\n", "\n").replace("\r", "\n").strip()
                    # Support both ASCII colon and fullwidth colon (e.g. from some models)
                    index_line_pattern = re.compile(r"^\s*(\d+)\s*[:：]\s*(.*)$")
                    has_indexed_segments = bool(re.search(r"^\s*\d+\s*[:：]\s", normalized_target, re.MULTILINE))
                    if has_indexed_segments:
                        lines = normalized_target.split("\n")
                        current_seg_idx = None
                        current_text_lines = []
                        first_line_handled = False

                        for line_idx, line in enumerate(lines):
                            line_clean = line.rstrip("\r")
                            match = index_line_pattern.match(line_clean)
                            if match:
                                # Save previous segment if exists
                                if current_seg_idx is not None:
                                    indexed_segments_map[current_seg_idx] = "\n".join(current_text_lines).strip()
                                # Start new segment
                                current_seg_idx = int(match.group(1))
                                text_part = (match.group(2) or "").strip()
                                current_text_lines = [text_part] if text_part else []
                                first_line_handled = True
                            else:
                                # Continuation of current segment's text
                                if current_seg_idx is not None:
                                    current_text_lines.append(line_clean)
                                elif not first_line_handled and line_idx == 0 and chunk_segment_indices:
                                    first_seg_idx = chunk_segment_indices[0]
                                    current_seg_idx = first_seg_idx
                                    current_text_lines.append(line_clean)
                                    first_line_handled = True

                        if current_seg_idx is not None:
                            indexed_segments_map[current_seg_idx] = "\n".join(current_text_lines).strip()
                    else:
                        # Single segment or no "N: " prefix: treat entire normalized_target as first segment
                        if chunk_segment_indices:
                            indexed_segments_map[chunk_segment_indices[0]] = normalized_target

                # Fallback: split by double newline and parse each block (handles "0: ...\n\n1: ..." reliably)
                expected_indices = set(chunk_segment_indices)
                if expected_indices and (not indexed_segments_map or expected_indices - set(indexed_segments_map.keys())):
                    parts = re.split(r"\n\s*\n", normalized_target)
                    for part in parts:
                        part = part.strip()
                        if not part:
                            continue
                        block_match = re.match(r"^\s*(\d+)\s*[:：]\s*(.*)", part, re.DOTALL)
                        if block_match:
                            seg_idx = int(block_match.group(1))
                            seg_text = (block_match.group(2) or "").strip()
                            if seg_idx in expected_indices and (seg_idx not in indexed_segments_map or not indexed_segments_map[seg_idx].strip()):
                                indexed_segments_map[seg_idx] = seg_text

                if indexed_segments_map:
                    logger.debug(
                        LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Parsed {len(indexed_segments_map)} indexed segments from chunk {chunk_idx}. "
                        f"Segment indices found: {sorted(list(indexed_segments_map.keys()))[:10]}...",
                    )
            
            # Create segment records for each segment in this chunk
            for seg_idx_in_chunk, actual_segment_index in enumerate(chunk_segment_indices):
                # CRITICAL: Get segment-specific target_text
                # 优先使用按 index 解析出的子段；只有在完全没有 indexed map 且单段 chunk 时，才可以用整块译文
                segment_target_text = target_text
                if indexed_segments_map:
                    if actual_segment_index in indexed_segments_map:
                        segment_target_text = indexed_segments_map[actual_segment_index]
                        if actual_segment_index < 3:
                            logger.debug(
                                LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Chunk {chunk_idx}, segment {actual_segment_index}: "
                                f"Using parsed indexed segment text (length: {len(segment_target_text)}).",
                            )
                    else:
                        # 有 indexed map 但当前 segment 没有对应译文时，绝不能把整块译文塞给它
                        # 使用源文，后续 failure 检测会把它标记为“翻译失败”或“未翻译”
                        if seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                            segment_target_text = str(chunk_source_segments[seg_idx_in_chunk])
                        else:
                            segment_target_text = ""
                        logger.warning(
                            LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx}: Indexed map missing segment {actual_segment_index}, "
                            f"using source_text instead of full chunk to avoid misalignment.",
                        )
                elif len(chunk_segment_indices) > 1:
                    # Multi-segment chunk but没有解析出任何 index：不要用整块译文覆盖所有 segments
                    if seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                        segment_target_text = str(chunk_source_segments[seg_idx_in_chunk])
                    else:
                        segment_target_text = ""
                    if actual_segment_index == 0:
                        logger.warning(
                            LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx} maps to {len(chunk_segment_indices)} segments "
                            f"but indexed format parsing failed. Using source_text for segments; "
                            f"failure detection will mark as failed.",
                        )
                        logger.debug(
                            LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Chunk {chunk_idx} target_text sample (first 400 chars): "
                            f"{repr((target_text or '')[:400])}",
                        )

                # CRITICAL: Check if segment already exists from pre-fill stage
                # If it exists, update it instead of creating a new one (preserves exclusion_reason)
                existing_segment_dict = None
                if actual_segment_index in seen_segment_indices:
                    # Find existing segment in segments list
                    for seg in segments:
                        if isinstance(seg, dict) and seg.get("segment_index") == actual_segment_index:
                            existing_segment_dict = seg
                            break
                    
                    if existing_segment_dict:
                        # Update existing segment with translated text, but preserve exclusion_reason
                        # CRITICAL: Only update target_text if segment is not excluded
                        exclusion_reason_existing = excluded_segments_with_reasons.get(actual_segment_index)
                        is_excluded_existing = exclusion_reason_existing is not None
                        
                        # Check if this is an image segment
                        is_image_existing = _is_image_segment(source_text) or _is_image_segment(segment_target_text)
                        
                        if not is_excluded_existing and not is_image_existing:
                            # Not excluded and not image - update target_text with translation
                            # Get segment-specific source_text for failure detection
                            segment_source_text_for_check = existing_segment_dict.get("source_text", source_text)
                            if seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                                segment_source_text_for_check = chunk_source_segments[seg_idx_in_chunk]
                            
                            existing_segment_dict["target_text"] = segment_target_text
                            
                            # CRITICAL: Check if translation failed using should_treat_as_failure
                            # This ensures that segments with target_text == source_text are marked as failed
                            # IMPORTANT: Use segment_target_text here, not whole-chunk target_text,
                            # to avoid treating partially-translated chunks as successful for segments
                            # that actually没有单独译文（例如 PDF 合并 chunk 的场景）。
                            from utils.translation_validator import should_treat_as_failure
                            source_text_stripped = segment_source_text_for_check.strip()
                            target_text_stripped = (segment_target_text or "").strip()
                            
                            # Log when source and target are the same (potential failure case)
                            if source_text_stripped == target_text_stripped and source_text_stripped:
                                logger.debug(LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} (chunks path) has same source and target text. "
                                    f"Checking if should be marked as failed. "
                                    f"Source preview: '{source_text_stripped[:100]}...', "
                                    f"Target preview: '{target_text_stripped[:100]}...'"
                                )
                            
                            is_failed_existing, failure_reason_existing = should_treat_as_failure(
                                source_text_stripped, target_text_stripped
                            )
                            
                            # Log the result of failure detection for debugging
                            if source_text_stripped == target_text_stripped and source_text_stripped:
                                logger.info(LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} (chunks path) failure detection result: "
                                    f"is_failed={is_failed_existing}, reason={failure_reason_existing}, "
                                    f"source_length={len(source_text_stripped)}, "
                                    f"source_preview='{source_text_stripped[:100]}...'"
                                )
                            
                            existing_segment_dict["is_failed"] = is_failed_existing
                            existing_segment_dict["failure_reason"] = failure_reason_existing
                            existing_segment_dict["needs_retry"] = is_failed_existing
                            
                            # CRITICAL: For failed translations, use source_text as target_text (fill with original text)
                            # This ensures failed segments display the original text, not empty or incorrect translation
                            if is_failed_existing:
                                existing_segment_dict["target_text"] = segment_source_text_for_check
                                logger.info(LogModule.TRANS,
                                    f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} (chunks path) translation failed, "
                                    f"reason={failure_reason_existing}, using source_text as target_text: '{segment_source_text_for_check[:50]}...'"
                                )
                        else:
                            # Excluded or image - check if translation result exists before overwriting
                            # CRITICAL: For language_match and user_selected exclusions, if translation result exists and is different from source,
                            # preserve the translation result instead of overwriting with source_text.
                            # This handles cases where segment was translated before being marked as excluded.
                            # For user_selected exclusions, user may have excluded segments after translation, but we should still show the translation.
                            from exclusion.core import ExclusionReason
                            is_language_match = exclusion_reason_existing == ExclusionReason.LANGUAGE_MATCH
                            is_user_selected = exclusion_reason_existing == ExclusionReason.USER_SELECTED
                            
                            # Get segment-specific source_text for comparison
                            segment_source_text_for_check = existing_segment_dict.get("source_text", source_text)
                            if seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                                segment_source_text_for_check = chunk_source_segments[seg_idx_in_chunk]
                            
                            # Check if translation exists and differs from source for language_match or user_selected exclusions
                            if (is_language_match or is_user_selected) and segment_target_text and segment_target_text.strip():
                                # Check if translation result is different from source (actual translation exists)
                                source_text_stripped = segment_source_text_for_check.strip()
                                target_text_stripped = (segment_target_text or '').strip()
                                if target_text_stripped != source_text_stripped:
                                    # Translation exists and is different - preserve it
                                    existing_segment_dict["target_text"] = segment_target_text
                                    logger.info(LogModule.TRANS,
                                        f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} (chunks path) is {exclusion_reason_existing.value if exclusion_reason_existing else 'UNKNOWN'} excluded, "
                                        f"but translation exists and differs from source. Preserving translation: "
                                        f"source='{source_text_stripped[:50]}...', target='{target_text_stripped[:50]}...'"
                                    )
                                else:
                                    # Translation same as source - use source_text
                                    existing_segment_dict["target_text"] = segment_source_text_for_check
                                    logger.debug(LogModule.TRANS,
                                        f"[RECORD_SEGMENTS] Task {task_id}: Existing segment {actual_segment_index} (chunks path) is {exclusion_reason_existing.value if exclusion_reason_existing else 'UNKNOWN'} excluded, "
                                        f"and translation same as source. Using source_text: '{source_text_stripped[:50]}...'"
                                    )
                            else:
                                # For other exclusions (e.g., IDENTIFIER, IMAGE, FORMULA, REFERENCE, STRUCTURAL), always use source_text
                                # These are content-based exclusions that should not be translated
                                existing_segment_dict["target_text"] = segment_source_text_for_check
                            
                            existing_segment_dict["is_excluded"] = True
                            existing_segment_dict["exclusion_reason"] = exclusion_reason_existing.value if exclusion_reason_existing else None
                            existing_segment_dict["is_failed"] = False
                            existing_segment_dict["failure_reason"] = None
                            existing_segment_dict["needs_retry"] = False
                        
                        # Log update for debugging (log all excluded segments, not just first 3)
                        if actual_segment_index < 3 or is_excluded_existing:
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Updated existing segment {actual_segment_index} "
                                f"from pre-fill stage (chunks path, is_excluded={is_excluded_existing}, "
                                f"exclusion_reason={existing_segment_dict.get('exclusion_reason')})"
                            )
                        continue
                
                seen_segment_indices.add(actual_segment_index)
                
                # Get source text for this specific segment (if available)
                # CRITICAL: For image chunks, always use chunk's source_text (it's the placeholder)
                # For excluded chunks, use the segment-specific source_text from chunk_source_segments
                # This ensures each excluded segment uses its own source_text, not the chunk's combined text
                if is_chunk_image:
                    segment_source_text = source_text  # Use chunk's source_text directly for images
                elif is_chunk_excluded:
                    # Excluded chunk: use segment-specific source_text from chunk_source_segments
                    if seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                        segment_source_text = chunk_source_segments[seg_idx_in_chunk]
                    else:
                        # This should not happen if chunk_source_segments was built correctly
                        logger.error(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Excluded segment {actual_segment_index}: "
                            f"seg_idx_in_chunk={seg_idx_in_chunk} >= chunk_source_segments length {len(chunk_source_segments)}. "
                            f"Using chunk source_text as fallback."
                        )
                        segment_source_text = source_text
                elif seg_idx_in_chunk < len(chunk_source_segments) and chunk_source_segments[seg_idx_in_chunk]:
                    segment_source_text = chunk_source_segments[seg_idx_in_chunk]
                else:
                    # Fallback: use chunk source text
                    segment_source_text = source_text
                
                # CRITICAL: Check if this segment is excluded using unified ExclusionManager
                # excluded_segments_with_reasons already contains all excluded segments from task_state
                exclusion_reason = excluded_segments_with_reasons.get(actual_segment_index)
                is_excluded = exclusion_reason is not None
                exclusion_metadata = {}
                
                # CRITICAL: Preserve user_selected exclusions - do NOT re-detect or override them
                is_user_selected = exclusion_reason == ExclusionReason.USER_SELECTED
                
                # CRITICAL: Log excluded segments for debugging (especially segment 0)
                if actual_segment_index == 0:
                    logger.info(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Processing segment 0 - "
                        f"is_excluded={is_excluded}, exclusion_reason={exclusion_reason.value if exclusion_reason else None}, "
                        f"is_user_selected={is_user_selected}, "
                        f"excluded_segments_with_reasons contains 0: {0 in excluded_segments_with_reasons}, "
                        f"total excluded_segments_with_reasons: {len(excluded_segments_with_reasons)}"
                    )
                
                # CRITICAL: Translate phase is READ-ONLY for exclusion data
                # Do NOT refine UNKNOWN exclusion reasons here
                # All exclusion detection and refinement should happen in Extract phase
                # If exclusion_reason is UNKNOWN, it means Extract phase did not properly set it
                # We should log a warning but NOT try to fix it in Translate phase
                if is_excluded and exclusion_reason == ExclusionReason.UNKNOWN:
                    logger.warning(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} has UNKNOWN exclusion_reason. "
                        f"This indicates that Extract phase did not properly set the exclusion reason. "
                        f"Translate phase will use UNKNOWN as-is (will not refine). "
                        f"Exclusion data should be fixed in Extract phase."
                    )
                
                if is_excluded:
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is excluded "
                        f"(reason: {exclusion_reason.value})"
                    )
                    # CRITICAL: Translate phase is READ-ONLY for exclusion data
                    # Do NOT re-detect or modify exclusion reasons here
                    # All exclusion detection should happen in Extract phase
                else:
                    # CRITICAL: Translate phase does NOT detect new exclusions
                    # If a segment is not in excluded_segments_with_reasons, it should NOT be excluded
                    # This ensures that exclusion data is managed only in Extract phase
                    # If data is missing, log a warning but do NOT auto-fix
                    if actual_segment_index < 3:  # Log first few for debugging
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is NOT excluded "
                            f"(not in excluded_segments_with_reasons, will be translated)"
                    )
                
                # CRITICAL: Check if this is an image segment (before setting target_text)
                # Initialize segment_target_text first (will be set properly later)
                # For image detection, we primarily check segment_source_text
                # segment_target_text may not be initialized yet, so we check it only if available
                segment_target_text_for_check = target_text if target_text else ""
                is_image = _is_image_segment(segment_source_text) or _is_image_segment(segment_target_text_for_check)
                
                # CRITICAL: Check if this is a formula segment (before setting target_text)
                # Formula segments should also be marked as excluded (they were excluded in Extract phase)
                is_formula = _is_formula_segment(segment_source_text)
                
                # CRITICAL: Image segments should always be marked as excluded
                # According to design doc: Translate phase is READ-ONLY for exclusion data
                # These checks should only log warnings, not modify exclusion data
                if is_image and not is_excluded:
                    logger.warning(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is image but not excluded. "
                        f"This indicates Extract phase failed to mark image as excluded. "
                        f"Image segments should be excluded during Extract phase, not Translate phase."
                    )
                    # DO NOT modify excluded_segments_with_reasons or excluded_segment_indices_chunks
                
                # CRITICAL: Formula segments should always be marked as excluded
                # According to design doc: Translate phase is READ-ONLY for exclusion data
                # These checks should only log warnings, not modify exclusion data
                if is_formula and not is_excluded:
                    logger.warning(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is formula but not excluded. "
                        f"This indicates Extract phase failed to mark formula as excluded. "
                        f"Formula segments should be excluded during Extract phase, not Translate phase."
                    )
                    # DO NOT modify excluded_segments_with_reasons or excluded_segment_indices_chunks
                
                # CRITICAL: Use segment_target_text from indexed_segments_map if available
                # This was already parsed outside the loop for efficiency
                # If not available, try to parse from target_text (fallback for single-segment chunks or parsing failure)
                if indexed_segments_map and actual_segment_index in indexed_segments_map:
                    # Already parsed - use it
                    segment_target_text = indexed_segments_map[actual_segment_index]
                else:
                    # Not parsed yet - try to parse now (fallback)
                    segment_target_text = None
                    
                    # CRITICAL: Check if target_text contains indexed segments (format: "0: text1\n1: text2\n2: text3")
                    # This happens when split_merged_chunks returns chunks that still contain multiple indexed segments
                    # We can split them into individual segments for accurate mapping (re is module-level import)
                    has_indexed_segments_in_target = bool(re.search(r'^\d+:\s', target_text, re.MULTILINE))
                    if has_indexed_segments_in_target and len(chunk_segment_indices) > 1:
                        if actual_segment_index < 3:  # Log first few for debugging
                            logger.info(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Chunk {chunk_idx} contains indexed segments in target_text. "
                                f"Chunk maps to {len(chunk_segment_indices)} segments: {chunk_segment_indices[:10]}..."
                                f"{'...' if len(chunk_segment_indices) > 10 else ''}. "
                                f"Target text preview: {target_text[:200]}..."
                            )
                        # Parse indexed segments from target_text
                        indexed_segments = {}
                        lines = target_text.split('\n')
                        current_seg_idx = None
                        current_text_lines = []
                        first_line_handled = False
                        
                        for line_idx, line in enumerate(lines):
                            match = re.match(r'^\s*(\d+):\s*(.*)$', line)
                            if match:
                                # Save previous segment if exists
                                if current_seg_idx is not None:
                                    indexed_segments[current_seg_idx] = '\n'.join(current_text_lines)
                                
                                # Start new segment
                                current_seg_idx = int(match.group(1))
                                text_part = match.group(2)
                                current_text_lines = [text_part] if text_part else []
                                first_line_handled = True
                            else:
                                # Continuation of current segment's text
                                if current_seg_idx is not None:
                                    current_text_lines.append(line)
                                # CRITICAL: If no current segment and this is the first line,
                                # this is the first segment without index prefix
                                # Infer the segment index from chunk_segment_indices
                                elif not first_line_handled and line_idx == 0:
                                    # First segment doesn't have index prefix - infer from chunk_segment_indices
                                    if chunk_segment_indices:
                                        first_seg_idx = chunk_segment_indices[0]
                                        current_seg_idx = first_seg_idx
                                        current_text_lines.append(line)
                                        first_line_handled = True
                                        logger.debug(LogModule.TRANS,
                                            f"[RECORD_SEGMENTS] Chunk {chunk_idx}: First segment doesn't have index prefix. "
                                            f"Inferred index {first_seg_idx} from chunk_segment_indices. "
                                            f"First line: {line[:100]}..."
                                        )
                                    else:
                                        # No chunk_segment_indices - log warning
                                        if actual_segment_index == 0:
                                            logger.warning(LogModule.TRANS,
                                                f"[RECORD_SEGMENTS] Chunk {chunk_idx}: target_text doesn't start with index pattern "
                                                f"and chunk_segment_indices is empty. First line: {line[:100]}... "
                                                f"This may indicate a parsing issue."
                                            )
                        
                        # Don't forget the last segment
                        if current_seg_idx is not None:
                            indexed_segments[current_seg_idx] = '\n'.join(current_text_lines)
                        
                        # Log parsed segments for debugging
                        if actual_segment_index < 3:
                            logger.info(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Parsed {len(indexed_segments)} indexed segments from chunk {chunk_idx}. "
                                f"Segment indices found: {sorted(list(indexed_segments.keys()))[:20]}... "
                                f"Looking for segment {actual_segment_index}."
                            )
                        
                        # Get the specific segment's target_text
                        if actual_segment_index in indexed_segments:
                            segment_target_text = indexed_segments[actual_segment_index]
                            logger.info(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Segment {actual_segment_index}: Extracted individual segment text "
                                f"from indexed format (length: {len(segment_target_text)}). "
                                f"Found {len(indexed_segments)} indexed segments in chunk {chunk_idx}. "
                                f"Segment text preview: {segment_target_text[:100]}..."
                            )
                        else:
                            # Segment index not found in indexed segments - this is an error, not a fallback
                            # CRITICAL: Do NOT use chunk's target_text as fallback for individual segments
                            # This would cause all segments in the chunk to share the same target_text, which is incorrect
                            # Instead, log an error and leave segment_target_text as None (will be handled later)
                            logger.error(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Segment {actual_segment_index} not found in indexed segments. "
                                f"Chunk {chunk_idx} maps to segments {chunk_segment_indices}. "
                                f"Available indexed segment indices: {sorted(list(indexed_segments.keys()))[:20]}... "
                                f"This indicates a parsing error. Segment will be marked as failed."
                            )
                            segment_target_text = None  # Leave as None to mark as failed
                
                # CRITICAL: If segment_target_text is still None, it means:
                # 1. Chunk contains only one segment (no need to parse indexed format), OR
                # 2. Indexed format parsing failed or segment not found
                # For single-segment chunks, use chunk's target_text directly
                # For multi-segment chunks with parsing failure, leave as None (will be marked as failed)
                if segment_target_text is None:
                    if len(chunk_segment_indices) == 1:
                        # Single segment chunk - use chunk's target_text directly
                        segment_target_text = target_text
                        if actual_segment_index < 3:
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Single-segment chunk {chunk_idx}: "
                                f"Using chunk's target_text directly for segment {actual_segment_index}."
                            )
                    else:
                        # Multi-segment chunk but parsing failed - mark as failed
                        logger.error(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Multi-segment chunk {chunk_idx} (maps to {len(chunk_segment_indices)} segments) "
                            f"but segment {actual_segment_index} has no target_text. "
                            f"This indicates a parsing error. Segment will be marked as failed."
                        )
                        segment_target_text = None  # Will be handled as failed translation
                
                if is_excluded:
                    # CRITICAL: For language_match and user_selected exclusions, if translation result exists and is different from source,
                    # preserve the translation result instead of overwriting with source_text.
                    # This handles cases where segment was translated before being marked as excluded.
                    # For user_selected exclusions, user may have excluded segments after translation, but we should still show the translation.
                    from exclusion.core import ExclusionReason
                    is_language_match = exclusion_reason == ExclusionReason.LANGUAGE_MATCH
                    is_user_selected = exclusion_reason == ExclusionReason.USER_SELECTED
                    
                    # Check if translation exists and differs from source for language_match or user_selected exclusions
                    if (is_language_match or is_user_selected) and segment_target_text and segment_target_text.strip():
                        # Check if translation result is different from source (actual translation exists)
                        if segment_target_text.strip() != segment_source_text.strip():
                            # Translation exists and is different - preserve it
                            logger.info(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is {exclusion_reason.value if exclusion_reason else 'UNKNOWN'} excluded, "
                                f"but translation exists and differs from source. Preserving translation: "
                                f"source='{segment_source_text[:50]}...', target='{segment_target_text[:50]}...'"
                            )
                            # Keep segment_target_text as is (don't overwrite with source_text)
                        else:
                            # Translation same as source - use source_text
                            segment_target_text = segment_source_text
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is {exclusion_reason.value if exclusion_reason else 'UNKNOWN'} excluded, "
                                f"and translation same as source. Using source_text: '{segment_source_text[:50]}...'"
                            )
                    else:
                        # For other exclusions (e.g., IDENTIFIER, IMAGE, FORMULA, REFERENCE, STRUCTURAL), always use source_text
                        # These are content-based exclusions that should not be translated
                        segment_target_text = segment_source_text
                    
                    if actual_segment_index not in excluded_segment_indices_chunks:
                        excluded_segment_indices_chunks.append(actual_segment_index)
                    # Log excluded segments for debugging (especially segment 0)
                    if actual_segment_index == 0:
                        logger.info(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment 0 is EXCLUDED, "
                            f"exclusion_reason={exclusion_reason.value if exclusion_reason else None}, "
                            f"target_text='{segment_target_text[:50]}...' (preserved translation if language_match and translated)"
                        )
                    elif actual_segment_index < 3:
                        logger.trace(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Segment {actual_segment_index} is excluded, "
                            f"exclusion_reason={exclusion_reason.value if exclusion_reason else None}, "
                            f"target_text='{segment_target_text[:50]}...'"
                        )
                elif is_image:
                    # Image segments: always use source_text as target_text (keep placeholder)
                    segment_target_text = segment_source_text
                    # Only log first few image segments for debugging
                    if actual_segment_index < 3:
                        logger.trace(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Segment {actual_segment_index} is image, "
                            f"using source_text as target_text: '{segment_source_text[:50]}...'"
                        )
                else:
                    # segment_target_text was already set above (either from indexed format or from target_text)
                    # CRITICAL: If segment_target_text is still None, it means parsing failed for multi-segment chunk
                    # In this case, mark it as failed (empty string) instead of using chunk's target_text
                    if segment_target_text is None:
                        segment_target_text = ""  # Mark as failed
                        logger.error(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Segment {actual_segment_index} has None target_text after parsing. "
                            f"Chunk {chunk_idx} maps to {len(chunk_segment_indices)} segments. "
                            f"This indicates a parsing error. Segment will be marked as failed."
                        )
                    # Only override for XLSX workflow special case
                    # CRITICAL: For XLSX workflow, if we're using chunk logic but target_chunks are actually segments,
                    # we need to get the correct segment target_text from target_chunks
                    # This is a workaround for when is_actually_segments was not correctly detected
                    elif is_xlsx_workflow and actual_segment_index < len(target_chunks):
                        # Use segment-specific target_text from target_chunks (which are actually segments)
                        segment_target_text = target_chunks[actual_segment_index]
                        if actual_segment_index < 3:  # Log first few for debugging
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] XLSX workflow: Using segment-specific target_text for segment {actual_segment_index} "
                                f"from target_chunks (first 50 chars): '{segment_target_text[:50] if segment_target_text else ''}...'"
                            )
                    # CRITICAL: Do NOT use source_text as fallback for empty target_text.
                    # Keep empty string to allow should_treat_as_failure to detect and mark as failed.
                    # User can retranslate failed segments via "Translate Failed" feature.
                    if not segment_target_text or not segment_target_text.strip():
                        segment_target_text = ""  # Keep empty, will be marked as failed
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Segment {actual_segment_index} has empty target_text. "
                            f"Keeping empty (will be marked as failed). User can retranslate via 'Translate Failed'."
                        )
                
                # Check if translation failed using validation utility
                from utils.translation_validator import should_treat_as_failure
                
                source_text_stripped = segment_source_text.strip()
                target_text_stripped = (segment_target_text or '').strip()
                
                is_failed = False
                failure_reason = None
                
                # CRITICAL: Excluded segments and image segments should never be marked as failed
                # Check is_excluded FIRST before checking for translation failure
                # This ensures that segments marked as excluded in Extract phase (e.g., formulas)
                # are not incorrectly marked as failed during translation phase
                if not is_excluded and not is_image:
                    # Log when source and target are the same (potential failure case)
                    if source_text_stripped == target_text_stripped and source_text_stripped:
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} has same source and target text. "
                            f"Checking if should be marked as failed. "
                            f"Source preview: '{source_text_stripped[:100]}...', "
                            f"Target preview: '{target_text_stripped[:100]}...'"
                        )
                    
                    is_failed, failure_reason = should_treat_as_failure(
                        source_text_stripped, target_text_stripped
                    )
                    
                    # Log the result of failure detection for debugging
                    if source_text_stripped == target_text_stripped and source_text_stripped:
                        logger.info(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} failure detection result: "
                            f"is_failed={is_failed}, reason={failure_reason}, "
                            f"source_length={len(source_text_stripped)}, "
                            f"source_preview='{source_text_stripped[:100]}...'"
                        )
                    
                    # CRITICAL: For failed translations, only use source_text as target_text if:
                    # 1. target_text is empty, OR
                    # 2. target_text is same as source_text
                    # If target_text exists and differs from source_text, preserve it even if marked as failed.
                    # This handles cases where API returned correct translation but was incorrectly marked as failed
                    # (e.g., due to validation logic issues or timing issues with exclusion detection).
                    if is_failed:
                        if not segment_target_text or segment_target_text.strip() == segment_source_text.strip():
                            # No translation or same as source - use source_text
                            segment_target_text = segment_source_text
                            logger.info(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} translation failed, "
                                f"reason={failure_reason}, target_text empty or same as source. "
                                f"Using source_text as target_text: '{segment_source_text[:50]}...'"
                            )
                        else:
                            # Translation exists and differs from source - preserve it even if marked as failed
                            # This ensures correct translations are not lost due to incorrect failure detection
                            logger.warning(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} marked as FAILED "
                                f"(reason={failure_reason}), but target_text differs from source_text. "
                                f"Preserving translation: source='{segment_source_text[:50]}...', "
                                f"target='{segment_target_text[:50]}...'. "
                                f"This may indicate incorrect failure detection."
                            )
                            # Keep segment_target_text as is (don't overwrite with source_text)
                
                # CRITICAL: Final safety check - if segment is excluded, clear is_failed flag
                # This prevents excluded segments (e.g., formulas from Extract phase) from being marked as failed
                # even if should_treat_as_failure was called before is_excluded was properly set
                if is_excluded or is_image:
                    if is_failed:
                        logger.info(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} is excluded/image, "
                            f"clearing is_failed flag (was set to True, reason={failure_reason}). "
                            f"is_excluded={is_excluded}, is_image={is_image}"
                        )
                    is_failed = False
                    failure_reason = None
                elif is_failed:
                    # Log when segment is marked as failed (for debugging)
                    logger.info(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Segment {actual_segment_index} marked as failed. "
                        f"is_excluded={is_excluded}, is_image={is_image}, failure_reason={failure_reason}, "
                        f"source_preview='{segment_source_text[:100] if segment_source_text else 'None'}...', "
                        f"target_preview='{segment_target_text[:100] if segment_target_text else 'None'}...'"
                    )
                
                # Create segment record
                # CRITICAL: If translation failed, automatically mark as needs_retry
                # This allows the "Translate Failed" feature to show these segments for retranslation
                needs_retry = is_failed and not is_excluded and not is_image
                
                segment_dict = {
                    "segment_index": actual_segment_index,
                    "source_text": segment_source_text,
                    "target_text": segment_target_text,
                    "modified": False,
                    "separator_after": "",
                    "is_excluded": is_excluded,
                    "is_image": is_image,
                    "is_failed": is_failed,
                    "failure_reason": failure_reason,
                    "needs_retry": needs_retry,
                    "exclusion_reason": exclusion_reason.value if exclusion_reason else None,
                    "exclusion_metadata": exclusion_metadata if exclusion_reason else None,
                }
                
                # CRITICAL: Set platform_used if platform_key is available
                # This allows frontend to display correct platform/model information
                if platform_key:
                    segment_dict["platform_used"] = platform_key
                    # Initialize used_platforms list if not already set
                    if "used_platforms" not in segment_dict:
                        segment_dict["used_platforms"] = [platform_key] if platform_key else []
                
                segments.append(segment_dict)
        
        # Batch log excluded segments from chunks (only if there are any)
        if excluded_segment_indices_chunks:
            if len(excluded_segment_indices_chunks) <= 10:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Excluded {len(excluded_segment_indices_chunks)} segments from chunks: {excluded_segment_indices_chunks}")
            else:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Excluded {len(excluded_segment_indices_chunks)} segments from chunks: {excluded_segment_indices_chunks[:10]}... (and {len(excluded_segment_indices_chunks) - 10} more)")
    
    # Fill in missing segments from source_segments (segments that weren't in any chunk)
    # This ensures all segments from source_chunks_cache are represented
    if source_segments:
        for seg_idx in range(len(source_segments)):
            if seg_idx not in seen_segment_indices:
                # This segment wasn't in any chunk - create a record with source text as target
                seg_text = str(source_segments[seg_idx]).strip()
                if seg_text:
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Segment {seg_idx} not found in any chunk, creating record with source text as target"
                    )
                    segment = TranslationSegment.create(
                        task_id=task_id,
                        segment_index=seg_idx,
                        source_text=seg_text,
                        target_text=seg_text,  # Use source as target (not translated)
                        source_format=source_format,
                        workflow_type=workflow_type,
                    )
                    segment_dict = segment.to_dict()
                    
                    # Check if excluded using unified ExclusionManager
                    exclusion_reason = excluded_segments_with_reasons.get(seg_idx)
                    is_excluded = exclusion_reason is not None
                    exclusion_metadata = {}
                    
                    # CRITICAL: Translate phase does NOT detect new exclusions
                    # If segment is not in excluded_segments_with_reasons, it should NOT be excluded
                    # This ensures that exclusion data is managed only in Extract phase
                    if not is_excluded:
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Segment {seg_idx} (missing from chunks) is NOT excluded "
                            f"(not in excluded_segments_with_reasons, will be marked as not excluded)"
                        )
                    
                    if is_excluded:
                        segment_dict['is_excluded'] = True
                        segment_dict['excluded_at'] = time.time()
                        segment_dict['exclusion_reason'] = exclusion_reason.value if exclusion_reason else None
                        segment_dict['exclusion_metadata'] = exclusion_metadata if exclusion_reason else None
                    
                    # Check if image
                    is_image = _is_image_segment(seg_text)
                    if is_image:
                        segment_dict['is_image'] = True
                        if not is_excluded:
                            is_excluded = True
                            exclusion_reason = ExclusionReason.IMAGE
                            exclusion_metadata = {}
                            excluded_segments_with_reasons[seg_idx] = exclusion_reason
                            segment_dict['is_excluded'] = True
                            segment_dict['excluded_at'] = time.time()
                            segment_dict['exclusion_reason'] = exclusion_reason.value
                            segment_dict['exclusion_metadata'] = exclusion_metadata
                    
                    # Add separator if available
                    if seg_idx < len(separators):
                        separator = separators[seg_idx]
                        if separator is not None:
                            segment_dict['separator_after'] = separator
                    
                    # CRITICAL: Set platform_used if platform_key is available
                    # This allows frontend to display correct platform/model information
                    if platform_key:
                        segment_dict["platform_used"] = platform_key
                        # Initialize used_platforms list if not already set
                        if "used_platforms" not in segment_dict:
                            segment_dict["used_platforms"] = [platform_key] if platform_key else []
                    
                    segments.append(segment_dict)
    
    # CRITICAL: Validate and filter out segments with None segment_index before sorting
    # Frontend expects segment_index to be int, not None
    valid_segments = []
    invalid_count = 0
    for seg in segments:
        if isinstance(seg, dict):
            segment_index = seg.get('segment_index')
            if segment_index is not None:
                valid_segments.append(seg)
            else:
                invalid_count += 1
                logger.warning(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Filtered out segment with None segment_index. "
                    f"Segment keys: {list(seg.keys())}"
                )
        else:
            # Include non-dict segments (backward compatibility)
            valid_segments.append(seg)
    
    if invalid_count > 0:
        logger.warning(LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: Filtered out {invalid_count} segments with None segment_index. "
            f"Valid segments: {len(valid_segments)}"
        )
    
    segments = valid_segments
    
    # Sort segments by segment_index to ensure correct order
    # CRITICAL: Handle None segment_index by using a default value (0) for sorting
    # (After filtering, all segments should have valid segment_index, but keep this for safety)
    segments.sort(key=lambda s: s.get('segment_index') if s.get('segment_index') is not None else 0)
    
    # Validate that we have recorded all expected segments
    if source_segments:
        expected_count = len(source_segments)
        recorded_count = len(segments)
        # CRITICAL: Filter out None values to avoid type errors
        recorded_indices = {s.get('segment_index', -1) for s in segments if s.get('segment_index') is not None}
        expected_indices = set(range(expected_count))
        missing_indices = expected_indices - recorded_indices
        
        if recorded_count != expected_count or missing_indices:
            logger.warning(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Segment count mismatch: expected {expected_count}, recorded {recorded_count}. "
                f"Missing segment indices: {sorted(missing_indices)[:20]}{'...' if len(missing_indices) > 20 else ''}"
            )
            # Fill in missing segments with source text as target
            # CRITICAL: For PDF workflow, missing segments may be due to chunk merging/splitting failures
            # In this case, we should use the correct source_text from source_segments (not from chunks)
            # and mark them as failed if they should have been translated
            for missing_idx in sorted(missing_indices):
                if missing_idx < len(source_segments):
                    seg_text = str(source_segments[missing_idx]).strip()
                    if seg_text:
                        # Check if this segment should have been translated (not excluded, not image)
                        # Use unified ExclusionManager
                        exclusion_reason_seg = excluded_segments_with_reasons.get(missing_idx)
                        is_excluded_seg = exclusion_reason_seg is not None
                        exclusion_metadata_seg = {}
                        
                        # CRITICAL: Translate phase does NOT detect new exclusions
                        # If segment is not in excluded_segments_with_reasons, it should NOT be excluded
                        # This ensures that exclusion data is managed only in Extract phase
                        if not is_excluded_seg:
                            logger.debug(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Missing segment {missing_idx} is NOT excluded "
                                f"(not in excluded_segments_with_reasons, will be marked as not excluded)"
                            )
                        
                        is_image_seg = _is_image_segment(seg_text)
                        # If image, ensure it's marked as excluded in segment record
                        # According to design doc: Translate phase is READ-ONLY for exclusion data
                        # Do NOT modify excluded_segments_with_reasons
                        if is_image_seg and not is_excluded_seg:
                            is_excluded_seg = True
                            exclusion_reason_seg = ExclusionReason.IMAGE
                            exclusion_metadata_seg = {}
                            logger.warning(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Missing segment {missing_idx} is image but not excluded. "
                                f"This indicates Extract phase failed to mark image as excluded. "
                                f"Image segments should be excluded during Extract phase, not Translate phase."
                            )
                            # DO NOT modify excluded_segments_with_reasons
                        
                        # For all workflows, if segment is not excluded/image, it should have been translated
                        # Mark it as failed to indicate translation issue
                        is_failed = False
                        failure_reason = None
                        if not is_excluded_seg and not is_image_seg:
                            is_failed = True
                            failure_reason = "Segment missing from translation result"
                            logger.warning(LogModule.TRANS,
                                f"[RECORD_SEGMENTS] Task {task_id}: Missing segment {missing_idx} should have been translated. "
                                f"Marking as failed. Source: '{seg_text[:100]}...', workflow_type={workflow_type}"
                            )
                        
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Creating missing segment {missing_idx} with source text as target "
                            f"(is_failed={is_failed}, is_excluded={is_excluded_seg}, is_image={is_image_seg})"
                        )
                        # CRITICAL: If segment is marked as failed, automatically mark as needs_retry
                        needs_retry = is_failed and not is_excluded_seg and not is_image_seg
                        
                        segment_dict = {
                            "segment_index": missing_idx,
                            "source_text": seg_text,
                            "target_text": seg_text,  # Use source as target (not translated)
                            "modified": False,
                            "separator_after": "",
                            "is_excluded": is_excluded_seg,
                            "is_image": is_image_seg,
                            "is_failed": is_failed,
                            "failure_reason": failure_reason,
                            "needs_retry": needs_retry,
                            "exclusion_reason": exclusion_reason_seg.value if exclusion_reason_seg else None,
                            "exclusion_metadata": exclusion_metadata_seg if exclusion_reason_seg else None,
                        }
                        
                        # CRITICAL: Set platform_used if platform_key is available
                        # This allows frontend to display correct platform/model information
                        if platform_key:
                            segment_dict["platform_used"] = platform_key
                            # Initialize used_platforms list if not already set
                            if "used_platforms" not in segment_dict:
                                segment_dict["used_platforms"] = [platform_key] if platform_key else []
                        
                        segments.append(segment_dict)
            # Re-sort after adding missing segments
            # CRITICAL: Handle None segment_index by using a default value (0) for sorting
            segments.sort(key=lambda s: s.get('segment_index') if s.get('segment_index') is not None else 0)
            
            # Count and log failed segments for debugging
            failed_segments = [s for s in segments if s.get('is_failed', False)]
            if failed_segments:
                failed_indices = [s.get('segment_index') for s in failed_segments if s.get('segment_index') is not None]
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Found {len(failed_segments)} failed segments after processing: "
                    f"{sorted(failed_indices)[:20]}{'...' if len(failed_indices) > 20 else ''}"
                )
                # Log details for first 5 failed segments (for troubleshooting)
                for seg in failed_segments[:5]:
                    seg_idx = seg.get('segment_index')
                    if seg_idx is not None:
                        failure_reason = seg.get('failure_reason')
                        logger.debug(LogModule.TRANS,
                            f"[RECORD_SEGMENTS] Task {task_id}: Failed segment {seg_idx}: reason={failure_reason}"
                        )
            else:
                # Debug: Check for segments with target==source that should be marked as failed
                target_equals_source = [
                    s for s in segments 
                    if s.get('segment_index') is not None 
                    and not s.get('is_excluded', False) 
                    and not s.get('is_image', False)
                    and s.get('source_text', '').strip() == s.get('target_text', '').strip()
                    and s.get('source_text', '').strip() != ''
                ]
                if target_equals_source:
                    logger.debug(LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Found {len(target_equals_source)} segments with target==source "
                        f"but NOT marked as failed (likely non-translatable content). First 5 indices: "
                        f"{[s.get('segment_index') for s in target_equals_source[:5]]}"
                    )
            
            logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] After filling missing segments: {len(segments)} segments recorded")
        else:
            logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] All {recorded_count} segments recorded successfully")
    
    # Get segment_info from task_state if available (e.g., cell coordinates for XLSX, paragraph info for DOCX)
    segment_info_list = None
    if task_state:
        segments_metadata = task_state.get("segments_metadata", {})
        if isinstance(segments_metadata, dict):
            segment_info_list = segments_metadata.get("segment_info")
            if segment_info_list:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Found segment_info with {len(segment_info_list)} entries from segments_metadata")
                # Associate segment_info with each segment by segment_index
                for segment_dict in segments:
                    seg_idx = segment_dict.get('segment_index', -1)
                    if seg_idx >= 0 and seg_idx < len(segment_info_list):
                        segment_dict['segment_info'] = segment_info_list[seg_idx]
    
    # Create metadata (P0: source_input_type for layout vs text boundary in export/rebuild)
    source_input_type = (task_state.get("source_input_type", "text") if task_state else "text")
    if source_input_type not in ("layout", "text"):
        source_input_type = "text"
    metadata = TranslationSegmentsMetadata(
        original_format=source_format,
        original_filename=original_filename,
        workflow_type=workflow_type,
        source_lang=source_lang,
        target_lang=target_lang,
        total_segments=len(segments),
        segment_info=segment_info_list,
        source_input_type=source_input_type,
    )
    
    # P1: Write layout_block_indices when layout path (segment_layout_block_map, layout_chunk_block_map, or layout_document).
    # segment_layout_block_map is per-segment (Extract phase). layout_chunk_block_map is per translation chunk
    # and must NOT be indexed by segment_index when chunk count != segment count.
    segment_layout_block_map = (
        task_state.get("segment_layout_block_map") if task_state else None
    )
    if segment_layout_block_map and segments:
        mapped_count = _apply_layout_block_indices_to_segments(
            segments, segment_layout_block_map, use_segment_index=True
        )
        logger.info(
            LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: PDF path - wrote layout_block_indices for "
            f"{mapped_count} segments from segment_layout_block_map (source_input_type={source_input_type})"
        )
    elif (
        layout_chunk_block_map
        and segments
        and len(layout_chunk_block_map) == len(segments)
    ):
        mapped_count = _apply_layout_block_indices_to_segments(
            segments, layout_chunk_block_map, use_segment_index=False
        )
        logger.info(
            LogModule.TRANS,
            f"[RECORD_SEGMENTS] Task {task_id}: PDF path - wrote layout_block_indices for "
            f"{mapped_count} segments from 1:1 layout_chunk_block_map (source_input_type={source_input_type})"
        )
    else:
        # Fallback: map using layout_document when available (format conversion / PDF path may not pass layout_chunk_block_map)
        layout_doc = task_state.get("layout_document")
        if layout_doc is not None:
            try:
                from layout.base import LayoutDocument as _LD
                if isinstance(layout_doc, _LD):
                    _map_segments_to_layout_blocks(segments, source_chunks, layout_doc, logger)
                    logger.info(LogModule.TRANS, f"[RECORD_SEGMENTS] Task {task_id}: PDF path - mapped segments to layout blocks via layout_document fallback")
            except Exception as e:
                logger.debug(LogModule.TRANS, f"Failed to map segments to layout blocks: {e}")
        elif source_input_type != "layout":
            logger.debug(
                LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: Text path - not writing layout_block_indices (source_input_type={source_input_type}, no layout_chunk_block_map or layout_document)"
            )
    
    # P2: Build and store layout_block_bbox at segment recording (Layout extraction phase) so export does not need to iterate layout_document.
    # Also attach layout_block_bbox to each segment (list of bboxes for that segment's blocks) for use in export.
    if task_state:
        layout_doc = task_state.get("layout_document")
        bbox_map = task_state.get("layout_block_bbox")
        if layout_doc is not None and not bbox_map:
            try:
                from utils.format_convert_utils import get_layout_block_bbox
                bbox_map = get_layout_block_bbox(layout_doc)
                if bbox_map:
                    task_state["layout_block_bbox"] = bbox_map
                    logger.info(
                        LogModule.TRANS,
                        f"[RECORD_SEGMENTS] Task {task_id}: Stored layout_block_bbox for {len(bbox_map)} blocks (from layout_document)"
                    )
            except Exception as e:
                logger.debug(LogModule.TRANS, f"[RECORD_SEGMENTS] Failed to build layout_block_bbox: {e}")
        if bbox_map and segments:
            for segment_dict in segments:
                bidxs = segment_dict.get("layout_block_indices", [])
                if bidxs:
                    segment_dict["layout_block_bbox"] = [bbox_map[bidx] for bidx in bidxs if bidx in bbox_map]
    
    # For PDF workflow, segment_index already follows layout blocks' original order
    # Layout blocks' order is optimized by the layout algorithm, so we don't need to reassign
    # The chunks are extracted in the same order as layout blocks, so segment_index already reflects
    # the optimized layout text order
    
    # Store in task_state
    task_state["translation_segments"] = {
        "segments": segments,
        "metadata": metadata.to_dict(),
    }
    
    # CRITICAL: Update excluded_segments in segments_metadata using ExclusionManager
    # This ensures exclusion reasons are properly stored for future use
    if excluded_segments_with_reasons and task_state:
        # CRITICAL: Translate phase is READ-ONLY for exclusion data
        # Do NOT update segments_metadata.excluded_segments here
        # All exclusion data should be managed in Extract phase
        # Only log a warning if we have excluded segments that weren't in the original data
        # (This indicates a data inconsistency that should be fixed in Extract phase)
        if excluded_segments_with_reasons:
            segments_metadata = task_state.get("segments_metadata", {})
            existing_excluded = segments_metadata.get("excluded_segments", {})
            existing_excluded_indices = set(int(k) for k in existing_excluded.keys())
            new_excluded_indices = set(excluded_segments_with_reasons.keys())
            
            # Check for segments that are excluded but not in original data
            missing_in_original = new_excluded_indices - existing_excluded_indices
            if missing_in_original:
                logger.info(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Found {len(missing_in_original)} excluded segments "
                    f"that are not in segments_metadata.excluded_segments: {sorted(missing_in_original)[:10]}... "
                    f"This indicates a data inconsistency. These segments will be excluded in translation, "
                    f"but the exclusion data should be fixed in Extract phase."
                )
            
            # Check for segments that are in original data but not in excluded_segments_with_reasons
            missing_in_excluded_segments_with_reasons = existing_excluded_indices - new_excluded_indices
            if missing_in_excluded_segments_with_reasons:
                logger.warning(LogModule.TRANS,
                    f"[RECORD_SEGMENTS] Task {task_id}: Found {len(missing_in_excluded_segments_with_reasons)} excluded segments "
                    f"in segments_metadata.excluded_segments that are NOT in excluded_segments_with_reasons: "
                    f"{sorted(missing_in_excluded_segments_with_reasons)[:10]}... "
                    f"This indicates a data inconsistency. These segments will NOT be excluded in translation. "
                    f"Exclusion data should be fixed in Extract phase."
                )
            
            # Log summary with detailed reason breakdown
            reason_counts = {}
            for reason in excluded_segments_with_reasons.values():
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            # Also log reason breakdown from original data for comparison
            original_reason_counts = {}
            for seg_idx_str, exclusion_info in existing_excluded.items():
                reason_str = exclusion_info.get("reason", "unknown")
                try:
                    from exclusion.core import ExclusionReason
                    reason = ExclusionReason(reason_str)
                    original_reason_counts[reason] = original_reason_counts.get(reason, 0) + 1
                except ValueError:
                    pass
            
            # Get total segment count for comparison
            total_segments = len(segments) if segments else None
            source_segments_count = len(source_segments) if source_segments else None
            
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: Using {len(excluded_segments_with_reasons)} excluded segments from Extract phase. "
                f"Reason breakdown: {', '.join(f'{count} {reason.value}' for reason, count in sorted(reason_counts.items()))}. "
                f"Original data had {len(existing_excluded)} excluded segments with reasons: "
                f"{', '.join(f'{count} {reason.value}' for reason, count in sorted(original_reason_counts.items()))}. "
                f"Segment 0 included: {0 in excluded_segments_with_reasons}. "
                f"Total segments: {total_segments}, source_segments: {source_segments_count}"
            )
            
            # Log detailed comparison if counts don't match
            if len(excluded_segments_with_reasons) != len(existing_excluded):
                excluded_indices_in_reasons = set(excluded_segments_with_reasons.keys())
                excluded_indices_in_original = existing_excluded_indices
                missing_in_reasons = excluded_indices_in_original - excluded_indices_in_reasons
                if missing_in_reasons:
                    logger.warning(LogModule.EXCLUSION,
                        f"[RECORD_SEGMENTS] Task {task_id}: {len(missing_in_reasons)} excluded segments from Extract phase "
                        f"are missing in excluded_segments_with_reasons: {sorted(missing_in_reasons)[:20]}{'...' if len(missing_in_reasons) > 20 else ''}. "
                        f"This may indicate segment index validation or range issues."
                    )
        else:
            logger.debug(LogModule.TRANS,
                f"[RECORD_SEGMENTS] Task {task_id}: No excluded segments found (all segments will be translated)"
            )
    
    logger.info(LogModule.TRANS,
        f"Recorded {len(segments)} translation segments for task {task_id} "
        f"(format: {source_format}, workflow: {workflow_type})"
    )


def build_segment_layout_block_indices(
    chunk_block_indices: Optional[List[int]],
    block_index: Optional[int],
) -> List[int]:
    """Build per-segment layout block indices from LayoutChunk metadata."""
    unique_indices: List[int] = []
    seen: set[int] = set()
    for raw_idx in chunk_block_indices or []:
        try:
            value = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if value not in seen:
            seen.add(value)
            unique_indices.append(value)
    if unique_indices:
        return unique_indices
    if block_index is not None:
        try:
            return [int(block_index)]
        except (TypeError, ValueError):
            pass
    return []


def build_segment_layout_block_map(all_segments: List[dict]) -> List[List[int]]:
    """Build segment_index-indexed layout block map from extract-phase segment dicts."""
    if not all_segments:
        return []
    max_idx = -1
    for i, seg in enumerate(all_segments):
        try:
            seg_idx = int(seg.get("segment_index", i))
        except (TypeError, ValueError):
            seg_idx = i
        if seg_idx > max_idx:
            max_idx = seg_idx
    if max_idx < 0:
        return []
    block_map: List[List[int]] = [[] for _ in range(max_idx + 1)]
    for i, seg in enumerate(all_segments):
        try:
            seg_idx = int(seg.get("segment_index", i))
        except (TypeError, ValueError):
            seg_idx = i
        if seg_idx < 0 or seg_idx > max_idx:
            continue
        indices = seg.get("layout_block_indices") or seg.get("block_indices")
        if not indices:
            indices = build_segment_layout_block_indices([], seg.get("block_index"))
        block_map[seg_idx] = list(indices or [])
    return block_map


def _dedupe_layout_block_indices(block_indices: List[int]) -> List[int]:
    unique_indices: List[int] = []
    seen_indices: set[int] = set()
    for raw_idx in block_indices:
        try:
            value = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if value not in seen_indices:
            seen_indices.add(value)
            unique_indices.append(value)
    return unique_indices


def _apply_layout_block_indices_to_segments(
    segments: List[dict],
    block_map: List[List[int]],
    *,
    use_segment_index: bool = True,
) -> int:
    """Write layout_block_indices onto translation segment dicts; returns count updated."""
    updated = 0
    for idx, segment_dict in enumerate(segments):
        if use_segment_index:
            seg_idx = segment_dict.get("segment_index", idx)
            try:
                seg_idx = int(seg_idx)
            except (TypeError, ValueError):
                continue
        else:
            seg_idx = idx
        if seg_idx < 0 or seg_idx >= len(block_map):
            continue
        unique_indices = _dedupe_layout_block_indices(block_map[seg_idx] or [])
        if unique_indices:
            segment_dict["layout_block_indices"] = unique_indices
            updated += 1
    return updated


def _map_segments_to_layout_blocks(
    segments: List[dict],
    source_chunks: List[str],
    layout_doc,
    logger
) -> None:
    """
    Map translation segments to layout blocks using content-based matching.
    
    Args:
        segments: List of segment dictionaries (will be modified in-place)
        source_chunks: List of source text chunks
        layout_doc: LayoutDocument instance
        logger: Logger instance
    """
    # Flatten all text blocks from layout document
    text_blocks = []
    for block in layout_doc.iter_text_blocks():
        if block.text and block.text.strip() and block.index is not None:
            text_blocks.append(block)
    
    if not text_blocks:
        logger.debug(LogModule.TRANS, "No text blocks found in layout document for mapping")
        return
    
    # Build a concatenated text string with block indices
    # This allows us to find where each source_chunk appears in the layout
    # We'll build both original and normalized versions for matching
    full_text_parts = []
    normalized_full_text_parts = []
    char_block_indices = []  # Maps character position to block index
    normalized_char_block_indices = []  # Maps normalized character position to block index
    
    for block in text_blocks:
        block_text = block.text.strip()
        if not block_text:
            continue
        
        # Normalize block text for matching
        normalized_block_text = _normalize_text_for_matching(block_text)
        if not normalized_block_text:
            continue
        
        # Build original text mapping (for character position tracking)
        full_text_parts.append(block_text)
        for _ in range(len(block_text)):
            char_block_indices.append(block.index)
        
        # Build normalized text mapping (for matching)
        normalized_full_text_parts.append(normalized_block_text)
        for _ in range(len(normalized_block_text)):
            normalized_char_block_indices.append(block.index)
        
        # Add a space between blocks for matching
        full_text_parts.append(' ')
        char_block_indices.append(-1)  # -1 means separator
        normalized_full_text_parts.append(' ')
        normalized_char_block_indices.append(-1)
    
    full_text = ''.join(full_text_parts)
    normalized_full_text = ''.join(normalized_full_text_parts)
    
    logger.info(LogModule.TRANS, f"[MAP] Built full_text: {len(full_text)} chars, normalized: {len(normalized_full_text)} chars, {len(text_blocks)} blocks")
    
    # Match each source_chunk to layout blocks
    current_pos = 0
    mapped_count = 0
    
    for seg_idx, source_text in enumerate(source_chunks):
        if seg_idx >= len(segments):
            break
        
        source_stripped = source_text.strip()
        if not source_stripped:
            continue
        
        # Normalize source text for matching
        normalized_source = _normalize_text_for_matching(source_stripped)
        if not normalized_source:
            logger.debug(LogModule.TRANS, f"[MAP] Segment {seg_idx} normalized to empty, skipping")
            continue
        
        # Try to find normalized source_text in normalized full_text
        found_pos = normalized_full_text.find(normalized_source, current_pos)
        
        if found_pos >= 0:
            # Found a match - collect all block indices that this segment covers
            block_indices = set()
            start_char = found_pos
            end_char = found_pos + len(normalized_source)
            
            for char_pos in range(start_char, min(end_char, len(normalized_char_block_indices))):
                block_idx = normalized_char_block_indices[char_pos]
                if block_idx >= 0:
                    block_indices.add(block_idx)
            
            if block_indices:
                segments[seg_idx]["layout_block_indices"] = sorted(block_indices)
                mapped_count += 1
                logger.debug(LogModule.TRANS,
                    f"[MAP] Mapped segment {seg_idx} to {len(block_indices)} layout blocks: "
                    f"{sorted(block_indices)[:5]}{'...' if len(block_indices) > 5 else ''}"
                )
            else:
                logger.debug(LogModule.TRANS, f"[MAP] Segment {seg_idx} matched but no valid block indices found")
            
            # Update current_pos for next search
            current_pos = found_pos + len(normalized_source)
        else:
            # No exact match found - log for debugging
            logger.debug(LogModule.TRANS,
                f"[MAP] Could not find match for segment {seg_idx} "
                f"(normalized: '{normalized_source[:50]}...' if len(normalized_source) > 50 else normalized_source)"
            )
    
    # Log mapping statistics
    mapped_count = sum(1 for seg in segments if seg.get("layout_block_indices"))
    logger.info(LogModule.TRANS,
        f"Mapped {mapped_count}/{len(segments)} segments to layout blocks "
        f"({len(text_blocks)} text blocks available)"
    )


def get_translation_segments(task_id: str, task_state: Optional[dict] = None) -> Optional[dict]:
    """
    Get translation segments from task state.
    
    Args:
        task_id: Task identifier
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Dictionary with 'segments' and 'metadata' keys, or None if not found.
        For backward compatibility, if translation_segments is a list (old format),
        it will be converted to dict format.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            return None
    
    translation_segments = task_state.get("translation_segments")
    
    # CRITICAL: Handle backward compatibility - translation_segments might be a list (old format) or dict (new format)
    if translation_segments is None:
        return None
    elif isinstance(translation_segments, list):
        # Old format - convert to dict format for consistency
        return {
            "segments": translation_segments,
            "metadata": {}
        }
    elif isinstance(translation_segments, dict):
        # New format - return as is
        return translation_segments
    else:
        # Unexpected type - return None
        return None


def update_translation_segment(
    task_id: str,
    segment_index: int,
    target_text: Optional[str] = None,
    reviewed: Optional[bool] = None,
    review_notes: Optional[str] = None,
    modified_by: Optional[str] = None,
    font_size_pt: Optional[float] = None,
    font_size_reset: bool = False,
    font_weight: Optional[str] = None,
    font_style: Optional[str] = None,
    font_weight_reset: bool = False,
    font_style_reset: bool = False,
    pdf_font_reset: bool = False,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Update a translation segment.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to update
        target_text: New target text (if provided)
        reviewed: Whether to mark as reviewed
        review_notes: Review notes
        modified_by: Identifier of who made the modification
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS, f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS, f"Segment index {segment_index} not found in segments for task {task_id}")
        return None
    
    # Update fields
    if target_text is not None:
        old_text = segment.get("target_text", "")
        segment["target_text"] = target_text
        segment["modified_text"] = target_text  # Also update modified_text for document rebuilding
        segment["target_length"] = len(target_text)
        segment["modified"] = True
        segment["modified_by"] = modified_by
        segment["modified_at"] = time.time()
        segment["status"] = "modified"
        logger.info(LogModule.TRANS, f"Updated segment {segment_index} for task {task_id}: modified=True, old_length={len(old_text)}, new_length={len(target_text)}")
        
        # CRITICAL: Sync manual edit back to html_translated_texts for html workflow rebuild
        if task_state and "html_original_texts" in task_state:
            html_translated_texts = task_state.get("html_translated_texts", [])
            if (
                segment_index is not None
                and 0 <= segment_index < len(html_translated_texts)
            ):
                html_translated_texts[segment_index] = target_text
                task_state["html_translated_texts"] = html_translated_texts
                logger.info(
                    LogModule.TRANS,
                    f"[UPDATE-SEGMENT] Task {task_id}: Synced segment {segment_index} to html_translated_texts"
                )
    
    if reviewed is not None:
        segment["reviewed"] = reviewed
        if reviewed and segment["status"] == "translated":
            segment["status"] = "reviewed"
    
    if review_notes is not None:
        segment["review_notes"] = review_notes

    if font_size_reset or pdf_font_reset:
        segment.pop("font_size_pt", None)
        segment["modified"] = True
        segment["modified_by"] = modified_by or segment.get("modified_by")
        segment["modified_at"] = time.time()
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            invalidate_pdf_export_cache,
        )
        invalidate_pdf_export_cache(task_state)
        logger.info(
            LogModule.TRANS,
            f"Reset font_size_pt for segment {segment_index} on task {task_id}",
        )
    elif font_size_pt is not None:
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            normalize_user_font_size_pt,
        )
        normalized = normalize_user_font_size_pt(font_size_pt)
        if normalized is None:
            logger.warning(
                LogModule.TRANS,
                f"Invalid font_size_pt={font_size_pt} for segment {segment_index} task {task_id}",
            )
        else:
            segment["font_size_pt"] = normalized
            segment["modified"] = True
            segment["modified_by"] = modified_by or segment.get("modified_by")
            segment["modified_at"] = time.time()
            from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
                invalidate_pdf_export_cache,
            )
            invalidate_pdf_export_cache(task_state)
            logger.info(
                LogModule.TRANS,
                f"Set font_size_pt={normalized} for segment {segment_index} on task {task_id}",
            )

    if font_weight_reset or pdf_font_reset:
        segment.pop("font_weight", None)
        segment["modified"] = True
        segment["modified_by"] = modified_by or segment.get("modified_by")
        segment["modified_at"] = time.time()
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            invalidate_pdf_export_cache,
        )
        invalidate_pdf_export_cache(task_state)
        logger.info(
            LogModule.TRANS,
            f"Reset font_weight for segment {segment_index} on task {task_id}",
        )
    elif font_weight is not None:
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            normalize_user_font_weight,
        )
        normalized_weight = normalize_user_font_weight(font_weight)
        if normalized_weight is None:
            logger.warning(
                LogModule.TRANS,
                f"Invalid font_weight={font_weight} for segment {segment_index} task {task_id}",
            )
        else:
            segment["font_weight"] = normalized_weight
            segment["modified"] = True
            segment["modified_by"] = modified_by or segment.get("modified_by")
            segment["modified_at"] = time.time()
            from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
                invalidate_pdf_export_cache,
            )
            invalidate_pdf_export_cache(task_state)
            logger.info(
                LogModule.TRANS,
                f"Set font_weight={normalized_weight} for segment {segment_index} on task {task_id}",
            )

    if font_style_reset or pdf_font_reset:
        segment.pop("font_style", None)
        segment["modified"] = True
        segment["modified_by"] = modified_by or segment.get("modified_by")
        segment["modified_at"] = time.time()
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            invalidate_pdf_export_cache,
        )
        invalidate_pdf_export_cache(task_state)
        logger.info(
            LogModule.TRANS,
            f"Reset font_style for segment {segment_index} on task {task_id}",
        )
    elif font_style is not None:
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            normalize_user_font_style,
        )
        normalized_style = normalize_user_font_style(font_style)
        if normalized_style is None:
            logger.warning(
                LogModule.TRANS,
                f"Invalid font_style={font_style} for segment {segment_index} task {task_id}",
            )
        else:
            segment["font_style"] = normalized_style
            segment["modified"] = True
            segment["modified_by"] = modified_by or segment.get("modified_by")
            segment["modified_at"] = time.time()
            from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
                invalidate_pdf_export_cache,
            )
            invalidate_pdf_export_cache(task_state)
            logger.info(
                LogModule.TRANS,
                f"Set font_style={normalized_style} for segment {segment_index} on task {task_id}",
            )
    
    logger.info(LogModule.TRANS, f"Segment {segment_index} update completed for task {task_id}: modified={segment.get('modified', False)}")
    return segment


def mark_segment_for_retry(
    task_id: str,
    segment_index: int,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Mark a translation segment as needing retry.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to mark
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS, f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS, f"Segment index {segment_index} not found in segments for task {task_id}")
        return None
    segment["needs_retry"] = True
    
    # User-initiated retry should override auto-exclusion.
    # Clear exclusion flags so the segment will actually be retranslated.
    if segment.get("is_excluded", False):
        segment["is_excluded"] = False
        segment["exclusion_reason"] = None
        logger.info(LogModule.TRANS, f"Cleared auto-exclusion for segment {segment_index} (reason was: {segment.get('exclusion_reason')})")
    
    # Also remove from segments_metadata so downstream APIs don't re-attach old detected_exclusion_reason
    segments_metadata = task_state.get("segments_metadata", {})
    if segments_metadata:
        excluded_segments = segments_metadata.get("excluded_segments", {})
        if str(segment_index) in excluded_segments:
            del excluded_segments[str(segment_index)]
        excluded_indices = segments_metadata.get("excluded_segment_indices", [])
        if segment_index in excluded_indices:
            excluded_indices.remove(segment_index)
        detected_reasons = segments_metadata.get("detected_exclusion_reasons", {})
        if str(segment_index) in detected_reasons:
            del detected_reasons[str(segment_index)]
    
    logger.info(LogModule.TRANS, f"Marked segment {segment_index} for retry in task {task_id}")
    return segment


def exclude_translation_segment(
    task_id: str,
    segment_index: int,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Exclude a translation segment (user-initiated operation).
    
    This function allows users to manually exclude a segment in Translate phase.
    It directly updates segments_metadata.excluded_segments without triggering auto-detection.
    
    Note:
        - This is a user-initiated operation, NOT an auto-detection
        - It directly updates segments_metadata.excluded_segments
        - It does NOT trigger any automatic exclusion detection
    """
    """
    Exclude a translation segment from translation: restore target_text to source_text and mark as excluded.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to exclude
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    """
    logger.info(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Starting exclude_translation_segment for task {task_id}, segment {segment_index}")
    
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            logger.warning(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Task {task_id} not found in task_manager")
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS,f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Segment index {segment_index} not found in segments for task {task_id}")
        # CRITICAL: In Extract phase, segment may not be in translation_segments yet
        # Try to update segments_metadata.excluded_segments directly
        logger.info(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Segment not in translation_segments, trying to update segments_metadata.excluded_segments directly (Extract phase)")
        from exclusion.core import ExclusionReason, ExclusionManager, detect_exclusion_reason
        
        # CRITICAL: Check if segment already has an exclusion reason in segments_metadata.excluded_segments
        # This preserves existing reasons (e.g., IDENTIFIER, LANGUAGE_MATCH) when user excludes via checkbox
        current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
        existing_reason = current_excluded_map.get(segment_index)
        
        if existing_reason:
            # Segment already has an exclusion reason (e.g., IDENTIFIER, LANGUAGE_MATCH)
            # Preserve the existing reason instead of overriding with USER_SELECTED
            logger.info(LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} already has exclusion reason={existing_reason.value} "
                f"in segments_metadata.excluded_segments, preserving it (Extract phase)"
            )
            exclusion_reason = existing_reason
        else:
            # No existing exclusion reason - try to detect one from segment text
            # Get segment text from source_chunks_cache or segments_metadata
            segment_text = None
            segments_metadata = task_state.get("segments_metadata", {})
            source_chunks_cache = task_state.get("source_chunks_cache", {})
            segments_text = source_chunks_cache.get("segments", [])
            
            if segment_index < len(segments_text):
                segment_text = segments_text[segment_index]
            
            # Also try to get block_type and other metadata from segment_info
            segment_info = segments_metadata.get("segment_info", [])
            block_type = None
            is_image = False
            is_table = False
            if segment_index < len(segment_info):
                seg_info = segment_info[segment_index]
                if isinstance(seg_info, dict):
                    block_type = seg_info.get("block_type")
                    is_image = seg_info.get("is_image", False)
                    is_table = seg_info.get("is_table_cell", False) or seg_info.get("is_table", False)
            
            # Detect exclusion reason if we have segment text
            if segment_text:
                detected_result = detect_exclusion_reason(
                    text=segment_text,
                    block_type=block_type,
                    target_lang=None,  # Don't check language match for manual exclusion
                    is_image=is_image,
                    is_table=is_table
                )
                if detected_result:
                    detected_reason, _ = detected_result
                    exclusion_reason = detected_reason
                    logger.info(LogModule.TRANS,
                        f"[EXCLUDE_SEGMENT] Detected exclusion reason={exclusion_reason.value} "
                        f"for segment {segment_index} in Extract phase"
                    )
                else:
                    # No specific reason detected - set as user_selected
                    exclusion_reason = ExclusionReason.USER_SELECTED
                    logger.info(LogModule.TRANS,
                        f"[EXCLUDE_SEGMENT] No exclusion reason detected for segment {segment_index}, "
                        f"using USER_SELECTED (Extract phase)"
                    )
            else:
                # No segment text available - set as user_selected
                exclusion_reason = ExclusionReason.USER_SELECTED
                logger.info(LogModule.TRANS,
                    f"[EXCLUDE_SEGMENT] Segment text not available for segment {segment_index}, "
                    f"using USER_SELECTED (Extract phase)"
                )
        
        # Update segments_metadata.excluded_segments with the determined reason
        current_excluded_map[segment_index] = exclusion_reason
        ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
        logger.info(LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Updated segments_metadata.excluded_segments for segment {segment_index} "
            f"with reason={exclusion_reason.value} in Extract phase"
        )
        # Return a minimal segment dict for API response
        return {
            "segment_index": segment_index,
            "is_excluded": True,
            "exclusion_reason": exclusion_reason.value,
        }
    
    source_text = segment.get("source_text", "")
    logger.debug(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Found segment {segment_index} in translation_segments, source_text length={len(source_text)}")
    
    # Restore target_text to source_text
    segment["target_text"] = source_text
    segment["target_length"] = len(source_text)
    # Mark as excluded
    segment["is_excluded"] = True
    segment["excluded_at"] = time.time()
    # Clear retry flags since we're excluding
    segment["needs_retry"] = False
    segment["is_failed"] = False
    segment["failure_reason"] = None
    
    # CRITICAL: Set exclusion_reason based on current state
    # Priority order:
    # 1. segments_metadata.excluded_segments (PRIMARY - Extract phase detection)
    # 2. segment.exclusion_reason (Translate phase, if available)
    # 3. Detect from segment text (fallback)
    from exclusion.core import ExclusionReason, ExclusionManager, detect_exclusion_reason
    
    # Update segments_metadata.excluded_segments (single source of truth)
    current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
    logger.debug(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Current excluded_segments count: {len(current_excluded_map)}")
    
    # CRITICAL: Check segments_metadata.excluded_segments first (PRIMARY source)
    # This ensures that exclusion reasons from Extract phase (e.g., IDENTIFIER, LANGUAGE_MATCH) are preserved
    existing_reason_from_metadata = current_excluded_map.get(segment_index)
    current_reason_value = segment.get("exclusion_reason")
    
    logger.debug(LogModule.TRANS,
        f"[EXCLUDE_SEGMENT] Current exclusion_reason for segment {segment_index}: "
        f"from_metadata={existing_reason_from_metadata.value if existing_reason_from_metadata else None}, "
        f"from_segment={current_reason_value}"
    )
    
    # Priority 1: Use existing reason from segments_metadata.excluded_segments (if available)
    # This preserves exclusion reasons from Extract phase (e.g., IDENTIFIER, LANGUAGE_MATCH)
    if existing_reason_from_metadata:
        # Segment already has an exclusion reason in segments_metadata (from Extract phase)
        # Preserve it instead of overriding
        segment["exclusion_reason"] = existing_reason_from_metadata.value
        # Keep the existing reason in current_excluded_map (don't override)
        logger.info(LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Segment {segment_index} already has exclusion reason={existing_reason_from_metadata.value} "
            f"in segments_metadata.excluded_segments, preserving it"
        )
    elif current_reason_value:
        # Priority 2: Use exclusion_reason from segment (Translate phase)
        # Already excluded - keep the original reason (don't override auto-detected)
        # Just update excluded_at timestamp
        segment["exclusion_reason"] = current_reason_value
        try:
            current_excluded_map[segment_index] = ExclusionReason(current_reason_value)
        except ValueError:
            # Invalid reason, use UNKNOWN
            current_excluded_map[segment_index] = ExclusionReason.UNKNOWN
            segment["exclusion_reason"] = ExclusionReason.UNKNOWN.value
        logger.info(LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Segment {segment_index} already excluded with reason={current_reason_value}, "
            f"keeping original reason and updating segments_metadata"
        )
    else:
        # Not excluded yet - detect appropriate exclusion reason
        # CRITICAL: For table segments, set as TABLE instead of USER_SELECTED
        # This allows users to properly identify and manage table exclusions
        source_text = segment.get("source_text", "")
        block_type = segment.get("block_type")  # May be "table_body" for PDF tables
        is_table = (block_type == "table_body" or block_type == "table")
        
        # Check if this is a table segment (for markdown/HTML workflows)
        if not is_table:
            from utils.translation_segments import _is_table_segment
            is_table = _is_table_segment(source_text)
        
        # Detect exclusion reason
        detected_result = detect_exclusion_reason(
            text=source_text,
            block_type=block_type,
            target_lang=None,  # Don't check language match for manual exclusion
            is_image=segment.get("is_image", False),
            is_table=is_table
        )
        
        if detected_result:
            detected_reason, detected_metadata = detected_result
            segment["exclusion_reason"] = detected_reason.value
            segment["exclusion_metadata"] = detected_metadata
            current_excluded_map[segment_index] = detected_reason
            logger.info(LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} marked as excluded with reason={detected_reason.value} "
                f"(detected) and updated segments_metadata"
            )
        else:
            # No specific reason detected - set as user_selected
            segment["exclusion_reason"] = ExclusionReason.USER_SELECTED.value
            segment["exclusion_metadata"] = {}
            current_excluded_map[segment_index] = ExclusionReason.USER_SELECTED
            logger.info(LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} marked as excluded with reason=user_selected "
                f"(no specific reason detected) and updated segments_metadata"
            )
    
    # Update segments_metadata using ExclusionManager
    ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
    
    # CRITICAL: Remove from user_unexcluded_segments if present (user is re-excluding)
    segments_metadata = task_state.get("segments_metadata", {})
    user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
    if segment_index in user_unexcluded:
        user_unexcluded.remove(segment_index)
        segments_metadata["user_unexcluded_segments"] = user_unexcluded
        logger.info(LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Removed segment {segment_index} from user_unexcluded_segments "
            f"(user is re-excluding). remaining user_unexcluded: {len(user_unexcluded)}"
        )
    
    # CRITICAL: Also add back to excluded_segment_indices for consistency with frontend refresh
    existing_indices = segments_metadata.get("excluded_segment_indices", [])
    if segment_index not in existing_indices:
        existing_indices.append(segment_index)
        existing_indices.sort()
        segments_metadata["excluded_segment_indices"] = existing_indices
    
    logger.info(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Successfully excluded segment {segment_index} for task {task_id} (updated segments_metadata.excluded_segments)")
    return segment


def clear_translation_segment(
    task_id: str,
    segment_index: int,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Clear a translation segment's target text (set to empty string).
    
    This is useful when AI merges adjacent segments during translation,
    causing one segment to display translations for multiple segments.
    Clearing the segment allows it to be skipped during export or exported as empty.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to clear
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS,f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS,f"Segment index {segment_index} not found in segments for task {task_id}")
        return None
    
    # Clear target text
    segment["target_text"] = ""
    segment["modified_text"] = ""  # Also clear modified_text
    segment["target_length"] = 0
    segment["modified"] = True
    segment["modified_at"] = time.time()
    segment["status"] = "cleared"
    # CRITICAL: Clear retry flags to prevent cleared segments from being retranslated
    segment["needs_retry"] = False
    segment["is_failed"] = False
    segment["failure_reason"] = None
    # Don't mark as excluded - just clear the text and mark as cleared
    # This allows the segment to be skipped during retranslation but exported as empty
    
    logger.info(LogModule.TRANS, f"Cleared segment {segment_index} translation for task {task_id}")
    return segment


def unexclude_translation_segment(
    task_id: str,
    segment_index: int,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Unexclude a translation segment (user-initiated operation).
    
    This function allows users to manually unexclude a segment in Translate phase.
    It directly updates segments_metadata.excluded_segments without triggering auto-detection.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to unexclude
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    
    Note:
        - This is a user-initiated operation, NOT an auto-detection
        - It directly updates segments_metadata.excluded_segments
        - It does NOT trigger any automatic exclusion detection
        - The segment is added to user_unexcluded_segments to prevent re-detection in Extract phase
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS,f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS,f"Segment index {segment_index} not found in segments for task {task_id}")
        return None
    
    # CRITICAL: Get exclusion reason before removing
    from exclusion.core import ExclusionReason, detect_exclusion_reason, ExclusionManager
    current_reason_value = segment.get("exclusion_reason")
    
    # Update segments_metadata.excluded_segments (single source of truth)
    current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
    
    # CRITICAL: Allow unexclude for ALL exclusion types (including content-based)
    # User choice should be respected - if user wants to unexclude, we allow it
    # The segment will be added to user_unexcluded_segments to prevent re-detection
    original_reason = None
    if current_reason_value:
        try:
            original_reason = ExclusionReason(current_reason_value)
            logger.info(LogModule.EXCLUSION,
                f"[UNEXCLUDE] Task {task_id}: User requested to unexclude segment {segment_index} "
                f"with exclusion_reason={original_reason.value}. User choice will be respected."
            )
        except ValueError:
            # Unknown reason - allow unexclude
            logger.debug(LogModule.EXCLUSION,
                f"Unknown exclusion_reason={current_reason_value} for segment {segment_index}, "
                f"allowing unexclude"
            )
    
    # Clear exclusion flag
    segment["is_excluded"] = False
    segment["excluded_at"] = None
    segment["exclusion_reason"] = None
    segment["exclusion_metadata"] = None
    
    # Remove from current_excluded_map (single source of truth)
    if segment_index in current_excluded_map:
        if original_reason is None:
            original_reason = current_excluded_map[segment_index]
        del current_excluded_map[segment_index]
        ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
        logger.debug(LogModule.EXCLUSION,
            f"Removed segment {segment_index} from segments_metadata.excluded_segments (single source of truth)"
        )
    
    # CRITICAL: Record that user explicitly chose to unexclude this segment to prevent re-detection
    # This applies to ALL exclusion types (content-based, language-based, user-based, optional)
    # to prevent get_layout_extract from re-detecting and re-excluding the segment
    # NOTE: Also handles segments excluded by layout pipeline (e.g., interline_equation / formula)
    # that are NOT tracked in segments_metadata.excluded_segments — original_reason will be None
    # but we still MUST add to user_unexcluded_segments to prevent re-exclusion.
    segments_metadata = task_state.get("segments_metadata", {})
    user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
    if segment_index not in user_unexcluded:
        user_unexcluded.append(segment_index)
        segments_metadata["user_unexcluded_segments"] = user_unexcluded
        reason_label = original_reason.value if original_reason else 'unknown (layout-level exclusion)'
        logger.info(LogModule.EXCLUSION,
            f"[UNEXCLUDE] Task {task_id}: Recorded segment {segment_index} as user-unexcluded "
            f"(original reason: {reason_label}) to prevent re-detection in get_layout_extract. "
            f"user_unexcluded_segments={user_unexcluded}"
        )
    else:
        logger.debug(LogModule.EXCLUSION,
            f"[UNEXCLUDE] Task {task_id}: Segment {segment_index} already in user_unexcluded_segments"
        )
    if original_reason is None:
        logger.warning(LogModule.EXCLUSION,
            f"[UNEXCLUDE] Task {task_id}: Segment {segment_index} original_reason is None — "
            f"likely a layout-level exclusion (e.g., interline_equation) not tracked in excluded_segments. "
            f"Segment has been added to user_unexcluded_segments to prevent re-exclusion."
        )
    
    # CRITICAL: Also update excluded_segment_indices to keep it in sync
    # This ensures frontend refresh reads the correct excluded set
    existing_indices = segments_metadata.get("excluded_segment_indices", [])
    if segment_index in existing_indices:
        existing_indices.remove(segment_index)
        segments_metadata["excluded_segment_indices"] = existing_indices
        logger.debug(LogModule.EXCLUSION,
            f"[UNEXCLUDE] Task {task_id}: Removed segment {segment_index} from excluded_segment_indices "
            f"(remaining: {len(existing_indices)})"
        )
    
    # CRITICAL: Do NOT re-detect exclusion reason after unexclude
    # User explicitly chose to unexclude this segment - respect user choice
    # The segment has already been added to user_unexcluded_segments to prevent re-detection
    # Re-detection would override user choice, which is not desired
    logger.info(LogModule.EXCLUSION,
        f"[UNEXCLUDE] Task {task_id}: Unexcluded segment {segment_index} (original reason: {original_reason.value if original_reason else 'unknown'}). "
        f"User choice respected - segment added to user_unexcluded_segments to prevent re-detection."
    )
    
    return segment


def exclude_translation_segments_batch(
    task_id: str,
    segment_indices: List[int],
    task_state: Optional[dict] = None,
) -> dict:
    """
    Exclude multiple translation segments in one task_state load.

    Returns dict with success flag, updated segment dicts, and failed indices.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.TRANS, f"[EXCLUDE_BATCH] Task {task_id} not found")
        return {
            "success": False,
            "segments": [],
            "failed_indices": list(segment_indices),
        }

    segments_out: List[dict] = []
    failed_indices: List[int] = []
    seen: set[int] = set()
    for segment_index in segment_indices:
        idx = int(segment_index)
        if idx in seen:
            continue
        seen.add(idx)
        segment = exclude_translation_segment(
            task_id=task_id,
            segment_index=idx,
            task_state=task_state,
        )
        if segment is None:
            failed_indices.append(idx)
        else:
            segments_out.append(segment)

    logger.info(
        LogModule.TRANS,
        f"[EXCLUDE_BATCH] Task {task_id}: excluded {len(segments_out)}/{len(seen)} segments"
        + (f", failed={failed_indices}" if failed_indices else ""),
    )
    return {
        "success": len(failed_indices) == 0,
        "segments": segments_out,
        "failed_indices": failed_indices,
    }


def unexclude_translation_segments_batch(
    task_id: str,
    segment_indices: List[int],
    task_state: Optional[dict] = None,
) -> dict:
    """
    Unexclude multiple translation segments in one task_state load.

    Returns dict with success flag, updated segment dicts, and failed indices.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.TRANS, f"[UNEXCLUDE_BATCH] Task {task_id} not found")
        return {
            "success": False,
            "segments": [],
            "failed_indices": list(segment_indices),
        }

    segments_out: List[dict] = []
    failed_indices: List[int] = []
    seen: set[int] = set()
    for segment_index in segment_indices:
        idx = int(segment_index)
        if idx in seen:
            continue
        seen.add(idx)
        segment = unexclude_translation_segment(
            task_id=task_id,
            segment_index=idx,
            task_state=task_state,
        )
        if segment is None:
            failed_indices.append(idx)
        else:
            segments_out.append(segment)

    logger.info(
        LogModule.TRANS,
        f"[UNEXCLUDE_BATCH] Task {task_id}: unexcluded {len(segments_out)}/{len(seen)} segments"
        + (f", failed={failed_indices}" if failed_indices else ""),
    )
    return {
        "success": len(failed_indices) == 0,
        "segments": segments_out,
        "failed_indices": failed_indices,
    }


def _get_total_segment_count(task_state: dict) -> int:
    """Get total segment count from task_state (source_chunks_cache or segment_info or translation_segments)."""
    cache_info = task_state.get("source_chunks_cache", {})
    segments_list = cache_info.get("segments", [])
    if segments_list and isinstance(segments_list, list):
        return len(segments_list)
    seg_info = task_state.get("segments_metadata", {}).get("segment_info", [])
    if seg_info and isinstance(seg_info, list):
        return len(seg_info)
    ts_data = task_state.get("translation_segments", {})
    segs = ts_data.get("segments", []) if isinstance(ts_data, dict) else []
    if segs:
        return len(segs)
    return 0


def excluded_indices_from_layout_prepared_chunks(task_state: dict) -> set[int]:
    """Collect segment indices marked is_excluded on layout_prepared_chunks (PDF layout path)."""
    indices: set[int] = set()
    for chunk in task_state.get("layout_prepared_chunks") or []:
        if not isinstance(chunk, dict) or not chunk.get("is_excluded"):
            continue
        for raw_idx in chunk.get("segment_indices") or []:
            try:
                indices.add(int(raw_idx))
            except (TypeError, ValueError):
                continue
    return indices


def _replace_excluded_segments_metadata(
    task_state: dict,
    excluded_by_index: dict[int, "ExclusionReason"],
) -> None:
    """
    Replace excluded_segments wholesale (does not preserve stale USER_SELECTED entries).
    Used when reconciling against layout_prepared_chunks after mistaken exclude-all.
    """
    import time
    from exclusion.core import ExclusionReason

    if "segments_metadata" not in task_state:
        task_state["segments_metadata"] = {}
    segments_metadata = task_state["segments_metadata"]
    excluded_dict_str_keys: dict[str, dict] = {}
    for idx, reason in excluded_by_index.items():
        reason_str = reason.value if isinstance(reason, ExclusionReason) else str(reason)
        excluded_dict_str_keys[str(int(idx))] = {
            "reason": reason_str,
            "detected_at": time.time(),
            "metadata": {},
        }
    segments_metadata["excluded_segments"] = excluded_dict_str_keys
    segments_metadata["excluded_segment_indices"] = sorted(int(k) for k in excluded_dict_str_keys)


def apply_copy_source_only_exclusions(task_state: dict, task_id: str = "") -> bool:
    """
    Mark every segment excluded on the translate task so complete_translation_with_source_only
    fills target from source. Does not modify the linked convert/extract task.
    """
    from exclusion.core import ExclusionReason

    total = _get_total_segment_count(task_state)
    if total <= 0:
        logger.warning(
            LogModule.TRANS,
            f"[COPY-SOURCE-ONLY] Task {task_id}: cannot apply — no segments in task_state",
        )
        return False

    task_state["copy_source_only"] = True
    rebuilt = {i: ExclusionReason.USER_SELECTED for i in range(total)}
    _replace_excluded_segments_metadata(task_state, rebuilt)
    logger.info(
        LogModule.TRANS,
        f"[COPY-SOURCE-ONLY] Task {task_id}: marked all {total} segments excluded for source-as-target copy",
    )
    return True


def reconcile_excluded_segments_from_layout(task_state: dict, task_id: str = "") -> bool:
    """
    Fix stale metadata when every segment appears excluded but layout chunks still have translatable text.
    Returns True if segments_metadata was corrected.
    """
    from exclusion.core import ExclusionManager, ExclusionReason

    total = _get_total_segment_count(task_state)
    if total <= 0:
        return False

    current = ExclusionManager.get_excluded_segments(task_state)
    if len(current) < total:
        return False

    layout_excluded = excluded_indices_from_layout_prepared_chunks(task_state)
    if not layout_excluded or len(layout_excluded) >= total:
        return False

    segments_metadata = task_state.get("segments_metadata") or {}
    existing_dict = segments_metadata.get("excluded_segments") or {}
    rebuilt: dict[int, ExclusionReason] = {}
    for idx in layout_excluded:
        key = str(idx)
        info = existing_dict.get(key) or existing_dict.get(idx)
        reason_str = None
        if isinstance(info, dict):
            reason_str = info.get("reason")
        elif isinstance(info, str):
            reason_str = info
        if reason_str == ExclusionReason.USER_SELECTED.value:
            reason_str = None
        try:
            reason = ExclusionReason(reason_str) if reason_str else ExclusionReason.UNKNOWN
        except ValueError:
            reason = ExclusionReason.UNKNOWN
        rebuilt[idx] = reason

    _replace_excluded_segments_metadata(task_state, rebuilt)
    logger.warning(
        LogModule.EXCLUSION,
        f"[EXCLUSION-RECONCILE] Task {task_id}: corrected excluded segments "
        f"{len(current)} -> {len(rebuilt)} using layout_prepared_chunks "
        f"(total_segments={total})",
    )
    return True


def complete_translation_with_source_only(
    task_id: str,
    task_state: Optional[dict] = None,
) -> bool:
    """
    When all segments are excluded, fill translation_segments with source as target
    and return True so the caller can skip execute_translate and mark task completed.
    Returns False if not all segments are excluded or source data is missing.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        return False

    from exclusion.core import ExclusionManager

    if not task_state.get("copy_source_only"):
        reconcile_excluded_segments_from_layout(task_state, task_id or "")

    total = _get_total_segment_count(task_state)
    if total <= 0:
        return False
    excluded = ExclusionManager.get_excluded_segments(task_state)
    if len(excluded) != total:
        return False

    cache_info = task_state.get("source_chunks_cache", {})
    source_list = cache_info.get("segments", []) or []

    # Fallback: if cache is missing or length mismatched, try source_preview segments.
    if not source_list or len(source_list) != total:
        preview = task_state.get("source_preview", {}) or {}
        preview_segments = preview.get("segments", []) or []
        if preview_segments and len(preview_segments) == total:
            source_list = preview_segments
        else:
            logger.warning(
                LogModule.TRANS,
                f"[ALL_EXCLUDED] Task {task_id}: source_segments length mismatch "
                f"(cache={len(source_list) if source_list else 0}, preview={len(preview_segments)}, total={total}), "
                f"cannot fill from source"
            )
            return False

    segments_metadata = task_state.get("segments_metadata", {})
    segment_info_list = segments_metadata.get("segment_info", []) or []
    segments_out = []
    for idx in range(total):
        source_text = source_list[idx] if idx < len(source_list) else ""
        if not isinstance(source_text, str):
            source_text = str(source_text) if source_text is not None else ""
        reason = excluded.get(idx)
        reason_value = reason.value if reason is not None else "user_selected"
        seg_info = segment_info_list[idx] if idx < len(segment_info_list) and isinstance(segment_info_list[idx], dict) else {}
        is_image = seg_info.get("is_image", False) or _is_image_segment(source_text)
        # Preserve paragraph break: use separator from segment_info if available, else default newline
        separator_after = seg_info.get("separator_after", "\n\n")
        if not isinstance(separator_after, str):
            separator_after = "\n\n"
        segment_dict = {
            "segment_index": idx,
            "source_text": source_text,
            "target_text": source_text,
            "modified": False,
            "separator_after": separator_after,
            "is_excluded": True,
            "is_image": is_image,
            "is_failed": False,
            "failure_reason": None,
            "needs_retry": False,
            "exclusion_reason": reason_value,
            "exclusion_metadata": {},
        }
        segments_out.append(segment_dict)

    task_state["translation_segments"] = {"segments": segments_out, "metadata": {}}
    logger.info(
        LogModule.TRANS,
        f"[ALL_EXCLUDED] Task {task_id}: All {total} segments excluded; filled translation_segments with source as target, skipping AI translation"
    )
    return True


def exclude_all_segments(
    task_id: str,
    task_state: Optional[dict] = None,
) -> dict:
    """
    Exclude all segments for a task. Segments already excluded (any reason) are kept;
    segments not yet excluded are marked with USER_SELECTED (manual exclusion).
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.TRANS, f"[EXCLUDE_ALL] Task {task_id} not found")
        return {"success": False, "excluded_segment_indices": [], "message": "Task not found"}

    from exclusion.core import ExclusionManager, ExclusionReason

    total = _get_total_segment_count(task_state)
    if total <= 0:
        logger.warning(LogModule.TRANS, f"[EXCLUDE_ALL] Task {task_id}: total segments is 0")
        return {"success": True, "excluded_segment_indices": [], "message": "No segments"}

    current_excluded = ExclusionManager.get_excluded_segments(task_state)
    # Add USER_SELECTED for every index not already excluded
    for idx in range(total):
        if idx not in current_excluded:
            current_excluded[idx] = ExclusionReason.USER_SELECTED
    ExclusionManager.update_excluded_segments(task_state, current_excluded)
    indices = sorted(current_excluded.keys())
    logger.info(LogModule.TRANS,
        f"[EXCLUDE_ALL] Task {task_id}: excluded all {total} segments; {len(indices)} total excluded"
    )
    return {"success": True, "excluded_segment_indices": indices, "total_segments": total}


def restore_auto_exclusion(
    task_id: str,
    task_state: Optional[dict] = None,
) -> dict:
    """
    Restore exclusion state to what Extract completed with (content-based auto-detection).
    Clears user_unexcluded_segments and removes USER_SELECTED so the next layout-extract
    will re-detect exclusions from scratch. Use when user wants to undo manual exclusions
    and one-click excludes, reverting to the initial Extract completion state.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.TRANS, f"[RESTORE_AUTO_EXCLUSION] Task {task_id} not found")
        return {"success": False, "excluded_segment_indices": [], "message": "Task not found"}

    from exclusion.core import ExclusionManager, ExclusionReason
    import time

    if "segments_metadata" not in task_state:
        task_state["segments_metadata"] = {}
    segments_metadata = task_state["segments_metadata"]

    # CRITICAL: Clear user_unexcluded_segments so layout-extract will re-detect those segments
    segments_metadata["user_unexcluded_segments"] = []
    logger.info(
        LogModule.TRANS,
        f"[RESTORE_AUTO_EXCLUSION] Task {task_id}: Cleared user_unexcluded_segments to allow re-detection",
    )

    current_excluded = ExclusionManager.get_excluded_segments(task_state)
    # Keep only content-based exclusions (remove USER_SELECTED, UNKNOWN)
    remaining = {
        idx: reason for idx, reason in current_excluded.items()
        if not ExclusionReason.is_user_based(reason) and reason != ExclusionReason.UNKNOWN
    }
    excluded_dict_str = {}
    for idx, reason in remaining.items():
        reason_str = reason.value if isinstance(reason, ExclusionReason) else str(reason)
        excluded_dict_str[str(idx)] = {
            "reason": reason_str,
            "detected_at": time.time(),
            "metadata": {},
        }
    segments_metadata["excluded_segments"] = excluded_dict_str
    segments_metadata["excluded_segment_indices"] = sorted(remaining.keys())
    indices = sorted(remaining.keys())
    removed = len(current_excluded) - len(remaining)

    # Sync layout_prepared_chunks so MD translator uses correct is_excluded
    remaining_indices = set(remaining.keys())
    layout_chunks = task_state.get("layout_prepared_chunks")
    if layout_chunks and isinstance(layout_chunks, list):
        updated = 0
        for chunk in layout_chunks:
            if not isinstance(chunk, dict):
                continue
            segment_indices = chunk.get("segment_indices", [])
            is_excluded = bool(
                segment_indices and all(seg_idx in remaining_indices for seg_idx in segment_indices)
            )
            if chunk.get("is_excluded") != is_excluded:
                chunk["is_excluded"] = is_excluded
                chunk["chunk_type"] = "image" if is_excluded else "text"
                chunk["is_image"] = is_excluded
                updated += 1
        if updated:
            logger.info(
                LogModule.TRANS,
                f"[RESTORE_AUTO_EXCLUSION] Task {task_id}: Updated is_excluded on {updated} layout_prepared_chunks",
            )

    logger.info(
        LogModule.TRANS,
        f"[RESTORE_AUTO_EXCLUSION] Task {task_id}: restored to auto exclusion; "
        f"{removed} user exclusions removed, {len(indices)} content-based excluded. "
        "Frontend should call getLayoutExtract to re-detect.",
    )

    _sync_translate_tasks_exclusion_from_convert(task_id, task_state)

    return {"success": True, "excluded_segment_indices": indices, "removed_count": removed}


def _sync_translate_tasks_exclusion_from_convert(convert_task_id: str, convert_state: dict) -> None:
    """Copy reconciled segments_metadata to translate tasks that inherit this convert task."""
    import copy

    try:
        from backend.app.services.task import task_manager
    except Exception:
        return

    metadata_snapshot = copy.deepcopy(convert_state.get("segments_metadata") or {})
    layout_chunks_snapshot = copy.deepcopy(convert_state.get("layout_prepared_chunks") or [])
    if not metadata_snapshot and not layout_chunks_snapshot:
        return

    for other_id, other_state in list(task_manager.tasks.items()):
        if not isinstance(other_state, dict):
            continue
        if other_state.get("convert_task_id") != convert_task_id:
            continue
        if other_id == convert_task_id:
            continue
        if metadata_snapshot:
            other_state["segments_metadata"] = copy.deepcopy(metadata_snapshot)
        if layout_chunks_snapshot:
            other_state["layout_prepared_chunks"] = copy.deepcopy(layout_chunks_snapshot)
        other_state.pop("translation_segments", None)
        other_state.pop("chunk_to_segment_map", None)
        logger.info(
            LogModule.TRANS,
            f"[EXCLUSION-SYNC] Updated translate task {other_id} exclusion state from convert task {convert_task_id}",
        )


def cancel_user_exclusion(
    task_id: str,
    task_state: Optional[dict] = None,
) -> dict:
    """
    Alias for restore_auto_exclusion. Kept for API backward compatibility.
    """
    return restore_auto_exclusion(task_id, task_state)


def clear_all_exclusions_except_image(
    task_id: str,
    task_state: Optional[dict] = None,
) -> dict:
    """
    Remove all exclusions except image segments. Only segments with exclusion_reason IMAGE
    remain excluded; all other segments (formula, reference, identifier, user_selected, etc.)
    are cleared from exclusion.
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.TRANS, f"[CLEAR_ALL_EXCEPT_IMAGE] Task {task_id} not found")
        return {"success": False, "excluded_segment_indices": [], "message": "Task not found"}

    from exclusion.core import ExclusionManager, ExclusionReason
    import time

    current_excluded = ExclusionManager.get_excluded_segments(task_state)
    # Keep only segments that are excluded as IMAGE
    image_only = {
        idx: reason for idx, reason in current_excluded.items()
        if reason == ExclusionReason.IMAGE
    }
    if "segments_metadata" not in task_state:
        task_state["segments_metadata"] = {}
    segments_metadata = task_state["segments_metadata"]
    excluded_dict_str = {}
    for idx, reason in image_only.items():
        reason_str = reason.value if isinstance(reason, ExclusionReason) else str(reason)
        excluded_dict_str[str(idx)] = {
            "reason": reason_str,
            "detected_at": time.time(),
            "metadata": {},
        }
    segments_metadata["excluded_segments"] = excluded_dict_str
    segments_metadata["excluded_segment_indices"] = sorted(image_only.keys())
    indices = sorted(image_only.keys())
    removed = len(current_excluded) - len(image_only)

    # CRITICAL: Add cleared (non-image) segments to user_unexcluded_segments so that when
    # get_layout_extract runs exclusion detection again, it will NOT re-exclude them.
    # Without this, layout-extract overwrites segments_metadata with content-based detection.
    unexcluded_indices = sorted(set(current_excluded.keys()) - set(image_only.keys()))
    if unexcluded_indices:
        existing = segments_metadata.get("user_unexcluded_segments", []) or []
        existing_set = set(existing)
        for idx in unexcluded_indices:
            if idx not in existing_set:
                existing_set.add(idx)
        segments_metadata["user_unexcluded_segments"] = sorted(existing_set)
        logger.info(
            LogModule.TRANS,
            f"[CLEAR_ALL_EXCEPT_IMAGE] Task {task_id}: Added {len(unexcluded_indices)} segments to "
            f"user_unexcluded_segments (total={len(existing_set)}) to prevent re-detection in layout-extract",
        )

    # CRITICAL: Sync layout_prepared_chunks so MD translator uses correct is_excluded.
    # Translator reads is_excluded from each chunk; without this, cleared segments stay excluded.
    image_only_indices = set(image_only.keys())
    layout_chunks = task_state.get("layout_prepared_chunks")
    if layout_chunks and isinstance(layout_chunks, list):
        updated = 0
        for chunk in layout_chunks:
            if not isinstance(chunk, dict):
                continue
            segment_indices = chunk.get("segment_indices", [])
            # Chunk is excluded only if ALL its segments are image (remain excluded).
            is_excluded = bool(
                segment_indices and all(seg_idx in image_only_indices for seg_idx in segment_indices)
            )
            if chunk.get("is_excluded") != is_excluded:
                chunk["is_excluded"] = is_excluded
                chunk["chunk_type"] = "image" if is_excluded else "text"
                chunk["is_image"] = is_excluded
                updated += 1
        if updated:
            logger.info(
                LogModule.TRANS,
                f"[CLEAR_ALL_EXCEPT_IMAGE] Task {task_id}: Updated is_excluded on {updated} layout_prepared_chunks to match image-only exclusion",
            )

    logger.info(LogModule.TRANS,
        f"[CLEAR_ALL_EXCEPT_IMAGE] Task {task_id}: cleared all non-image exclusions; "
        f"{removed} removed, {len(indices)} image segments still excluded"
    )
    return {"success": True, "excluded_segment_indices": indices, "removed_count": removed}


def update_exclusion_reason(
    task_id: str,
    segment_index: int,
    new_reason: Optional[str] = None,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Update exclusion reason for a segment (user-initiated operation).
    
    This function allows users to manually modify exclusion data in Translate phase.
    It directly updates segments_metadata.excluded_segments without triggering auto-detection.
    
    Supports both Extract phase (segments_metadata.excluded_segments) and Translate phase (translation_segments).
    
    Args:
        task_id: Task identifier
        segment_index: Segment index
        new_reason: New exclusion reason (None to remove exclusion)
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    
    Note:
        - This is a user-initiated operation, NOT an auto-detection
        - It directly updates segments_metadata.excluded_segments
        - It does NOT trigger any automatic exclusion detection
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            logger.warning(LogModule.TRANS, f"Task {task_id} not found for updating exclusion reason")
            return None
    
    from exclusion.core import ExclusionReason, ExclusionManager
    
    # Try to find segment in translation_segments first (Translate phase)
    segments_data = task_state.get("translation_segments")
    segment = None
    
    if segments_data:
        # Handle both dict and list formats
        if isinstance(segments_data, dict):
            segments = segments_data.get("segments", [])
        elif isinstance(segments_data, list):
            segments = segments_data
        else:
            segments = []
        
        # Find segment by segment_index
        for seg in segments:
            if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
                segment = seg
                break
    
    # If segment found in translation_segments, update it
    if segment is not None:
        segments_metadata = task_state.get("segments_metadata", {})
        
        if new_reason is None:
            # Remove exclusion
            # Get the original exclusion reason to check if it was content-based
            current_excluded = ExclusionManager.get_excluded_segments(task_state)
            original_reason = current_excluded.get(segment_index)
            
            segment["is_excluded"] = False
            segment["exclusion_reason"] = None
            segment["exclusion_metadata"] = None
            segment["excluded_at"] = None
            logger.info(LogModule.TRANS, f"Removed exclusion for segment {segment_index} in task {task_id} (from translation_segments)")
            
            # Update segments_metadata using ExclusionManager for consistency
            if segment_index in current_excluded:
                updated_excluded = {idx: reason for idx, reason in current_excluded.items() if idx != segment_index}
                ExclusionManager.update_excluded_segments(task_state, updated_excluded)
            
            # CRITICAL: Record that user explicitly chose to unexclude this segment to prevent re-detection
            # This applies to ALL exclusion types (content-based, language-based, user-based)
            # to prevent get_layout_extract from re-detecting and re-excluding the segment
            if original_reason:
                # Add to user_unexcluded_segments to prevent re-detection in get_layout_extract
                user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
                if segment_index not in user_unexcluded:
                    user_unexcluded.append(segment_index)
                    segments_metadata["user_unexcluded_segments"] = user_unexcluded
                    logger.info(LogModule.TRANS,
                        f"Recorded segment {segment_index} as user-unexcluded (original reason: {original_reason.value}) "
                        f"to prevent re-detection in get_layout_extract. user_unexcluded_segments={user_unexcluded}"
                    )
            else:
                # Log warning if original_reason is None (should not happen if segment was excluded)
                logger.warning(LogModule.TRANS,
                    f"Segment {segment_index} was unexcluded but original_reason is None. "
                    f"This may indicate the segment was not in excluded_segments. "
                    f"current_excluded keys: {list(current_excluded.keys())[:10]}..."
                )
        else:
            # Update exclusion reason
            try:
                # Validate reason
                ExclusionReason(new_reason)
                segment["is_excluded"] = True
                segment["exclusion_reason"] = new_reason
                segment["exclusion_metadata"] = {}  # Clear metadata when manually changed
                segment["excluded_at"] = time.time()
                logger.info(LogModule.TRANS,
                    f"Updated exclusion reason for segment {segment_index} in task {task_id}: "
                    f"{segment.get('exclusion_reason')} -> {new_reason} (from translation_segments)"
                )
                
                # Update segments_metadata using ExclusionManager for consistency
                current_excluded = ExclusionManager.get_excluded_segments(task_state)
                current_excluded[segment_index] = ExclusionReason(new_reason)
                ExclusionManager.update_excluded_segments(task_state, current_excluded)
                
                # CRITICAL: If user re-excludes a segment that was previously user-unexcluded,
                # remove it from user_unexcluded_segments to allow normal detection again
                user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
                if segment_index in user_unexcluded:
                    user_unexcluded = [idx for idx in user_unexcluded if idx != segment_index]
                    segments_metadata["user_unexcluded_segments"] = user_unexcluded
                    logger.info(LogModule.TRANS,
                        f"Removed segment {segment_index} from user_unexcluded_segments "
                        f"(user re-excluded it with reason: {new_reason})"
                    )
            except ValueError:
                logger.error(LogModule.TRANS, f"Invalid exclusion reason: {new_reason}")
                return None
        
        return segment
    
    # If not found in translation_segments, try Extract phase (segments_metadata.excluded_segments)
    segments_metadata = task_state.get("segments_metadata", {})
    
    # CRITICAL: Use ExclusionManager.get_excluded_segments as single source of truth
    # This ensures consistency between is_excluded field and excluded_segments
    current_excluded = ExclusionManager.get_excluded_segments(task_state)
    is_in_excluded_segments = segment_index in current_excluded
    
    # CRITICAL: For Extract phase, we need to check if segment_index is valid
    # Get segment count from source_chunks_cache or segments_metadata
    source_chunks_cache = task_state.get("source_chunks_cache", {})
    cache_segments = source_chunks_cache.get("segments", [])
    total_segments = len(cache_segments) if cache_segments else 0
    
    # Validate segment_index range
    if total_segments > 0 and segment_index >= total_segments:
        logger.warning(LogModule.TRANS,
            f"Segment index {segment_index} is out of range for task {task_id}. "
            f"Total segments: {total_segments}"
        )
        return None
    
    # Check if segment is in excluded_segments or if user wants to add exclusion
    if is_in_excluded_segments or new_reason is not None:
        # Update segments_metadata.excluded_segments using ExclusionManager
        # (current_excluded already retrieved above)
        
        if new_reason is None:
            # Remove exclusion
            # CRITICAL: Only remove if segment is actually in excluded_segments
            # If not, this is a data inconsistency - log warning and return None
            if segment_index not in current_excluded:
                logger.warning(LogModule.TRANS,
                    f"Segment {segment_index} was requested to be unexcluded but is not in excluded_segments. "
                    f"This may indicate a data inconsistency between frontend and backend. "
                    f"current_excluded keys: {list(current_excluded.keys())[:10]}..."
                )
                return None
            
            if segment_index in current_excluded:
                # Get the original exclusion reason to check if it was content-based
                original_reason = current_excluded.get(segment_index)
                
                updated_excluded = {idx: reason for idx, reason in current_excluded.items() if idx != segment_index}
                ExclusionManager.update_excluded_segments(task_state, updated_excluded)
                
                # Also update excluded_segment_indices
                excluded_indices = segments_metadata.get("excluded_segment_indices", [])
                if segment_index in excluded_indices:
                    excluded_indices = [idx for idx in excluded_indices if idx != segment_index]
                    segments_metadata["excluded_segment_indices"] = excluded_indices
                
                # CRITICAL: Record that user explicitly chose to unexclude this segment to prevent re-detection
                # This applies to ALL exclusion types (content-based, language-based, user-based)
                # to prevent get_layout_extract from re-detecting and re-excluding the segment
                if original_reason:
                    # Add to user_unexcluded_segments to prevent re-detection in get_layout_extract
                    user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
                    if segment_index not in user_unexcluded:
                        user_unexcluded.append(segment_index)
                        segments_metadata["user_unexcluded_segments"] = user_unexcluded
                        logger.info(LogModule.TRANS,
                            f"Recorded segment {segment_index} as user-unexcluded (original reason: {original_reason.value}) "
                            f"to prevent re-detection in get_layout_extract. user_unexcluded_segments={user_unexcluded}"
                        )
                else:
                    # Log warning if original_reason is None (should not happen if segment was excluded)
                    logger.warning(LogModule.TRANS,
                        f"Segment {segment_index} was unexcluded but original_reason is None (Extract phase). "
                        f"This may indicate the segment was not in excluded_segments. "
                        f"current_excluded keys: {list(current_excluded.keys())[:10]}..."
                    )
                
                logger.info(LogModule.TRANS, f"Removed exclusion for segment {segment_index} in task {task_id} (from segments_metadata)")
        else:
            # Update exclusion reason
            try:
                # Validate reason
                ExclusionReason(new_reason)
                current_excluded[segment_index] = ExclusionReason(new_reason)
                ExclusionManager.update_excluded_segments(
                    task_state,
                    current_excluded,
                    metadata={segment_index: {}}  # Clear metadata when manually changed
                )
                
                # Also update excluded_segment_indices
                excluded_indices = segments_metadata.get("excluded_segment_indices", [])
                if segment_index not in excluded_indices:
                    excluded_indices.append(segment_index)
                    excluded_indices.sort()
                    segments_metadata["excluded_segment_indices"] = excluded_indices
                
                # CRITICAL: If user re-excludes a segment that was previously user-unexcluded,
                # remove it from user_unexcluded_segments to allow normal detection again
                user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
                if segment_index in user_unexcluded:
                    user_unexcluded = [idx for idx in user_unexcluded if idx != segment_index]
                    segments_metadata["user_unexcluded_segments"] = user_unexcluded
                    logger.info(LogModule.TRANS,
                        f"Removed segment {segment_index} from user_unexcluded_segments "
                        f"(user re-excluded it with reason: {new_reason})"
                    )
                
                logger.info(LogModule.TRANS,
                    f"Updated exclusion reason for segment {segment_index} in task {task_id}: "
                    f"-> {new_reason} (from segments_metadata)"
                )
            except ValueError:
                logger.error(LogModule.TRANS,f"Invalid exclusion reason: {new_reason}")
                return None
        
        # Return a mock segment dict for consistency with API response
        return {
            "segment_index": segment_index,
            "is_excluded": new_reason is not None,
            "exclusion_reason": new_reason,
            "exclusion_metadata": {},
        }
    
    # Segment not found in either location
    # CRITICAL: In Extract phase, if segment is not in excluded_segments and new_reason is None,
    # this means user is trying to unexclude a segment that was never excluded
    # This is a valid operation - we should allow it and return a success response
    if new_reason is None:
        # User wants to unexclude, but segment is not in excluded_segments
        # This is fine - just return success (segment is already not excluded)
        logger.info(LogModule.TRANS,
            f"Segment index {segment_index} is not excluded in task {task_id}. "
            f"No action needed (already unexcluded)."
        )
        return {
            "segment_index": segment_index,
            "is_excluded": False,
            "exclusion_reason": None,
            "exclusion_metadata": {},
        }
    
    # If new_reason is not None but segment is not in excluded_segments and not in translation_segments,
    # this means we're trying to add exclusion to a segment that doesn't exist
    logger.warning(LogModule.TRANS,
        f"Segment index {segment_index} not found in segments for task {task_id}. "
        f"Cannot update exclusion reason. "
        f"total_segments={total_segments if 'total_segments' in locals() else 'unknown'}, "
        f"is_in_excluded_segments={is_in_excluded_segments}, "
        f"new_reason={new_reason}"
    )
    return None


async def retranslate_segment(
    task_id: str,
    segment_index: int,
    platform_key: Optional[str] = None,
    to_lang: Optional[str] = None,  # CRITICAL: User's current target language selection (highest priority)
    user_prompt: Optional[str] = None,  # Optional user prompt for retry (e.g. "请帮我翻译人名")
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Retranslate a single segment using a different AI platform.
    
    Args:
        task_id: Task identifier
        segment_index: Segment index to retranslate
        platform_key: Optional platform key to use (if None, uses default from task config)
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Updated segment dictionary, or None if not found
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            logger.warning(LogModule.TRANS, f"Task {task_id} not found")
            return None
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS,f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # CRITICAL: Find segment by segment_index, not by array index
    # Segments list may not be in segment_index order after modifications
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        logger.warning(LogModule.TRANS,f"Segment index {segment_index} not found in segments for task {task_id}")
        return None
    
    # Skip if segment is excluded, unless user explicitly marked it for retry
    if segment.get("is_excluded", False) and not segment.get("needs_retry", False):
        logger.info(LogModule.TRANS, f"Skipping retranslation of excluded segment {segment_index} for task {task_id}")
        return segment
    
    # CRITICAL: Skip if segment is cleared (status="cleared")
    # Cleared segments should not be retranslated to preserve user's intent to clear them
    if segment.get("status") == "cleared":
        logger.info(LogModule.TRANS, f"Skipping retranslation of cleared segment {segment_index} for task {task_id}")
        return segment
    
    source_text = segment.get("source_text", "")
    
    if not source_text:
        logger.warning(LogModule.TRANS, f"Segment {segment_index} has no source text for task {task_id}")
        return None
    
    try:
        # Get task payload/config to extract translation settings
        payload = task_state.get("payload")
        if not payload:
            logger.error(LogModule.TRANS, f"No payload found in task state for task {task_id}")
            return None
        
        # Get platform configuration
        from backend.config.config_loader import get_unified_config
        from backend.config.secrets_manager import get_secrets_manager
        unified_config = get_unified_config()
        secrets_manager = get_secrets_manager()
        
        # Determine which platform to use
        if platform_key:
            selected_platform_key = platform_key
        else:
            # Use default platform from task config or unified config
            # Try to get from payload first, then from unified config
            default_platform = None
            if hasattr(payload, 'ai_platform'):
                default_platform = payload.ai_platform
            elif hasattr(payload, 'platform_type'):
                # Legacy support: platform_type might be the platform key
                default_platform = payload.platform_type
            
            # Get from unified config if not in payload
            if not default_platform:
                default_platform = unified_config.ai_platforms_default_platform or 'deepseek'
            
            selected_platform_key = default_platform
        
        # Get platform configuration from unified config
        platform_config_dict = unified_config.get_ai_platform_config(selected_platform_key)
        if not platform_config_dict:
            raise ValueError(f"Platform '{selected_platform_key}' not found in configuration")
        
        # Convert dict to object-like interface for compatibility
        class PlatformConfigObj:
            def __init__(self, config_dict):
                for key, value in config_dict.items():
                    setattr(self, key, value)
        
        platform_config_obj = PlatformConfigObj(platform_config_dict)
        if not platform_config_obj:
            raise ValueError(f"Platform '{selected_platform_key}' not found in configuration")
        
        # Get platform API credentials
        base_url = platform_config_obj.url or ''
        model_id = platform_config_obj.model or ''

        # Check if platform requires API key (Ollama, local deployments don't)
        requires_api_key = getattr(platform_config_obj, 'requires_api_key', True)

        # Get API key from secrets manager
        api_key = secrets_manager.get_api_keys().get(selected_platform_key, '')

        # Validate platform configuration
        # For platforms that don't require API key (e.g., Ollama), only check base_url
        if not base_url:
            raise ValueError(
                f"Platform '{selected_platform_key}' is not properly configured: base_url is missing"
            )

        if requires_api_key and not api_key:
            raise ValueError(
                f"Platform '{selected_platform_key}' is not properly configured "
                f"(requires_api_key=True but api_key is missing)"
            )
        
        # CRITICAL: Get translation settings from multiple sources (priority order):
        # 1. translation_segments metadata (from translation phase) - highest priority
        # 2. task_state config (if available)
        # 3. payload (fallback)
        segments_data = task_state.get("translation_segments")
        segments_metadata = {}
        if segments_data and isinstance(segments_data, dict):
            segments_metadata = segments_data.get("metadata", {})
        
        # CRITICAL: Priority order for target_lang:
        # 1. User's current selection (to_lang parameter from frontend) - highest priority
        # 2. Translation phase stored target_lang (from metadata)
        # 3. Payload to_lang (fallback)
        # CRITICAL: Always initialize workflow_type regardless of to_lang source
        workflow_type = None
        
        if to_lang:
            # User's current selection takes highest priority
            logger.info(LogModule.TRANS, f"[RETRY] Task {task_id}: Using target_lang={to_lang} from user's current selection (frontend)")
            # Still need to get workflow_type from metadata or payload
            if isinstance(segments_metadata, dict):
                workflow_type = segments_metadata.get("workflow_type")
            if not workflow_type:
                workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
        elif isinstance(segments_metadata, dict):
            # Get target_lang from metadata (from translation phase)
            metadata_target_lang = segments_metadata.get("target_lang")
            if metadata_target_lang:
                to_lang = metadata_target_lang
                logger.info(LogModule.TRANS, f"[RETRY] Task {task_id}: Using target_lang={to_lang} from translation_segments metadata")
            else:
                # Fallback to payload
                to_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', 'en')
                logger.warning(LogModule.TRANS, f"[RETRY] Task {task_id}: target_lang not found in metadata, using payload.to_lang={to_lang}")
            
            # Get workflow_type from metadata to determine agent type
            workflow_type = segments_metadata.get("workflow_type")
            if not workflow_type:
                # Fallback to payload or segments_metadata
                workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
        else:
            # Fallback to payload if metadata is not available
            if not to_lang:
                to_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', 'en')
                logger.warning(LogModule.TRANS, f"[RETRY] Task {task_id}: translation_segments metadata not available, using payload.to_lang={to_lang}")
            workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
        
        # Get custom_prompt: user_prompt from frontend (retry) overrides task config and payload
        custom_prompt = (user_prompt or '').strip()
        if not custom_prompt:
            task_config = task_state.get("config", {})
            if isinstance(task_config, dict):
                custom_prompt = task_config.get("custom_prompt", '') or ''
            if not custom_prompt:
                custom_prompt = getattr(payload, 'custom_prompt', '') or ''
        if custom_prompt:
            logger.info(LogModule.TRANS, f"[RETRY] Task {task_id}: Using custom_prompt for retranslate (length={len(custom_prompt)})")
        
        # Get other settings from payload
        temperature = getattr(payload, 'temperature', 0.3)
        thinking = getattr(payload, 'thinking', False)
        timeout = getattr(payload, 'timeout', 1200)
        write_timeout = getattr(payload, 'write_timeout', None)
        retry = getattr(payload, 'retry', 5)
        
        # Get chunk_size from payload or use default (for send_chunks_async parameter)
        chunk_size = getattr(payload, 'chunk_size', None) or 2000
        
        # CRITICAL: Determine agent type based on workflow_type
        # JSON/XLSX/TXT/SRT/QT_TS use SegmentsTranslateAgent (JSON format)
        # DOCX/PPTX/PDF/MD/HTML use MDTranslateAgent (Markdown format)
        use_segments_agent = False
        if workflow_type in ['json', 'xlsx', 'txt', 'srt', 'qt_ts']:
            use_segments_agent = True
            logger.info(LogModule.TRANS, f"[RETRY] Task {task_id}: Using SegmentsTranslateAgent for workflow_type={workflow_type}")
        else:
            logger.info(LogModule.TRANS, f"[RETRY] Task {task_id}: Using MDTranslateAgent for workflow_type={workflow_type}")
        
        # Create agent for translation (use same agent type as translation phase)
        if use_segments_agent:
            from agents.segments_agent import SegmentsTranslateAgent, SegmentsTranslateAgentConfig
            
            agent_config = SegmentsTranslateAgentConfig(
                custom_prompt=custom_prompt,
                to_lang=to_lang,
                base_url=base_url,
                api_key=api_key,
                model_id=model_id,
                temperature=temperature,
                thinking=thinking,
                concurrent=1,  # Single segment translation
                connect_timeout=15,
                timeout=timeout,
                write_timeout=write_timeout,
                logger=logger,
                glossary_dict=None,  # TODO: Load glossary if available
                retry=retry,
                segment_limit=1,  # Single segment — always limit to 1
            )

            agent = SegmentsTranslateAgent(agent_config)
        else:
            from agents import MDTranslateAgent
            from agents.markdown_agent import MDTranslateAgentConfig
            
            agent_config = MDTranslateAgentConfig(
                custom_prompt=custom_prompt,
                to_lang=to_lang,
                base_url=base_url,
                api_key=api_key,
                model_id=model_id,
                temperature=temperature,
                thinking=thinking,
                concurrent=1,  # Single segment translation
                connect_timeout=15,
                timeout=timeout,
                write_timeout=write_timeout,
                logger=logger,
                glossary_dict=None,  # TODO: Load glossary if available
                retry=retry
            )
            
            agent = MDTranslateAgent(agent_config)
        
        # CRITICAL: Set task_state on agent so it can save API logs
        # This allows the agent to store llm_api_input and llm_api_output in task_state
        agent.task_state = task_state
        agent.task_id = task_id
        
        # CRITICAL: Use appropriate method based on agent type
        if use_segments_agent:
            # SegmentsTranslateAgent uses send_segments_async (JSON format)
            # NOTE: send_segments_async expects chunk_size in tokens (not bytes)
            results = await agent.send_segments_async(
                [source_text],
                chunk_size=chunk_size  # Pass chunk_size in tokens (SegmentsTranslateAgent handles conversion)
            )
            if not results or len(results) == 0:
                raise ValueError(f"Translation failed: empty response from AI platform")
            translated_text = results[0]
        else:
            # MDTranslateAgent: use SEG-tag format even for single-segment retry so behavior
            # is consistent with the main markdown/PDF pipeline and never leaks marker lines.

            prompt = f"[SEG {segment_index}]:\n{source_text}"
            results = await agent.send_prompts_async(
                prompts=[prompt],
                pre_send_handler=agent._pre_send_handler,  # type: ignore[attr-defined]
                progress_callback=None,
            )
            if not results or len(results) == 0:
                raise ValueError(f"Translation failed: empty response from AI platform")

            raw_output = results[0]
            if not isinstance(raw_output, str):
                translated_text = str(raw_output)
            else:
                parsed = parse_seg_output(raw_output)
                translated_text = parsed.get(segment_index, "")
                if not translated_text and parsed:
                    # Found segments but not our idx — take first available
                    translated_text = next(iter(parsed.values()))
                if not translated_text:
                    # Last resort: use raw output as-is
                    translated_text = raw_output.strip()
        
        if not translated_text or not isinstance(translated_text, str):
            raise ValueError(f"Translation failed: invalid response from AI platform")
        
        # Check if translation actually succeeded (not empty and not same as source)
        translated_text = translated_text.strip()
        source_text_stripped = source_text.strip()
        
        if not translated_text:
            # Empty translation is always failure
            failure_reason = "Translation failed: empty response from AI platform"
            segment["is_failed"] = True
            segment["failure_reason"] = failure_reason
            segment["status"] = "failed"
            segment["retry_count"] = segment.get("retry_count", 0) + 1
            
            logger.warning(LogModule.TRANS,
                f"Retranslation failed for segment {segment_index} in task {task_id}: {failure_reason}"
            )
            
            return segment
        
        # Check if translation result is same as source and if it should be treated as failure
        if translated_text == source_text_stripped:
            from utils.translation_validator import should_treat_as_failure
            
            is_failure, reason = should_treat_as_failure(source_text_stripped, translated_text)
            
            if is_failure:
                # Mark segment as failed
                segment["is_failed"] = True
                segment["failure_reason"] = reason
                segment["status"] = "failed"
                segment["retry_count"] = segment.get("retry_count", 0) + 1
                # Don't update target_text, keep the old one
                
                logger.warning(LogModule.TRANS,
                    f"Retranslation failed for segment {segment_index} in task {task_id}: {reason}"
                )
                
                return segment
            else:
                # Same text but likely doesn't need translation (e.g., "1、2")
                # Treat as successful translation (no change needed)
                logger.info(LogModule.TRANS,
                    f"Retranslation for segment {segment_index} in task {task_id}: {reason}. "
                    f"Keeping original text (content likely doesn't need translation)."
                )
                # Mark as successful but don't update target_text (it's already the same)
                segment["is_failed"] = False
                segment["failure_reason"] = None
                segment["status"] = "translated"
                segment["retry_count"] = segment.get("retry_count", 0) + 1
                segment["modified"] = True  # Mark as modified to indicate retry was attempted
                
                # Clear any remaining exclusion flags after successful retranslation
                if segment.get("is_excluded", False):
                    segment["is_excluded"] = False
                    segment["exclusion_reason"] = None
                
                return segment
        
        # Update segment
        old_platform = segment.get("platform_used")
        used_platforms = segment.get("used_platforms", [])
        if not isinstance(used_platforms, list):
            used_platforms = []
        
        # Add old platform to used list if not already there
        if old_platform and old_platform not in used_platforms:
            used_platforms.append(old_platform)
        
        # Add current platform to used list
        if selected_platform_key not in used_platforms:
            used_platforms.append(selected_platform_key)
        
        segment["target_text"] = translated_text
        segment["target_length"] = len(translated_text)
        segment["platform_used"] = selected_platform_key
        segment["used_platforms"] = used_platforms
        segment["retry_count"] = segment.get("retry_count", 0) + 1
        segment["is_failed"] = False
        segment["failure_reason"] = None
        segment["needs_retry"] = False
        segment["status"] = "translated"
        # Mark segment as modified so it will be included in document rebuild
        segment["modified"] = True
        # CRITICAL: Clear old manual modification so get_source_preview doesn't fallback to stale text
        segment["modified_text"] = None
        
        # Clear any remaining exclusion flags after successful retranslation
        if segment.get("is_excluded", False):
            segment["is_excluded"] = False
            segment["exclusion_reason"] = None
        
        logger.info(LogModule.TRANS,
            f"Retranslated segment {segment_index} for task {task_id} using platform '{selected_platform_key}' "
            f"(retry count: {segment['retry_count']})"
        )
        
        # Save API logs to temp directory (Retry1 subfolder)
        # Determine retry folder name based on retry_count
        retry_folder = f"Retry{segment['retry_count']}"
        try:
            from utils.chunk_translation_helper import save_api_logs_to_temp_dir

            # Collect LLM API parameters for diagnosis
            llm_api_params = {
                'model_id': model_id,
                'temperature': temperature,
                'thinking': thinking,
                'chunk_size': chunk_size,
                'platform_key': selected_platform_key,
                'to_lang': to_lang,
                'agent_type': 'SegmentsTranslateAgent' if use_segments_agent else 'MDTranslateAgent',
                'segment_index': segment_index,
            }

            save_api_logs_to_temp_dir(
                task_state=task_state,
                task_id=task_id,
                subfolder=retry_folder,
                llm_api_input=task_state.get('llm_api_input'),
                llm_api_output=task_state.get('llm_api_output'),
                llm_api_system_prompt=task_state.get('llm_api_system_prompt'),
                llm_api_params=llm_api_params,  # API parameters for diagnosis
                segment_index=segment_index,  # CRITICAL: Pass segment_index to create separate file per segment
            )
        except Exception as log_e:
            logger.warning(LogModule.TRANS,
                f"Failed to save API logs for retry segment {segment_index} in task {task_id}: {log_e}",
                exc_info=True
            )
        
        return segment
        
    except Exception as e:
        logger.error(LogModule.TRANS, f"Failed to retranslate segment {segment_index} for task {task_id}: {str(e)}", exc_info=True)
        
        # Mark segment as failed
        segment["is_failed"] = True
        segment["failure_reason"] = str(e)
        segment["status"] = "failed"
        
        return segment


async def retranslate_segments_batch(
    task_id: str,
    segment_indices: List[int],
    platform_key: Optional[str] = None,
    user_prompt: Optional[str] = None,  # Optional user prompt for retry (e.g. "请帮我翻译人名")
    task_state: Optional[dict] = None,
    to_lang_from_frontend: Optional[str] = None,
) -> Dict[int, Optional[dict]]:
    """
    Batch retranslate multiple segments together to enable chunk merging.
    
    This function collects all segments to retry and translates them together,
    which allows MDTranslateAgent.send_chunks_async to merge small chunks together,
    reducing API calls and improving efficiency.
    
    Args:
        task_id: Task identifier
        segment_indices: List of segment indices to retranslate
        platform_key: Optional platform key to use (if None, uses default from task config)
        task_state: Task state dictionary (if None, will be imported)
    
    Returns:
        Dictionary mapping segment_index to updated segment dictionary (or None if not found)
    """
    if task_state is None:
        from backend.app.services.task import task_manager
        task_state = task_manager.get_task(task_id)
        if task_state is None:
            logger.warning(LogModule.TRANS, f"Task {task_id} not found")
            return {}
    
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.warning(LogModule.TRANS,f"No translation segments found for task {task_id}")
        return {}
    
    segments = segments_data.get("segments", [])
    
    # Collect all segments to retry
    segments_to_retry = []
    
    for seg_idx, seg in enumerate(segments):
        segment_index = None
        if isinstance(seg, dict):
            segment_index = seg.get("segment_index")
        elif hasattr(seg, "segment_index"):
            segment_index = seg.segment_index
        
        if segment_index in segment_indices:
            # Skip if segment is excluded or cleared
            is_excluded = seg.get("is_excluded", False) if isinstance(seg, dict) else getattr(seg, "is_excluded", False)
            status = seg.get("status") if isinstance(seg, dict) else getattr(seg, "status", None)
            
            needs_retry = seg.get("needs_retry", False) if isinstance(seg, dict) else getattr(seg, "needs_retry", False)
            if (not is_excluded or needs_retry) and status != "cleared":
                source_text = seg.get("source_text") if isinstance(seg, dict) else getattr(seg, "source_text", "")
                if source_text:
                    segments_to_retry.append({
                        "segment_index": segment_index,
                        "source_text": source_text,
                        "segment": seg,
                        "array_index": seg_idx
                    })
    
    if not segments_to_retry:
        logger.warning(LogModule.TRANS,f"No valid segments to retry for task {task_id}")
        return {}
    
    # Get platform configuration (same logic as retranslate_segment)
    payload = task_state.get("payload")
    if not payload:
        logger.error(LogModule.TRANS, f"No payload found in task state for task {task_id}")
        return {}
    
    from backend.config.config_loader import get_unified_config
    from backend.config.secrets_manager import get_secrets_manager
    unified_config = get_unified_config()
    secrets_manager = get_secrets_manager()
    
    # Determine which platform to use
    if platform_key:
        selected_platform_key = platform_key
    else:
        default_platform = None
        if hasattr(payload, 'ai_platform'):
            default_platform = payload.ai_platform
        elif hasattr(payload, 'platform_type'):
            default_platform = payload.platform_type
        
        if not default_platform:
            default_platform = unified_config.ai_platforms_default_platform or 'deepseek'
        
        selected_platform_key = default_platform
    
    # Get platform configuration
    platform_config_dict = unified_config.get_ai_platform_config(selected_platform_key)
    if not platform_config_dict:
        raise ValueError(f"Platform '{selected_platform_key}' not found in configuration")
    
    class PlatformConfigObj:
        def __init__(self, config_dict):
            for key, value in config_dict.items():
                setattr(self, key, value)
    
    platform_config_obj = PlatformConfigObj(platform_config_dict)

    # Get platform API credentials
    base_url = platform_config_obj.url or ''
    model_id = platform_config_obj.model or ''

    # Check if platform requires API key (Ollama, local deployments don't)
    requires_api_key = getattr(platform_config_obj, 'requires_api_key', True)

    # Get segment_limit from platform config (max segments per batch, 0 = unlimited)
    segment_limit = getattr(platform_config_obj, 'segment_limit', 100)
    if segment_limit is None:
        segment_limit = 100
    if not isinstance(segment_limit, int) or segment_limit < 0:
        logger.warning(
            LogModule.TRANS,
            f"[BATCH_RETRY] Task {task_id}: Invalid segment_limit '{segment_limit}', falling back to 100"
        )
        segment_limit = 100
    logger.info(
        LogModule.TRANS,
        f"[BATCH_RETRY] Task {task_id}: Platform '{selected_platform_key}' segment_limit={segment_limit} (0=unlimited)"
    )

    api_key = secrets_manager.get_api_keys().get(selected_platform_key, '')

    # Validate platform configuration
    # For platforms that don't require API key (e.g., Ollama), only check base_url
    if not base_url:
        raise ValueError(
            f"Platform '{selected_platform_key}' is not properly configured: base_url is missing"
        )

    if requires_api_key and not api_key:
        raise ValueError(
            f"Platform '{selected_platform_key}' is not properly configured "
            f"(requires_api_key=True but api_key is missing)"
        )
    
    # CRITICAL: Get translation settings from multiple sources (priority order):
    # 1. User's current selection (to_lang parameter from frontend) - highest priority
    # 2. Translation phase stored target_lang (from metadata)
    # 3. Payload to_lang (fallback)
    # CRITICAL: Always initialize workflow_type regardless of to_lang source
    workflow_type = None
    segments_metadata = segments_data.get("metadata", {})
    to_lang = to_lang_from_frontend  # Initialize from parameter
    
    if to_lang:
        # User's current selection takes highest priority
        logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Using target_lang={to_lang} from user's current selection (frontend)")
        # Still need to get workflow_type from metadata or payload
        if isinstance(segments_metadata, dict):
            workflow_type = segments_metadata.get("workflow_type")
        if not workflow_type:
            workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
    elif isinstance(segments_metadata, dict):
        # Get target_lang from metadata (from translation phase)
        metadata_target_lang = segments_metadata.get("target_lang")
        if metadata_target_lang:
            to_lang = metadata_target_lang
            # Reduced to debug level to reduce log verbosity
            logger.debug(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Using target_lang={to_lang} from translation_segments metadata")
        else:
            # Fallback to payload
            to_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', 'en')
            logger.warning(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: target_lang not found in metadata, using payload.to_lang={to_lang}")
        
        # Get workflow_type from metadata to determine agent type
        workflow_type = segments_metadata.get("workflow_type")
        if not workflow_type:
            # Fallback to payload or segments_metadata
            workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
    else:
        # Fallback to payload if metadata is not available
        if not to_lang:
            to_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', 'en')
            logger.warning(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: translation_segments metadata not available, using payload.to_lang={to_lang}")
        workflow_type = getattr(payload, 'workflow_type', None) or task_state.get("segments_metadata", {}).get("workflow_type")
    
    # Get custom_prompt: user_prompt from frontend (retry) overrides task config and payload
    custom_prompt = (user_prompt or '').strip()
    if not custom_prompt:
        task_config = task_state.get("config", {})
        if isinstance(task_config, dict):
            custom_prompt = task_config.get("custom_prompt", '') or ''
        if not custom_prompt:
            custom_prompt = getattr(payload, 'custom_prompt', '') or ''
    if custom_prompt:
        logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Using custom_prompt for retranslate (length={len(custom_prompt)})")
    
    # Get other settings from payload
    temperature = getattr(payload, 'temperature', 0.3)
    thinking = getattr(payload, 'thinking', False)
    timeout = getattr(payload, 'timeout', 1200)
    write_timeout = getattr(payload, 'write_timeout', None)
    retry = getattr(payload, 'retry', 5)
    chunk_size = getattr(payload, 'chunk_size', None) or 2000  # CRITICAL: Get chunk_size for merging
    
    # CRITICAL: Determine agent type based on workflow_type
    # JSON/XLSX/TXT/SRT/QT_TS use SegmentsTranslateAgent (JSON format)
    # DOCX/PPTX/PDF/MD/HTML use MDTranslateAgent (Markdown format)
    use_segments_agent = False
    if workflow_type in ['json', 'xlsx', 'txt', 'srt', 'qt_ts']:
        use_segments_agent = True
        # Reduced to debug level to reduce log verbosity
        logger.debug(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Using SegmentsTranslateAgent for workflow_type={workflow_type}")
    else:
        # Reduced to debug level to reduce log verbosity
        logger.debug(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Using MDTranslateAgent for workflow_type={workflow_type}")
    
    # Create agent for translation (use same agent type as translation phase)
    if use_segments_agent:
        from agents.segments_agent import SegmentsTranslateAgent, SegmentsTranslateAgentConfig
        
        agent_config = SegmentsTranslateAgentConfig(
            custom_prompt=custom_prompt,
            to_lang=to_lang,
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
            thinking=thinking,
            concurrent=1,  # Batch translation
            connect_timeout=15,
            timeout=timeout,
            write_timeout=write_timeout,
            logger=logger,
            glossary_dict=None,  # TODO: Load glossary if available
            retry=retry,
            segment_limit=segment_limit,  # Pass platform's segment_limit
        )

        agent = SegmentsTranslateAgent(agent_config)
    else:
        from agents import MDTranslateAgent
        from agents.markdown_agent import MDTranslateAgentConfig
        
        agent_config = MDTranslateAgentConfig(
            custom_prompt=custom_prompt,
            to_lang=to_lang,
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
            thinking=thinking,
            concurrent=1,  # Batch translation
            connect_timeout=15,
            timeout=timeout,
            write_timeout=write_timeout,
            logger=logger,
            glossary_dict=None,  # TODO: Load glossary if available
            retry=retry
        )

        agent = MDTranslateAgent(agent_config)
    
    # CRITICAL: Set task_state on agent so it can save API logs
    agent.task_state = task_state
    agent.task_id = task_id
    
    # Collect all source texts and segment indices
    source_texts = [seg["source_text"] for seg in segments_to_retry]
    segment_indices_list = [seg["segment_index"] for seg in segments_to_retry]
    
    # CRITICAL: Initialize progress callback for retry (similar to translation phase)
    # Start at 10%, then update based on chunk progress (10%-90%)
    last_logged_progress = {'completed': -1, 'mapped_percent': -1}
    
    def retry_progress_callback(completed: int, total: int, percent: int) -> bool:
        # Map retry progress (0%-100%) to overall progress (10%-90%)
        mapped_percent = 10 + int(percent * 0.8)  # Map 0-100 to 10-90
        task_state["progress"] = mapped_percent
        task_state["message"] = f"Retranslating... {completed}/{total} chunks ({mapped_percent}%)"
        
        # Only log DEBUG when progress actually changes
        if (completed != last_logged_progress['completed'] or 
            mapped_percent != last_logged_progress['mapped_percent']):
            logger.debug(LogModule.TRANS, f"[BATCH_RETRY] Progress: {completed}/{total} chunks ({mapped_percent}%)")
            last_logged_progress['completed'] = completed
            last_logged_progress['mapped_percent'] = mapped_percent
        
        # CRITICAL: Check if batch retry should be cancelled
        # Return True to continue, False to cancel
        if task_state.get("cancel_batch_retry", False):
            logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Cancel signal detected, stopping batch retry")
            return False
        return True
    
    # Set initial progress to 10% (same as translation phase)
    task_state["progress"] = 10
    task_state["message"] = "Preparing retranslation..."
    # CRITICAL: Set status to "processing" so frontend polling continues
    task_state["status"] = "processing"
    logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Starting batch retry for {len(segments_to_retry)} segments (progress: 10%, status=processing)")
    
    # CRITICAL: Clear any previous cancel flag and set batch retry in progress flag
    task_state["cancel_batch_retry"] = False
    task_state["batch_retry_in_progress"] = True
    
    # CRITICAL: Initialize accumulated API logs for batch retry
    # This ensures all chunks are saved to the same file, not overwritten
    accumulated_api_input = []
    accumulated_api_output = []
    accumulated_system_prompt = None
    
    # CRITICAL: Use appropriate method based on agent type
    results: list[Any] = []
    try:
        if use_segments_agent:
            # SegmentsTranslateAgent uses send_segments_async (JSON format)
            # NOTE: send_segments_async expects chunk_size in tokens (not bytes)
            # It internally converts to text_token_limit using get_text_content_token_limit
            logger.info(LogModule.TRANS,
                f"[BATCH_RETRY] Task {task_id}: Translating {len(source_texts)} segments together "
                f"(chunk_size={chunk_size} tokens) using SegmentsTranslateAgent"
            )
            
            # CRITICAL: Check if batch retry was cancelled before sending requests
            if task_state.get("cancel_batch_retry", False):
                logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Cancelled before sending segment requests")
                results = [None] * len(segments_to_retry)
                raise asyncio.CancelledError("Batch retry cancelled by user")
            
            results = await agent.send_segments_async(
                source_texts,
                chunk_size=chunk_size,  # Pass chunk_size in tokens (SegmentsTranslateAgent handles conversion)
                progress_callback=retry_progress_callback  # CRITICAL: Pass progress callback
            )
            
            # CRITICAL: SegmentsTranslateAgent returns list[str], but we need to map to segment_indices
            # The results are in the same order as source_texts, so we can map them directly
            if len(results) != len(segment_indices_list):
                logger.warning(LogModule.TRANS,
                    f"[BATCH_RETRY] Task {task_id}: Results count ({len(results)}) doesn't match segment_indices count ({len(segment_indices_list)})"
                )
        else:
            # MDTranslateAgent: for markdown/PDF/HTML workflows, use SEG-tag format for batch retry
            # Build prompts with segment_limit-based chunking:
            # segment_limit caps max segments per batch; chunk_size caps max tokens per batch.
            # The actual batch size = min(segment_limit, what fits in chunk_size tokens).
            logger.info(
                LogModule.TRANS,
                f"[BATCH_RETRY] Task {task_id}: Translating {len(source_texts)} segments using MDTranslateAgent "
                f"(segment_limit={segment_limit})"
            )

            from utils.json_utils import segments2json_chunks
            from utils.chunk_size_converter import get_text_content_token_limit

            text_token_limit = get_text_content_token_limit(chunk_size)
            retry_segments_list = [seg_info["source_text"] for seg_info in segments_to_retry]
            retry_segment_indices = [seg_info["segment_index"] for seg_info in segments_to_retry]

            # 0 = unlimited, pass None to segments2json_chunks
            max_segs = segment_limit if segment_limit > 0 else None

            indexed_originals, chunks, merged_indices_list = await asyncio.to_thread(
                segments2json_chunks,
                retry_segments_list,
                text_token_limit,
                False,  # merge_small
                retry_segment_indices,
                max_segs,  # max_segments_per_chunk (segment_limit cap)
            )

            # Build SEG-tag prompts for each chunk
            prompts: list[str] = []
            chunk_seg_indices: list[list[int]] = []
            for chunk_dict in chunks:
                lines: list[str] = []
                seg_indices: list[int] = []
                for seg_idx_str, text in chunk_dict.items():
                    seg_index = int(seg_idx_str)
                    lines.append(f"[SEG {seg_index}]:")
                    lines.append(text or "")
                    seg_indices.append(seg_index)
                prompts.append("\n".join(lines))
                chunk_seg_indices.append(seg_indices)

            logger.info(
                LogModule.TRANS,
                f"[BATCH_RETRY] Task {task_id}: Grouped {len(segments_to_retry)} segments into {len(chunks)} chunks "
                f"(segment_limit={segment_limit}, chunk_size={chunk_size}, token_limit={text_token_limit})"
            )

            # CRITICAL: Check if batch retry was cancelled before sending requests
            if task_state.get("cancel_batch_retry", False):
                logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Cancelled before sending requests")
                results = [None] * len(segments_to_retry)
                raise asyncio.CancelledError("Batch retry cancelled by user")

            # Send all prompts/chunks (send_prompts_async handles concurrency)
            raw_results = await agent.send_prompts_async(
                prompts=prompts,
                pre_send_handler=agent._pre_send_handler,  # type: ignore[attr-defined]
                progress_callback=retry_progress_callback,
            )

            if not raw_results or len(raw_results) == 0:
                raise ValueError(f"Translation failed: empty response from AI platform")

            # Parse each response and collect translations
            index_to_translation: dict[int, str] = {}

            for idx, (llm_output, seg_indices_in_chunk) in enumerate(zip(raw_results, chunk_seg_indices)):
                if not isinstance(llm_output, str):
                    llm_output = str(llm_output)

                # Parse [SEG n]: headers back to index -> text
                chunk_parsed: dict[int, str] = parse_seg_output(llm_output)

                if not chunk_parsed:
                    logger.warning(
                        LogModule.TRANS,
                        f"[BATCH_RETRY] Task {task_id}: Request {idx} (segments {seg_indices_in_chunk}): "
                        f"SEG-tag parser found no segments in response",
                    )
                else:
                    # Merge results
                    for seg_index, translated_text in chunk_parsed.items():
                        index_to_translation[seg_index] = translated_text

                    logger.debug(
                        LogModule.TRANS,
                        f"[BATCH_RETRY] Task {task_id}: Request {idx}/{len(prompts)} parsed "
                        f"{len(chunk_parsed)}/{len(seg_indices_in_chunk)} segments"
                    )

            # Build results list in the same order as segments_to_retry
            results = []
            parsed_count = 0
            missing_count = 0
            for seg_info in segments_to_retry:
                seg_index = seg_info["segment_index"]
                translation = index_to_translation.get(seg_index)
                results.append(translation)
                if translation:
                    parsed_count += 1
                else:
                    missing_count += 1

            logger.info(
                LogModule.TRANS,
                f"[BATCH_RETRY] Task {task_id}: Total parsed {parsed_count}/{len(segments_to_retry)} segments, "
                f"{missing_count} missing (segment_limit={segment_limit})"
            )
    except asyncio.CancelledError as e:
        # Handle user cancellation gracefully
        logger.info(LogModule.TRANS, f"[BATCH_RETRY] Task {task_id}: Batch retry cancelled by user")
        task_state["cancel_batch_retry"] = True
        # Return partial results if any, otherwise all None
        if not results:
            results = [None for _ in segments_to_retry]
        elif len(results) != len(segments_to_retry):
            # Pad results with None for missing segments
            results = results + [None] * (len(segments_to_retry) - len(results))
    except Exception as e:
        error_msg = str(e)
        logger.error(
            LogModule.TRANS,
            f"[BATCH_RETRY] Task {task_id}: Agent call failed: {error_msg}",
            exc_info=True,
        )
        # Ensure task state carries the error so UI can display it
        if task_state and not task_state.get("llm_error"):
            task_state["llm_error"] = error_msg
        # Treat all segments as failed so caller sees per-segment errors
        results = [None for _ in segments_to_retry]
        # Set error status so frontend knows retry failed
        task_state["status"] = "completed"
        task_state["progress"] = 100
        task_state["message"] = f"Retranslation failed: {error_msg}"
    
    # CRITICAL: Accumulate API logs from agent (may contain merged chunks)
    # send_chunks_async saves logs to task_state, but we need to accumulate them
    # because multiple chunks may be merged into one API call
    if hasattr(agent, 'task_state') and agent.task_state:
        current_input = agent.task_state.get('llm_api_input', [])
        current_output = agent.task_state.get('llm_api_output', [])
        current_system_prompt = agent.task_state.get('llm_api_system_prompt')
        
        if current_input and current_output:
            accumulated_api_input.extend(current_input)
            accumulated_api_output.extend(current_output)
            if current_system_prompt and not accumulated_system_prompt:
                accumulated_system_prompt = current_system_prompt
    
    if not results or len(results) != len(segments_to_retry):
        raise ValueError(
            f"Translation failed: expected {len(segments_to_retry)} results, got {len(results) if results else 0}"
        )
    
    # Update all segments with translated text
    result_map = {}
    for idx, seg_info in enumerate(segments_to_retry):
        segment_index = seg_info["segment_index"]
        segment = seg_info["segment"]
        translated_text = results[idx] if idx < len(results) else None
        
        if not translated_text or not isinstance(translated_text, str):
            segment["is_failed"] = True
            # Prefer the actual LLM error (e.g., 404, 401) if available
            llm_error = task_state.get("llm_error") if task_state else None
            segment["failure_reason"] = (
                llm_error if llm_error else "Translation failed: invalid response from AI platform"
            )
            segment["status"] = "failed"
            segment["retry_count"] = segment.get("retry_count", 0) + 1
            result_map[segment_index] = segment
            continue
        
        translated_text = translated_text.strip()
        source_text_stripped = seg_info["source_text"].strip()
        
        if not translated_text:
            segment["is_failed"] = True
            segment["failure_reason"] = "Translation failed: empty response from AI platform"
            segment["status"] = "failed"
            segment["retry_count"] = segment.get("retry_count", 0) + 1
            result_map[segment_index] = segment
            continue
        
        if translated_text == source_text_stripped:
            from utils.translation_validator import should_treat_as_failure
            is_failure, reason = should_treat_as_failure(source_text_stripped, translated_text)
            
            if is_failure:
                segment["is_failed"] = True
                segment["failure_reason"] = reason
                segment["status"] = "failed"
                segment["retry_count"] = segment.get("retry_count", 0) + 1
                result_map[segment_index] = segment
                continue
        
        # Update segment
        old_platform = segment.get("platform_used")
        used_platforms = segment.get("used_platforms", [])
        if not isinstance(used_platforms, list):
            used_platforms = []
        
        if old_platform and old_platform not in used_platforms:
            used_platforms.append(old_platform)
        
        if selected_platform_key not in used_platforms:
            used_platforms.append(selected_platform_key)
        
        segment["target_text"] = translated_text
        segment["target_length"] = len(translated_text)
        segment["platform_used"] = selected_platform_key
        segment["used_platforms"] = used_platforms
        segment["retry_count"] = segment.get("retry_count", 0) + 1
        segment["is_failed"] = False
        segment["failure_reason"] = None
        segment["needs_retry"] = False
        segment["status"] = "translated"
        segment["modified"] = True
        # CRITICAL: Clear old manual modification so get_source_preview doesn't fallback to stale text
        segment["modified_text"] = None
        
        # Clear any remaining exclusion flags after successful retranslation
        if segment.get("is_excluded", False):
            segment["is_excluded"] = False
            segment["exclusion_reason"] = None
        
        result_map[segment_index] = segment
    
    # CRITICAL: Sync updated translations back to html_translated_texts so that
    # html workflow export can rebuild the translated HTML from segments.
    if task_state and "html_original_texts" in task_state:
        html_translated_texts = task_state.get("html_translated_texts", [])
        html_modified = False
        for seg_idx, segment in result_map.items():
            if (
                seg_idx is not None
                and 0 <= seg_idx < len(html_translated_texts)
                and not segment.get("is_failed", False)
            ):
                html_translated_texts[seg_idx] = segment["target_text"]
                html_modified = True
        if html_modified:
            task_state["html_translated_texts"] = html_translated_texts
            logger.info(
                LogModule.TRANS,
                f"[BATCH_RETRY] Task {task_id}: Synced {len(result_map)} segment(s) to html_translated_texts"
            )
    
    # Save API logs to temp directory (batch retry)
    # CRITICAL: Use accumulated logs, not task_state (which may be overwritten)
    retry_count = max(seg.get("retry_count", 0) for seg in result_map.values() if seg)
    retry_folder = f"Retry{retry_count}"
    try:
        from utils.chunk_translation_helper import save_api_logs_to_temp_dir
        # Use accumulated logs if available, otherwise fall back to task_state
        api_input_to_save = accumulated_api_input if accumulated_api_input else task_state.get('llm_api_input')
        api_output_to_save = accumulated_api_output if accumulated_api_output else task_state.get('llm_api_output')
        system_prompt_to_save = accumulated_system_prompt if accumulated_system_prompt else task_state.get('llm_api_system_prompt')

        # Collect LLM API parameters for diagnosis
        llm_api_params = {
            'model_id': model_id,
            'temperature': temperature,
            'thinking': thinking,
            'chunk_size': chunk_size,
            'platform_key': selected_platform_key,
            'to_lang': to_lang,
            'agent_type': 'SegmentsTranslateAgent' if use_segments_agent else 'MDTranslateAgent',
        }

        save_api_logs_to_temp_dir(
            task_state=task_state,
            task_id=task_id,
            subfolder=retry_folder,
            llm_api_input=api_input_to_save,
            llm_api_output=api_output_to_save,
            llm_api_system_prompt=system_prompt_to_save,
            llm_api_params=llm_api_params,  # API parameters for diagnosis
            segment_index=None,  # Batch retry - save to single file (append mode)
        )
    except Exception as log_e:
        logger.warning(LogModule.TRANS,
            f"Failed to save API logs for batch retry in task {task_id}: {log_e}",
            exc_info=True
        )
    
    # CRITICAL: Clear batch retry in progress flag
    task_state["batch_retry_in_progress"] = False
    
    # Check if batch retry was cancelled
    was_cancelled = task_state.get("cancel_batch_retry", False)
    if was_cancelled:
        logger.info(LogModule.TRANS,
            f"[BATCH_RETRY] Task {task_id}: Batch retry was cancelled by user, "
            f"returning partial results ({len(result_map)} segments processed)"
        )
        task_state["message"] = f"Batch retry cancelled ({len(result_map)} segments processed)"
        task_state["progress"] = 100
        task_state["status"] = "completed"
    else:
        logger.info(LogModule.TRANS,
            f"[BATCH_RETRY] Task {task_id}: Successfully retranslated {len(result_map)} segments "
            f"using platform '{selected_platform_key}' (chunks were merged to reduce API calls)"
        )
        # CRITICAL: Set final progress and status so frontend knows retry is complete
        task_state["progress"] = 100
        task_state["message"] = f"Retranslation completed: {len(result_map)} segments processed"
        task_state["status"] = "completed"
    
    # Clear cancel flag after completion
    task_state["cancel_batch_retry"] = False
    
    return result_map