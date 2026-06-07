# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Generic utility for translating segments/chunks with chunk merging to save tokens.

This module provides a unified approach for translating segments/chunks by:
1. Merging segments into chunks based on chunk_size (for DOCX/Excel)
2. Translating chunks (reducing API calls and system prompt overhead)
3. Mapping translated chunks back to individual segments
4. Saving segments/chunks to source_chunks_cache for proper mapping

This can be used by DOCX, Excel, PDF, and other workflows that need to optimize token usage.

Usage Examples:
    # For DOCX/Excel translators using SegmentsTranslateAgent:
    from utils.chunk_translation_helper import translate_segments_with_agent
    
    translated_segments, metadata = translate_segments_with_agent(
        segments=original_texts,
        chunk_size=self.chunk_size,
        translate_agent=self.translate_agent,  # SegmentsTranslateAgent
        task_id=task_id,
        task_state=task_state,
        original_filename=original_filename,
        file_contents=file_contents,
    )
    chunk_to_segment_map = metadata.get("chunk_to_segment_map")
    
    # For PDF translators using MDTranslateAgent:
    from utils.chunk_translation_helper import translate_chunks_with_agent_async
    
    translated_chunks, metadata = await translate_chunks_with_agent_async(
        chunks=chunks_for_translation,
        chunk_size=self.chunk_size,
        translate_agent=self.translate_agent,  # MDTranslateAgent
        task_id=task_id,
        task_state=task_state,
        layout_chunk_block_map=layout_chunk_block_map,  # PDF-specific
    )
    chunk_to_segment_map = metadata.get("chunk_to_segment_map")
