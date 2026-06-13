# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
API routes for translation segments management.
"""

from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import copy
import time

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

            # If user manually retried and successfully translated this segment, don't overlay old reason
            is_user_translated = seg.get("status") == "translated" and seg.get("modified") is True
            if is_user_translated:
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
async def get_translation_segments_api(
    task_id: str,
    offset: int = Query(0, ge=0, description="Offset for pagination (0-based)"),
    limit: int = Query(0, ge=0, description="Max segments to return (0 = no limit)"),
):
    """Get translation segments for a task. Supports optional pagination for large documents."""
    logger.debug(
        LogModule.ROUTE,
        f"[TRANSLATION-SEGMENTS-API] Get segments request: task_id={task_id}, offset={offset}, limit={limit}"
    )
    
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.ROUTE, f"[TRANSLATION-SEGMENTS-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    segments_data = _ts_module().get_translation_segments(task_id)
    if segments_data is None:
        # Distinguish "still processing" (segments not ready yet) from
        # "terminal with no segments" (e.g. format-conversion-only task).
        task_status = (task_state.get("status") or "").lower()
        terminal = task_status in ("completed", "failed", "cancelled")

        if terminal:
            logger.debug(
                LogModule.ROUTE,
                f"[TRANSLATION-SEGMENTS-API] Task '{task_id}' terminal ({task_status}) with no segments"
            )
            raise HTTPException(
                status_code=404,
                detail=f"No translation segments available for task '{task_id}'. "
                       "This may be an older task or a format conversion task without translation."
            )
        else:
            logger.debug(
                LogModule.ROUTE,
                f"[TRANSLATION-SEGMENTS-API] Task '{task_id}' processing ({task_status}), segments not ready yet"
            )
            raise HTTPException(
                status_code=202,
                detail=f"Translation segments not ready yet. Task status: {task_status}"
            )

    # Build response data with shallow copy instead of deep copy for performance.
    # Deep copying 10k+ segments on every poll is extremely expensive.
    if isinstance(segments_data, dict):
        # Shallow copy: copy the container dict and segment list, but share inner dicts
        # We will clone individual segment dicts only when we need to mutate them.
        response_data = {
            "segments": list(segments_data.get("segments", [])),
            "metadata": dict(segments_data.get("metadata", {})),
        }
    elif isinstance(segments_data, list):
        response_data = {
            "segments": list(segments_data),
            "metadata": {}
        }
    else:
        # Fallback for unexpected types
        response_data = copy.deepcopy(segments_data)

    # CRITICAL: Filter out segments with None segment_index to prevent frontend TypeError
    if isinstance(response_data, dict) and "segments" in response_data:
        segments_list = response_data.get("segments", [])
        if segments_list:
            valid_segments = []
            invalid_count = 0
            for seg in segments_list:
                if isinstance(seg, dict):
                    segment_index = seg.get("segment_index")
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
                    valid_segments.append(seg)
            
            if invalid_count > 0:
                logger.warning(
                    LogModule.ROUTE,
                    f"[TRANSLATION-SEGMENTS-API] Task {task_id}: Filtered out {invalid_count} segments with None segment_index. "
                    f"Valid segments: {len(valid_segments)}"
                )
            
            total_valid = len(valid_segments)
            response_data["segments"] = valid_segments
            if "metadata" in response_data and isinstance(response_data["metadata"], dict):
                response_data["metadata"]["total_segments"] = total_valid
            
            # Apply pagination after filtering
            if limit > 0:
                paginated = valid_segments[offset:offset + limit]
                response_data["segments"] = paginated
                if "metadata" in response_data and isinstance(response_data["metadata"], dict):
                    response_data["metadata"]["offset"] = offset
                    response_data["metadata"]["limit"] = limit
                    response_data["metadata"]["returned_segments"] = len(paginated)
                    response_data["metadata"]["total_segments"] = total_valid

    # Enrich segments with detected exclusion reasons so Translate phase filters
    # can display categories like language_match even when segments are not excluded.
    _enrich_translation_segments_with_detected_reasons(task_id, response_data)

    # Attach has_latex flag to each segment so frontend can decide whether to show
    # the "Test PDF Compatibility" button (only useful for segments with LaTeX).
    from utils.latex_repair_payload import has_latex_content
    segments_list = response_data.get("segments", []) if isinstance(response_data, dict) else []
    for seg in segments_list:
        if isinstance(seg, dict):
            text = seg.get("modified_text") or seg.get("target_text") or seg.get("source_text") or ""
            seg["has_latex"] = has_latex_content(text)

    # Enrich PDF layout segments with computed/user font size metadata.
    layout_doc = task_state.get("layout_document")
    if layout_doc is not None and segments_list:
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            enrich_segments_font_fields,
        )
        text_field = "modified_text"
        if not any(
            isinstance(s, dict) and s.get("modified_text")
            for s in segments_list
        ):
            text_field = "target_text"
        enrich_segments_font_fields(layout_doc, segments_list, text_field=text_field)

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
    font_size_pt = body.get("font_size_pt")
    font_size_reset = bool(body.get("font_size_reset", False))
    font_weight = body.get("font_weight")
    font_style = body.get("font_style")
    font_weight_reset = bool(body.get("font_weight_reset", False))
    font_style_reset = bool(body.get("font_style_reset", False))
    leading_em = body.get("leading_em")
    leading_em_reset = bool(body.get("leading_em_reset", False))
    pdf_font_reset = bool(body.get("pdf_font_reset", False))

    segment = _ts_module().update_translation_segment(
        task_id=task_id,
        segment_index=segment_index,
        target_text=target_text,
        reviewed=reviewed,
        review_notes=review_notes,
        modified_by=modified_by,
        font_size_pt=font_size_pt,
        font_size_reset=font_size_reset,
        font_weight=font_weight,
        font_style=font_style,
        font_weight_reset=font_weight_reset,
        font_style_reset=font_style_reset,
        leading_em=leading_em,
        leading_em_reset=leading_em_reset,
        pdf_font_reset=pdf_font_reset,
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
    "/translation-segments/{task_id}/exclude-batch",
    summary="Exclude multiple segments from translation",
    description=(
        "Mark multiple translation segments as excluded in a single request. "
        "Excluded segments revert to the original text and are skipped in subsequent translations."
    ),
    responses={
        200: {"description": "Batch exclude completed (check failed_indices for partial failures)."},
        404: {"description": "Task ID not found."},
    },
)
async def exclude_segments_batch_api(
    task_id: str,
    body: dict = Body(...),
):
    """Exclude multiple translation segments in one request."""
    segment_indices_raw = body.get("segment_indices")
    if not isinstance(segment_indices_raw, list):
        raise HTTPException(
            status_code=400,
            detail="Request body must include 'segment_indices' as a list of integers.",
        )
    try:
        segment_indices = [int(idx) for idx in segment_indices_raw]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Each entry in 'segment_indices' must be an integer.",
        ) from exc

    logger.info(
        LogModule.ROUTE,
        f"[EXCLUDE_BATCH_API] Received exclude-batch for task {task_id}, "
        f"count={len(segment_indices)}",
    )

    if task_manager.get_task(task_id) is None:
        logger.warning(
            LogModule.ROUTE,
            f"[EXCLUDE_BATCH_API] Task ID '{task_id}' not found",
        )
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    result = _ts_module().exclude_translation_segments_batch(
        task_id=task_id,
        segment_indices=segment_indices,
    )
    return JSONResponse(content=result)


@router.post(
    "/translation-segments/{task_id}/unexclude-batch",
    summary="Remove exclusion from multiple segments",
    description="Remove the exclusion flag from multiple segments in a single request.",
    responses={
        200: {"description": "Batch unexclude completed (check failed_indices for partial failures)."},
        404: {"description": "Task ID not found."},
    },
)
async def unexclude_segments_batch_api(
    task_id: str,
    body: dict = Body(...),
):
    """Remove exclusion from multiple translation segments in one request."""
    segment_indices_raw = body.get("segment_indices")
    if not isinstance(segment_indices_raw, list):
        raise HTTPException(
            status_code=400,
            detail="Request body must include 'segment_indices' as a list of integers.",
        )
    try:
        segment_indices = [int(idx) for idx in segment_indices_raw]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Each entry in 'segment_indices' must be an integer.",
        ) from exc

    logger.info(
        LogModule.ROUTE,
        f"[UNEXCLUDE_BATCH_API] Received unexclude-batch for task {task_id}, "
        f"count={len(segment_indices)}",
    )

    if task_manager.get_task(task_id) is None:
        logger.warning(
            LogModule.ROUTE,
            f"[UNEXCLUDE_BATCH_API] Task ID '{task_id}' not found",
        )
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    result = _ts_module().unexclude_translation_segments_batch(
        task_id=task_id,
        segment_indices=segment_indices,
    )
    return JSONResponse(content=result)


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
    "/translation-segments/{task_id}/cancel-batch-retry",
    summary="Cancel ongoing batch retry operation",
    description="Cancel the currently running batch retry operation for the task.",
    responses={
        200: {"description": "Cancel signal sent successfully."},
        404: {"description": "Task not found."},
    }
)
async def cancel_batch_retry_api(task_id: str):
    """Cancel the ongoing batch retry operation."""
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.ROUTE, f"[CANCEL-BATCH-RETRY-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    
    # Set cancel flag in task state
    task_state["cancel_batch_retry"] = True
    logger.info(LogModule.ROUTE, f"[CANCEL-BATCH-RETRY-API] Cancel signal set for task {task_id}")
    
    return JSONResponse(content={
        "success": True,
        "message": "Batch retry cancel signal sent",
        "task_id": task_id,
    })


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


@router.post(
    "/translation-segments/{task_id}/{segment_index}/test-pdf-compat",
    summary="Test PDF compatibility for a single segment",
    description="Run Pandoc + XeLaTeX on a single segment's target_text to detect LaTeX errors before full export. "
                "Segments without LaTeX content are skipped (assumed OK).",
    responses={
        200: {
            "description": "PDF compatibility check result.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "passed": True,
                        "has_latex": True,
                        "pandoc_available": True,
                        "message": "PDF compatibility check passed.",
                        "issues": [],
                        "stderr": None,
                    }
                }
            }
        },
        404: {"description": "Task ID or segment not found."},
    }
)
async def test_segment_pdf_compat_api(
    task_id: str,
    segment_index: int,
):
    """Test a single segment's PDF compatibility using Pandoc + XeLaTeX dry-run."""
    logger.info(
        LogModule.ROUTE,
        f"[TEST-PDF-COMPAT-API] Request: task_id={task_id}, segment_index={segment_index}"
    )

    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[TEST-PDF-COMPAT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    # Retrieve the segment
    segments_data = _ts_module().get_translation_segments(task_id)
    if segments_data is None:
        raise HTTPException(status_code=404, detail="No translation segments available.")

    if isinstance(segments_data, list):
        segments_list = segments_data
    else:
        segments_list = segments_data.get("segments", []) or []

    segment = None
    for seg in segments_list:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break

    if segment is None:
        logger.warning(
            LogModule.ROUTE,
            f"[TEST-PDF-COMPAT-API] Segment index {segment_index} not found for task '{task_id}'"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    # Use modified_text if available, else target_text
    target_text = segment.get("modified_text") or segment.get("target_text") or ""

    # Run the compatibility check
    from utils.latex_formula_checker import check_segment_pdf_compat

    result = check_segment_pdf_compat(target_text, segment_index=segment_index)

    # If check failed, try to get LLM repair suggestion automatically
    repair_suggestion = None
    if not result.passed:
        logger.warning(
            LogModule.ROUTE,
            f"[TEST-PDF-COMPAT-API] Segment {segment_index} FAILED PDF compat check "
            f"(issues={len(result.issues)}, has_latex={result.has_latex})"
        )
        try:
            from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm
            task_state = task_manager.get_task(task_id)
            llm_cfg = task_state.get("llm_config_for_repair") if task_state else None
            if llm_cfg:
                repair_req = LatexRepairRequest(
                    error_type="manual_segment_repair",
                    tex_context=result.stderr or "",
                    md_context=target_text,
                    original_md_snippet=target_text,
                    task_id=task_id,
                    segment_index=segment_index,
                    llm_config=llm_cfg,
                )
                llm_result = repair_latex_snippet_with_llm(repair_req)
                if llm_result.fixed_md_snippet and llm_result.fixed_md_snippet.strip() != target_text.strip():
                    repair_suggestion = llm_result.fixed_md_snippet
                    logger.info(
                        LogModule.ROUTE,
                        f"[TEST-PDF-COMPAT-API] LLM repair suggestion generated for segment {segment_index}"
                    )
        except Exception as repair_err:
            logger.debug(
                LogModule.ROUTE,
                f"[TEST-PDF-COMPAT-API] LLM repair suggestion failed for segment {segment_index}: {repair_err}"
            )
    else:
        logger.info(
            LogModule.ROUTE,
            f"[TEST-PDF-COMPAT-API] Segment {segment_index} passed PDF compat check "
            f"(has_latex={result.has_latex}, pandoc={result.pandoc_available})"
        )

    return JSONResponse(content={
        "success": True,
        "passed": result.passed,
        "has_latex": result.has_latex,
        "pandoc_available": result.pandoc_available,
        "message": result.message,
        "issues": [
            {
                "snippet_index": issue.snippet_index,
                "message": issue.message,
                "severity": issue.severity,
                "raw_stderr": issue.raw_stderr,
            }
            for issue in result.issues
        ],
        "stderr": result.stderr,
        "repair_suggestion": repair_suggestion,
    })


@router.post(
    "/translation-segments/{task_id}/batch-test-pdf-compat",
    summary="Batch test PDF compatibility for all LaTeX-containing segments",
    description="Run Pandoc + XeLaTeX on all segments that contain LaTeX math/commands. "
                "Segments without LaTeX are skipped (assumed OK). Returns a summary of passed/failed.",
    responses={
        200: {
            "description": "Batch PDF compatibility check result.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "task_id": "task123",
                        "total_segments": 100,
                        "latex_segments_checked": 15,
                        "passed_count": 14,
                        "failed_count": 1,
                        "results": []
                    }
                }
            }
        },
        404: {"description": "Task ID not found."},
    }
)
async def batch_test_pdf_compat_api(task_id: str):
    """Batch test PDF compatibility for all LaTeX-containing segments."""
    logger.info(
        LogModule.ROUTE,
        f"[BATCH-TEST-PDF-COMPAT-API] Request: task_id={task_id}"
    )

    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[BATCH-TEST-PDF-COMPAT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    segments_data = _ts_module().get_translation_segments(task_id)
    if segments_data is None:
        raise HTTPException(status_code=404, detail="No translation segments available.")

    if isinstance(segments_data, list):
        segments_list = segments_data
    else:
        segments_list = segments_data.get("segments", []) or []

    from utils.latex_repair_payload import has_latex_content
    from utils.latex_formula_checker import check_segment_pdf_compat

    total_segments = len(segments_list)
    latex_segments = []
    for seg in segments_list:
        if isinstance(seg, dict):
            text = seg.get("modified_text") or seg.get("target_text") or ""
            if has_latex_content(text):
                latex_segments.append(seg)

    results = []
    passed_count = 0
    failed_count = 0

    # Pre-fetch LLM config once for batch repair suggestions
    task_state_for_repair = task_manager.get_task(task_id)
    llm_cfg_batch = task_state_for_repair.get("llm_config_for_repair") if task_state_for_repair else None
    failed_entries_for_repair = []

    for seg in latex_segments:
        seg_idx = seg.get("segment_index", -1)
        text = seg.get("modified_text") or seg.get("target_text") or ""
        result = check_segment_pdf_compat(text, segment_index=seg_idx)

        entry = {
            "segment_index": seg_idx,
            "passed": result.passed,
            "has_latex": result.has_latex,
            "pandoc_available": result.pandoc_available,
            "message": result.message,
            "issues": [
                {
                    "snippet_index": issue.snippet_index,
                    "message": issue.message,
                    "severity": issue.severity,
                    "raw_stderr": issue.raw_stderr,
                }
                for issue in result.issues
            ],
            "stderr": result.stderr,
            "repair_suggestion": None,
        }
        if not result.passed:
            failed_entries_for_repair.append((entry, text))
        results.append(entry)
        if result.passed:
            passed_count += 1
        else:
            failed_count += 1

    # Generate LLM repair suggestions for failed segments (max 3 to avoid long waits)
    if llm_cfg_batch and failed_entries_for_repair:
        try:
            from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm
            for entry, text in failed_entries_for_repair[:3]:
                seg_idx = entry["segment_index"]
                repair_req = LatexRepairRequest(
                    error_type="pre_check_failed",
                    tex_context=entry.get("stderr") or "",
                    md_context=text,
                    original_md_snippet=text,
                    task_id=task_id,
                    segment_index=seg_idx,
                    llm_config=llm_cfg_batch,
                )
                llm_result = repair_latex_snippet_with_llm(repair_req)
                if llm_result.fixed_md_snippet and llm_result.fixed_md_snippet.strip() != text.strip():
                    entry["repair_suggestion"] = llm_result.fixed_md_snippet
                    logger.info(
                        LogModule.ROUTE,
                        f"[BATCH-TEST-PDF-COMPAT-API] Generated repair suggestion for segment {seg_idx}"
                    )
        except Exception as repair_err:
            logger.debug(
                LogModule.ROUTE,
                f"[BATCH-TEST-PDF-COMPAT-API] Batch repair suggestion generation failed: {repair_err}"
            )

    # Cache results in task_state so get_source_preview can attach them to segments
    try:
        task_state = task_manager.get_task(task_id)
        if task_state is not None:
            pdf_compat_results = {}
            for entry in results:
                seg_idx = entry.get("segment_index")
                if seg_idx is not None:
                    pdf_compat_results[str(seg_idx)] = {
                        "passed": entry["passed"],
                        "has_latex": entry["has_latex"],
                        "pandoc_available": entry["pandoc_available"],
                        "message": entry["message"],
                        "checked_at": time.time(),
                    }
            task_state["pdf_compat_results"] = pdf_compat_results
    except Exception as cache_err:
        logger.debug(
            LogModule.ROUTE,
            f"[BATCH-TEST-PDF-COMPAT-API] Failed to cache results: {cache_err}"
        )

    logger.info(
        LogModule.ROUTE,
        f"[BATCH-TEST-PDF-COMPAT-API] Task {task_id}: "
        f"total={total_segments}, latex_checked={len(latex_segments)}, "
        f"passed={passed_count}, failed={failed_count}"
    )

    return JSONResponse(content={
        "success": True,
        "task_id": task_id,
        "total_segments": total_segments,
        "latex_segments_checked": len(latex_segments),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "results": results,
    })


@router.post(
    "/translation-segments/{task_id}/clear-pdf-compat-cache",
    summary="Clear cached PDF compatibility check results",
    description="Remove cached pdf_compat_results from task_state. Call this after segments are modified."
)
async def clear_pdf_compat_cache_api(task_id: str):
    """Clear cached PDF compatibility results so next check starts fresh."""
    logger.info(
        LogModule.ROUTE,
        f"[CLEAR-PDF-COMPAT-CACHE-API] Request: task_id={task_id}"
    )

    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[CLEAR-PDF-COMPAT-CACHE-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    task_state = task_manager.get_task(task_id)
    cleared = False
    if task_state and "pdf_compat_results" in task_state:
        del task_state["pdf_compat_results"]
        cleared = True
        logger.info(
            LogModule.ROUTE,
            f"[CLEAR-PDF-COMPAT-CACHE-API] Cleared pdf_compat_results for task {task_id}"
        )
    else:
        logger.info(
            LogModule.ROUTE,
            f"[CLEAR-PDF-COMPAT-CACHE-API] No pdf_compat_results to clear for task {task_id}"
        )

    return JSONResponse(content={
        "success": True,
        "cleared": cleared,
        "message": "PDF compatibility cache cleared." if cleared else "No cache to clear.",
    })


@router.post(
    "/translation-segments/{task_id}/{segment_index}/repair-for-pdf-export",
    summary="AI repair a segment for PDF export failure",
    description="Call LLM to suggest a fix for a segment that caused PDF export to fail. "
                "Uses pdf_export_latex_issue error context if available, otherwise uses generic repair.",
    responses={
        200: {
            "description": "Repair suggestion returned.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "segment_index": 53,
                        "original_text": "...",
                        "fixed_text": "...",
                        "error_type": "undefined_control_sequence",
                        "notes": "LLM repair executed successfully.",
                    }
                }
            }
        },
        404: {"description": "Task ID or segment not found."},
    }
)
async def repair_for_pdf_export_api(
    task_id: str,
    segment_index: int,
    body: dict = Body(...),
):
    """AI repair a segment using LLM, with PDF export error context."""
    user_prompt = body.get("user_prompt") or body.get("custom_prompt")
    logger.info(
        LogModule.ROUTE,
        f"[REPAIR-FOR-PDF-EXPORT-API] Request: task_id={task_id}, segment_index={segment_index}, has_user_prompt={bool(user_prompt)}"
    )

    task_state = task_manager.get_task(task_id)
    if task_state is None:
        logger.warning(LogModule.ROUTE, f"[REPAIR-FOR-PDF-EXPORT-API] Task ID '{task_id}' not found")
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    # Retrieve the segment
    segments_data = _ts_module().get_translation_segments(task_id)
    if segments_data is None:
        raise HTTPException(status_code=404, detail="No translation segments available.")

    if isinstance(segments_data, list):
        segments_list = segments_data
    else:
        segments_list = segments_data.get("segments", []) or []

    segment = None
    for seg in segments_list:
        if isinstance(seg, dict) and seg.get("segment_index") == segment_index:
            segment = seg
            break

    if segment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Segment index {segment_index} not found for task '{task_id}'."
        )

    target_text = segment.get("modified_text") or segment.get("target_text") or ""
    if not target_text:
        raise HTTPException(
            status_code=400,
            detail=f"Segment {segment_index} has no text to repair."
        )

    # Gather error context from pdf_export_latex_issue if available
    error_type = "manual_segment_repair"
    tex_context = ""
    pdf_issue = task_state.get("pdf_export_latex_issue")
    if isinstance(pdf_issue, dict):
        # Prefer the error context for this specific segment
        if pdf_issue.get("segment_index") == segment_index:
            error_type = pdf_issue.get("error_type") or error_type
            tex_context = pdf_issue.get("stderr_excerpt", "") or ""
        else:
            # If the failing segment is different, still use the error type but not the context
            error_type = pdf_issue.get("error_type") or error_type

    # Also try to get error context from pdf_compat_results
    pdf_compat = task_state.get("pdf_compat_results", {})
    if isinstance(pdf_compat, dict):
        seg_compat = pdf_compat.get(str(segment_index)) or pdf_compat.get(segment_index)
        if isinstance(seg_compat, dict) and not seg_compat.get("passed", True):
            if not tex_context:
                tex_context = seg_compat.get("message", "")

    from utils.latex_repair_llm import LatexRepairRequest, repair_latex_snippet_with_llm

    llm_cfg = task_state.get("llm_config_for_repair")
    req = LatexRepairRequest(
        error_type=error_type,
        tex_context=tex_context,
        md_context=target_text,
        original_md_snippet=target_text,
        task_id=task_id,
        segment_index=segment_index,
        llm_config=llm_cfg,
        user_prompt=user_prompt,
    )
    llm_result = repair_latex_snippet_with_llm(req)

    changed = (llm_result.fixed_md_snippet or "").strip() != target_text.strip()

    logger.info(
        LogModule.ROUTE,
        f"[REPAIR-FOR-PDF-EXPORT-API] Repair suggestion for task {task_id}, segment {segment_index}: "
        f"changed={changed}, error_type={error_type}, notes={llm_result.notes}"
    )

    return JSONResponse(content={
        "success": True,
        "segment_index": segment_index,
        "original_text": target_text,
        "fixed_text": llm_result.fixed_md_snippet,
        "error_type": error_type,
        "changed": changed,
        "notes": llm_result.notes,
    })


