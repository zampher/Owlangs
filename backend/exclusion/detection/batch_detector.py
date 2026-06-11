# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Batch exclusion detection service for all document formats.

This module provides a unified batch detection service that processes
all segments using format-specific metadata extractors and stores
exclusions using ExclusionManager.
"""

from typing import Dict, List, Optional, Union, Any, Tuple, Callable
import time
import os
import re
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_manager import (
    ExclusionManager,
    ExclusionReason
)
from exclusion.core.exclusion_detector import detect_exclusion_reason
from exclusion.extractors.base import FormatMetadataExtractor


def _process_single_segment(
    idx: int,
    segment: Union[str, dict],
    segment_text: str,
    metadata: dict,
    format_name: str,
    target_lang: Optional[str],
    existing_excluded: dict,
    user_unexcluded_set: set,
    preserve_existing: bool,
    auto_exclude_optional: bool,
    default_excluded_reasons: Optional[set] = None,
) -> Tuple[int, Optional[ExclusionReason], Optional[ExclusionReason]]:
    """
    Process a single segment for exclusion detection.
    
    Returns:
        Tuple of (idx, excluded_reason, detected_reason):
        - idx: Segment index
        - excluded_reason: ExclusionReason if segment should be excluded, None otherwise
        - detected_reason: ExclusionReason if detected, None otherwise
    """
    # Skip if user explicitly unexcluded
    if idx in user_unexcluded_set:
        return (idx, None, None)
    
    # Determine if strict_table_priority should be used (PDF format only)
    strict_table_priority = (format_name == "pdf")
    
    # CRITICAL: Check if segment contains actual text content (not just placeholder)
    # Image captions (e.g., "Figure 1: ...") contain actual text and should NOT be excluded as image
    # even if is_image=True (because they share block_indices with image blocks)
    has_actual_text = False
    if segment_text:
        # Remove placeholder and whitespace, check if there's actual text left
        text_without_placeholder = re.sub(r'<ph-[^>]+>', '', segment_text).strip()
        # Check if there's meaningful text (not just whitespace or very short)
        if text_without_placeholder and len(text_without_placeholder) > 3:
            has_actual_text = True
    
    # CRITICAL: If segment has actual text content (e.g., image caption), set is_image=False
    # to prevent it from being detected as IMAGE exclusion reason
    # Image captions share block_indices with image blocks, but contain actual text content
    metadata_is_image = metadata.get("is_image", False)
    detection_is_image = metadata_is_image if not has_actual_text else False
    
    # CRITICAL: Check if already excluded (preserve existing) BEFORE detection
    # This ensures user_selected exclusions are preserved even if no exclusion reason is detected
    if preserve_existing and idx in existing_excluded:
        existing_reason = existing_excluded[idx]
        # Preserve user-selected exclusions (highest priority)
        if existing_reason == ExclusionReason.USER_SELECTED:
            # Still try to detect reason for frontend display, but preserve user_selected
            detected_result = detect_exclusion_reason(
                text=segment_text,
                block_type=metadata.get("block_type"),
                target_lang=target_lang,
                is_image=detection_is_image,
                is_table=metadata.get("is_table", False),
                strict_table_priority=strict_table_priority
            )
            detected_reason = detected_result[0] if detected_result else None
            return (idx, existing_reason, detected_reason)
    
    # Detect exclusion reason
    detected_result = detect_exclusion_reason(
        text=segment_text,
        block_type=metadata.get("block_type"),
        target_lang=target_lang,
        is_image=detection_is_image,
        is_table=metadata.get("is_table", False),
        strict_table_priority=strict_table_priority
    )
    
    if not detected_result:
        # CRITICAL: Even if no exclusion reason is detected, check if segment was already excluded
        # This preserves user_selected exclusions that don't match any automatic detection criteria
        if preserve_existing and idx in existing_excluded:
            existing_reason = existing_excluded[idx]
            # Preserve user-selected exclusions even when no detection result
            if existing_reason == ExclusionReason.USER_SELECTED:
                return (idx, existing_reason, None)
        return (idx, None, None)
    
    detected_reason, detected_metadata = detected_result
    
    # CRITICAL: If segment has actual text content (e.g., image caption), do NOT exclude it as IMAGE
    # even if detected_reason is IMAGE (because image captions share block_indices with image blocks)
    # NOTE: This is a defensive check. Since we set detection_is_image=False when has_actual_text=True,
    # detect_exclusion_reason should not return IMAGE. However, we keep this check as a safety net
    # in case _is_image_segment() returns True for edge cases (e.g., markdown image syntax in caption).
    if has_actual_text and detected_reason == ExclusionReason.IMAGE:
        # This is likely an image caption segment - it has actual text content, so don't exclude it
        logger.debug(
            LogModule.EXCLUSION,
            f"[EXCLUSION-BATCH] Segment {idx} has actual text content (likely image caption), "
            f"not excluding as image. detected_reason=IMAGE, text_preview={segment_text[:50]}..."
        )
        # Return detected_reason for frontend display, but don't exclude it
        return (idx, None, detected_reason)
    
    # CRITICAL: Check if already excluded (preserve existing) BEFORE processing detected reason
    # User-selected exclusions have highest priority and should be preserved even if
    # content-based exclusion is detected
    if preserve_existing and idx in existing_excluded:
        existing_reason = existing_excluded[idx]
        # Preserve user-selected exclusions (highest priority)
        if existing_reason == ExclusionReason.USER_SELECTED:
            return (idx, existing_reason, detected_reason)
        # Preserve content-based exclusions
        if ExclusionReason.is_content_based(existing_reason):
            return (idx, existing_reason, detected_reason)
    
    # --- Config-driven auto-exclusion decision ---
    # Build effective set: config defaults + auto_exclude_optional override
    effective_excluded = default_excluded_reasons if default_excluded_reasons is not None else ExclusionReason.get_default_excluded()
    if auto_exclude_optional:
        # Add optional types (TABLE, CHART) to effective_excluded if not already present
        optional_reasons = {ExclusionReason.TABLE, ExclusionReason.CHART}
        effective_excluded = effective_excluded | {r for r in optional_reasons if r not in effective_excluded}

    if detected_reason in effective_excluded:
        # Auto-exclude per configuration
        return (idx, detected_reason, detected_reason)
    else:
        # Detect only — preserve existing user choice if present
        if preserve_existing and idx in existing_excluded:
            existing_reason = existing_excluded[idx]
            if existing_reason == detected_reason:
                return (idx, detected_reason, detected_reason)
        return (idx, None, detected_reason)


class ExclusionDetectionBatch:
    """Batch exclusion detection service for all document formats."""
    
    @staticmethod
    def _get_optimal_thread_count() -> int:
        """
        Calculate optimal thread count: 2/3 of CPU cores.
        
        Returns:
            Thread count (at least 1)
        """
        cpu_count = multiprocessing.cpu_count()
        thread_count = max(1, int(cpu_count * 2 / 3))
        return thread_count
    
    @staticmethod
    def _update_progress(
        task_state: dict,
        operation: str,
        completed: int,
        total: int,
        base_progress: int = 0,
        progress_range: int = 100
    ) -> None:
        """
        Update progress for an operation.
        
        Args:
            task_state: Task state dictionary
            operation: Operation name (e.g., 'identifying', 'language_matching')
            completed: Number of completed items
            total: Total number of items
            base_progress: Base progress percentage (default: 0)
            progress_range: Progress range percentage (default: 100)
        """
        if total == 0:
            return
        
        percent = int((completed / total) * progress_range)
        progress = base_progress + percent
        
        # Map operation names to friendly display names
        operation_display_map = {
            'identifying': 'Detect Identifier',
            'language_matching': 'Detect Language',
            'detecting_exclusions': 'Detect Exclusions',
        }
        operation_display = operation_display_map.get(operation, operation.replace('_', ' ').title())
        message = f"{operation_display}: {completed}/{total} segments ({percent}%)"
        
        try:
            task_state["progress"] = min(100, progress)
            task_state["message"] = message
            # Update via task_manager if available (so getStatus returns latest progress for frontend)
            task_id = task_state.get("task_id")
            if task_id:
                from backend.app.services.task import task_manager
                task_manager.update_last_logged_status(
                    task_id,
                    {'status': task_state.get('status', 'processing'), 'progress': progress, 'message': message}
                )
                logger.debug(
                    LogModule.EXCLUSION,
                    f"[EXCLUSION-BATCH] Progress persisted for task_id={task_id}: {message} (progress={progress}%)"
                )
        except Exception as e:
            logger.warning(LogModule.EXCLUSION, f"Failed to update progress: {e}")
    
    @staticmethod
    def detect_exclusions_batch(
        segments: List[Union[str, dict]],
        metadata_extractor: FormatMetadataExtractor,
        task_state: dict,
        target_lang: Optional[str] = None,
        format_specific_data: Optional[Dict[int, dict]] = None,
        preserve_existing: bool = True,
        auto_exclude_optional: bool = False
    ) -> Tuple[Dict[int, ExclusionReason], Dict[int, ExclusionReason]]:
        """
        Batch detect exclusions for all segments.
        
        Args:
            segments: List of segment texts or segment objects
            metadata_extractor: Format-specific metadata extractor
            task_state: Task state dictionary (for preserving existing exclusions)
            target_lang: Target language for language-based exclusion
            format_specific_data: Optional format-specific data for each segment
                (e.g., {"0": {"chunk_block_indices": [1, 2], "chunk_type": "image"}})
            preserve_existing: If True, preserve existing exclusions from task_state
            auto_exclude_optional: If True, automatically exclude optional types (TABLE, CHART)
        
        Returns:
            Tuple of (excluded_segments, all_detected_reasons):
            - excluded_segments: Dict mapping segment_index -> ExclusionReason (only excluded segments)
            - all_detected_reasons: Dict mapping segment_index -> ExclusionReason (all detected reasons, including non-excluded)
                This is used for frontend to display all detected types (identifier, language_match, etc.)
        """
        excluded_segments = {}
        all_detected_reasons = {}  # Store all detected reasons for frontend display
        
        # Get existing exclusions if preserve_existing is True
        existing_excluded = {}
        if preserve_existing:
            existing_excluded = ExclusionManager.get_excluded_segments(task_state)
            # CRITICAL: Log existing exclusions for debugging user_selected preservation
            user_selected_count = sum(1 for reason in existing_excluded.values() if reason == ExclusionReason.USER_SELECTED)
            if user_selected_count > 0:
                user_selected_indices = [idx for idx, reason in existing_excluded.items() if reason == ExclusionReason.USER_SELECTED]
                logger.info(
                    LogModule.EXCLUSION,
                    f"[EXCLUSION-BATCH] Found {user_selected_count} user_selected exclusions in existing_excluded: {user_selected_indices[:10]}{'...' if len(user_selected_indices) > 10 else ''}"
                )
        
        # Get user-unexcluded segments
        user_unexcluded_segments = task_state.get("segments_metadata", {}).get("user_unexcluded_segments", [])
        user_unexcluded_set = set(user_unexcluded_segments)
        
        # Get format name once (used for all segments)
        format_name = metadata_extractor.get_format_name()
        
        # Prepare segment data for parallel processing
        # Extract metadata for all segments first (this is usually fast and not CPU-intensive)
        segment_data_list = []
        for idx, segment in enumerate(segments):
            # Get segment text
            if isinstance(segment, dict):
                segment_text = segment.get("text") or segment.get("source_text", "")
            else:
                segment_text = str(segment)
            
            # Extract metadata using format-specific extractor
            format_data = format_specific_data.get(idx, {}) if format_specific_data else {}
            metadata = metadata_extractor.extract_metadata(idx, segment_text, format_data)
            
            segment_data_list.append({
                'idx': idx,
                'segment': segment,
                'segment_text': segment_text,
                'metadata': metadata
            })
        
        # Precompute config-driven default exclusion set (shared by all workers)
        default_excluded_reasons = ExclusionReason.get_default_excluded()

        # Use concurrent processing with ThreadPoolExecutor
        # Thread count: 2/3 of CPU cores
        num_segments = len(segment_data_list)
        thread_count = ExclusionDetectionBatch._get_optimal_thread_count()
        
        logger.info(
            LogModule.EXCLUSION,
            f"[EXCLUSION-BATCH] Using concurrent processing: {num_segments} segments, "
            f"{multiprocessing.cpu_count()} CPU cores, {thread_count} threads"
        )
        
        # Process all segments concurrently
        # Separate Identifier and Language Match detection for independent progress tracking
        segments_to_process = []
        for seg_data in segment_data_list:
            idx = seg_data['idx']
            # Skip if user explicitly unexcluded
            if idx in user_unexcluded_set:
                continue
            segments_to_process.append(seg_data)
        
        # Process segments concurrently with progress updates
        completed = 0
        last_progress_update = 0
        PROGRESS_INTERVAL = 500
        
        # Track Identifier and Language Match progress separately
        identifier_completed = 0
        language_match_completed = 0
        identifier_last_update = 0
        language_match_last_update = 0
        
        # Count total segments for each operation
        identifier_total = len(segments_to_process)  # All segments need Identifier check
        language_match_total = len(segments_to_process) if target_lang else 0  # All segments need Language Match check if target_lang provided
        
        # Initial progress updates
        if identifier_total > 0:
            ExclusionDetectionBatch._update_progress(
                task_state, "identifying", 0, identifier_total,
                base_progress=0, progress_range=50
            )
        if language_match_total > 0:
            ExclusionDetectionBatch._update_progress(
                task_state, "language_matching", 0, language_match_total,
                base_progress=50, progress_range=50
            )
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {executor.submit(_process_single_segment,
                seg_data['idx'],
                seg_data['segment'],
                seg_data['segment_text'],
                seg_data['metadata'],
                format_name,
                target_lang,
                existing_excluded,
                user_unexcluded_set,
                preserve_existing,
                auto_exclude_optional,
                default_excluded_reasons,
            ): seg_data['idx'] for seg_data in segments_to_process}
            
            # Collect results with progress updates
            for future in as_completed(futures):
                try:
                    idx, excluded_reason, detected_reason = future.result()
                    
                    # Skip if user explicitly unexcluded (already handled in _process_single_segment)
                    if idx in user_unexcluded_set:
                        continue
                    
                    # Track Identifier detection progress (every PROGRESS_INTERVAL segments)
                    identifier_completed += 1
                    if identifier_completed - identifier_last_update >= PROGRESS_INTERVAL or identifier_completed == identifier_total:
                        ExclusionDetectionBatch._update_progress(
                            task_state, "identifying", identifier_completed, identifier_total,
                            base_progress=0, progress_range=50
                        )
                        identifier_last_update = identifier_completed
                    
                    # Track Language Match detection progress (every PROGRESS_INTERVAL segments)
                    if target_lang:
                        language_match_completed += 1
                        if language_match_completed - language_match_last_update >= PROGRESS_INTERVAL or language_match_completed == language_match_total:
                            ExclusionDetectionBatch._update_progress(
                                task_state, "language_matching", language_match_completed, language_match_total,
                                base_progress=50, progress_range=50
                            )
                            language_match_last_update = language_match_completed
                    
                    # Log detection result for identifier and language_match
                    if detected_reason and detected_reason in [ExclusionReason.IDENTIFIER, ExclusionReason.LANGUAGE_MATCH]:
                        segment_text = segment_data_list[idx]['segment_text'] if idx < len(segment_data_list) else ''
                        logger.info(
                            LogModule.EXCLUSION,
                            f"[EXCLUSION-BATCH] Segment {idx} detected as {detected_reason.value}: "
                            f"text='{segment_text[:50]}{'...' if len(segment_text) > 50 else ''}', "
                            f"target_lang={target_lang}, "
                            f"is_content_based={ExclusionReason.is_content_based(detected_reason)}, "
                            f"is_language_based={ExclusionReason.is_language_based(detected_reason)}"
                        )
                    
                    # Store detected reason
                    if detected_reason:
                        all_detected_reasons[idx] = detected_reason
                    
                    # Store excluded reason
                    if excluded_reason:
                        excluded_segments[idx] = excluded_reason
                        if ExclusionReason.is_content_based(excluded_reason):
                            logger.debug(
                                LogModule.EXCLUSION,
                                f"[EXCLUSION-BATCH] Segment {idx} detected as {excluded_reason.value} "
                                f"(content-based, auto-excluding). Stored as {excluded_reason.value}."
                            )
                        elif ExclusionReason.is_language_based(excluded_reason):
                            logger.debug(
                                LogModule.EXCLUSION,
                                f"[EXCLUSION-BATCH] Segment {idx} detected as {excluded_reason.value} "
                                f"(language-based, auto-excluding)"
                            )
                        
                except Exception as e:
                    logger.error(
                        LogModule.EXCLUSION,
                        f"[EXCLUSION-BATCH] Error processing segment: {e}"
                    )
        
        # Final progress updates
        if identifier_total > 0:
            ExclusionDetectionBatch._update_progress(
                task_state, "identifying", identifier_total, identifier_total,
                base_progress=0, progress_range=50
            )
        if language_match_total > 0:
            ExclusionDetectionBatch._update_progress(
                task_state, "language_matching", language_match_total, language_match_total,
                base_progress=50, progress_range=50
            )
        
        # Always return tuple: (excluded_segments, all_detected_reasons)
        return excluded_segments, all_detected_reasons
    
    @staticmethod
    def store_exclusions(
        task_state: dict,
        excluded_segments: Dict[int, ExclusionReason],
        segment_metadata: Optional[Dict[int, dict]] = None,
        source: str = "batch_detection",
        all_detected_reasons: Optional[Dict[int, ExclusionReason]] = None
    ) -> None:
        """
        Store exclusions using ExclusionManager.
        
        Args:
            task_state: Task state dictionary
            excluded_segments: Dict mapping segment_index -> ExclusionReason (only excluded segments)
            segment_metadata: Optional metadata for each segment
            source: Source identifier for logging
            all_detected_reasons: Optional dict mapping segment_index -> ExclusionReason (all detected reasons)
                This is used to store all detected exclusion reasons (including non-excluded ones) for frontend display
        """
        # CRITICAL: Store all_detected_reasons even if excluded_segments is empty
        # This ensures frontend can display all detected types (identifier, language_match, etc.)
        # even if they are not currently excluded
        if all_detected_reasons:
            if "segments_metadata" not in task_state:
                task_state["segments_metadata"] = {}
            segments_metadata = task_state["segments_metadata"]
            
            # CRITICAL: Merge with existing detected_exclusion_reasons instead of overwriting
            # This preserves previously detected reasons (e.g., identifier) when updating language_match
            existing_detected_reasons = segments_metadata.get("detected_exclusion_reasons", {})
            if not isinstance(existing_detected_reasons, dict):
                existing_detected_reasons = {}
            
            # Start with existing detected reasons
            detected_reasons_dict = existing_detected_reasons.copy()
            
            # Update with new detected reasons (this will overwrite existing entries for the same segment)
            for idx, reason in all_detected_reasons.items():
                detected_reasons_dict[str(idx)] = {
                    "reason": reason.value,
                    "detected_at": time.time()
                }
            
            segments_metadata["detected_exclusion_reasons"] = detected_reasons_dict
            
            logger.debug(
                LogModule.EXCLUSION,
                f"[EXCLUSION-BATCH] Stored {len(all_detected_reasons)} detected exclusion reasons "
                f"(including {len(excluded_segments)} excluded) for frontend display"
            )
        
        if not excluded_segments:
            return
        
        # Prepare metadata for ExclusionManager
        metadata = {}
        if segment_metadata:
            for idx, reason in excluded_segments.items():
                if idx in segment_metadata:
                    metadata[idx] = segment_metadata[idx]
        
        # Store using ExclusionManager
        ExclusionManager.update_excluded_segments(
            task_state=task_state,
            excluded_segments=excluded_segments,
            metadata=metadata if metadata else None
        )
        
        # Log summary
        reason_counts = {}
        for reason in excluded_segments.values():
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        reason_summary = ', '.join(f'{count} {reason.value}' for reason, count in sorted(reason_counts.items()))
        logger.info(
            LogModule.EXCLUSION,
            f"[EXCLUSION-BATCH] Stored {len(excluded_segments)} excluded segments ({reason_summary})"
        )
