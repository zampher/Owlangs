# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
API routes for translation segments management.
"""

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import copy

from backend.app.services.task import task_manager
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()


def _ts_module():
    """
    Lazy loader for utils.translation_segments module.

    IMPORTANT:
    - Importing translation_segments at route-import time can participate in
      complex circular import chains when worker processes start up and
      FastAPI routes are imported inside background executors.
    - By importing the module only inside request handlers, we guarantee that
      all modules (including routes and services) have finished initialization
      before we touch utils.translation_segments.
    """
    from utils import translation_segments  # type: ignore

    return translation_segments


def _enrich_translation_segments_with_detected_reasons(
    task_id: str,
    response_data: Dict[str, Any],
) -> None:
    """
    Enrich translation segments with detected exclusion reasons for Translate phase filters.

    This mirrors the behavior of StatusService.get_source_preview, but applies to the
    /translation-segments API so that the Translate page can:
    - Show Exclusion Filters for NOT-excluded categories (e.g. language_match, table, structural)
    - Build statistics based on detected types instead of only excluded state.

    IMPORTANT:
    - This function does NOT change exclusion decisions (is_excluded or exclusion_reason).
      Exclusion remains decided during Extract phase and by user actions.
    - It only adds:
        - detected_exclusion_reason
        - exclusion_metadata (when available, e.g. language_match target_lang / detected_lang)
      to each segment dictionary, based on segments_metadata.detected_exclusion_reasons.
    """
    try:
        if not isinstance(response_data, dict):
            return

        segments_list = response_data.get("segments")
        if not isinstance(segments_list, list) or not segments_list:
            return

        task_state = task_manager.get_task(task_id) or {}
        segments_metadata = task_state.get("segments_metadata", {})
        detected_exclusion_reasons = segments_metadata.get("detected_exclusion_reasons", {})

        if not isinstance(detected_exclusion_reasons, dict) or not detected_exclusion_reasons:
            # Nothing to enrich
            return

        enriched_count = 0
        reason_counts: Dict[str, int] = {}

        for seg in segments_list:
            if not isinstance(seg, dict):
                continue

            seg_idx = seg.get("segment_index")
            if not isinstance(seg_idx, int):
                continue

            detected_info = detected_exclusion_reasons.get(str(seg_idx))
            if not detected_info:
                continue

            # Support both dict and string formats from detected_exclusion_reasons
            detected_reason: str
            detected_metadata: Dict[str, Any] = {}

            if isinstance(detected_info, dict):
                detected_reason = str(detected_info.get("reason", "") or "")
                meta = detected_info.get("metadata")
                if isinstance(meta, dict):
                    detected_metadata = meta
            else:
                detected_reason = str(detected_info)

            if not detected_reason:
                continue

            # Attach detected_exclusion_reason without overriding exclusion_reason
            seg["detected_exclusion_reason"] = detected_reason

            # Merge exclusion_metadata when available (for language_match, etc.)
            if detected_metadata:
                existing_meta = seg.get("exclusion_metadata")
                if isinstance(existing_meta, dict):
                    merged_meta = {**existing_meta, **detected_metadata}
                else:
                    merged_meta = detected_metadata
                seg["exclusion_metadata"] = merged_meta

            enriched_count += 1
            reason_counts[detected_reason] = reason_counts.get(detected_reason, 0) + 1

        if enriched_count > 0:
            # Log a concise summary to help debug Translate phase filters
            reason_summary = ", ".join(
                f"{count} {reason}" for reason, count in sorted(reason_counts.items())
            )
            logger.info(
                LogModule.ROUTE,
                f"[TRANSLATION-SEGMENTS-API] Task {task_id}: Enriched "
                f"{enriched_count} segments with detected_exclusion_reason "
                f"({reason_summary}) for Translate phase filters",
            )

            # Also expose detected exclusion reason counts in the response metadata so that
            # the Translate phase can align its Segment Type Filters with Extract.
            # NOTE: This is based on Extract phase detection results and is independent
            # of whether segments are currently excluded on the Translate page.
            if isinstance(response_data.get("metadata"), dict):
                response_data["metadata"]["detected_exclusion_reason_counts"] = reason_counts
            else:
                response_data["metadata"] = {
                    "detected_exclusion_reason_counts": reason_counts
                }
    except Exception as e:
        # Do not break API if enrichment fails; just log for debugging.
        logger.warning(
            LogModule.ROUTE,
            f"[TRANSLATION-SEGMENTS-API] Failed to enrich segments with detected_exclusion_reasons "
            f"for task {task_id}: {e}",
        )


@router.get(
    "/translation-segments/{task_id}",
    summary="Get translation segments",
    description="Get structured translation segments (source/target pairs) for a task.",
    responses={
        200: {
            "description": "Successfully retrieved translation segments.",
            "content": {
                "application/json": {
                    "example": {
                        "segments": [
                            {
                                "segment_id": "task123_segment_0",
                                "segment_index": 0,
                                "source_text": "Original text...",
                                "target_text": "Translated text...",
                                "status": "translated",
                                "reviewed": False,
                                "modified": False
                            }
                        ],
                        "metadata": {
                            "original_format": "pdf",
                            "workflow_type": "markdown_based",
                            "total_segments": 10
                        }
                    }
                }
            }
        },
        404: {"description": "Task ID not found or no segments available."}
    }
)
async def get_translation_segments_api(task_id: str):
    """Get translation segments for a task."""
    logger.debug(LogModule.ROUTE, f"[TRANSLATION-SEGMENTS-API] Get segments request: task_id={task_id}")
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[TRANSLATION-SEGMENTS-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    
    segments_data = _ts_module().get_translation_segments(task_id)
    if segments_data is None:
        logger.info(
            LogModule.ROUTE,
            f"[TRANSLATION-SEGMENTS-API] No translation segments available for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404, 
            detail=f"No translation segments available for task '{task_id}'. "
                  "This may be an older task or a format conversion task without translation."
        )

    # Create a defensive copy before mutating
    response_data = copy.deepcopy(segments_data)
    
    # CRITICAL: Handle backward compatibility - segments_data might be a list (old format) or dict (new format)
    # If it's a list, convert to dict format for consistency
    if isinstance(response_data, list):
        response_data = {
            "segments": response_data,
            "metadata": {}
        }

    # CRITICAL: Filter out segments with None segment_index to prevent frontend TypeError
    # Frontend expects segment_index to be int, not None
    if isinstance(response_data, dict) and "segments" in response_data:
        segments_list = response_data.get("segments", [])
        if segments_list:
            # Filter out segments with None segment_index
            valid_segments = []
            invalid_count = 0
            for seg in segments_list:
                if isinstance(seg, dict):
                    segment_index = seg.get("segment_index")
                    # Only include segments with valid (non-None) segment_index
                    if segment_index is not None:
                        valid_segments.append(seg)
                    else:
                        invalid_count += 1
                        logger.warning(
                            LogModule.ROUTE,
                            f"[TRANSLATION-SEGMENTS-API] Task {task_id}: Filtered out segment with None segment_index. "
                            f"Segment keys: {list(seg.keys())}"
                        )
                else:
                    # Include non-dict segments (backward compatibility)
                    valid_segments.append(seg)
            
            if invalid_count > 0:
                logger.warning(
                    LogModule.ROUTE,
                    f"[TRANSLATION-SEGMENTS-API] Task {task_id}: Filtered out {invalid_count} segments with None segment_index. "
                    f"Valid segments: {len(valid_segments)}"
                )
            
            response_data["segments"] = valid_segments
            # Update metadata total_segments if present
            if "metadata" in response_data and isinstance(response_data["metadata"], dict):
                response_data["metadata"]["total_segments"] = len(valid_segments)

    # Enrich segments with detected exclusion reasons so Translate phase filters
    # can display categories like language_match even when segments are not excluded.
    _enrich_translation_segments_with_detected_reasons(task_id, response_data)

    # Include image data map if available so frontend can render placeholders as images
    # Prefer translation-specific image map (placeholder IDs generated during translation)
    task_state = task_manager.get_task(task_id) or {}
    image_data_map_raw = (
        task_state.get("translation_image_data_map")
        or task_state.get("image_data_map")
    )
    if image_data_map_raw:
        # Convert image_data_map format to frontend expected format
        # Backend format: {image_path: {"data": data_uri, "mime": mime_type, "size": size}}
        # Frontend format: {placeholder_id: {"data": data_uri, "alt": alt_text}}
        # For MOBI/EPUB, placeholder_id = image_path, so we can use image_path as key
        image_data_map = {}
        import os
        for image_path, image_info in image_data_map_raw.items():
            if isinstance(image_info, dict):
                # Use image_path as placeholder_id (matches placeholder format in segments)
                placeholder_id = image_path
                alt_text = os.path.basename(image_path) or image_path
                image_data_map[placeholder_id] = {
                    "data": image_info.get("data", ""),
                    "alt": alt_text,
                }
        if image_data_map:
            response_data["image_data_map"] = image_data_map

    return JSONResponse(content=response_data)


@router.post(
    "/translation-segments/{task_id}/{segment_index}/update",
    summary="Update a translation segment",
    description="Update a translation segment (for review/correction).",
    responses={
        200: {
            "description": "Successfully updated segment.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "segment": {
                            "segment_id": "task123_segment_0",
                            "target_text": "Updated translation...",
                            "modified": True
                        }
                    }
                }
            }
        },
        404: {"description": "Task ID or segment not found."}
    }
)
async def update_segment_api(
    task_id: str,
    segment_index: int,
    body: dict = Body(...)
):
    """Update a translation segment."""
    logger.info(
        LogModule.ROUTE,
        f"[UPDATE-SEGMENT-API] Update segment request: task_id={task_id}, segment_index={segment_index}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[UPDATE-SEGMENT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    # Extract fields from JSON body safely
    target_text = body.get("target_text")
    reviewed = body.get("reviewed")
    review_notes = body.get("review_notes")
    modified_by = body.get("modified_by")

    segment = _ts_module().update_translation_segment(
        task_id=task_id,
        segment_index=segment_index,
        target_text=target_text,
        reviewed=reviewed,
        review_notes=review_notes,
        modified_by=modified_by,
    )

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[UPDATE-SEGMENT-API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    logger.info(
        LogModule.ROUTE,
        f"[UPDATE-SEGMENT-API] Successfully updated segment {segment_index} for task {task_id}"
    )
    return JSONResponse(content={
        "success": True,
        "segment": segment
    })


@router.post(
    "/translation-segments/{task_id}/{segment_index}/exclude",
    summary="Exclude a segment from translation",
    description="Mark a translation segment as excluded. Excluded segments will revert to the original text and be skipped in subsequent translations.",
    responses={
        200: {"description": "Segment excluded successfully."},
        404: {"description": "Task ID or segment not found."},
    }
)
async def exclude_segment_api(
    task_id: str,
    segment_index: int,
):
    """Exclude a translation segment."""
    logger.info(
        LogModule.ROUTE,
        f"[EXCLUDE_API] Received exclude request for task {task_id}, segment {segment_index}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(
            LogModule.ROUTE,
            f"[EXCLUDE_API] Task ID '{task_id}' not found"
        )
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    logger.info(
        LogModule.ROUTE,
        f"[EXCLUDE_API] Calling exclude_translation_segment for task {task_id}, segment {segment_index}"
    )
    segment = _ts_module().exclude_translation_segment(
        task_id=task_id,
        segment_index=segment_index,
    )

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[EXCLUDE_API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    logger.info(
        LogModule.ROUTE,
        f"[EXCLUDE_API] Successfully excluded segment {segment_index} for task {task_id}"
    )
    return JSONResponse(content={
        "success": True,
        "segment": segment
    })


@router.post(
    "/translation-segments/{task_id}/{segment_index}/unexclude",
    summary="Remove exclusion from a segment",
    description="Remove the exclusion flag so a segment can be translated again.",
    responses={
        200: {"description": "Segment un-excluded successfully."},
        404: {"description": "Task ID or segment not found."},
    }
)
async def unexclude_segment_api(
    task_id: str,
    segment_index: int,
):
    """Remove exclusion from a translation segment."""
    logger.info(
        LogModule.ROUTE,
        f"[UNEXCLUDE-API] Unexclude segment request: task_id={task_id}, segment_index={segment_index}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[UNEXCLUDE-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    segment = _ts_module().unexclude_translation_segment(
        task_id=task_id,
        segment_index=segment_index,
    )

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[UNEXCLUDE-API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    logger.info(
        LogModule.ROUTE,
        f"[UNEXCLUDE-API] Successfully unexcluded segment {segment_index} for task {task_id}"
    )
    return JSONResponse(content={
        "success": True,
        "segment": segment
    })


@router.post(
    "/translation-segments/{task_id}/exclude-all",
    summary="Exclude all segments",
    description="Mark all segments as excluded. Segments not already excluded are marked with user (manual) exclusion.",
    responses={
        200: {"description": "All segments excluded."},
        404: {"description": "Task not found."},
    }
)
async def exclude_all_segments_api(task_id: str):
    """Exclude all segments for the task (user exclusion for any not already excluded)."""
    if task_manager.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    result = _ts_module().exclude_all_segments(task_id)
    return JSONResponse(content=result)


@router.post(
    "/translation-segments/{task_id}/cancel-user-exclusion",
    summary="Cancel user exclusions only",
    description="Remove only manual/user exclusions. Other exclusion types (identifier, language_match, etc.) are unchanged.",
    responses={
        200: {"description": "User exclusions cancelled."},
        404: {"description": "Task not found."},
    }
)
async def cancel_user_exclusion_api(task_id: str):
    """Cancel only user/manual exclusions for the task."""
    if task_manager.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    result = _ts_module().cancel_user_exclusion(task_id)
    return JSONResponse(content=result)


@router.post(
    "/translation-segments/{task_id}/clear-all-exclusions-except-image",
    summary="Clear all exclusions except image segments",
    description="Remove exclusions from all segments except image segments. Only image segments remain excluded.",
    responses={
        200: {"description": "Non-image exclusions cleared."},
        404: {"description": "Task not found."},
    }
)
async def clear_all_exclusions_except_image_api(task_id: str):
    """Clear all exclusions except image segments for the task."""
    if task_manager.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    result = _ts_module().clear_all_exclusions_except_image(task_id)
    return JSONResponse(content=result)


@router.post(
    "/translation-segments/{task_id}/{segment_index}/exclusion_reason",
    summary="Update exclusion reason for a segment",
    description="Update or remove exclusion reason for a translation segment.",
    responses={
        200: {"description": "Exclusion reason updated successfully."},
        404: {"description": "Task ID or segment not found."},
        400: {"description": "Invalid exclusion reason."},
    }
)
async def update_exclusion_reason_api(
    task_id: str,
    segment_index: int,
    body: dict = Body(...),
):
    """Update exclusion reason for a segment."""
    if task_manager.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    # Extract new_reason from JSON body (can be None/null to remove exclusion)
    new_reason = body.get("new_reason")
    # Convert empty string to None for consistency
    if new_reason == "":
        new_reason = None
    
    # Log the request for debugging
    logger.debug(
        LogModule.ROUTE,
        f"[UPDATE_EXCLUSION_REASON_API] Received request: task_id={task_id}, "
        f"segment_index={segment_index}, new_reason={new_reason}, body={body}"
    )

    # CRITICAL: Validate exclusion reason BEFORE calling update_exclusion_reason
    # This ensures we return 400 (Bad Request) for invalid reasons, not 404 (Not Found)
    if new_reason is not None:
        try:
            from exclusion.core import ExclusionReason
            # Validate the reason - this will raise ValueError if invalid
            ExclusionReason(new_reason)
        except ValueError as e:
            valid_reasons = [r.value for r in ExclusionReason]
            error_msg = (
                f"Invalid exclusion reason: {new_reason}. "
                f"Valid reasons are: {', '.join(valid_reasons)}"
            )
            logger.warning(
                LogModule.ROUTE,
                f"[UPDATE_EXCLUSION_REASON_API] {error_msg} for task {task_id}, segment {segment_index}"
            )
            raise HTTPException(status_code=400, detail=error_msg)

    try:
        segment = _ts_module().update_exclusion_reason(
            task_id=task_id,
            segment_index=segment_index,
            new_reason=new_reason,
        )

        if segment is None:
            logger.warning(
                LogModule.ROUTE,
                f"[UPDATE_EXCLUSION_REASON_API] Segment {segment_index} not found for task {task_id}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Segment index {segment_index} not found for task '{task_id}'."
            )

        logger.info(
            LogModule.ROUTE,
            f"[UPDATE_EXCLUSION_REASON_API] Successfully updated exclusion reason for "
            f"task {task_id}, segment {segment_index}, new_reason={new_reason}"
        )
        return JSONResponse(content={
            "success": True,
            "segment": segment
        })
    except HTTPException:
        # Re-raise HTTP exceptions (400, 404, etc.)
        raise
    except Exception as e:
        # Catch any other unexpected errors and return 500
        logger.error(
            LogModule.ROUTE,
            f"[UPDATE_EXCLUSION_REASON_API] Unexpected error updating exclusion reason "
            f"for task {task_id}, segment {segment_index}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while updating exclusion reason: {str(e)}"
        )


@router.post(
    "/translation-segments/{task_id}/{segment_index}/retranslate",
    summary="Retranslate a segment",
    description="Retranslate a single translation segment using a different AI platform (optional).",
    responses={
        200: {
            "description": "Successfully retranslated segment.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "segment": {
                            "segment_id": "task123_segment_0",
                            "target_text": "Retranslated text...",
                            "platform_used": "doubao"
                        }
                    }
                }
            }
        },
        404: {"description": "Task ID or segment not found."},
        500: {"description": "Failed to retranslate segment."}
    }
)
async def retranslate_segment_api(
    task_id: str,
    segment_index: int,
    body: dict = Body(...)
):
    """Retranslate a single segment."""
    platform_key = body.get("platform_key")
    to_lang = body.get("to_lang")
    user_prompt = body.get("user_prompt") or body.get("custom_prompt")  # User prompt for retry (e.g. "请帮我翻译人名")
    
    logger.info(
        LogModule.ROUTE,
        f"[RETRANSLATE-SEGMENT-API] Retranslate segment request: task_id={task_id}, "
        f"segment_index={segment_index}, platform_key={platform_key}, to_lang={to_lang}, has_user_prompt={bool(user_prompt)}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[RETRANSLATE-SEGMENT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    try:
        segment = await _ts_module().retranslate_segment(
            task_id=task_id,
            segment_index=segment_index,
            platform_key=platform_key,
            to_lang=to_lang,
            user_prompt=user_prompt,
        )

        if segment is None:
            logger.warning(
                LogModule.ROUTE,
                f"[RETRANSLATE-SEGMENT-API] Segment index {segment_index} not found for task '{task_id}'"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Segment index {segment_index} not found for task '{task_id}'."
            )

        # Check if retranslation actually succeeded by examining segment status
        is_failed = segment.get("is_failed", False)
        success = not is_failed

        if success:
            logger.info(
                LogModule.ROUTE,
                f"[RETRANSLATE-SEGMENT-API] Successfully retranslated segment {segment_index} for task {task_id}"
            )
        else:
            logger.warning(
                LogModule.ROUTE,
                f"[RETRANSLATE-SEGMENT-API] Retranslation failed for segment {segment_index} in task {task_id}: "
                f"{segment.get('failure_reason', 'Unknown error')}"
            )

        return JSONResponse(content={
            "success": success,
            "segment": segment,
            "error": segment.get("failure_reason") if is_failed else None,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[RETRANSLATE-SEGMENT-API] Unexpected error retranslating segment {segment_index} "
            f"for task {task_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retranslate segment: {str(e)}"
        )


@router.post(
    "/translation-segments/{task_id}/batch-retranslate",
    summary="Batch retranslate multiple segments",
    description="Retranslate multiple segments together to enable chunk merging and reduce API calls.",
    responses={
        200: {
            "description": "Successfully retranslated segments.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "segments": {
                            "0": {"segment_index": 0, "target_text": "...", "is_failed": False},
                            "1": {"segment_index": 1, "target_text": "...", "is_failed": False},
                        },
                        "errors": {}
                    }
                }
            }
        },
        404: {"description": "Task not found."},
        500: {"description": "Failed to retranslate segments."}
    }
)
async def batch_retranslate_segments_api(
    task_id: str,
    body: dict = Body(...)
):
    """Batch retranslate multiple segments together."""
    segment_indices = body.get("segment_indices", [])
    platform_key = body.get("platform_key")
    to_lang = body.get("to_lang")
    user_prompt = body.get("user_prompt") or body.get("custom_prompt")  # User prompt for retry
    
    logger.info(
        LogModule.ROUTE,
        f"[BATCH-RETRANSLATE-API] Batch retranslate request: task_id={task_id}, "
        f"segment_count={len(segment_indices) if isinstance(segment_indices, list) else 0}, "
        f"platform_key={platform_key}, to_lang={to_lang}, has_user_prompt={bool(user_prompt)}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[BATCH-RETRANSLATE-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    if not segment_indices or not isinstance(segment_indices, list):
        logger.warning(
            LogModule.ROUTE,
            f"[BATCH-RETRANSLATE-API] Invalid segment_indices: {segment_indices}"
        )
        raise HTTPException(
            status_code=400,
            detail="segment_indices must be a non-empty list of segment indices."
        )

    try:
        result_map = await _ts_module().retranslate_segments_batch(
            task_id=task_id,
            segment_indices=segment_indices,
            platform_key=platform_key,
            user_prompt=user_prompt,
            to_lang_from_frontend=to_lang,
        )

        if not result_map:
            logger.warning(
                LogModule.ROUTE,
                f"[BATCH-RETRANSLATE-API] No valid segments found for retranslation in task '{task_id}'"
            )
            raise HTTPException(
                status_code=404,
                detail=f"No valid segments found for retranslation in task '{task_id}'."
            )

        # Separate successful and failed segments
        segments = {}
        errors = {}
        
        for seg_idx, segment in result_map.items():
            if segment:
                is_failed = segment.get("is_failed", False)
                if is_failed:
                    errors[str(seg_idx)] = segment.get("failure_reason", "Translation failed")
                segments[str(seg_idx)] = segment

        success = len(errors) == 0
        
        if success:
            logger.info(
                LogModule.ROUTE,
                f"[BATCH-RETRANSLATE-API] Successfully retranslated {len(segments)} segments for task {task_id}"
            )
        else:
            logger.warning(
                LogModule.ROUTE,
                f"[BATCH-RETRANSLATE-API] Batch retranslation completed with {len(errors)} errors "
                f"out of {len(segments)} segments for task {task_id}"
            )

        return JSONResponse(content={
            "success": success,
            "segments": segments,
            "errors": errors,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[BATCH-RETRANSLATE-API] Unexpected error batch retranslating segments "
            f"for task {task_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to batch retranslate segments: {str(e)}"
        )


@router.post(
    "/translation-segments/{task_id}/{segment_index}/mark-retry",
    summary="Mark segment for retry",
    description="Mark a translation segment as needing retry (manual flag).",
    responses={
        200: {
            "description": "Successfully marked segment for retry.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "segment": {
                            "segment_id": "task123_segment_0",
                            "needs_retry": True
                        }
                    }
                }
            }
        },
        404: {"description": "Task ID or segment not found."}
    }
)
async def mark_segment_retry_api(
    task_id: str,
    segment_index: int,
):
    """Mark a segment for retry."""
    logger.info(
        LogModule.ROUTE,
        f"[MARK-RETRY-API] Mark segment for retry request: task_id={task_id}, segment_index={segment_index}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[MARK-RETRY-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    segment = _ts_module().mark_segment_for_retry(
        task_id=task_id,
        segment_index=segment_index,
    )

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[MARK-RETRY-API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    logger.info(
        LogModule.ROUTE,
        f"[MARK-RETRY-API] Successfully marked segment {segment_index} for retry in task {task_id}"
    )
    return JSONResponse(content={
        "success": True,
        "segment": segment
    })


@router.post(
    "/translation-segments/{task_id}/{segment_index}/clear",
    summary="Clear a segment translation",
    description="Clear a translation segment's target text (set to empty string). Useful when AI merges adjacent segments during translation.",
    responses={
        200: {"description": "Segment cleared successfully."},
        404: {"description": "Task ID or segment not found."},
    }
)
async def clear_segment_api(
    task_id: str,
    segment_index: int,
):
    """Clear a translation segment's target text."""
    logger.info(
        LogModule.ROUTE,
        f"[CLEAR-SEGMENT-API] Clear segment request: task_id={task_id}, segment_index={segment_index}"
    )
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[CLEAR-SEGMENT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    segment = _ts_module().clear_translation_segment(
        task_id=task_id,
        segment_index=segment_index,
    )

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[CLEAR-SEGMENT-API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    logger.info(
        LogModule.ROUTE,
        f"[CLEAR-SEGMENT-API] Successfully cleared segment {segment_index} for task {task_id}"
    )
    return JSONResponse(content={
        "success": True,
        "segment": segment
    })