"""

import hashlib
import logging
import os
import tempfile
import time
from typing import List, Tuple, Optional, Callable, Any

from utils.json_utils import segments2json_chunks
from logger.logger import TRACE_LEVEL
from logger import unified_logger as logger
from logger.logger import LogModule


def save_api_logs_to_temp_dir(
    task_state: dict,
    task_id: str,
    subfolder: str = "translation",
    llm_api_input: Optional[List[str]] = None,
    llm_api_output: Optional[List[Any]] = None,
    llm_api_system_prompt: Optional[str] = None,
    llm_api_params: Optional[dict] = None,  # LLM API call parameters (thinking, temperature, model, etc.)
    segment_index: Optional[int] = None,  # For retry: create separate file per segment
) -> Optional[str]:
    """
    Save API logs (input/output) to temp directory for debugging.

    Args:
        task_state: Task state dictionary containing temp_dir
        task_id: Task identifier for logging
        subfolder: Subfolder name (e.g., "translation", "Retry1", "Retry2")
        llm_api_input: List of API input prompts (if None, will try to get from task_state)
        llm_api_output: List of API output responses (if None, will try to get from task_state)
        llm_api_system_prompt: System prompt used (if None, will try to get from task_state)
        llm_api_params: LLM API call parameters for diagnosis (thinking, temperature, model_id, etc.)

    Returns:
        Path to debug directory if successful, None otherwise
    """
    try:
        # Get API logs from task_state if not provided
        if llm_api_input is None:
            llm_api_input = task_state.get('llm_api_input')
        if llm_api_output is None:
            llm_api_output = task_state.get('llm_api_output')
        if llm_api_system_prompt is None:
            llm_api_system_prompt = task_state.get('llm_api_system_prompt')
        
        # Use task_state temp_dir if available
        debug_dir = None
        temp_dir = task_state.get("temp_dir")
        if temp_dir and os.path.isdir(temp_dir):
            debug_dir = os.path.join(temp_dir, "debug", subfolder)
            os.makedirs(debug_dir, exist_ok=True)
            # Store debug directory path in task_state
            if "debug_files" not in task_state:
                task_state["debug_files"] = {}
            task_state["debug_files"][f"{subfolder}_debug_dir"] = debug_dir
        
        # Fallback: create independent debug directory if task_state temp_dir not available
        if not debug_dir:
            debug_dir = tempfile.mkdtemp(prefix=f"{subfolder}_debug_{task_id or 'unknown'}_")
            logger.warning(
                LogModule.TRANS,
                f"[API_LOGS] Task {task_id}: temp_dir not available, created independent debug directory: {debug_dir}"
            )
        
        # Save LLM API input and output if available
        if llm_api_input and llm_api_output:
            # For retry operations, create separate file per segment to avoid overwriting
            if segment_index is not None:
                llm_api_comparison_file = os.path.join(debug_dir, f"llm_api_comparison_segment_{segment_index}.txt")
                # For single segment retry: append to file if it already exists (multiple retries of same segment)
                file_mode = 'a'
            else:
                llm_api_comparison_file = os.path.join(debug_dir, "llm_api_comparison.txt")
                # For batch retry or translation: append to accumulate all chunks
                # This ensures multiple chunks are saved in the same file, not overwritten
                file_mode = 'a'
            
            # Check if file exists and has content (for appending separator)
            file_exists = False
            try:
                if os.path.exists(llm_api_comparison_file):
                    file_exists = os.path.getsize(llm_api_comparison_file) > 0
            except Exception:
                file_exists = False
            
            # Compute key count per chunk (for summary) by parsing each input as JSON when possible
            import json
            key_counts_per_chunk = []
            for inp in llm_api_input:
                try:
                    obj = json.loads(inp) if isinstance(inp, str) else inp
                    key_counts_per_chunk.append(len(obj) if isinstance(obj, dict) else 0)
                except Exception:
                    key_counts_per_chunk.append(-1)
            total_keys = sum(c for c in key_counts_per_chunk if c > 0)
            
            with open(llm_api_comparison_file, file_mode, encoding='utf-8') as f:
                # If appending and file has content, add separator to distinguish different chunks/attempts
                if file_mode == 'a' and file_exists:
                    f.write(f"\n{'='*80}\n")
                    if segment_index is not None:
                        f.write(f"RETRY ATTEMPT (Segment {segment_index})\n")
                    else:
                        f.write(f"CHUNK {len(llm_api_input)} (Appended)\n")
                    f.write(f"{'='*80}\n\n")
                
                # Write summary so user can verify all chunks are present (total chunks, key count per chunk)
                f.write(f"[SUMMARY] Total API requests (chunks): {len(llm_api_input)}. ")
                f.write(f"Segment keys per chunk: {key_counts_per_chunk}. Total segment keys: {total_keys}\n\n")
                
                # Write API parameters for diagnosis
                if llm_api_params:
                    f.write(f"{'='*80}\n")
                    f.write("LLM API PARAMETERS:\n")
                    f.write(f"{'='*80}\n")
                    for key, value in llm_api_params.items():
                        f.write(f"  {key}: {value}\n")
                    f.write(f"{'='*80}\n\n")

                # Write system prompt at the beginning if available (only for new file or first chunk)
                if llm_api_system_prompt and not file_exists:
                    f.write(f"{'='*80}\n")
                    f.write("SYSTEM PROMPT:\n")
                    f.write(f"{'='*80}\n")
                    f.write(llm_api_system_prompt)
                    f.write("\n\n")
                    f.write("Note: The system prompt above may be modified by pre_send_handler (e.g., glossary added).\n")
                    f.write("Each request below uses this system prompt (or a modified version with glossary).\n")
                    f.write(f"{'='*80}\n\n")
                
                # Calculate starting request index (for appending multiple chunks)
                start_idx = 0
                if file_mode == 'a' and file_exists:
                    # Try to read existing file to determine next request index
                    # This is a simple approach - count existing "LLM API Request" markers
                    try:
                        with open(llm_api_comparison_file, 'r', encoding='utf-8') as rf:
                            content = rf.read()
                            # Count how many "LLM API Request" markers exist
                            start_idx = content.count("LLM API Request")
                    except Exception:
                        pass  # If we can't read, start from 0
                
                max_idx = max(len(llm_api_input), len(llm_api_output))
                for idx in range(max_idx):
                    request_idx = start_idx + idx
                    keys_in_request = key_counts_per_chunk[idx] if idx < len(key_counts_per_chunk) else -1
                    f.write(f"{'='*80}\n")
                    f.write(f"LLM API Request {request_idx}\n")
                    if keys_in_request >= 0:
                        f.write(f"[Keys in this request: {keys_in_request}]\n")
                    f.write(f"{'='*80}\n")
                    f.write("INPUT:\n")
                    f.write("-" * 80 + "\n")
                    if idx < len(llm_api_input):
                        f.write(llm_api_input[idx])
                    else:
                        f.write("(missing)")
                    f.write("\n\n")
                    f.write("OUTPUT:\n")
                    f.write("-" * 80 + "\n")
                    if idx < len(llm_api_output):
                        f.write(str(llm_api_output[idx]))
                    else:
                        f.write("(missing)")
                    f.write("\n\n")
            
            logger.info(
                LogModule.TRANS,
                f"[API_LOGS] Task {task_id}: Saved API logs to {debug_dir} "
                f"({len(llm_api_input)} requests, {len(llm_api_output)} responses)"
            )
            logger.debug(
                LogModule.TRANS,
                f"[API_LOGS] Task {task_id}: API logs saved to: {llm_api_comparison_file}"
            )
        else:
            logger.warning(
                LogModule.TRANS,
                f"[API_LOGS] Task {task_id}: API logs not available "
                f"(llm_api_input: {llm_api_input is not None}, llm_api_output: {llm_api_output is not None})"
            )
        
        return debug_dir
    except Exception as e:
        logger.warning(
            LogModule.TRANS,
            f"[API_LOGS] Task {task_id}: Failed to save API logs to temp directory: {e}",
            exc_info=True
        )
        return None


def translate_segments_with_agent(
    segments: List[str],
    chunk_size: int,
    translate_agent: Any,  # SegmentsTranslateAgent instance
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
    progress_callback: Optional[Callable] = None,
    segment_indices: Optional[List[int]] = None,  # Original segment indices (may be non-continuous)
) -> Tuple[List[str], dict]:
    """
    Translate segments using SegmentsTranslateAgent with chunk merging and cache saving.
    
    This is a convenience wrapper around SegmentsTranslateAgent.send_segments that:
    1. Saves segments to source_chunks_cache before translation
    2. Builds chunk_to_segment_map for proper mapping
    3. Calls translate_agent.send_segments for translation (with chunk merging)
    4. Returns translated segments and mapping metadata
    
    This ensures proper segment-to-chunk mapping for record_translation_segments.
    
    Args:
        segments: List of original text segments to translate
        chunk_size: Maximum size (in bytes) for merged chunks
        translate_agent: SegmentsTranslateAgent instance with send_segments method
        task_id: Optional task ID for saving segments cache
        task_state: Optional task state dictionary for saving segments cache
        original_filename: Optional original filename for cache key
        file_contents: Optional original file contents for cache hash
        progress_callback: Optional progress callback function
        
    Returns:
        Tuple containing:
        - translated_segments: List of translated segments (same length as input segments)
        - metadata: Dictionary with mapping information:
            - chunk_to_segment_map: List of lists, mapping chunk index to segment indices
    
    Example:
        # In DocxTranslator or XlsxTranslator:
        translated_texts, metadata = translate_segments_with_agent(
            segments=original_texts,
            chunk_size=self.chunk_size,
            translate_agent=self.translate_agent,
            task_id=task_id,
            task_state=task_state,
            original_filename=original_filename,
            file_contents=document.content,
        )
        chunk_to_segment_map = metadata.get("chunk_to_segment_map")
    """
    # Step 1: Check if chunk_to_segment_map already exists in task_state (from import phase)
    # Priority: Use pre-computed map from import phase to ensure consistency with excluded segments
    chunk_to_segment_map: List[List[int]] = []
    chunk_tokens_info: List[int] = []
    total_estimated_tokens = 0
    use_precomputed_map = False
    
    if task_state and task_id:
        existing_map = task_state.get("chunk_to_segment_map")
        existing_chunk_size = task_state.get("chunk_tokens_info")  # Check if chunk_size matches via tokens info
        cache_info = task_state.get("source_chunks_cache", {})
        cached_chunk_size = cache_info.get("chunk_size")
        cached_segments = cache_info.get("segments", [])
        
        # Use precomputed map if:
        # 1. Map exists
        # 2. Chunk size matches EXACTLY (critical for correct chunking)
        # 3. Cached segments exist and match the segments we're translating (after filtering excluded)
        if existing_map and isinstance(existing_map, list) and len(existing_map) > 0:
            # CRITICAL: chunk_size must match exactly, otherwise chunks will be different
            # Do NOT use precomputed map if chunk_size differs
            if cached_chunk_size == chunk_size:
                # Verify segments match (after filtering excluded)
                # Note: segments passed here are already filtered (excluded removed)
                # cached_segments contains ALL segments (including excluded)
                # We need to check if filtered segments match cached segments (excluding excluded ones)
                if cached_segments:
                    # Count non-excluded segments in cache
                    from utils.translation_segments import _is_image_segment
                    excluded_indices = task_state.get("segments_metadata", {}).get("excluded_segment_indices", [])
                    excluded_set = set(excluded_indices) if excluded_indices else set()
                    
                    # Count non-excluded segments
                    non_excluded_count = sum(1 for i, seg in enumerate(cached_segments) if i not in excluded_set)
                    
                    if non_excluded_count == len(segments):
                        # Segments match - use precomputed map
                        chunk_to_segment_map = existing_map
                        use_precomputed_map = True
                        chunk_tokens_info = task_state.get("chunk_tokens_info", [])
                        total_estimated_tokens = task_state.get("total_estimated_input_tokens", 0)
                        segment_limit_log = task_state.get('segment_limit', 'N/A')
                        logger.info(
                            LogModule.TRANS,
                            f"[CHUNK_TRANSLATION] Using precomputed chunk_to_segment_map from import phase: "
                            f"{len(chunk_to_segment_map)} chunks, chunk_size={chunk_size} (matches cached={cached_chunk_size}), "
                            f"segment_limit={segment_limit_log}, "
                            f"total_estimated_tokens={total_estimated_tokens}, "
                            f"segments={len(segments)} (non-excluded from {len(cached_segments)} total)"
                        )
                        # Log first few chunk mappings for debugging
                        if chunk_to_segment_map and len(chunk_to_segment_map) > 0:
                            sample_mappings = chunk_to_segment_map[:3]
                            logger.debug(
                                LogModule.TRANS,
                                f"[CHUNK_TRANSLATION] Sample precomputed chunk mappings (first 3): {sample_mappings}"
                            )
                    else:
                        logger.debug(
                            LogModule.TRANS,
                            f"[CHUNK_TRANSLATION] Precomputed map segment count mismatch: "
                            f"cached non-excluded={non_excluded_count}, current segments={len(segments)}. "
                            f"Will rebuild map."
                        )
                else:
                    logger.debug(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] No cached segments found, will rebuild chunk_to_segment_map"
                    )
            else:
                logger.info(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Chunk size mismatch: cached={cached_chunk_size}, "
                    f"current={chunk_size}. Will rebuild map with new chunk_size."
                )
    
    # Step 2: Build chunk_to_segment_map if not using precomputed one
    if not use_precomputed_map:
        try:
            # Calculate text content token limit (excluding system prompt and overhead)
            from utils.chunk_size_converter import get_text_content_token_limit
            text_token_limit = get_text_content_token_limit(chunk_size)
            if task_id:
                logger.debug(LogModule.TRANS, f"[CHUNK_TRANSLATION] Task {task_id}: Using text_token_limit={text_token_limit} (from total chunk_size={chunk_size} tokens) for chunking")
            
            indexed_originals, chunks, merged_indices_list, chunk_tokens = segments2json_chunks(segments, text_token_limit, estimate_tokens=True)
            
            # Build chunk_to_segment_map from chunks
            # chunks is a list of dicts like [{"0": "text1", "1": "text2"}, {"2": "text3"}]
            for chunk_idx, chunk_dict in enumerate(chunks):
                # Get segment indices for this chunk (sorted by key)
                segment_indices = [int(k) for k in sorted(chunk_dict.keys(), key=int)]
                chunk_to_segment_map.append(segment_indices)
                
                # Store token estimate for this chunk
                if chunk_tokens and chunk_idx < len(chunk_tokens):
                    estimated_tokens = chunk_tokens[chunk_idx]
                    chunk_tokens_info.append(estimated_tokens)
                    total_estimated_tokens += estimated_tokens
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Built new chunk_to_segment_map: {len(chunk_to_segment_map)} chunks "
                f"mapping to {len(segments)} segments (chunk_size={chunk_size}, total estimated tokens: {total_estimated_tokens})"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to build chunk_to_segment_map: {e}, "
                f"will fall back to content-based matching",
                exc_info=True
            )
            # Fallback: assume one-to-one mapping
            chunk_to_segment_map = [[i] for i in range(len(segments))]
    
    # Step 3: Save segments and mapping to source_chunks_cache before translation
    # CRITICAL: Only update cache if we rebuilt the map (not using precomputed one)
    # If using precomputed map, keep the original cache (which contains ALL segments including excluded)
    if task_state and task_id and not use_precomputed_map:
        try:
            content_hash = None
            if file_contents:
                content_hash = hashlib.sha1(file_contents).hexdigest()
            elif original_filename:
                content_hash = hashlib.sha1(original_filename.encode('utf-8')).hexdigest()
            
            # CRITICAL: Preserve existing source_chunks_cache if it exists
            # For PDF workflow, Extract phase has already built source_chunks_cache with correct segment_index-based indexing
            # Only create new cache if it doesn't exist (shouldn't happen for PDF workflow)
            cache_info = task_state.get("source_chunks_cache", {})
            if not cache_info or not cache_info.get("segments"):
                task_state["source_chunks_cache"] = {
                    "content_hash": content_hash,
                    "chunk_size": chunk_size,
                    "segments": segments,
                    "total_segments": len(segments),
                    "created_at": time.time(),
                }
            
            # Always update chunk_to_segment_map (even if using precomputed, ensure it's set)
            task_state["chunk_to_segment_map"] = chunk_to_segment_map
            
            # Save chunk tokens info if available
            if chunk_tokens_info:
                task_state["chunk_tokens_info"] = chunk_tokens_info
                task_state["total_estimated_input_tokens"] = total_estimated_tokens
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] {'Updated' if use_precomputed_map else 'Saved'} "
                f"chunk_to_segment_map to task_state for task {task_id} "
                f"({len(chunk_to_segment_map)} chunks, total estimated tokens: {total_estimated_tokens})"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to save segments to cache: {e}",
                exc_info=True
            )
    
    # Step 3: Translate using SegmentsTranslateAgent (handles chunk merging internally)
    # IMPORTANT: send_segments will rebuild chunks internally using segments2json_chunks
    # This should match the chunk_to_segment_map we built above (same segments, same chunk_size)
    if translate_agent:
        # Set task_id and task_state on agent for timeout error reporting
        if task_id and task_state:
            translate_agent.task_id = task_id
            translate_agent.task_state = task_state
        
        logger.debug(
            LogModule.TRANS,
            f"[CHUNK_TRANSLATION] Calling send_segments with {len(segments)} segments, chunk_size={chunk_size}, "
            f"expected {len(chunk_to_segment_map)} chunks"
        )
        try:
            translated_segments = translate_agent.send_segments(
                segments=segments,
                chunk_size=chunk_size,
                progress_callback=progress_callback,
                segment_indices=segment_indices,
            )
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] send_segments returned {len(translated_segments)} translated segments"
            )
            
            # Save segments and chunks to temporary folder for debugging if DEBUG or TRACE mode is enabled
            from logger.logger import TRACE_LEVEL
            is_debug_enabled = (
                logger.level <= logging.DEBUG or 
                logger.isEnabledFor(logging.DEBUG) or 
                logger.isEnabledFor(TRACE_LEVEL)
            )
            
            # Also check config file directly
            try:
                from logger.logger import get_log_level_from_config
                config_level = get_log_level_from_config()
                if config_level <= logging.DEBUG:
                    is_debug_enabled = True
            except Exception:
                pass
            
            if is_debug_enabled:
                try:
                    # Use task_state temp_dir if available, otherwise create independent debug directory
                    debug_dir = None
                    if task_state:
                        temp_dir = task_state.get("temp_dir")
                        if temp_dir and os.path.isdir(temp_dir):
                            debug_dir = os.path.join(temp_dir, "debug", "translation")
                            os.makedirs(debug_dir, exist_ok=True)
                            if "debug_files" not in task_state:
                                task_state["debug_files"] = {}
                            task_state["debug_files"]["translation_debug_dir"] = debug_dir
                    
                    # Fallback: create independent debug directory if task_state temp_dir not available
                    if not debug_dir:
                        debug_dir = tempfile.mkdtemp(prefix=f"translation_debug_{task_id or 'unknown'}_")
                    
                    # Save segments side-by-side comparison
                    segments_comparison_file = os.path.join(debug_dir, "segments_comparison.txt")
                    with open(segments_comparison_file, 'w', encoding='utf-8') as f:
                        max_idx = max(len(segments), len(translated_segments))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"Segment {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("ORIGINAL:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(segments):
                                f.write(segments[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("TRANSLATED:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(translated_segments):
                                f.write(translated_segments[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    
                    # Reconstruct chunks from segments and chunk_to_segment_map
                    # Build original chunks
                    original_chunks = []
                    for chunk_idx, segment_indices in enumerate(chunk_to_segment_map):
                        chunk_texts = []
                        for seg_idx in segment_indices:
                            if seg_idx < len(segments):
                                chunk_texts.append(segments[seg_idx])
                        original_chunks.append("\n\n".join(chunk_texts))
                    
                    # Build translated chunks
                    translated_chunks = []
                    for chunk_idx, segment_indices in enumerate(chunk_to_segment_map):
                        chunk_texts = []
                        for seg_idx in segment_indices:
                            if seg_idx < len(translated_segments):
                                chunk_texts.append(translated_segments[seg_idx])
                        translated_chunks.append("\n\n".join(chunk_texts))
                    
                    # Save chunks side-by-side comparison
                    chunks_comparison_file = os.path.join(debug_dir, "chunks_comparison.txt")
                    with open(chunks_comparison_file, 'w', encoding='utf-8') as f:
                        max_idx = max(len(original_chunks), len(translated_chunks))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"Chunk {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("ORIGINAL:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(original_chunks):
                                f.write(original_chunks[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("TRANSLATED:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(translated_chunks):
                                f.write(translated_chunks[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    
                    # Note: llm_api_comparison.txt is saved directly in segments_agent.py
                    # No need to save it here to avoid duplication
                    
                    logger.debug(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] Debug files saved:\n"
                        f"  - Segments comparison: {segments_comparison_file}\n"
                        f"  - Chunks comparison: {chunks_comparison_file}\n"
                        f"  - Temporary folder: {debug_dir}"
                    )
                except Exception as debug_e:
                    logger.warning(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] Failed to save debug segments to temporary folder: {debug_e}",
                        exc_info=True
                    )
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            is_timeout_error = (
                "timeout" in error_msg_lower or 
                "readtimeout" in error_msg_lower or
                "timed out" in error_msg_lower
            )
            
            # If timeout error, update task state with helpful message
            if is_timeout_error and task_state and task_id:
                from backend.app.services.task import task_manager
                current_timeout = getattr(translate_agent, 'timeout', None)
                if current_timeout and hasattr(current_timeout, 'read'):
                    timeout_seconds = current_timeout.read
                else:
                    # Fallback: try to get from config
                    from backend.config.app_config import AppConfig
                    app_config = AppConfig()
                    timeout_seconds = app_config.translator_timeout
                
                timeout_message = (
                    f"Translation timeout detected (current timeout: {timeout_seconds}s). "
                    f"If it happens frequently, please go to Settings -> Translation and increase the Timeout value "
                    f"(recommended: {max(timeout_seconds * 2, 60)}s or higher)."
                )
                task_state["message"] = timeout_message
                task_manager.add_log(
                    task_id,
                    "warning",
                    f"Translation timeout error (current timeout: {timeout_seconds}s). "
                    f"Please increase timeout in Settings -> Translation."
                )
                logger.warning(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Timeout error during translation: {error_msg}. "
                    f"Current timeout: {timeout_seconds}s"
                )
            
            # Re-raise the exception to let it propagate (agent will handle retries)
            raise
    else:
        # Fallback: return original segments if no agent provided
        logger.warning(LogModule.TRANS, "[CHUNK_TRANSLATION] No translate_agent provided, returning original segments")
        translated_segments = segments
    
    metadata = {
        "chunk_to_segment_map": chunk_to_segment_map,
    }
    
    return translated_segments, metadata


async def translate_segments_with_agent_async(
    segments: List[str],
    chunk_size: int,
    translate_agent: Any,  # SegmentsTranslateAgent instance
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
    progress_callback: Optional[Callable] = None,
    segment_indices: Optional[List[int]] = None,  # Original segment indices (may be non-continuous)
) -> Tuple[List[str], dict]:
    # CRITICAL: Log function entry to ensure we can track execution
    logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_segments_with_agent_async ENTRY: segments={len(segments)}, task_id={task_id}, task_state exists={task_state is not None}")
    """
    Async version of translate_segments_with_agent.
    
    Args:
        segments: List of original text segments to translate
        chunk_size: Maximum size (in bytes) for merged chunks
        translate_agent: SegmentsTranslateAgent instance with send_segments_async method
        task_id: Optional task ID for saving segments cache
        task_state: Optional task state dictionary for saving segments cache
        original_filename: Optional original filename for cache key
        file_contents: Optional original file contents for cache hash
        progress_callback: Optional progress callback function
        segment_indices: Optional list of original segment indices (may be non-continuous)
        
    Returns:
        Tuple containing:
        - translated_segments: List of translated segments (same length as input segments)
        - metadata: Dictionary with mapping information:
            - chunk_to_segment_map: List of lists, mapping chunk index to segment indices
    """
    # Step 1: Check if chunk_to_segment_map already exists in task_state (from import phase)
    # Priority: Use pre-computed map from import phase to ensure consistency with excluded segments
    chunk_to_segment_map: List[List[int]] = []
    chunk_tokens_info: List[int] = []
    total_estimated_tokens = 0
    use_precomputed_map = False
    
    if task_state and task_id:
        existing_map = task_state.get("chunk_to_segment_map")
        existing_chunk_size = task_state.get("chunk_tokens_info")  # Check if chunk_size matches via tokens info
        cache_info = task_state.get("source_chunks_cache", {})
        cached_chunk_size = cache_info.get("chunk_size")
        cached_segments = cache_info.get("segments", [])
        
        # Use precomputed map if:
        # 1. Map exists
        # 2. Chunk size matches EXACTLY (critical for correct chunking)
        # 3. Cached segments exist and match the segments we're translating (after filtering excluded)
        if existing_map and isinstance(existing_map, list) and len(existing_map) > 0:
            # CRITICAL: chunk_size must match exactly, otherwise chunks will be different
            # Do NOT use precomputed map if chunk_size differs
            if cached_chunk_size == chunk_size:
                # Verify segments match (after filtering excluded)
                # Note: segments passed here are already filtered (excluded removed)
                # cached_segments contains ALL segments (including excluded)
                # We need to check if filtered segments match cached segments (excluding excluded ones)
                if cached_segments:
                    # Count non-excluded segments in cache
                    from utils.translation_segments import _is_image_segment
                    excluded_indices = task_state.get("segments_metadata", {}).get("excluded_segment_indices", [])
                    excluded_set = set(excluded_indices) if excluded_indices else set()
                    
                    # Count non-excluded segments
                    non_excluded_count = sum(1 for i, seg in enumerate(cached_segments) if i not in excluded_set)
                    
                    if non_excluded_count == len(segments):
                        # Segments match - use precomputed map
                        chunk_to_segment_map = existing_map
                        use_precomputed_map = True
                        chunk_tokens_info = task_state.get("chunk_tokens_info", [])
                        total_estimated_tokens = task_state.get("total_estimated_input_tokens", 0)
                        segment_limit_log = task_state.get('segment_limit', 'N/A')
                        logger.info(
                            LogModule.TRANS,
                            f"[CHUNK_TRANSLATION] Using precomputed chunk_to_segment_map from import phase: "
                            f"{len(chunk_to_segment_map)} chunks, chunk_size={chunk_size} (matches cached={cached_chunk_size}), "
                            f"segment_limit={segment_limit_log}, "
                            f"total_estimated_tokens={total_estimated_tokens}, "
                            f"segments={len(segments)} (non-excluded from {len(cached_segments)} total)"
                        )
                        # Log first few chunk mappings for debugging
                        if chunk_to_segment_map and len(chunk_to_segment_map) > 0:
                            sample_mappings = chunk_to_segment_map[:3]
                            logger.debug(
                                LogModule.TRANS,
                                f"[CHUNK_TRANSLATION] Sample precomputed chunk mappings (first 3): {sample_mappings}"
                            )
                    else:
                        logger.debug(
                            LogModule.TRANS,
                            f"[CHUNK_TRANSLATION] Precomputed map segment count mismatch: "
                            f"cached non-excluded={non_excluded_count}, current segments={len(segments)}. "
                            f"Will rebuild map."
                        )
                else:
                    logger.debug(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] No cached segments found, will rebuild chunk_to_segment_map"
                    )
            else:
                logger.info(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Chunk size mismatch: cached={cached_chunk_size}, "
                    f"current={chunk_size}. Will rebuild map with new chunk_size."
                )
    
    # Step 2: Build chunk_to_segment_map if not using precomputed one
    if not use_precomputed_map:
        try:
            # Calculate text content token limit (excluding system prompt and overhead)
            from utils.chunk_size_converter import get_text_content_token_limit
            text_token_limit = get_text_content_token_limit(chunk_size)
            if task_id:
                logger.debug(LogModule.TRANS, f"[CHUNK_TRANSLATION] Task {task_id}: Using text_token_limit={text_token_limit} (from total chunk_size={chunk_size} tokens) for chunking")
            
            indexed_originals, chunks, merged_indices_list, chunk_tokens = segments2json_chunks(segments, text_token_limit, estimate_tokens=True)
            
            for chunk_idx, chunk_dict in enumerate(chunks):
                segment_indices = [int(k) for k in sorted(chunk_dict.keys(), key=int)]
                chunk_to_segment_map.append(segment_indices)
                
                # Store token estimate for this chunk
                if chunk_tokens and chunk_idx < len(chunk_tokens):
                    estimated_tokens = chunk_tokens[chunk_idx]
                    chunk_tokens_info.append(estimated_tokens)
                    total_estimated_tokens += estimated_tokens
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Built new chunk_to_segment_map: {len(chunk_to_segment_map)} chunks "
                f"mapping to {len(segments)} segments (chunk_size={chunk_size}, total estimated tokens: {total_estimated_tokens})"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to build chunk_to_segment_map: {e}, "
                f"will fall back to content-based matching",
                exc_info=True
            )
            chunk_to_segment_map = [[i] for i in range(len(segments))]
    
    # Step 3: Save segments and mapping to source_chunks_cache (same as sync version)
    # CRITICAL: Only update cache if we rebuilt the map (not using precomputed one)
    # If using precomputed map, keep the original cache (which contains ALL segments including excluded)
    if task_state and task_id and not use_precomputed_map:
        try:
            content_hash = None
            if file_contents:
                content_hash = hashlib.sha1(file_contents).hexdigest()
            elif original_filename:
                content_hash = hashlib.sha1(original_filename.encode('utf-8')).hexdigest()
            
            # CRITICAL: Preserve existing source_chunks_cache if it exists
            # For PDF workflow, Extract phase has already built source_chunks_cache with correct segment_index-based indexing
            # Only create new cache if it doesn't exist (shouldn't happen for PDF workflow)
            cache_info = task_state.get("source_chunks_cache", {})
            if not cache_info or not cache_info.get("segments"):
                task_state["source_chunks_cache"] = {
                    "content_hash": content_hash,
                    "chunk_size": chunk_size,
                    "segments": segments,
                    "total_segments": len(segments),
                    "created_at": time.time(),
                }
            
            # Always update chunk_to_segment_map (even if using precomputed, ensure it's set)
            task_state["chunk_to_segment_map"] = chunk_to_segment_map
            
            # Save chunk tokens info if available
            if chunk_tokens_info:
                task_state["chunk_tokens_info"] = chunk_tokens_info
                task_state["total_estimated_input_tokens"] = total_estimated_tokens
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] {'Updated' if use_precomputed_map else 'Saved'} "
                f"chunk_to_segment_map to task_state for task {task_id} "
                f"({len(chunk_to_segment_map)} chunks, total estimated tokens: {total_estimated_tokens})"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to save segments to cache: {e}",
                exc_info=True
            )
    
    # Step 3: Translate using SegmentsTranslateAgent (async)
    # IMPORTANT: send_segments_async will rebuild chunks internally using segments2json_chunks
    # This should match the chunk_to_segment_map we built above (same segments, same chunk_size)
    if translate_agent:
        # Set task_id and task_state on agent for timeout error reporting
        if task_id and task_state:
            translate_agent.task_id = task_id
            translate_agent.task_state = task_state
        
        segment_limit_log = task_state.get('segment_limit', 'N/A') if task_state else 'N/A'
        logger.info(
            LogModule.TRANS,
            f"[CHUNK_TRANSLATION] Calling send_segments_async with {len(segments)} segments, chunk_size={chunk_size}, "
            f"segment_limit={segment_limit_log}, expected {len(chunk_to_segment_map)} chunks"
        )
        try:
            logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_segments_with_agent_async: Starting translation with {len(segments)} segments")
            
            translated_segments = await translate_agent.send_segments_async(
                segments=segments,
                chunk_size=chunk_size,
                progress_callback=progress_callback,
                segment_indices=segment_indices,
            )
            logger.info(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] send_segments_async returned {len(translated_segments)} translated segments"
            )
            
            # Save segments and chunks to temporary folder for debugging if DEBUG or TRACE mode is enabled
            from logger.logger import TRACE_LEVEL
            is_debug_enabled = (
                logger.level <= logging.DEBUG or 
                logger.isEnabledFor(logging.DEBUG) or 
                logger.isEnabledFor(TRACE_LEVEL)
            )
            
            # Also check config file directly
            try:
                from logger.logger import get_log_level_from_config
                config_level = get_log_level_from_config()
                if config_level <= logging.DEBUG:
                    is_debug_enabled = True
            except Exception:
                pass
            
            if is_debug_enabled:
                try:
                    # Use task_state temp_dir if available, otherwise create independent debug directory
                    debug_dir = None
                    if task_state:
                        temp_dir = task_state.get("temp_dir")
                        if temp_dir and os.path.isdir(temp_dir):
                            debug_dir = os.path.join(temp_dir, "debug", "translation")
                            os.makedirs(debug_dir, exist_ok=True)
                            if "debug_files" not in task_state:
                                task_state["debug_files"] = {}
                            task_state["debug_files"]["translation_debug_dir"] = debug_dir
                    
                    # Fallback: create independent debug directory if task_state temp_dir not available
                    if not debug_dir:
                        debug_dir = tempfile.mkdtemp(prefix=f"translation_debug_{task_id or 'unknown'}_")
                    
                    # Save segments side-by-side comparison
                    segments_comparison_file = os.path.join(debug_dir, "segments_comparison.txt")
                    with open(segments_comparison_file, 'w', encoding='utf-8') as f:
                        max_idx = max(len(segments), len(translated_segments))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"Segment {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("ORIGINAL:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(segments):
                                f.write(segments[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("TRANSLATED:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(translated_segments):
                                f.write(translated_segments[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    
                    # Reconstruct chunks from segments and chunk_to_segment_map
                    # Build original chunks
                    original_chunks = []
                    for chunk_idx, segment_indices in enumerate(chunk_to_segment_map):
                        chunk_texts = []
                        for seg_idx in segment_indices:
                            if seg_idx < len(segments):
                                chunk_texts.append(segments[seg_idx])
                        original_chunks.append("\n\n".join(chunk_texts))
                    
                    # Build translated chunks
                    translated_chunks = []
                    for chunk_idx, segment_indices in enumerate(chunk_to_segment_map):
                        chunk_texts = []
                        for seg_idx in segment_indices:
                            if seg_idx < len(translated_segments):
                                chunk_texts.append(translated_segments[seg_idx])
                        translated_chunks.append("\n\n".join(chunk_texts))
                    
                    # Save chunks side-by-side comparison
                    chunks_comparison_file = os.path.join(debug_dir, "chunks_comparison.txt")
                    with open(chunks_comparison_file, 'w', encoding='utf-8') as f:
                        max_idx = max(len(original_chunks), len(translated_chunks))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"Chunk {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("ORIGINAL:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(original_chunks):
                                f.write(original_chunks[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("TRANSLATED:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(translated_chunks):
                                f.write(translated_chunks[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    
                    # Note: llm_api_comparison.txt is saved directly in segments_agent.py
                    # No need to save it here to avoid duplication
                    
                    logger.debug(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] Debug files saved:\n"
                        f"  - Segments comparison: {segments_comparison_file}\n"
                        f"  - Chunks comparison: {chunks_comparison_file}\n"
                        f"  - Temporary folder: {debug_dir}"
                    )
                except Exception as debug_e:
                    logger.warning(
                        LogModule.TRANS,
                        f"[CHUNK_TRANSLATION] Failed to save debug segments to temporary folder: {debug_e}",
                        exc_info=True
                    )
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            is_timeout_error = (
                "timeout" in error_msg_lower or 
                "readtimeout" in error_msg_lower or
                "timed out" in error_msg_lower
            )
            
            # If timeout error, update task state with helpful message
            if is_timeout_error and task_state and task_id:
                from backend.app.services.task import task_manager
                current_timeout = getattr(translate_agent, 'timeout', None)
                if current_timeout and hasattr(current_timeout, 'read'):
                    timeout_seconds = current_timeout.read
                else:
                    # Fallback: try to get from config
                    from backend.config.app_config import AppConfig
                    app_config = AppConfig()
                    timeout_seconds = app_config.translator_timeout
                
                timeout_message = (
                    f"Translation timeout detected (current timeout: {timeout_seconds}s). "
                    f"Please go to Settings -> Translation and increase the Timeout value "
                    f"(recommended: {max(timeout_seconds * 2, 60)}s or higher)."
                )
                task_state["message"] = timeout_message
                task_manager.add_log(
                    task_id,
                    "warning",
                    f"Translation timeout error (current timeout: {timeout_seconds}s). "
                    f"Please increase timeout in Settings -> Translation."
                )
                logger.warning(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Timeout error during translation: {error_msg}. "
                    f"Current timeout: {timeout_seconds}s"
                )
            
            # Re-raise the exception to let it propagate (agent will handle retries)
            raise
    else:
        logger.warning(LogModule.TRANS, "[CHUNK_TRANSLATION] No translate_agent provided, returning original segments")
        translated_segments = segments
    
    metadata = {
        "chunk_to_segment_map": chunk_to_segment_map,
    }
    
    return translated_segments, metadata


async def translate_chunks_with_agent_async(
    chunks: List[str],
    chunk_size: int,
    translate_agent: Any,  # MDTranslateAgent instance (send_chunks_async)
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
    progress_callback: Optional[Callable] = None,
    layout_chunk_block_map: Optional[List[List[int]]] = None,  # PDF-specific: layout block mapping
    segment_indices: Optional[List[int]] = None,  # CRITICAL: Original segment indices for each chunk
) -> Tuple[List[str], dict]:
    # CRITICAL: Log function entry to ensure we can track execution
    logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async ENTRY: chunks={len(chunks)}, task_id={task_id}, task_state exists={task_state is not None}")
    """
    Translate chunks using MDTranslateAgent (for PDF workflow).
    
    CRITICAL: This function now allows chunk merging (like DOCX workflow) to reduce token consumption.
    - Input chunks are treated as segments and may be merged into larger chunks
    - Builds chunk_to_segment_map that maps merged chunks back to original segment indices
    - Uses send_chunks_async which handles merging internally
    
    This is similar to translate_segments_with_agent_async, but:
    - Uses send_chunks_async instead of send_segments_async
    - Handles layout_chunk_block_map for PDF rendering
    
    This function:
    1. Saves chunks (as segments) to source_chunks_cache before translation
    2. Builds chunk_to_segment_map that allows merging (not one-to-one)
    3. Calls translate_agent.send_chunks_async for translation (with merging)
    4. Returns translated chunks and mapping metadata
    
    Args:
        chunks: List of original text chunks to translate (treated as segments, may be merged)
        chunk_size: Maximum size (in tokens) for merged chunks (used by send_chunks_async internally)
        translate_agent: MDTranslateAgent instance with send_chunks_async method
        task_id: Optional task ID for saving chunks cache
        task_state: Optional task state dictionary for saving chunks cache
        original_filename: Optional original filename for cache key
        file_contents: Optional original file contents for cache hash
        progress_callback: Optional progress callback function
        layout_chunk_block_map: Optional PDF-specific layout block mapping (chunk index -> block indices)
        
    Returns:
        Tuple containing:
        - translated_chunks: List of translated chunks (same length as input chunks after split_merged_chunks)
        - metadata: Dictionary with mapping information:
            - chunk_to_segment_map: List of lists, mapping chunk index to segment indices (allows merging)
            - layout_chunk_block_map: PDF-specific layout block mapping (passed through)
    
    Example:
        # In MDTranslator (PDF workflow):
        translated_chunks, metadata = await translate_chunks_with_agent_async(
            chunks=chunks_for_translation,
            chunk_size=self.chunk_size,
            translate_agent=self.translate_agent,  # MDTranslateAgent
            task_id=task_id,
            task_state=task_state,
            layout_chunk_block_map=layout_chunk_block_map,
        )
        chunk_to_segment_map = metadata.get("chunk_to_segment_map")
    """
    # Step 1: Build chunk_to_segment_map that allows merging (like DOCX workflow)
    # CRITICAL: We need to build the map BEFORE merging, so we know which segments map to which chunks
    # send_chunks_async will merge chunks internally, but we need to track the mapping
    # Strategy: Build map based on how chunks will be merged by send_chunks_async
    
    # CRITICAL: chunks2merged_chunks expects chunk_size in characters (bytes), not tokens
    # But send_chunks_async passes chunk_size (tokens) directly to chunks2merged_chunks
    # This is a design issue - we need to match send_chunks_async's behavior
    # For now, we'll use chunk_size directly (as send_chunks_async does) and let it handle the conversion
    # In the future, we might want to convert tokens to characters more accurately
    
    from utils.markdown_chunk_merger import chunks2merged_chunks
    import asyncio
    
    # CRITICAL: Use provided segment_indices or extract from chunks
    # segment_indices should be the original segment indices (e.g., [0, 1, 2, 4, 5, ...] if 3 is excluded)
    # This ensures chunks are formatted as "0: text\n1: text\n2: text\n4: text" (skipping 3)
    segment_indices_for_chunks = segment_indices
    if segment_indices_for_chunks is None:
        # Fallback: use chunk position as segment index (not ideal, but backward compatible)
        segment_indices_for_chunks = list(range(len(chunks)))
        logger.warning(
            LogModule.TRANS,
            f"[CHUNK_TRANSLATION] No segment_indices provided, using chunk position as segment index. "
            f"This may cause incorrect mapping if segments are excluded."
        )
    
    # Build chunk_to_segment_map by simulating the merging process
    # chunks2merged_chunks will merge small chunks together
    # NOTE: chunk_size is in tokens, but chunks2merged_chunks expects characters
    # send_chunks_async passes it directly, so we do the same for consistency
    # This may not be perfect, but it matches the actual merging behavior
    # CRITICAL: Pass segment_indices to chunks2merged_chunks to preserve original segment indices
    merged_chunks, merged_indices_list = await asyncio.to_thread(
        chunks2merged_chunks, chunks, chunk_size, segment_indices_for_chunks
    )
    
    # Build chunk_to_segment_map from merged_indices_list
    # merged_indices_list is a list of (start_idx, end_idx) tuples
    # CRITICAL: Build a map that maps ORIGINAL chunks (before merging) to segment indices
    # This is needed because split_merged_chunks returns translated chunks for original chunks
    # CRITICAL: segment_indices_for_chunks may contain integers (single segment per chunk)
    # or lists (multiple segments per chunk when chunks were expanded)
    chunk_to_segment_map: List[List[int]] = []
    for chunk_idx in range(len(chunks)):
        # Get segment index(es) for this original chunk
        if segment_indices_for_chunks and chunk_idx < len(segment_indices_for_chunks):
            segment_idx_or_list = segment_indices_for_chunks[chunk_idx]
            # Handle both single integer and list of integers
            if isinstance(segment_idx_or_list, list):
                # Multiple segments per chunk (expanded chunks)
                chunk_to_segment_map.append(segment_idx_or_list)
            else:
                # Single segment per chunk
                chunk_to_segment_map.append([segment_idx_or_list])
        else:
            # Fallback: use chunk position as segment index
            chunk_to_segment_map.append([chunk_idx])
    
    logger.info(
        LogModule.TRANS,
        f"[CHUNK_TRANSLATION] Built chunk_to_segment_map for PDF (with merging): "
        f"{len(chunk_to_segment_map)} merged chunks mapping to {len(chunks)} segments. "
        f"Sample mappings: {chunk_to_segment_map[:3] if len(chunk_to_segment_map) > 3 else chunk_to_segment_map}"
    )
    
    # Step 2: Save chunk_to_segment_map to task_state for record_translation_segments
    # CRITICAL: Do NOT overwrite source_chunks_cache here!
    # For PDF workflow, Extract phase has already built source_chunks_cache with correct segment_index-based indexing
    # This cache contains ALL segments (including excluded ones) indexed by segment_index
    # If we overwrite it with filtered chunks, record_translation_segments will use wrong indices
    if task_state and task_id:
        try:
            # Save chunk_to_segment_map to task_state for record_translation_segments
            task_state["chunk_to_segment_map"] = chunk_to_segment_map
            
            # CRITICAL: Preserve existing source_chunks_cache from Extract phase
            # For PDF workflow, Extract phase has already built source_chunks_cache with correct segment_index-based indexing
            # If we overwrite it with filtered chunks, record_translation_segments will use wrong indices
            existing_cache = task_state.get("source_chunks_cache", {})
            if not existing_cache or not existing_cache.get("segments"):
                # This should not happen for PDF workflow - Extract phase should have created the cache
                logger.error(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] No existing source_chunks_cache found for PDF workflow! "
                    f"This will cause index mismatches for excluded segments. "
                    f"Creating fallback cache with filtered chunks ({len(chunks)} chunks)."
                )
                content_hash = None
                if file_contents:
                    content_hash = hashlib.sha1(file_contents).hexdigest()
                elif original_filename:
                    content_hash = hashlib.sha1(original_filename.encode('utf-8')).hexdigest()
                
                task_state["source_chunks_cache"] = {
                    "content_hash": content_hash,
                    "chunk_size": chunk_size,
                    "segments": chunks,  # Fallback only - may cause index mismatches
                    "total_segments": len(chunks),
                    "created_at": time.time(),
                }
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Saved chunk_to_segment_map to task_state for task {task_id}"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to save chunk_to_segment_map to cache: {e}",
                exc_info=True
            )
    
    # Step 3: Translate using MDTranslateAgent (handles chunk merging internally via send_chunks_async)
    # send_chunks_async will merge chunks and then split them back
    # CRITICAL: Pass original segment_indices_for_chunks so that merged chunks are formatted as "0: text\n1: text\n4: text" (skipping excluded segments)
    # This allows accurate splitting after translation based on segment indices, not chunk positions
    if translate_agent:
        # Set task_id and task_state on agent for LLM API input/output saving
        if task_id and task_state:
            translate_agent.task_id = task_id
            translate_agent.task_state = task_state
        
        logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Starting translation with {len(chunks)} chunks")
        
        translated_chunks = await translate_agent.send_chunks_async(
            chunks,
            progress_callback,
            chunk_size=chunk_size,
            segment_indices=segment_indices_for_chunks  # CRITICAL: Use original segment indices
        )
        
        logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Translation completed, got {len(translated_chunks)} translated chunks")
        
        # CRITICAL: Validate that translated chunks count matches input chunks count
        # After split_merged_chunks, the count should match
        if len(translated_chunks) != len(chunks):
            error_msg = (
                f"Translation failed: translated chunks count ({len(translated_chunks)}) "
                f"does not match input chunks count ({len(chunks)}). "
                f"This may be caused by chunk merging/splitting errors in send_chunks_async."
            )
            logger.error(LogModule.TRANS, f"[CHUNK_TRANSLATION] {error_msg}")
            raise ValueError(error_msg)
        
        # CRITICAL: Always try to save debug files - log this decision point
        logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: About to check debug mode and save comparison files")
        
        # Save chunks to temporary folder for debugging if DEBUG or TRACE mode is enabled
        # CRITICAL: Check both logger.level and isEnabledFor to ensure we catch DEBUG and TRACE levels
        # TRACE_LEVEL (5) < DEBUG (10), so check for both levels
        from logger.logger import TRACE_LEVEL
        is_debug_enabled = (
            logger.level <= logging.DEBUG or 
            logger.isEnabledFor(logging.DEBUG) or 
            logger.isEnabledFor(TRACE_LEVEL)
        )
        
        # CRITICAL: Also check config file directly to ensure we save files when DEBUG is set
        try:
            from logger.logger import get_log_level_from_config
            config_level = get_log_level_from_config()
            # If config level is DEBUG or lower, force enable debug file saving
            if config_level <= logging.DEBUG:
                is_debug_enabled = True
                logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] Forcing debug file saving because config level ({config_level}) <= DEBUG")
        except Exception:
            pass  # If we can't check config, use the previous check result
        
        # Log debug mode check result for diagnosis
        check_msg = (
            f"[CHUNK_TRANSLATION] Debug mode check (translate_chunks_with_agent_async): "
            f"isEnabledFor(DEBUG)={logger.isEnabledFor(logging.DEBUG)}, "
            f"isEnabledFor(TRACE)={logger.isEnabledFor(TRACE_LEVEL)}, "
            f"logger.level={logger.level}, DEBUG={logging.DEBUG}, TRACE={TRACE_LEVEL}, "
            f"is_debug_enabled={is_debug_enabled}"
        )
        if hasattr(logger, 'trace'):
            logger.trace(LogModule.TRANS, check_msg)
        else:
            logger.debug(LogModule.TRANS, check_msg)
        logger.info(LogModule.TRANS, check_msg)  # Also log at info level
        
        # CRITICAL: Always try to save debug files if DEBUG or TRACE level is configured
        # This ensures files are created even if logger level check fails
        logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: is_debug_enabled={is_debug_enabled}, will {'SAVE' if is_debug_enabled else 'SKIP'} debug files")
        
        if is_debug_enabled:
            try:
                logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Creating debug directory...")
                # Use task_state temp_dir if available, otherwise create independent debug directory
                debug_dir = None
                if task_state:
                    temp_dir = task_state.get("temp_dir")
                    logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: task_state exists, temp_dir={temp_dir}")
                    if temp_dir and os.path.isdir(temp_dir):
                        debug_dir = os.path.join(temp_dir, "debug", "translation")
                        os.makedirs(debug_dir, exist_ok=True)
                        logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Created debug_dir from temp_dir: {debug_dir}")
                        # Store debug directory path in task_state
                        if "debug_files" not in task_state:
                            task_state["debug_files"] = {}
                        task_state["debug_files"]["translation_debug_dir"] = debug_dir
                
                # Fallback: create independent debug directory if task_state temp_dir not available
                if not debug_dir:
                    debug_dir = tempfile.mkdtemp(prefix=f"translation_debug_{task_id or 'unknown'}_")
                    logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Created fallback debug_dir: {debug_dir}")
                
                # Save chunks side-by-side comparison
                chunks_comparison_file = os.path.join(debug_dir, "chunks_comparison.txt")
                with open(chunks_comparison_file, 'w', encoding='utf-8') as f:
                    max_idx = max(len(chunks), len(translated_chunks))
                    for idx in range(max_idx):
                        f.write(f"{'='*80}\n")
                        f.write(f"Chunk {idx}\n")
                        f.write(f"{'='*80}\n")
                        f.write("ORIGINAL:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(chunks):
                            f.write(chunks[idx])
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                        f.write("TRANSLATED:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(translated_chunks):
                            f.write(translated_chunks[idx])
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                
                # Save LLM API input and output if available
                # CRITICAL: Get from task_state AFTER send_segments/send_segments_async has updated it
                # Also try to get from translate_agent.task_state if available (more reliable)
                llm_api_input = None
                llm_api_output = None
                llm_api_system_prompt = None
                
                # First try to get from translate_agent.task_state (most reliable)
                if translate_agent and hasattr(translate_agent, 'task_state') and translate_agent.task_state:
                    llm_api_input = translate_agent.task_state.get('llm_api_input')
                    llm_api_output = translate_agent.task_state.get('llm_api_output')
                    llm_api_system_prompt = translate_agent.task_state.get('llm_api_system_prompt')
                
                # Fallback to task_state parameter if not found in agent
                if not llm_api_input or not llm_api_output:
                    if task_state:
                        llm_api_input = task_state.get('llm_api_input') or llm_api_input
                        llm_api_output = task_state.get('llm_api_output') or llm_api_output
                        llm_api_system_prompt = task_state.get('llm_api_system_prompt') or llm_api_system_prompt
                
                # Log debug info to help diagnose why file might not be created
                api_check_msg = (
                    f"[CHUNK_TRANSLATION] LLM API debug info check (translate_chunks_with_agent_async): "
                    f"task_state exists={task_state is not None}, "
                    f"llm_api_input exists={llm_api_input is not None}, "
                    f"llm_api_output exists={llm_api_output is not None}, "
                    f"llm_api_input length={len(llm_api_input) if llm_api_input else 0}, "
                    f"llm_api_output length={len(llm_api_output) if llm_api_output else 0}"
                )
                if hasattr(logger, 'trace'):
                    logger.trace(LogModule.TRANS, api_check_msg)
                else:
                    logger.debug(LogModule.TRANS, api_check_msg)
                logger.info(LogModule.TRANS, api_check_msg)  # Also log at info level
                
                # CRITICAL: Always try to save file if is_debug_enabled, even if llm_api_input/output are empty
                # This helps diagnose why data might be missing
                llm_api_comparison_file = os.path.join(debug_dir, "llm_api_comparison.txt")
                logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: Will create llm_api_comparison.txt at: {llm_api_comparison_file}")
                
                if llm_api_input and llm_api_output:
                    logger.info(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: llm_api_input and llm_api_output are available, creating comparison file with data")
                    create_msg = f"[CHUNK_TRANSLATION] Creating LLM API comparison file: {llm_api_comparison_file}"
                    logger.info(LogModule.TRANS, create_msg)
                    if hasattr(logger, 'trace'):
                        logger.trace(LogModule.TRANS, create_msg)
                    with open(llm_api_comparison_file, 'w', encoding='utf-8') as f:
                        # Write system prompt at the beginning if available
                        if llm_api_system_prompt:
                            f.write(f"{'='*80}\n")
                            f.write("SYSTEM PROMPT:\n")
                            f.write(f"{'='*80}\n")
                            f.write(llm_api_system_prompt)
                            f.write("\n\n")
                            f.write("Note: The system prompt above may be modified by pre_send_handler (e.g., glossary added).\n")
                            f.write("Each request below uses this system prompt (or a modified version with glossary).\n")
                            f.write(f"{'='*80}\n\n")
                        
                        max_idx = max(len(llm_api_input), len(llm_api_output))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"LLM API Request {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("INPUT:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(llm_api_input):
                                f.write(llm_api_input[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("OUTPUT:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(llm_api_output):
                                f.write(str(llm_api_output[idx]))
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    success_msg = f"[CHUNK_TRANSLATION] Successfully created LLM API comparison file: {llm_api_comparison_file}"
                    logger.info(LogModule.TRANS, success_msg)
                    if hasattr(logger, 'trace'):
                        logger.trace(LogModule.TRANS, success_msg)
                else:
                    # Create empty file with diagnostic info to help debug why data is missing
                    logger.warning(LogModule.TRANS, f"[CHUNK_TRANSLATION] translate_chunks_with_agent_async: llm_api_input or llm_api_output is missing, creating diagnostic file")
                    with open(llm_api_comparison_file, 'w', encoding='utf-8') as f:
                        f.write("="*80 + "\n")
                        f.write("LLM API COMPARISON FILE (DIAGNOSTIC MODE)\n")
                        f.write("="*80 + "\n\n")
                        f.write("WARNING: llm_api_input or llm_api_output is missing!\n\n")
                        f.write(f"Diagnostic Information:\n")
                        f.write(f"  - task_state exists: {task_state is not None}\n")
                        f.write(f"  - translate_agent exists: {translate_agent is not None}\n")
                        f.write(f"  - translate_agent.task_state exists: {translate_agent and hasattr(translate_agent, 'task_state') and translate_agent.task_state is not None}\n")
                        f.write(f"  - llm_api_input exists: {llm_api_input is not None}\n")
                        f.write(f"  - llm_api_input length: {len(llm_api_input) if llm_api_input else 0}\n")
                        f.write(f"  - llm_api_output exists: {llm_api_output is not None}\n")
                        f.write(f"  - llm_api_output length: {len(llm_api_output) if llm_api_output else 0}\n")
                        f.write(f"  - llm_api_system_prompt exists: {llm_api_system_prompt is not None}\n")
                        f.write("\nThis file was created because debug mode is enabled, but the LLM API data was not available.\n")
                        f.write("This may indicate that:\n")
                        f.write("  1. send_segments/send_segments_async did not save data to task_state\n")
                        f.write("  2. task_state was not properly passed to the translation agent\n")
                        f.write("  3. The translation agent's task_state was not updated\n")
                    
                    warning_msg = (
                        f"[CHUNK_TRANSLATION] LLM API comparison file created but EMPTY (data missing): {llm_api_comparison_file}\n"
                        f"  llm_api_input={llm_api_input is not None} (len={len(llm_api_input) if llm_api_input else 0}), "
                        f"llm_api_output={llm_api_output is not None} (len={len(llm_api_output) if llm_api_output else 0})"
                    )
                    logger.warning(LogModule.TRANS, warning_msg)
                    if hasattr(logger, 'trace'):
                        logger.trace(LogModule.TRANS, warning_msg)
                
                logger.info(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Debug mode enabled: Saved {len(chunks)} chunks to temporary folder: {debug_dir}"
                )
                logger.info(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] LLM API comparison file location: {llm_api_comparison_file}"
                )
            except Exception as debug_e:
                logger.error(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Failed to save debug files: {debug_e}",
                    exc_info=True
                )
                logger.debug(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Debug files saved:\n"
                    f"  - Chunks comparison: {chunks_comparison_file}\n"
                    f"  - LLM API comparison: {llm_api_comparison_file if 'llm_api_comparison_file' in locals() and llm_api_comparison_file else '(not available)'}\n"
                    f"  - Temporary folder: {debug_dir}"
                )
            except Exception as e:
                logger.warning(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Failed to save debug chunks to temporary folder: {e}",
                    exc_info=True
                )
        else:
            # Log why debug saving was skipped (use warning to ensure visibility)
            skip_msg = (
                f"[CHUNK_TRANSLATION] Debug file saving skipped (translate_chunks_with_agent_async): "
                f"isEnabledFor(DEBUG)={logger.isEnabledFor(logging.DEBUG)}, "
                f"isEnabledFor(TRACE)={logger.isEnabledFor(TRACE_LEVEL)}, "
                f"logger.level={logger.level}, DEBUG={logging.DEBUG}, TRACE={TRACE_LEVEL}"
            )
            logger.warning(LogModule.TRANS, skip_msg)  # Use warning to ensure visibility
            if hasattr(logger, 'trace'):
                logger.trace(LogModule.TRANS, skip_msg)
            else:
                logger.debug(LogModule.TRANS, skip_msg)
    else:
        # Fallback: return original chunks if no agent provided
        logger.warning(LogModule.TRANS, "[CHUNK_TRANSLATION] No translate_agent provided, returning original chunks")
        translated_chunks = chunks
    
    metadata = {
        "chunk_to_segment_map": chunk_to_segment_map,
        "layout_chunk_block_map": layout_chunk_block_map,  # Pass through for PDF rendering
    }
    
    return translated_chunks, metadata


def translate_segments_with_chunking(
    segments: List[str],
    chunk_size: int,
    translate_func: Callable[[List[str]], List[str]],
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
) -> Tuple[List[str], dict]:
    """
    Translate segments with chunk merging to save tokens.
    
    This function:
    1. Merges segments into chunks based on chunk_size
    2. Translates chunks using the provided translate_func
    3. Maps translated chunks back to individual segments
    4. Optionally saves segments to source_chunks_cache for proper mapping
    
    Args:
        segments: List of original text segments to translate
        chunk_size: Maximum size (in bytes) for merged chunks
        translate_func: Function that takes a list of chunk texts and returns translated texts
                       Signature: translate_func(chunks: List[str]) -> List[str]
        task_id: Optional task ID for saving segments cache
        task_state: Optional task state dictionary for saving segments cache
        original_filename: Optional original filename for cache key
        file_contents: Optional original file contents for cache hash
        
    Returns:
        Tuple containing:
        - translated_segments: List of translated segments (same length as input segments)
        - metadata: Dictionary with metadata about the translation process:
            - chunks_count: Number of chunks created
            - segments_count: Number of segments
            - chunk_to_segment_map: List of lists, mapping chunk index to segment indices
            - merged_indices_list: List of (start, end) tuples for merged segments
    
    Example:
        def my_translate_func(chunks):
            # Translate chunks using your translation agent
            return [translate(chunk) for chunk in chunks]
        
        segments = ["Hello", "World", "Foo", "Bar"]
        translated, metadata = translate_segments_with_chunking(
            segments=segments,
            chunk_size=3000,
            translate_func=my_translate_func,
            task_id="task123",
            task_state=task_state,
        )
    """
    if not segments:
        return [], {
            "chunks_count": 0,
            "segments_count": 0,
            "chunk_to_segment_map": [],
            "merged_indices_list": [],
        }
    
    # Step 1: Merge segments into chunks using segments2json_chunks logic
    # Calculate text content token limit (excluding system prompt and overhead)
    from utils.chunk_size_converter import get_text_content_token_limit
    text_token_limit = get_text_content_token_limit(chunk_size)
    indexed_originals, chunks, merged_indices_list = segments2json_chunks(segments, text_token_limit)
    
    # Convert chunks from dict format to list of strings for translation
    # chunks is a list of dicts like [{"0": "text1", "1": "text2"}, {"2": "text3"}]
    # We need to merge the values in each chunk into a single string
    chunk_texts = []
    chunk_to_segment_map = []  # Maps chunk index to list of segment indices
    
    for chunk_dict in chunks:
        # Get segment indices for this chunk
        segment_indices = [int(k) for k in sorted(chunk_dict.keys(), key=int)]
        chunk_to_segment_map.append(segment_indices)
        
        # Merge segment texts in this chunk with separator
        chunk_text = "\n\n".join(chunk_dict.values())
        chunk_texts.append(chunk_text)
    
    logger.info(
        LogModule.TRANS,
        f"[CHUNK_TRANSLATION] Merged {len(segments)} segments into {len(chunk_texts)} chunks "
        f"(chunk_size={chunk_size})"
    )
    
    # Step 2: Translate chunks
    translated_chunk_texts = translate_func(chunk_texts)
    
    if len(translated_chunk_texts) != len(chunk_texts):
        logger.error(
            LogModule.TRANS,
            f"[CHUNK_TRANSLATION] Translated chunks count ({len(translated_chunk_texts)}) "
            f"does not match source chunks count ({len(chunk_texts)})"
        )
        # Fallback: return original segments if translation fails
        return segments, {
            "chunks_count": len(chunk_texts),
            "segments_count": len(segments),
            "chunk_to_segment_map": chunk_to_segment_map,
            "merged_indices_list": merged_indices_list,
        }
    
    # Step 3: Map translated chunks back to segments
    # Strategy: Split translated chunk text back to segments
    # For merged segments, we need to split by the separator used during merging
    translated_segments = []
    
    for chunk_idx, translated_chunk_text in enumerate(translated_chunk_texts):
        segment_indices = chunk_to_segment_map[chunk_idx]
        
        if not segment_indices:
            # Empty chunk - skip
            continue
        
        if len(segment_indices) == 1:
            # Single segment - use translated chunk text as-is
            translated_segments.append((segment_indices[0], translated_chunk_text))
        else:
            # Multiple segments merged - try to split back
            # Use double newline as separator (same as used in merging)
            split_parts = translated_chunk_text.split("\n\n")
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Splitting chunk {chunk_idx}: "
                f"expected_segments={len(segment_indices)}, "
                f"actual_parts={len(split_parts)}, "
                f"text_preview={translated_chunk_text[:200]!r}"
            )
            
            if len(split_parts) == len(segment_indices):
                # Perfect split - assign each part to its segment
                for seg_idx, part in zip(segment_indices, split_parts):
                    translated_segments.append((seg_idx, part))
            elif len(split_parts) > len(segment_indices):
                # More parts than expected - distribute evenly
                parts_per_segment = len(split_parts) // len(segment_indices)
                remainder = len(split_parts) % len(segment_indices)
                
                part_idx = 0
                for i, seg_idx in enumerate(segment_indices):
                    count = parts_per_segment + (1 if i < remainder else 0)
                    segment_parts = split_parts[part_idx:part_idx + count]
                    translated_segments.append((seg_idx, "\n\n".join(segment_parts)))
                    part_idx += count
            else:
                # Fewer parts than expected - cannot reliably split
                # Mark all segments as failed (empty string) to allow user to retranslate via "Translate Failed"
                logger.warning(
                    LogModule.TRANS,
                    f"[CHUNK_TRANSLATION] Cannot split chunk {chunk_idx}: "
                    f"expected {len(segment_indices)} segments but got {len(split_parts)} parts. "
                    f"Marking segments {segment_indices} as failed (empty string). "
                    f"User can retranslate via 'Translate Failed' feature."
                )
                # Return empty string for all segments - user can retranslate via "Translate Failed"
                for seg_idx in segment_indices:
                    translated_segments.append((seg_idx, ""))
    
    # Sort by segment index and extract texts
    translated_segments.sort(key=lambda x: x[0])
    result_segments = [text for _, text in translated_segments]
    
    # Ensure result has the same length as input
    while len(result_segments) < len(segments):
        result_segments.append("")
    result_segments = result_segments[:len(segments)]
    
    # Step 4: Save segments to source_chunks_cache if task_state is provided
    if task_state and task_id:
        try:
            # Calculate content hash if file_contents is provided
            content_hash = None
            if file_contents:
                content_hash = hashlib.sha1(file_contents).hexdigest()
            elif original_filename:
                # Use filename as fallback hash
                content_hash = hashlib.sha1(original_filename.encode('utf-8')).hexdigest()
            
            # Save to source_chunks_cache
            task_state["source_chunks_cache"] = {
                "content_hash": content_hash,
                "chunk_size": chunk_size,
                "segments": segments,
                "total_segments": len(segments),
                "created_at": time.time(),
            }
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Saved {len(segments)} segments to source_chunks_cache "
                f"for task {task_id}"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to save segments to cache: {e}",
                exc_info=True
            )
    
    metadata = {
        "chunks_count": len(chunk_texts),
        "segments_count": len(segments),
        "chunk_to_segment_map": chunk_to_segment_map,
        "merged_indices_list": merged_indices_list,
    }
    
    return result_segments, metadata


async def translate_segments_with_chunking_async(
    segments: List[str],
    chunk_size: int,
    translate_func: Callable[[List[str]], Any],  # Returns awaitable
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
) -> Tuple[List[str], dict]:
    """
    Async version of translate_segments_with_chunking.
    
    Args:
        segments: List of original text segments to translate
        chunk_size: Maximum size (in bytes) for merged chunks
        translate_func: Async function that takes a list of chunk texts and returns translated texts
                       Signature: async translate_func(chunks: List[str]) -> List[str]
        task_id: Optional task ID for saving segments cache
        task_state: Optional task state dictionary for saving segments cache
        original_filename: Optional original filename for cache key
        file_contents: Optional original file contents for cache hash
        
    Returns:
        Same as translate_segments_with_chunking
    """
    if not segments:
        return [], {
            "chunks_count": 0,
            "segments_count": 0,
            "chunk_to_segment_map": [],
            "merged_indices_list": [],
        }
    
    # Step 1: Merge segments into chunks (same as sync version)
    # Calculate text content token limit (excluding system prompt and overhead)
    from utils.chunk_size_converter import get_text_content_token_limit
    text_token_limit = get_text_content_token_limit(chunk_size)
    indexed_originals, chunks, merged_indices_list = segments2json_chunks(segments, text_token_limit)
    
    chunk_texts = []
    chunk_to_segment_map = []
    
    for chunk_dict in chunks:
        segment_indices = [int(k) for k in sorted(chunk_dict.keys(), key=int)]
        chunk_to_segment_map.append(segment_indices)
        chunk_text = "\n\n".join(chunk_dict.values())
        chunk_texts.append(chunk_text)
    
    logger.info(
        LogModule.TRANS,
        f"[CHUNK_TRANSLATION] Merged {len(segments)} segments into {len(chunk_texts)} chunks "
        f"(chunk_size={chunk_size})"
    )
    
    # Step 2: Translate chunks (async)
    translated_chunk_texts = await translate_func(chunk_texts)
    
    if len(translated_chunk_texts) != len(chunk_texts):
        logger.error(
            LogModule.TRANS,
            f"[CHUNK_TRANSLATION] Translated chunks count ({len(translated_chunk_texts)}) "
            f"does not match source chunks count ({len(chunk_texts)})"
        )
        return segments, {
            "chunks_count": len(chunk_texts),
            "segments_count": len(segments),
            "chunk_to_segment_map": chunk_to_segment_map,
            "merged_indices_list": merged_indices_list,
        }
    
    # Step 3: Map translated chunks back to segments (same as sync version)
    translated_segments = []
    
    for chunk_idx, translated_chunk_text in enumerate(translated_chunk_texts):
        segment_indices = chunk_to_segment_map[chunk_idx]
        
        if not segment_indices:
            continue
        
        if len(segment_indices) == 1:
            translated_segments.append((segment_indices[0], translated_chunk_text))
        else:
            split_parts = translated_chunk_text.split("\n\n")
            
            if len(split_parts) == len(segment_indices):
                for seg_idx, part in zip(segment_indices, split_parts):
                    translated_segments.append((seg_idx, part))
            elif len(split_parts) > len(segment_indices):
                parts_per_segment = len(split_parts) // len(segment_indices)
                remainder = len(split_parts) % len(segment_indices)
                
                part_idx = 0
                for i, seg_idx in enumerate(segment_indices):
                    count = parts_per_segment + (1 if i < remainder else 0)
                    segment_parts = split_parts[part_idx:part_idx + count]
                    translated_segments.append((seg_idx, "\n\n".join(segment_parts)))
                    part_idx += count
            else:
                for seg_idx in segment_indices:
                    translated_segments.append((seg_idx, translated_chunk_text))
    
    translated_segments.sort(key=lambda x: x[0])
    result_segments = [text for _, text in translated_segments]
    
    while len(result_segments) < len(segments):
        result_segments.append("")
    result_segments = result_segments[:len(segments)]
    
    # Step 4: Save segments to source_chunks_cache (same as sync version)
    if task_state and task_id:
        try:
            content_hash = None
            if file_contents:
                content_hash = hashlib.sha1(file_contents).hexdigest()
            elif original_filename:
                content_hash = hashlib.sha1(original_filename.encode('utf-8')).hexdigest()
            
            task_state["source_chunks_cache"] = {
                "content_hash": content_hash,
                "chunk_size": chunk_size,
                "segments": segments,
                "total_segments": len(segments),
                "created_at": time.time(),
            }
            
            logger.debug(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Saved {len(segments)} segments to source_chunks_cache "
                f"for task {task_id}"
            )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[CHUNK_TRANSLATION] Failed to save segments to cache: {e}",
                exc_info=True
            )
    
    metadata = {
        "chunks_count": len(chunk_texts),
        "segments_count": len(segments),
        "chunk_to_segment_map": chunk_to_segment_map,
        "merged_indices_list": merged_indices_list,
    }
    
    return result_segments, metadata
