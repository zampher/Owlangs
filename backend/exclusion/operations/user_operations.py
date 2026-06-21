# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
User operations for exclusion management.

This module provides functions for user-initiated exclusion operations:
- exclude_translation_segment: Exclude a segment (user-initiated)
- unexclude_translation_segment: Unexclude a segment (user-initiated)

Note: These operations use the same detection interface as Extract phase,
but are user-initiated and should preserve user choices.
"""

import time
from typing import Optional

from layout.block_types import TABLE_BODY, TABLE
from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_reason import ExclusionReason
from exclusion.core.exclusion_manager import ExclusionManager
from exclusion.core.exclusion_detector import detect_exclusion_reason


def exclude_translation_segment(
    task_id: str,
    segment_index: int,
    task_state: Optional[dict] = None,
) -> Optional[dict]:
    """
    Exclude a translation segment (user-initiated operation).
    
    This function allows users to manually exclude a segment in Translate phase.
    It uses the same detection interface as Extract phase to ensure consistency.
    
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
        logger.warning(LogModule.TRANS, f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # Find segment by segment_index
    segment = None
    for seg in segments:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break
        elif hasattr(seg, "segment_index") and seg.segment_index == segment_index:
            segment = seg.to_dict() if hasattr(seg, "to_dict") else seg
            break
    
    if segment is None:
        # In Extract phase, segment may not be in translation_segments yet
        logger.info(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Segment not in translation_segments, trying to update segments_metadata.excluded_segments directly (Extract phase)")
        
        # Check if segment already has an exclusion reason
        current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
        existing_reason = current_excluded_map.get(segment_index)
        
        if existing_reason:
            logger.info(
                LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} already has exclusion reason={existing_reason.value} "
                f"in segments_metadata.excluded_segments, preserving it (Extract phase)"
            )
            exclusion_reason = existing_reason
        else:
            # Get segment text from source_chunks_cache or segments_metadata
            segment_text = None
            segments_metadata = task_state.get("segments_metadata", {})
            source_chunks_cache = task_state.get("source_chunks_cache", {})
            segments_text = source_chunks_cache.get("segments", [])
            
            if segment_index < len(segments_text):
                segment_text = segments_text[segment_index]
            
            # Get block_type and other metadata
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
            
            # Detect exclusion reason using same interface as Extract phase
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
                    logger.info(
                        LogModule.TRANS,
                        f"[EXCLUDE_SEGMENT] Detected exclusion reason={exclusion_reason.value} "
                        f"for segment {segment_index} in Extract phase"
                    )
                else:
                    exclusion_reason = ExclusionReason.USER_SELECTED
                    logger.info(
                        LogModule.TRANS,
                        f"[EXCLUDE_SEGMENT] No exclusion reason detected for segment {segment_index}, "
                        f"using USER_SELECTED (Extract phase)"
                    )
            else:
                exclusion_reason = ExclusionReason.USER_SELECTED
                logger.info(
                    LogModule.TRANS,
                    f"[EXCLUDE_SEGMENT] Segment text not available for segment {segment_index}, "
                    f"using USER_SELECTED (Extract phase)"
                )
        
        # Update segments_metadata.excluded_segments
        current_excluded_map[segment_index] = exclusion_reason
        ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
        logger.info(
            LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Updated segments_metadata.excluded_segments for segment {segment_index} "
            f"with reason={exclusion_reason.value} in Extract phase"
        )
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
    segment["is_excluded"] = True
    segment["excluded_at"] = time.time()
    segment["needs_retry"] = False
    segment["is_failed"] = False
    segment["failure_reason"] = None
    
    # Update segments_metadata.excluded_segments (single source of truth)
    current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
    
    # Check segments_metadata.excluded_segments first (PRIMARY source)
    existing_reason_from_metadata = current_excluded_map.get(segment_index)
    current_reason_value = segment.get("exclusion_reason")
    
    # Priority 1: Use existing reason from segments_metadata.excluded_segments
    if existing_reason_from_metadata:
        segment["exclusion_reason"] = existing_reason_from_metadata.value
        logger.info(
            LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Segment {segment_index} already has exclusion reason={existing_reason_from_metadata.value} "
            f"in segments_metadata.excluded_segments, preserving it"
        )
    elif current_reason_value:
        # Priority 2: Use exclusion_reason from segment
        segment["exclusion_reason"] = current_reason_value
        try:
            current_excluded_map[segment_index] = ExclusionReason(current_reason_value)
        except ValueError:
            current_excluded_map[segment_index] = ExclusionReason.UNKNOWN
            segment["exclusion_reason"] = ExclusionReason.UNKNOWN.value
        logger.info(
            LogModule.TRANS,
            f"[EXCLUDE_SEGMENT] Segment {segment_index} already excluded with reason={current_reason_value}, "
            f"keeping original reason and updating segments_metadata"
        )
    else:
        # Not excluded yet - detect appropriate exclusion reason using same interface as Extract phase
        source_text = segment.get("source_text", "")
        block_type = segment.get("block_type")
        is_table = (block_type == TABLE_BODY or block_type == TABLE)

        if not is_table:
            from utils.translation_segments import _is_table_segment
            is_table = _is_table_segment(source_text)
        
        # Use same detection interface as Extract phase
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
            logger.info(
                LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} marked as excluded with reason={detected_reason.value} "
                f"(detected) and updated segments_metadata"
            )
        else:
            segment["exclusion_reason"] = ExclusionReason.USER_SELECTED.value
            segment["exclusion_metadata"] = {}
            current_excluded_map[segment_index] = ExclusionReason.USER_SELECTED
            logger.info(
                LogModule.TRANS,
                f"[EXCLUDE_SEGMENT] Segment {segment_index} marked as excluded with reason=user_selected "
                f"(no specific reason detected) and updated segments_metadata"
            )
    
    # Update segments_metadata using ExclusionManager
    ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
    logger.info(LogModule.TRANS, f"[EXCLUDE_SEGMENT] Successfully excluded segment {segment_index} for task {task_id} (updated segments_metadata.excluded_segments)")
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
        logger.warning(LogModule.TRANS, f"No translation segments found for task {task_id}")
        return None
    
    segments = segments_data.get("segments", [])
    
    # Find segment by segment_index
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
    
    current_reason_value = segment.get("exclusion_reason")
    
    # Update segments_metadata.excluded_segments (single source of truth)
    current_excluded_map = ExclusionManager.get_excluded_segments(task_state)
    
    if current_reason_value:
        try:
            reason = ExclusionReason(current_reason_value)
            # Content-based exclusions cannot be unexcluded unless they were
            # user-selected or FORMULA (formula detection can be inaccurate)
            if (ExclusionReason.is_content_based(reason)
                    and reason != ExclusionReason.USER_SELECTED
                    and reason != ExclusionReason.FORMULA):
                logger.warning(
                    LogModule.TRANS,
                    f"Cannot unexclude segment {segment_index}: "
                    f"content-based exclusion ({reason.value}) cannot be removed"
                )
                return None
        except ValueError:
            pass
    
    # Clear exclusion flag
    segment["is_excluded"] = False
    segment["excluded_at"] = None
    segment["exclusion_reason"] = None
    segment["exclusion_metadata"] = None
    
    # Remove from current_excluded_map
    original_reason = None
    if segment_index in current_excluded_map:
        original_reason = current_excluded_map[segment_index]
        del current_excluded_map[segment_index]
        ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
    
    # Record that user explicitly chose to unexclude this segment
    segments_metadata = task_state.get("segments_metadata", {})
    if original_reason:
        user_unexcluded = segments_metadata.get("user_unexcluded_segments", [])
        if segment_index not in user_unexcluded:
            user_unexcluded.append(segment_index)
            segments_metadata["user_unexcluded_segments"] = user_unexcluded
            logger.info(
                LogModule.EXCLUSION,
                f"[UNEXCLUDE] Task {task_id}: Recorded segment {segment_index} as user-unexcluded "
                f"(original reason: {original_reason.value}) to prevent re-detection"
            )
    
    # Re-detect exclusion reason after unexclude
    # Only re-exclude if the detected reason is content-based
    source_text = segment.get("source_text", "")
    is_image = segment.get("is_image", False)
    block_type = segment.get("block_type")
    
    target_lang = None
    payload = task_state.get("payload")
    if payload and isinstance(payload, dict):
        target_lang = payload.get("to_lang") or payload.get("target_lang")

    is_table = (block_type == TABLE_BODY or block_type == TABLE)
    if not is_table:
        from utils.translation_segments import _is_table_segment
        is_table = _is_table_segment(source_text)
    
    detected_result = detect_exclusion_reason(
        text=source_text,
        block_type=block_type,
        target_lang=target_lang,
        is_image=is_image,
        is_table=is_table
    )
    
    if detected_result:
        detected_reason, detected_metadata = detected_result
        # Only re-exclude if the detected reason is content-based
        # Exception: FORMULA can be unexcluded by user (detection can be inaccurate)
        if (ExclusionReason.is_content_based(detected_reason)
                and detected_reason != ExclusionReason.FORMULA):
            segment["is_excluded"] = True
            segment["exclusion_reason"] = detected_reason.value
            segment["exclusion_metadata"] = detected_metadata
            segment["excluded_at"] = time.time()
            
            current_excluded_map[segment_index] = detected_reason
            ExclusionManager.update_excluded_segments(task_state, current_excluded_map)
            
            logger.info(
                LogModule.TRANS,
                f"Segment {segment_index} re-excluded after unexclude: "
                f"detected reason={detected_reason.value} (content-based)"
            )
    
    return segment
