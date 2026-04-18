# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Format conversion routes.

Handles format conversion and source resplit endpoints.
"""

from fastapi import APIRouter, HTTPException, Body, Path as FastApiPath, Query as FastApiQuery
from fastapi.responses import JSONResponse

from backend.app.models.service import ConvertFormatRequest
from backend.app.services.format_conversion_service import FormatConversionService
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# Initialize service instance
format_conversion_service = FormatConversionService()


@router.post(
    "/convert-format",
    summary="Convert document format (parse + convert, no translation)",
    description="""
    Convert document format without translation.
    
    This endpoint performs document parsing and format conversion only,
    without calling translation APIs. It reuses the translation workflow
    infrastructure with skip_translate=True.
    
    - **Workflow Auto-detection**: If `workflow_type` is not provided, it will be
      automatically determined from the file extension.
    - **Asynchronous Processing**: Returns a task ID immediately, client needs to
      poll the status endpoint to get progress.
    """,
    responses={
        200: {
            "description": "Format conversion task started successfully.",
            "content": {"application/json": {
                "example": {"success": True, "task_id": "a1b2c3d4", "message": "Format conversion task started successfully"}}
            }
        },
        400: {"description": "Invalid request body, e.g., Base64 decoding failed."},
        500: {"description": "Unknown error occurred while starting background task."},
    }
)
async def service_convert_format_route(
    request: ConvertFormatRequest = Body(..., description="Format conversion request with file content and parameters")
):
    """Convert document format without translation."""
    try:
        logger.info(
            LogModule.ROUTE,
            f"[FORMAT-CONVERSION] Format conversion request received: filename={request.file_name}, "
            f"workflow_type={getattr(request, 'workflow_type', 'auto')}"
        )
        
        # Use FormatConversionService instead of app_routes_service function
        result = await format_conversion_service.convert_format(request)
        
        task_id = result.get('task_id') if isinstance(result, dict) else getattr(result, 'task_id', None)
        if task_id:
            logger.info(
                LogModule.ROUTE,
                f"[FORMAT-CONVERSION] Format conversion task started successfully: task_id={task_id}, filename={request.file_name}"
            )
        
        from fastapi.responses import JSONResponse
        return JSONResponse(content=result.dict() if hasattr(result, 'dict') else result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[FORMAT-CONVERSION] Format conversion request failed: filename={request.file_name}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Format conversion failed: {str(e)}")


@router.post(
    "/source-resplit/{task_id}",
    summary="Re-split source text segments",
    description="Re-split source text segments with a new chunk size. This is useful when you want to adjust the segmentation before translation.",
)
async def service_source_resplit_route(
    task_id: str = FastApiPath(..., description="Unique task identifier."),
    chunk_size: int = FastApiQuery(None, description="Override chunk size (optional)"),
    excluded_segment_indices: str = FastApiQuery(None, description="Comma-separated list of segment indices to exclude (optional). If provided, these will be merged with existing excluded_segment_indices in segments_metadata."),
    ocr_language: str = FastApiQuery(None, description="Override OCR language for MinerU (markdown_based workflows). When provided, will update task payload and restart MinerU conversion on Re-extract."),
):
    """Re-split source text segments."""
    try:
        logger.info(
            LogModule.ROUTE,
            f"[SOURCE-RESPLIT] Source resplit request received: task_id={task_id}, "
            f"chunk_size={chunk_size}, excluded_segment_indices={excluded_segment_indices}"
        )
        
        # Use FormatConversionService instead of app_routes_service function
        result = await format_conversion_service.resplit_source(
            task_id=task_id,
            chunk_size=chunk_size,
            excluded_segment_indices=excluded_segment_indices,
            ocr_language=ocr_language,
        )
        
        logger.info(
            LogModule.ROUTE,
            f"[SOURCE-RESPLIT] Source resplit completed successfully: task_id={task_id}"
        )
        
        from fastapi.responses import JSONResponse
        return JSONResponse(content=result if isinstance(result, dict) else {"success": True, "message": "Re-split completed"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.ROUTE,
            f"[SOURCE-RESPLIT] Source resplit request failed: task_id={task_id}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Source resplit failed: {str(e)}")

