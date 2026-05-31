# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Status routes.

Handles task status queries, logs, and preview endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Path as FastApiPath, Query as FastApiQuery
from fastapi.responses import JSONResponse

from backend.app.services.task import task_manager
from backend.app.services.status import StatusService
from backend.app.config.pagination_config import MAX_PAGINATION_LIMIT
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# Initialize service instance
status_service = StatusService(task_manager)


@router.get(
    "/status/{task_id}",
    summary="Get task status",
    description="Get the current status of a task based on task ID. When `download_ready` is `true`, the `downloads` and `attachment` objects will contain available download links.",
    responses={
        200: {
            "description": "Successfully retrieved task status.",
            "content": {"application/json": {
                "example": {
                    "task_id": "a1b2c3d4",
                    "status": "completed",
                    "progress": 100,
                    "message": "Translation completed successfully",
                    "download_ready": True,
                    "downloads": {"html": "/service/download/a1b2c3d4/html"},
                    "attachments": {}
                }
            }}
        },
        404: {"description": "Task ID not found."}
    }
)
async def service_get_status_route(task_id: str = FastApiPath(..., description="Unique task identifier.")):
    """Get task status."""
    # Use StatusService instead of app_routes_service function
    result = await status_service.get_status(task_id)
    # StatusService.get_status returns a JSONResponse, so return it directly
    return result


@router.get(
    "/logs/{task_id}",
    summary="Get task logs",
    description="Get the log history for a specific task.",
    responses={
        200: {
            "description": "Successfully retrieved task logs.",
            "content": {"application/json": {
                "example": {
                    "task_id": "a1b2c3d4",
                    "logs": [
                        {"timestamp": "2025-01-27T10:00:00Z", "level": "info", "message": "Task started"},
                        {"timestamp": "2025-01-27T10:01:00Z", "level": "info", "message": "Processing file..."}
                    ]
                }
            }}
        },
        404: {"description": "Task ID not found."}
    }
)
async def service_get_logs_route(task_id: str = FastApiPath(..., description="Unique task identifier.")):
    """Get task logs."""
    # Use StatusService instead of app_routes_service function
    result = status_service.get_logs(task_id)
    return JSONResponse(content=result)


@router.get(
    "/source-preview/{task_id}",
    summary="Get source text preview segments",
    description="Return pre-split source text segments for preview to validate import before translation. Supports pagination with offset/limit. Includes workflow-specific metadata.",
)
async def service_get_source_preview_route(
    task_id: str = FastApiPath(..., description="Unique task identifier."),
    offset: int = FastApiQuery(0, ge=0, description="Number of segments to skip"),
    limit: int = FastApiQuery(200, ge=1, le=MAX_PAGINATION_LIMIT, description="Maximum number of segments to return"),
    target_lang: Optional[str] = FastApiQuery(None, description="Target language code for language match detection (e.g., 'zh', 'en'). If not provided, will try to get from task payload."),
):
    """Get source text preview segments."""
    # Use StatusService instead of app_routes_service function
    result = await status_service.get_source_preview(task_id, offset=offset, limit=limit, target_lang=target_lang)
    # StatusService.get_source_preview returns a JSONResponse, so return it directly
    return result


@router.get(
    "/layout-extract/{task_id}",
    summary="Get layout extraction result",
    description="Get layout extraction result for PDF files. Returns layout blocks, pages, and metadata.",
)
async def service_get_layout_extract_route(
    task_id: str = FastApiPath(..., description="Unique task identifier."),
    chunk_size: Optional[int] = FastApiQuery(None, description="Override chunk size for regenerating chunks (optional)"),
    excluded_segment_indices: Optional[str] = FastApiQuery(None, description="Comma-separated list of segment indices to exclude (optional)"),
    target_lang: Optional[str] = FastApiQuery(None, description="Target language code for language match detection (e.g., 'zh', 'en'). If not provided, will try to get from task payload."),
):
    """Get layout extraction result."""
    # CRITICAL: Log the received target_lang parameter at route level for debugging
    logger.info(
        LogModule.ROUTE,
        f"[LAYOUT-EXTRACT-ROUTE] Task {task_id}: Received target_lang parameter from FastAPI route: {target_lang} (type: {type(target_lang)})"
    )
    
    # Use StatusService instead of app_routes_service function
    result = await status_service.get_layout_extract(
        task_id,
        chunk_size=chunk_size,
        excluded_segment_indices=excluded_segment_indices,
        target_lang=target_lang
    )
    # StatusService.get_layout_extract returns a JSONResponse, so return it directly
    return result


