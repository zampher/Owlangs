# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Download routes.

Handles file download endpoints for translation results.
"""

import io
import json
import os
import zipfile
from typing import Dict, List, Optional

from fastapi import APIRouter, Path as FastApiPath, Query as FastApiQuery
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.app.services.download import DownloadService
from backend.app.services.download.output_generator import get_ebook_converters_availability
from backend.app.services.task import task_manager
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# Initialize service instance
download_service = DownloadService(task_manager)


class BatchDownloadRequest(BaseModel):
    task_ids: List[str]
    file_type: str  # "md", "html", "docx", "pdf", etc.


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
        chart_body_format: Optional[str] = FastApiQuery(None, description="Chart format for PDF rendering: 'html' or 'image' (overrides task payload setting, only applies to PDF/MD downloads). Default: 'image'", examples=["html", "image"]),
        embed_images: Optional[bool] = FastApiQuery(None, description="For MD downloads: if True, embed images as data URIs; if False, save images to folder and return ZIP. Default: True (embed).", examples=[True, False]),
        ebook_engine: Optional[str] = FastApiQuery(None, description="For epub/mobi: 'pandoc' or 'calibre'. Only used when both converters are available; choose which path to use for export.", examples=["pandoc", "calibre"]),
        bilingual_export: Optional[bool] = FastApiQuery(None, description="Enable bilingual export: include both source and target text in the output file.", examples=[True, False]),
        bilingual_order: Optional[str] = FastApiQuery(None, description="Bilingual paragraph order: 'target_after_source' (default) or 'target_before_source'.", examples=["target_after_source", "target_before_source"]),
        source_text_italic: Optional[bool] = FastApiQuery(None, description="Render source text in italic for bilingual export.", examples=[True, False]),
        source_text_color: Optional[str] = FastApiQuery(None, description="Source text color for bilingual export: 'gray', 'blue', 'red', 'green', 'orange', 'black'.", examples=["gray", "blue", "red"]),
        target_text_italic: Optional[bool] = FastApiQuery(None, description="Render target text in italic for bilingual export.", examples=[True, False]),
        target_text_color: Optional[str] = FastApiQuery(None, description="Target text color for bilingual export: 'gray', 'blue', 'red', 'green', 'orange', 'black'.", examples=["gray", "blue", "red"]),
        renderer_type: Optional[str] = FastApiQuery(None, description="PDF renderer: 'typst_overlay' = preserve original layout (default when omitted); 'pandoc' = reflow from Markdown via Pandoc+XeLaTeX. PDF downloads only.", examples=["typst_overlay", "pandoc"]),
):
    """Download translation result files."""
    resp = await download_service.download_file(
        task_id=task_id,
        file_type=file_type,
        table_body_format=table_body_format,
        equation_format=equation_format,
        chart_body_format=chart_body_format,
        embed_images=embed_images,
        ebook_engine=ebook_engine,
        bilingual_export=bilingual_export,
        bilingual_order=bilingual_order,
        source_text_italic=source_text_italic,
        source_text_color=source_text_color,
        target_text_italic=target_text_italic,
        target_text_color=target_text_color,
        renderer_type=renderer_type,
    )
    try:
        if isinstance(resp, FileResponse):
            # Prevent browser caching — ensures bilingual toggle works correctly
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"

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


async def _read_response_bytes(response) -> Optional[bytes]:
    """Read bytes from a FileResponse or StreamingResponse."""
    from fastapi.responses import FileResponse as FR, StreamingResponse as SR
    if isinstance(response, FR):
        path = getattr(response, "path", None)
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                return f.read()
    elif isinstance(response, SR):
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return b"".join(chunks) if chunks else None
    return None


@router.post(
    "/batch-download",
    summary="Batch download translation results as ZIP",
    description="Download results from multiple completed tasks in a single ZIP file. "
                "For each task_id, the requested file_type is downloaded. Tasks that do not "
                "support the requested format are skipped and listed in _manifest.json.",
    responses={
        200: {
            "description": "ZIP file containing all successfully downloaded results + _manifest.json",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "No task_ids provided or all tasks failed."},
    },
)
async def service_batch_download_route(body: BatchDownloadRequest):
    """Download results from multiple tasks as a ZIP."""
    if not body.task_ids:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "task_ids list is empty"},
        )

    buf = io.BytesIO()
    manifest: Dict[str, Dict[str, str]] = {}
    entry_counts: Dict[str, int] = {}

    def _resolve_conflict(name: str) -> str:
        """Resolve ZIP entry name conflicts Windows-style: file (1).ext, file (2).ext"""
        if name not in entry_counts:
            entry_counts[name] = 1
            return name
        if "." in name:
            base, ext = name.rsplit(".", 1)
            while True:
                candidate = f"{base} ({entry_counts[name]}).{ext}"
                entry_counts[name] += 1
                if candidate not in entry_counts:
                    entry_counts[candidate] = 1
                    return candidate
        else:
            while True:
                candidate = f"{name} ({entry_counts[name]})"
                entry_counts[name] += 1
                if candidate not in entry_counts:
                    entry_counts[candidate] = 1
                    return candidate

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for task_id in body.task_ids:
            try:
                ts = task_manager.get_task(task_id)
                original_filename = ""
                relative_path = ""
                if ts:
                    original_filename = ts.get("original_filename") or ""
                    relative_path = ts.get("original_relative_path") or ""

                # Map md_zip → md with embed_images=False
                dl_file_type = body.file_type
                dl_embed_images: Optional[bool] = None
                if body.file_type == "md_zip":
                    dl_file_type = "md"
                    dl_embed_images = False

                resp = await download_service.download_file(
                    task_id=task_id,
                    file_type=dl_file_type,
                    embed_images=dl_embed_images,
                )
                file_bytes = await _read_response_bytes(resp)
                if file_bytes is None:
                    manifest[task_id] = {
                        "status": "skipped",
                        "reason": "Failed to read response bytes",
                    }
                    logger.warning(
                        LogModule.ROUTE,
                        f"[BATCH-DOWNLOAD] task_id={task_id}: no bytes returned for {body.file_type}",
                    )
                    continue

                # Determine folder/entry name inside ZIP
                ext = body.file_type
                if body.file_type == "md_zip":
                    ext = "zip"
                base_name = task_id
                if original_filename:
                    base_name = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
                is_conv = False
                if ts:
                    is_conv = bool(ts.get("is_format_conversion") or ts.get("convert_only"))
                suffix = "converted" if is_conv else "translated"

                # Build path prefix from relative directory
                path_prefix = f"{relative_path}/" if relative_path else ""

                if body.file_type == "md_zip":
                    # Flatten: extract inner ZIP and place contents under a folder
                    folder_name = f"{base_name}_{suffix}"
                    folder_prefix = f"{path_prefix}{folder_name}"
                    try:
                        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as inner_zf:
                            for inner_name in inner_zf.namelist():
                                inner_bytes = inner_zf.read(inner_name)
                                # Rename _translated → actual suffix inside the folder
                                renamed = inner_name.replace("_translated", f"_{suffix}")
                                inner_entry = f"{folder_prefix}/{renamed}"
                                inner_entry = _resolve_conflict(inner_entry)
                                zf.writestr(inner_entry, inner_bytes)
                        entry_name = f"{folder_prefix}/"
                        entry_name = _resolve_conflict(entry_name)
                    except Exception:
                        # Not a valid ZIP, fall back to single entry
                        entry_name = f"{path_prefix}{folder_name}.{ext}"
                        entry_name = _resolve_conflict(entry_name)
                        zf.writestr(entry_name, file_bytes)
                else:
                    entry_name = f"{path_prefix}{base_name}_{suffix}.{ext}"
                    entry_name = _resolve_conflict(entry_name)
                    zf.writestr(entry_name, file_bytes)
                manifest[task_id] = {"status": "success", "file": entry_name}
                logger.info(
                    LogModule.ROUTE,
                    f"[BATCH-DOWNLOAD] task_id={task_id}: added {entry_name}",
                )
            except Exception as e:
                manifest[task_id] = {
                    "status": "skipped",
                    "reason": str(e),
                }
                logger.warning(
                    LogModule.ROUTE,
                    f"[BATCH-DOWNLOAD] task_id={task_id}: skipped ({e})",
                )

        # Write manifest
        zf.writestr("_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    buf.seek(0)
    content = buf.getvalue()

    if not content or all(
        v.get("status") != "success" for v in manifest.values()
    ):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "All tasks failed or were skipped", "manifest": manifest},
        )

    return StreamingResponse(
        iter([content]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=batch_download_{body.file_type}.zip"},
    )


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

