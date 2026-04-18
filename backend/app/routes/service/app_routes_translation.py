# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Translation routes.

Handles translation task submission, cancellation, and resource release.
"""

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse

from backend.app.models.service import TranslateServiceRequest
from backend.app.services.task import task_manager
from backend.app.services.translation import TranslationService
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# Initialize service instance
translation_service = TranslationService(task_manager)


@router.post(
    "/translate",
    summary="Submit translation task (unified entry point)",
    description="""
Receive a JSON request containing file content (Base64 encoded) and workflow parameters to start a background translation task.

- **Workflow Selection**: The `payload.workflow_type` field in the request body determines the type of this task (such as `markdown_based`, `txt`, `json`, `xlsx`, `docx`, `srt`, `epub`, `html`).
- **Dynamic Parameters**: Depending on the selected workflow, the API requires different parameter sets. Please refer to the Schema or examples below.
- **Asynchronous Processing**: This endpoint returns a task ID immediately, and the client needs to poll the status interface to get progress.
""",
    responses={
        200: {
            "description": "Translation task started successfully.",
            "content": {"application/json": {
                "example": {"task_started": True, "task_id": "a1b2c3d4", "message": "Translation task started successfully, please wait..."}}}
        },
        400: {"description": "Invalid request body, e.g., Base64 decoding failed."},
        429: {"description": "Server already has a task with the same ID being processed (theoretically should not happen since ID is newly generated)."},
        500: {"description": "Unknown error occurred while starting background task."},
    }
)
async def service_translate(request: TranslateServiceRequest = Body(..., description="Detailed parameters and file content for translation task.")):
    """Submit a translation task."""
    import base64
    import binascii
    import uuid

    task_id = uuid.uuid4().hex[:8]
    
    # Extract workflow_type for logging
    workflow_type_from_payload = 'unknown'
    if hasattr(request, 'payload') and request.payload:
        if hasattr(request.payload, 'workflow_type'):
            workflow_type_from_payload = getattr(request.payload, 'workflow_type', 'unknown')
        elif isinstance(request.payload, dict):
            workflow_type_from_payload = request.payload.get('workflow_type', 'unknown')
    
    logger.info(
        LogModule.ROUTE,
        f"[IMPORT] Translation task started: task_id={task_id}, filename={request.file_name}, "
        f"file_content_length={len(request.file_content) if request.file_content else 0} chars (base64), "
        f"workflow_type={workflow_type_from_payload}"
    )
    
    try:
        file_contents = base64.b64decode(request.file_content)
        logger.info(LogModule.ROUTE, f"[IMPORT] File decoded successfully: task_id={task_id}, decoded_size={len(file_contents)} bytes")
    except (binascii.Error, TypeError, ValueError) as e:
        # ValueError: 当输入包含非 ASCII 字符时（如中文字符）
        # binascii.Error: 当 Base64 格式无效时
        # TypeError: 当输入类型错误时
        error_msg = str(e)
        if "ASCII" in error_msg or "string argument" in error_msg:
            error_detail = "Invalid Base64 file content: input contains non-ASCII characters. Base64 encoding only supports ASCII characters."
        else:
            error_detail = f"Invalid Base64 file content: {error_msg}"
        logger.error(
            LogModule.ROUTE,
            f"[IMPORT] Failed to decode Base64 file content: task_id={task_id}, filename={request.file_name}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=400, detail=error_detail)
    
    try:
        # Determine smart glossary matching flag (request override > system default)
        from backend.config.config_loader import get_unified_config
        unified_config = get_unified_config()
        effective_smart_glossary = (
            request.smart_glossary_matching
            if request.smart_glossary_matching is not None
            else unified_config.smart_glossary_matching_enabled
        )
        
        logger.info(
            LogModule.ROUTE,
            f"[IMPORT] Starting translation task: task_id={task_id}, filename={request.file_name}, "
            f"file_size={len(file_contents)} bytes, smart_glossary={effective_smart_glossary}"
        )
        
        # Use TranslationService instead of app_routes_service function
        response_data = await translation_service.start_translation_task(
            task_id=task_id,
            payload=request.payload,
            file_contents=file_contents,
            original_filename=request.file_name
        )
        
        logger.info(LogModule.ROUTE, f"[IMPORT] Translation task started successfully: task_id={task_id}, response={response_data}")
        # Attach flag to response and record in task state if available
        try:
            task_state = task_manager.get_task(task_id)
            if task_state:
                task_state["smart_glossary_matching"] = effective_smart_glossary
                task_manager.add_log(task_id, "info", f"Smart glossary matching: {'enabled' if effective_smart_glossary else 'disabled'}")
        except Exception:
            pass
        return JSONResponse(content=response_data)
    except HTTPException as e:
        logger.error(
            LogModule.ROUTE,
            f"[IMPORT] HTTPException in translation task: task_id={task_id}, status_code={e.status_code}, detail={e.detail}",
            exc_info=True
        )
        if e.status_code == 429:
            return JSONResponse(status_code=e.status_code, content={"task_started": False, "message": e.detail})
        if e.status_code == 500:
            return JSONResponse(status_code=e.status_code, content={"task_started": False, "message": e.detail})
        raise e
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[IMPORT] Unexpected error in translation task: task_id={task_id}, filename={request.file_name}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to start translation task: {str(e)}")


@router.post(
    "/cancel/{task_id}",
    summary="Cancel translation task",
    description="""Cancel an ongoing translation task based on task ID. If the task has been completed, failed, or already cancelled, an error will be returned."""
)
async def service_cancel_translate(task_id: str):
    """Cancel a translation task."""
    logger.info(LogModule.ROUTE, f"[CANCEL-TRANSLATION] Cancel translation request: task_id={task_id}")
    
    try:
        # Use TranslationService instead of app_routes_service function
        result = translation_service.cancel_translation(task_id)
        logger.info(LogModule.ROUTE, f"[CANCEL-TRANSLATION] Translation task cancelled successfully: task_id={task_id}")
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[CANCEL-TRANSLATION] Unexpected error cancelling translation task {task_id}: {e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to cancel translation task: {str(e)}")


@router.post(
    "/release/{task_id}",
    summary="Release task resources",
    description="""Release all resources occupied by the task on the server based on task ID, including status, logs, and cached translation result files. If the task is in progress, it will first try to cancel the task. This operation is irreversible."""
)
async def service_release_task(task_id: str):
    """Release task resources."""
    import os
    import shutil
    
    logger.info(LogModule.ROUTE, f"[RELEASE-TASK] Release task resources request: task_id={task_id}")
    
    if task_manager.get_task(task_id) is None:
        logger.warning(LogModule.ROUTE, f"[RELEASE-TASK] Task ID '{task_id}' not found")
        return JSONResponse(status_code=404, content={"released": False, "message": f"Task ID '{task_id}' not found."})
    
    task_state = task_manager.get_task(task_id)
    message_parts = []
    
    if task_state and task_state.get("is_processing") and task_state.get("current_task_ref"):
        try:
            # Task is in progress, will try to cancel before release
            translation_service.cancel_translation(task_id)
            message_parts.append("Task has been cancelled.")
            logger.info(LogModule.ROUTE, f"[RELEASE-TASK] Task {task_id} cancelled before release")
        except HTTPException as e:
            # Expected situation when cancelling task (may have been completed)
            message_parts.append(f"Task cancellation step skipped (may have been completed or cancelled).")
            logger.debug(LogModule.ROUTE, f"[RELEASE-TASK] Task {task_id} cancellation skipped: {e.detail}")
    
    if task_state:
        temp_dir = task_state.get("temp_dir")
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                message_parts.append("Temporary files cleaned up.")
                logger.debug(LogModule.ROUTE, f"[RELEASE-TASK] Cleaned up temp directory for task {task_id}: {temp_dir}")
            except Exception as e:
                message_parts.append(f"Error cleaning up temporary files: {e}.")
                logger.warning(LogModule.ROUTE, f"[RELEASE-TASK] Failed to clean up temp directory for task {task_id}: {e}")
    
    task_manager.cleanup_task_resources(task_id)
    message_parts.append(f"Resources for task '{task_id}' have been released.")
    logger.info(LogModule.ROUTE, f"[RELEASE-TASK] Task resources released successfully: task_id={task_id}")
    return JSONResponse(content={"released": True, "message": " ".join(message_parts)})