@router.post(
    "/update-excluded-segments/{task_id}",
    summary="Update excluded segments for target language",
    description="Re-detect excluded segments based on new target language. Updates excluded_segment_indices in segments_metadata.",
    responses={
        200: {
            "description": "Successfully updated excluded segments.",
            "content": {"application/json": {
                "example": {
                    "task_id": "a1b2c3d4",
                    "target_lang": "zh",
                    "excluded_segment_indices": [0, 1, 2],
                    "total_segments": 100,
                    "excluded_count": 3,
                    "message": "Updated excluded segments for target language 'zh'"
                }
            }}
        },
        404: {"description": "Task ID not found or no segments available."},
        400: {"description": "Task has failed."}
    }
)
async def service_update_excluded_segments_route(
    task_id: str = FastApiPath(..., description="Unique task identifier."),
    target_lang: str = FastApiQuery(..., description="Target language code (e.g., 'zh', 'en')."),
    auto_exclude: bool = FastApiQuery(False, description="If True, automatically exclude language-matched segments. If False, return them for user confirmation."),
):
    """Update excluded segments for target language."""
    result = await status_service.update_excluded_segments_for_language(task_id, target_lang, auto_exclude=auto_exclude)
    return result


@router.get(
    "/format-settings/{task_id}",
    summary="Get format settings for a task",
    description="Get table_body_format and equation_format settings from task state.",
    responses={
        200: {
            "description": "Successfully retrieved format settings.",
            "content": {"application/json": {
                "example": {
                    "task_id": "a1b2c3d4",
                    "table_body_format": "html",
                    "equation_format": "text"
                }
            }}
        },
        404: {"description": "Task ID not found."}
    }
)
async def service_get_format_settings_route(task_id: str = FastApiPath(..., description="Unique task identifier.")):
    """Get format settings for a task."""
    result = status_service.get_format_settings(task_id)
    return JSONResponse(content=result)


@router.put(
    "/format-settings/{task_id}",
    summary="Update format settings for a task",
    description="Update table_body_format and equation_format settings in task state.",
    responses={
        200: {
            "description": "Successfully updated format settings.",
            "content": {"application/json": {
                "example": {
                    "task_id": "a1b2c3d4",
                    "table_body_format": "image",
                    "equation_format": "image",
                    "message": "Format settings updated successfully"
                }
            }}
        },
        400: {"description": "Invalid format values."},
        404: {"description": "Task ID not found."}
    }
)
async def service_update_format_settings_route(
    task_id: str = FastApiPath(..., description="Unique task identifier."),
    table_body_format: Optional[str] = FastApiQuery(None, description="Table format: 'html' or 'image'"),
    equation_format: Optional[str] = FastApiQuery(None, description="Equation format: 'text' or 'image'"),
    bilingual_export: Optional[bool] = FastApiQuery(None, description="Enable bilingual export: true or false"),
    bilingual_order: Optional[str] = FastApiQuery(None, description="Bilingual order: 'target_after_source' or 'target_before_source'"),
    source_text_italic: Optional[bool] = FastApiQuery(None, description="Source text italic: true or false"),
    source_text_color: Optional[str] = FastApiQuery(None, description="Source text color: 'gray', 'blue', 'red', 'green', 'orange', 'black'"),
    target_text_italic: Optional[bool] = FastApiQuery(None, description="Target text italic: true or false"),
    target_text_color: Optional[str] = FastApiQuery(None, description="Target text color: 'gray', 'blue', 'red', 'green', 'orange', 'black'"),
):
    """Update format settings for a task."""
    result = status_service.update_format_settings(
        task_id,
        table_body_format=table_body_format,
        equation_format=equation_format,
        bilingual_export=bilingual_export,
        bilingual_order=bilingual_order,
        source_text_italic=source_text_italic,
        source_text_color=source_text_color,
        target_text_italic=target_text_italic,
        target_text_color=target_text_color,
    )
    return JSONResponse(content=result)