@router.post(
    "/translation-segments/{task_id}/repair-docx-math-fragments",
    summary="AI repair segments that fail Pandoc DOCX fragment math check",
    description=(
        "Runs per-segment Pandoc markdown→docx smoke tests (unless refresh_check_first=false with cached "
        "docx_math_fragment_issues), sends each failing segment plus Pandoc/texmath stderr to the LLM, "
        "writes repaired target_text back into translation_segments, then optionally re-runs the fragment checks."
    ),
)
async def repair_docx_math_fragments_api(
    task_id: str,
    body: Dict[str, Any] = Body(default_factory=dict),
):
    """Batch repair using LLM + Pandoc stderr from DOCX fragment checks."""
    payload = body if isinstance(body, dict) else {}
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    llm_cfg = task_state.get("llm_config_for_repair")
    if not llm_cfg or not llm_cfg.get("base_url") or not llm_cfg.get("model_id"):
        raise HTTPException(
            status_code=400,
            detail="llm_config_for_repair is missing or incomplete (need base_url and model_id).",
        )

    from utils.docx_math_fragment_llm_repair import repair_docx_math_fragments_with_llm

    refresh = bool(payload.get("refresh_check_first", True))
    recheck = bool(payload.get("recheck_after", True))
    max_raw = payload.get("max_segments")
    max_segments = int(max_raw) if max_raw is not None else None

    result = repair_docx_math_fragments_with_llm(
        task_state,
        task_id,
        llm_cfg,
        refresh_check_first=refresh,
        recheck_after=recheck,
        max_segments=max_segments,
    )

    logger.info(
        LogModule.ROUTE,
        f"[REPAIR-DOCX-MATH-FRAGMENTS-API] task_id={task_id} success={result.get('success')} "
        f"updated={result.get('segments_updated')} issues_after={result.get('issues_after')}",
    )

    return JSONResponse(content=result)


