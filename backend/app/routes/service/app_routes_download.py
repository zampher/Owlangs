# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Download routes.

Handles file download endpoints for translation results.
"""

from typing import Optional

from fastapi import APIRouter, Path as FastApiPath, Query as FastApiQuery
from fastapi.responses import FileResponse

from backend.app.services.download import DownloadService
from backend.app.services.download.output_generator import get_ebook_converters_availability
from backend.app.services.task import task_manager
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# Initialize service instance
download_service = DownloadService(task_manager)


@router.get(
    "/download/{task_id}/{file_type}",
    summary="Download translation result files",
    description="Download translation result files after task completion.",
    responses={
        200: {
            "description": "Successfully returned file stream. Filename is specified via Content-Disposition header.",
            "content": {
                "text/html; charset=utf-8": {"schema": {"type": "string"}},
                "text/markdown; charset=utf-8": {"schema": {"type": "string"}},
                "text/plain; charset=utf-8": {"schema": {"type": "string"}},
                "text/csv; charset=utf-8": {"schema": {"type": "string"}},
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {"schema": {"type": "string", "format": "binary"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
                    "schema": {"type": "string", "format": "binary"}},
                "application/epub+zip": {
                    "schema": {"type": "string", "format": "binary"}},
            }
        },
        404: {"description": "Task ID does not exist, or the task does not support the requested file type, or temporary files have been lost."},
        500: {"description": "Internal error occurred while reading file on server."}
    }
)
async def service_download_file_route(
        task_id: str = FastApiPath(..., description="ID of completed task", examples=["b2865b93"]),
        file_type: str = FastApiPath(..., description="File type to download.", examples=["html", "md", "json", "csv", "docx", "srt", "epub", "mobi", "ts", "pdf"]),
        table_body_format: Optional[str] = FastApiQuery(None, description="Table format for PDF rendering: 'html' or 'image' (overrides task payload setting, only applies to PDF downloads)", examples=["html", "image"]),
        equation_format: Optional[str] = FastApiQuery(None, description="Equation format for PDF rendering: 'text' (LaTeX) or 'image' (overrides task payload setting, only applies to PDF/MD downloads)", examples=["text", "image"]),
        embed_images: Optional[bool] = FastApiQuery(None, description="For MD downloads: if True, embed images as data URIs; if False, save images to folder and return ZIP. Default: True (embed).", examples=[True, False]),
        ebook_engine: Optional[str] = FastApiQuery(None, description="For epub/mobi: 'pandoc' or 'calibre'. Only used when both converters are available; choose which path to use for export.", examples=["pandoc", "calibre"]),
):
    """Download translation result files."""
    resp = await download_service.download_file(
        task_id=task_id,
        file_type=file_type,
        table_body_format=table_body_format,
        equation_format=equation_format,
        embed_images=embed_images,
        ebook_engine=ebook_engine,
    )
    try:
        if isinstance(resp, FileResponse):
            path = getattr(resp, "path", None)
            ts = task_manager.get_task(task_id)
            if path and ts:
                from backend.app.services.translation.translation_result_stash import (
                    record_generated_result,
                )

                record_generated_result(task_id, file_type, path, ts)
    except Exception as e:
        logger.warning(LogModule.ROUTE, f"[DOWNLOAD-STASH] Record stash failed task_id={task_id}: {e}", exc_info=True)
    return resp


@router.get(
    "/ebook-converters",
    summary="Check ebook converter availability",
    description="Returns whether Pandoc and Calibre are available. When both are true, the frontend can offer a choice (pandoc vs calibre) for EPUB/MOBI export.",
    responses={
        200: {
            "description": "Availability of pandoc and calibre.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "pandoc": {"type": "boolean"},
                            "calibre": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    },
)
async def service_ebook_converters_route():
    """Return { pandoc: bool, calibre: bool } for export engine choice."""
    return get_ebook_converters_availability()


@router.get(
    "/debug/{task_id}/{file_type}",
    summary="Get debug files (HTML, bbox JSON, original PDF)",
    description="Get debug files for layout inspection. Available file types: 'html', 'bbox', 'original-pdf'.",
    responses={
        200: {
            "description": "Successfully returned debug file.",
            "content": {
                "text/html; charset=utf-8": {"schema": {"type": "string"}},
                "application/json": {"schema": {"type": "string"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
            }
        },
        404: {"description": "Task ID not found or debug file not available."}
    }
)
async def service_get_debug_file_route(
    task_id: str = FastApiPath(..., description="Task ID", examples=["a1b2c3d4"]),
    file_type: str = FastApiPath(..., description="Debug file type: 'html', 'bbox', or 'original-pdf'", examples=["html", "bbox", "original-pdf"]),
    table_body_format: Optional[str] = FastApiQuery(None, description="Table format for PDF rendering: 'html' or 'image' (overrides task payload setting)", examples=["html", "image"])
):
    """Get debug files for layout inspection."""
    # Use DownloadService instead of app_routes_service function
    return await download_service.get_debug_file(
        task_id=task_id,
        file_type=file_type,
        table_body_format=table_body_format
    )

