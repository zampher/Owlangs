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
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from backend.app.services.download import DownloadService
from backend.app.services.download.output_generator import get_ebook_converters_availability
from backend.app.services.task import task_manager
from backend.app.services.translation.translation_result_stash import load_meta
from logger import unified_logger as logger
from logger.logger import LogModule
from utils.http_content_disposition import (
    apply_content_disposition_header,
    bytes_download_response,
)
from utils.batch_download_zip import (
    add_md_zip_download_to_batch_archive,
    make_batch_folder_name,
    strip_legacy_output_suffix,
)
from utils.output_suffix import get_output_suffix

router = APIRouter()

# Initialize service instance
download_service = DownloadService(task_manager)

_PREVIEW_INLINE_FILE_TYPES = frozenset({"html", "source-html", "md"})


def _apply_inline_preview_headers(
    resp: FileResponse,
    file_type: str,
    preview: bool,
) -> None:
    """Serve HTML/MD inline for iframe compare preview instead of attachment download."""
    if not preview or file_type not in _PREVIEW_INLINE_FILE_TYPES:
        return
    filename = getattr(resp, "filename", None) or "preview.html"
    apply_content_disposition_header(resp, filename, disposition="inline")


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
        source_text_font_size_delta: Optional[float] = FastApiQuery(None, description="Font size delta in points for source text in bilingual export (e.g., -1, 0, 2).", examples=[-1.0, 0.0, 1.5]),
        target_text_font_size_delta: Optional[float] = FastApiQuery(None, description="Font size delta in points for target text in all exports (e.g., -1, 0, 2).", examples=[-1.0, 0.0, 1.5]),
        cover_color_mode: Optional[str] = FastApiQuery(None, description="Image overlay erase fill: 'max' (brightest strip pixel), 'min' (darkest), or 'avg' (mean).", examples=["max", "min", "avg"]),
        renderer_type: Optional[str] = FastApiQuery(None, description="PDF renderer: 'typst_overlay' = preserve original layout (default when omitted); 'pandoc' = reflow from Markdown via Pandoc+XeLaTeX. PDF downloads only.", examples=["typst_overlay", "pandoc"]),
        preview: Optional[bool] = FastApiQuery(None, description="When true, serve HTML/MD with Content-Disposition inline for iframe preview.", examples=[True]),
        dirty_segments: Optional[str] = FastApiQuery(None, description="Comma-separated segment indices for incremental PDF preview refresh (PDF revision).", examples=["12,13"]),
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
        source_text_font_size_delta=source_text_font_size_delta,
        target_text_font_size_delta=target_text_font_size_delta,
        cover_color_mode=cover_color_mode,
        renderer_type=renderer_type,
        dirty_segments=dirty_segments,
    )
    try:
        if isinstance(resp, (FileResponse, Response)):
            # Prevent browser caching — ensures bilingual toggle works correctly
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            if preview and isinstance(resp, FileResponse):
                _apply_inline_preview_headers(resp, file_type, True)

            path = getattr(resp, "path", None) or getattr(resp, "owlangs_stash_path", None)
            ts = task_manager.get_task(task_id)
            if path and ts:
                from backend.app.services.translation.translation_result_stash import (
                    record_generated_result,
                )
                from backend.app.services.download.download_service import (
                    _pdf_stash_key_for_download,
                )

                stash_key = (
                    _pdf_stash_key_for_download(renderer_type)
                    if file_type == "pdf"
                    else file_type
                )
                record_generated_result(task_id, stash_key, path, ts)
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
    zip_dir_records: set[str] = set()

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
                meta = load_meta(task_id) if not ts else None
                ctx = ts or meta or {}
                original_filename = ctx.get("original_filename") or ""
                relative_path = ctx.get("original_relative_path") or ""

                # Map md_zip → md with embed_images=False; pdf_reflow → pdf with pandoc renderer
                dl_file_type = body.file_type
                dl_embed_images: Optional[bool] = None
                dl_renderer_type: Optional[str] = None
                if body.file_type == "md_zip":
                    dl_file_type = "md"
                    dl_embed_images = False
                elif body.file_type == "pdf_reflow":
                    dl_file_type = "pdf"
                    dl_renderer_type = "pandoc"

                resp = await download_service.download_file(
                    task_id=task_id,
                    file_type=dl_file_type,
                    embed_images=dl_embed_images,
                    renderer_type=dl_renderer_type,
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
                elif body.file_type == "pdf_reflow":
                    ext = "pdf"
                base_name = task_id
                if original_filename:
                    stem = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
                    base_name = strip_legacy_output_suffix(stem)
                suffix = get_output_suffix(ctx)
                logger.debug(
                    LogModule.ROUTE,
                    f"[BATCH-DOWNLOAD] task_id={task_id}: output_suffix={suffix!r}, base_name={base_name!r}",
                )

                # Build path prefix from relative directory
                path_prefix = f"{relative_path}/" if relative_path else ""

                if body.file_type == "md_zip":
                    folder_name = make_batch_folder_name(base_name, task_id, suffix)
                    folder_prefix = f"{path_prefix}{folder_name}"
                    try:
                        entry_name = add_md_zip_download_to_batch_archive(
                            zf,
                            file_bytes,
                            folder_prefix,
                            base_name,
                            suffix,
                            _resolve_conflict,
                            written_dirs=zip_dir_records,
                        )
                    except Exception as flatten_err:
                        logger.warning(
                            LogModule.ROUTE,
                            f"[BATCH-DOWNLOAD] task_id={task_id}: md_zip flatten failed: {flatten_err}",
                        )
                        entry_name = f"{path_prefix}{folder_name}.zip"
                        entry_name = _resolve_conflict(entry_name)
                        zf.writestr(entry_name, file_bytes)
                else:
                    entry_name = f"{path_prefix}{base_name}{suffix}.{ext}"
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

    return bytes_download_response(
        content,
        filename=f"batch_download_{body.file_type}.zip",
        media_type="application/zip",
        headers={"Content-Length": str(len(content))},
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