@router.get(
    "/pdf-export-status/{task_id}",
    summary="Get current PDF export status and diagnosis",
    description="Returns the latest pdf_export_latex_issue, pdf_compat_results, and summary for the task.",
)
async def get_pdf_export_status(task_id: str):
    """Get current PDF export status, including any LaTeX compilation issues and diagnosis."""
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    pdf_issue = task_state.get("pdf_export_latex_issue")
    pdf_compat = task_state.get("pdf_compat_results", {})

    # Build summary from pdf_compat_results
    summary = None
    if isinstance(pdf_compat, dict) and pdf_compat:
        _checked = 0
        _passed = 0
        _failed = 0
        _failed_indices = []
        for _k, _v in pdf_compat.items():
            if isinstance(_v, dict):
                _checked += 1
                if _v.get("passed"):
                    _passed += 1
                else:
                    _failed += 1
                    try:
                        _failed_indices.append(int(_k))
                    except (ValueError, TypeError):
                        pass
        summary = {
            "checked_segments": _checked,
            "passed": _passed,
            "failed": _failed,
            "failed_segment_indices": sorted(_failed_indices),
        }

    return JSONResponse(content={
        "success": True,
        "task_id": task_id,
        "has_pdf_issue": pdf_issue is not None,
        "pdf_export_latex_issue": pdf_issue,
        "pdf_compat_results": pdf_compat,
        "pdf_compat_summary": summary,
    })

