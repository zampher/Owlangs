# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Exclusion management for translation segments.

This module provides ExclusionManager class for managing exclusion data.
"""

from typing import Optional, Dict, List
import time

from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_reason import ExclusionReason

# For backward compatibility: Re-export detect_exclusion_reason
# This allows code that imports from exclusion.core.exclusion_manager to work
from exclusion.core.exclusion_detector import detect_exclusion_reason
__all__ = ["ExclusionManager", "detect_exclusion_reason"]


class ExclusionManager:
    """Unified exclusion management for translation segments."""

    @staticmethod
    def prune_stale_excluded_segments(
        task_state: dict,
        *,
        new_total: int,
        task_id: str = "",
    ) -> int:
        """Drop out-of-range exclusions; keep in-range user_selected only.

        Used when layout rebuild changes segment count/hash so Translate phase
        does not inherit invalid Extract-phase indices.

        Returns number of exclusion entries removed.
        """
        sm = task_state.get("segments_metadata")
        if not isinstance(sm, dict):
            return 0
        excluded = sm.get("excluded_segments")
        if not isinstance(excluded, dict) or not excluded:
            return 0

        kept: Dict[str, object] = {}
        removed = 0
        for key, info in excluded.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                removed += 1
                continue
            if idx < 0 or idx >= new_total:
                removed += 1
                continue
            reason = None
            if isinstance(info, dict):
                reason = info.get("reason")
            elif isinstance(info, str):
                reason = info
            if reason == ExclusionReason.USER_SELECTED.value or reason == "user_selected":
                kept[str(idx)] = info
            else:
                # Auto-detected exclusions are invalid after rebuild; caller re-stores them.
                removed += 1

        if removed:
            sm["excluded_segments"] = kept
            indices = sm.get("excluded_segment_indices")
            if isinstance(indices, list):
                sm["excluded_segment_indices"] = [
                    i
                    for i in indices
                    if isinstance(i, int) and 0 <= i < new_total and str(i) in kept
                ]
            logger.debug(
                LogModule.EXCLUSION,
                f"ExclusionManager.prune_stale_excluded_segments: task={task_id} "
                f"kept={len(kept)} removed={removed} new_total={new_total}",
            )
        return removed

    @staticmethod
    def get_excluded_segments(
        task_state: dict,
        preserve_reasons: Optional[List[ExclusionReason]] = None
    ) -> Dict[int, ExclusionReason]:
        """
        Get excluded segments with their reasons from task_state.
        
        This is the SINGLE SOURCE OF TRUTH for reading exclusion information.
        All code should use this method to read exclusion information.
        
        Priority order:
        1. segments_metadata.excluded_segments (PRIMARY - Extract phase and manual exclusions)
        
        Args:
            task_state: Task state dictionary
            preserve_reasons: List of exclusion reasons to preserve (if None, preserve all)
        
        Returns:
            Dict mapping segment_index -> ExclusionReason
        """
        excluded = {}
        
        # Priority 1: Check segments_metadata.excluded_segments (PRIMARY SOURCE)
        # This is where Extract phase and manual exclusions are stored
        segments_metadata = task_state.get("segments_metadata", {})

        # FINAL OVERRIDE SET: user_unexcluded_segments
        #
        # 手动取消排除的段（user_unexcluded_segments）拥有最高优先级，
        # 必须在所有自动检测和回退逻辑之后再次过滤，保证它们在任何阶段都不会被重新视为排除。
        user_unexcluded = set(segments_metadata.get("user_unexcluded_segments", []) or [])
        excluded_segments = segments_metadata.get("excluded_segments", {})
        
        # Initialize invalid_indices list to track out-of-range segment indices
        invalid_indices = []
        total_segments = None
        
        # Validate excluded_segments format
        if excluded_segments and not isinstance(excluded_segments, dict):
            logger.warning(
                LogModule.EXCLUSION,
                f"excluded_segments is not a dict, got {type(excluded_segments)}"
            )
            excluded_segments = {}
        
        # CRITICAL: Log excluded_segments count for debugging
        if excluded_segments and isinstance(excluded_segments, dict):
            excluded_count = len(excluded_segments)
            # Count user_selected exclusions for debugging
            user_selected_in_excluded = sum(
                1 for info in excluded_segments.values()
                if (isinstance(info, dict) and info.get("reason") == ExclusionReason.USER_SELECTED.value)
                or (isinstance(info, str) and info == ExclusionReason.USER_SELECTED.value)
            )
            logger.debug(
                LogModule.EXCLUSION,
                f"ExclusionManager.get_excluded_segments: Found {excluded_count} excluded_segments in segments_metadata.excluded_segments "
                f"(including {user_selected_in_excluded} user_selected)"
            )
        
        if excluded_segments and isinstance(excluded_segments, dict):
            # Get total segment count for validation
            # CRITICAL: All workflows MUST store segment count in source_chunks_cache.segments
            if task_state:
                cache_info = task_state.get("source_chunks_cache", {})
                if cache_info:
                    cached_segments = cache_info.get("segments", [])
                    if cached_segments and isinstance(cached_segments, list):
                        total_segments = len(cached_segments)
                    else:
                        logger.error(
                            LogModule.EXCLUSION,
                            f"ExclusionManager.get_excluded_segments: source_chunks_cache exists but segments is missing or invalid. "
                            f"Expected List[str], got {type(cached_segments)}. "
                            f"This indicates a workflow implementation error. Segment count validation will be skipped."
                        )
                else:
                    workflow_type = None
                    segments_metadata = task_state.get("segments_metadata", {})
                    if segments_metadata:
                        workflow_type = segments_metadata.get("workflow_type")
                    if not workflow_type:
                        payload = task_state.get("payload")
                        if payload:
                            if isinstance(payload, dict):
                                workflow_type = payload.get("workflow_type")
                            else:
                                workflow_type = getattr(payload, "workflow_type", None)
                    
                    logger.error(
                        LogModule.EXCLUSION,
                        f"ExclusionManager.get_excluded_segments: source_chunks_cache is missing from task_state. "
                        f"Workflow type: {workflow_type}. "
                        f"This indicates Extract phase did not properly store segments in source_chunks_cache. "
                        f"Segment count validation will be skipped. "
                        f"All workflows MUST store segments in task_state['source_chunks_cache']['segments'] during Extract phase. "
                        f"See docs/SEGMENT_COUNT_STORAGE_SPECIFICATION.md for details."
                    )
            for seg_idx_str, exclusion_info in excluded_segments.items():
                try:
                    seg_idx = int(seg_idx_str)
                    
                    # Validate segment index if total_segments is available
                    if total_segments is not None and seg_idx >= total_segments:
                        invalid_indices.append(seg_idx)
                        logger.warning(
                            LogModule.EXCLUSION,
                            f"Excluded segment index {seg_idx} is out of range (total_segments={total_segments}). "
                            f"This may indicate Extract and Translate phases have different segment counts. "
                            f"Skipping this exclusion."
                        )
                        continue
                    
                    # Handle both dict and string formats
                    if isinstance(exclusion_info, dict):
                        reason_str = exclusion_info.get("reason", "unknown")
                    elif isinstance(exclusion_info, str):
                        reason_str = exclusion_info
                    else:
                        logger.warning(
                            LogModule.EXCLUSION,
                            f"Invalid exclusion_info type for segment {seg_idx_str}: {type(exclusion_info)}, value: {exclusion_info}"
                        )
                        reason_str = "unknown"
                    
                    try:
                        reason = ExclusionReason(reason_str)
                    except ValueError:
                        reason = ExclusionReason.UNKNOWN
                        logger.warning(
                            LogModule.EXCLUSION,
                            f"Invalid exclusion reason '{reason_str}' for segment {seg_idx}, using UNKNOWN"
                        )
                    
                    if preserve_reasons is None or reason in preserve_reasons:
                        excluded[seg_idx] = reason
                except (ValueError, TypeError) as e:
                    logger.warning(
                        LogModule.EXCLUSION,
                        f"Invalid excluded_segments entry: {seg_idx_str}={exclusion_info}, error: {e}"
                    )
            
            # CRITICAL: Log error if invalid indices were found
            if invalid_indices:
                logger.error(
                    LogModule.EXCLUSION,
                    f"ExclusionManager.get_excluded_segments: Found {len(invalid_indices)} invalid excluded segment indices "
                    f"(out of range): {invalid_indices[:10]}{'...' if len(invalid_indices) > 10 else ''}. "
                    f"Total segments: {total_segments}, Total excluded_segments: {excluded_count}. "
                    f"This indicates Extract and Translate phases have different segment counts or data inconsistency."
                )
        
        # CRITICAL: Log final count from PRIMARY source and validate consistency
        primary_final_count = len(excluded)
        if excluded_segments and isinstance(excluded_segments, dict):
            original_count = len(excluded_segments)
            if primary_final_count != original_count:
                logger.error(
                    LogModule.EXCLUSION,
                    f"ExclusionManager.get_excluded_segments: INCONSISTENCY DETECTED! "
                    f"Original excluded_segments count: {original_count}, Final excluded count (primary source only): {primary_final_count}. "
                    f"Difference: {original_count - primary_final_count} segments were filtered out. "
                    f"This may indicate segment index validation issues or data corruption."
                )
            else:
                logger.debug(
                    LogModule.EXCLUSION,
                    f"ExclusionManager.get_excluded_segments: Successfully retrieved {primary_final_count} excluded segments "
                    f"(consistent with original count, primary source only)"
                )
        
        # Translate phase uses only Extract-phase excluded_segments plus user modifications.
        # No fallback from detected_exclusion_reasons: exclusion is decided in Extract and by user only.

        # FINAL OVERRIDE: user_unexcluded_segments always win over exclusions
        #
        # Any segment index in user_unexcluded_segments must not appear in the final excluded set.
        if user_unexcluded:
            removed_for_user_unexcluded = 0
            for seg_idx in list(excluded.keys()):
                if seg_idx in user_unexcluded:
                    excluded.pop(seg_idx, None)
                    removed_for_user_unexcluded += 1

            if removed_for_user_unexcluded > 0:
                logger.info(
                    LogModule.EXCLUSION,
                    f"ExclusionManager.get_excluded_segments: Removed {removed_for_user_unexcluded} segments "
                    f"from excluded set due to user_unexcluded_segments override "
                    f"(user_unexcluded_size={len(user_unexcluded)}, final_excluded={len(excluded)})."
                )

        return excluded
    
    @staticmethod
    def update_excluded_segments(
        task_state: dict,
        excluded_segments: Dict[int, ExclusionReason],
        metadata: Optional[Dict[int, dict]] = None
    ) -> None:
        """
        Update excluded segments in task_state.
        
        Args:
            task_state: Task state dictionary
            excluded_segments: Dict mapping segment_index -> ExclusionReason
            metadata: Optional metadata for each excluded segment
        """
        if "segments_metadata" not in task_state:
            task_state["segments_metadata"] = {}
        
        segments_metadata = task_state["segments_metadata"]
        excluded_dict = {}
        
        # CRITICAL: First, preserve existing user_selected exclusions
        # User-selected exclusions are ALWAYS preserved regardless of whether they appear in new_excluded_segments,
        # because they represent explicit user choices that should not be lost during re-detection.
        # This is especially important for XLSX workflows where user manually excludes segments that are not
        # automatically detected as identifiers (e.g., segment 0).
        existing_excluded = segments_metadata.get("excluded_segments", {})
        new_excluded_indices = set(excluded_segments.keys())
        
        for seg_idx_str, exclusion_info in existing_excluded.items():
            # CRITICAL: Handle both dict and string formats for backward compatibility
            if isinstance(exclusion_info, dict):
                existing_reason_str = exclusion_info.get("reason", "")
            else:
                # If exclusion_info is a string, treat it as the reason directly
                existing_reason_str = str(exclusion_info)
            
            seg_idx_int = int(seg_idx_str)
            
            # CRITICAL: ALWAYS preserve user_selected exclusions unconditionally
            # User-selected exclusions represent explicit user choices and must be preserved even if
            # they are not in the new excluded_segments dict (e.g., manually excluded segments that
            # are not automatically detected as identifiers in XLSX workflows).
            # If a user wants to un-exclude a segment, they can do so manually, not through re-detection.
            if existing_reason_str == ExclusionReason.USER_SELECTED.value:
                excluded_dict[seg_idx_int] = {
                    "reason": ExclusionReason.USER_SELECTED.value,
                    "detected_at": exclusion_info.get("detected_at", time.time()) if isinstance(exclusion_info, dict) else time.time(),
                    "metadata": exclusion_info.get("metadata", {}) if isinstance(exclusion_info, dict) else {}
                }
        
        # Then, add/update other excluded segments from the new dict
        for seg_idx, reason in excluded_segments.items():
            seg_idx_int = int(seg_idx)
            if seg_idx_int in excluded_dict and excluded_dict[seg_idx_int]["reason"] == ExclusionReason.USER_SELECTED.value:
                continue
            
            # CRITICAL: Handle both ExclusionReason objects and string values
            if isinstance(reason, ExclusionReason):
                reason_str = reason.value
            else:
                reason_str = str(reason)
            
            excluded_dict[seg_idx_int] = {
                "reason": reason_str,
                "detected_at": time.time(),
                "metadata": metadata.get(seg_idx_int, {}) if metadata else {}
            }
        
        # CRITICAL: Convert integer keys to strings for JSON compatibility
        excluded_dict_str_keys = {str(k): v for k, v in excluded_dict.items()}
        segments_metadata["excluded_segments"] = excluded_dict_str_keys
        
        # Also update excluded_segment_indices for backward compatibility
        # CRITICAL: Use excluded_dict.keys() instead of excluded_segments.keys() to include
        # preserved user_selected exclusions that may not be in excluded_segments
        segments_metadata["excluded_segment_indices"] = sorted(excluded_dict.keys())
        
        # Log update for debugging
        # CRITICAL: Count reasons from excluded_dict (final result) not excluded_segments (input)
        # to accurately reflect all excluded segments including preserved user_selected
        reason_counts = {}
        for seg_idx, exclusion_info in excluded_dict_str_keys.items():
            if isinstance(exclusion_info, dict):
                reason_str = exclusion_info.get("reason", "unknown")
            else:
                reason_str = str(exclusion_info)
            reason_counts[reason_str] = reason_counts.get(reason_str, 0) + 1
        logger.debug(
                LogModule.EXCLUSION,
                f"Updated {len(excluded_dict)} excluded segments in segments_metadata.excluded_segments "
                f"({', '.join(f'{count} {reason}' for reason, count in sorted(reason_counts.items()))})"
            )
    
    @staticmethod
    def get_excluded_indices(
        task_state: dict,
        preserve_reasons: Optional[List[ExclusionReason]] = None
    ) -> List[int]:
        """
        Get list of excluded segment indices (for backward compatibility).
        
        Args:
            task_state: Task state dictionary
            preserve_reasons: List of exclusion reasons to preserve (if None, preserve all)
        
        Returns:
            List of excluded segment indices
        """
        excluded = ExclusionManager.get_excluded_segments(task_state, preserve_reasons)
        return sorted(excluded.keys())
    
    @staticmethod
    def refine_exclusion_reasons(
        task_state: dict,
        segment_indices: Optional[List[int]] = None,
        segment_texts: Optional[Dict[int, str]] = None,
        segment_block_types: Optional[Dict[int, str]] = None,
        target_lang: Optional[str] = None,
        layout_chunk_block_map: Optional[List[List[int]]] = None
    ) -> Dict[int, ExclusionReason]:
        """
        Refine exclusion reasons for excluded segments, updating UNKNOWN reasons to specific reasons.
        
        Args:
            task_state: Task state dictionary
            segment_indices: Optional list of segment indices to refine (if None, refine all UNKNOWN)
            segment_texts: Optional dict mapping segment_index -> text (for detection)
            segment_block_types: Optional dict mapping segment_index -> block_type
            target_lang: Optional target language code
            layout_chunk_block_map: Optional mapping from chunk_idx to block_indices
        
        Returns:
            Dict mapping segment_index -> updated ExclusionReason (only for segments that were updated)
        """
        from exclusion.core.exclusion_detector import detect_exclusion_reason
        from exclusion.core.exclusion_reason import ExclusionReason
        
        excluded_segments = ExclusionManager.get_excluded_segments(task_state)
        segments_to_refine = {}
        for seg_idx, reason in excluded_segments.items():
            if segment_indices is None or seg_idx in segment_indices:
                if reason == ExclusionReason.UNKNOWN:
                    segments_to_refine[seg_idx] = reason
        
        if not segments_to_refine:
            return {}
        
        updated_reasons = {}
        
        for seg_idx in segments_to_refine.keys():
            block_type = None
            segment_text = None
            
            if segment_block_types and seg_idx in segment_block_types:
                block_type = segment_block_types[seg_idx]
            
            if not block_type and layout_chunk_block_map is not None:
                if seg_idx < len(layout_chunk_block_map):
                    block_indices = layout_chunk_block_map[seg_idx]
                    if block_indices and len(block_indices) > 0:
                        layout_doc = task_state.get("layout_document")
                        if layout_doc is not None:
                            try:
                                from layout.base import LayoutDocument as _LD
                                if isinstance(layout_doc, _LD):
                                    first_block_idx = block_indices[0]
                                    for block in layout_doc.iter_blocks():
                                        if block.index == first_block_idx:
                                            block_type = block.type
                                            break
                            except Exception as e:
                                logger.debug(
                                    LogModule.EXCLUSION,
                                    f"Failed to get block_type from layout_document for segment {seg_idx}: {e}"
                                )
            
            if segment_texts and seg_idx in segment_texts:
                segment_text = segment_texts[seg_idx]
            else:
                translation_segments = task_state.get("translation_segments", {})
                if isinstance(translation_segments, dict):
                    segments_list = translation_segments.get("segments", [])
                elif isinstance(translation_segments, list):
                    segments_list = translation_segments
                else:
                    segments_list = []
                
                for seg in segments_list:
                    if isinstance(seg, dict) and seg.get("segment_index") == seg_idx:
                        segment_text = seg.get("source_text") or seg.get("text", "")
                        if not block_type:
                            block_type = seg.get("block_type")
                        break
            
            if segment_text:
                detected_result = detect_exclusion_reason(
                    text=segment_text,
                    block_type=block_type,
                    target_lang=target_lang,
                    is_image=False
                )
                
                if detected_result:
                    detected_reason, detected_metadata = detected_result
                    if detected_reason != ExclusionReason.UNKNOWN:
                        updated_reasons[seg_idx] = detected_reason
                        logger.debug(
                            LogModule.EXCLUSION,
                            f"Refined exclusion_reason for segment {seg_idx} "
                            f"from UNKNOWN to {detected_reason.value} (block_type={block_type})"
                        )
        
        if updated_reasons:
            current_excluded = ExclusionManager.get_excluded_segments(task_state)
            current_excluded.update(updated_reasons)
            ExclusionManager.update_excluded_segments(
                task_state,
                current_excluded,
                metadata=segment_block_types if segment_block_types else None
            )
        
        return updated_reasons
