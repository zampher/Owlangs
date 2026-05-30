# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Download Service

Handles file download and generation for translation results.
"""

import os
import io
import base64
import mimetypes
import asyncio
import tempfile
import zipfile
import re
import shutil
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from logger import unified_logger as logger
from logger.logger import LogModule
from app.services.task import TaskManager

# Relative import avoids circular import via app.services.download.__init__
from .pdf_generator import ENABLE_LAYOUT_PDF_GENERATION, PDFGenerator

# Media type mapping for different file types
MEDIA_TYPES = {
    "html": "text/html; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",  # Backward compatibility
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "arb": "application/json",  # ARB is JSON-based
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "srt": "text/plain; charset=utf-8",
    "epub": "application/epub+zip",
    "mobi": "application/x-mobipocket-ebook",
    "ts": "application/xml; charset=utf-8",  # Qt translation source file
    "zip": "application/zip",
    "pdf": "application/pdf",
}


def _get_to_lang_and_docx_font(task_state: Dict[str, Any], payload: Any = None) -> tuple:
    """Resolve target language and DOCX font name from task_state and optional payload. Returns (to_lang, docx_font_name)."""
    payload_obj = payload if payload is not None else task_state.get("payload")
    to_lang = (
        (payload_obj.get("to_lang") or payload_obj.get("target_language"))
        if isinstance(payload_obj, dict)
        else (getattr(payload_obj, "to_lang", None) or getattr(payload_obj, "target_language", None))
        if payload_obj
        else None
    )
    if not to_lang:
        to_lang = task_state.get("to_lang") or task_state.get("target_language")
    try:
        from translator.ai_translator.docx_translator import get_font_for_language
        docx_font_name = get_font_for_language(to_lang) if to_lang else "Calibri"
    except Exception:
        docx_font_name = "Calibri"
    return (to_lang, docx_font_name)


def _get_image_layout_for_grouping(
    task_state: Dict[str, Any],
    equation_format: Optional[str] = None,
    table_body_format: Optional[str] = None,
) -> tuple:
    """
    Get (image_block_indices, path_to_block_index, layout_document) from task_state for layout-based
    side-by-side image grouping. When layout is present, only images on the same
    row (bbox y overlap) will be grouped.
    equation_format and table_body_format should match the current export so the returned list
    order matches the actual image refs in the rebuilt markdown (e.g. exclude equation blocks when equation_format=text).
    Returns (list of block indices in image order, dict mapping normalized image path to block index, layout_doc or None).
    """
    from utils.format_convert_utils import get_image_block_indices_from_layout
    segs_data = task_state.get("translation_segments")
    seg_list = segs_data.get("segments", []) if isinstance(segs_data, dict) else (segs_data if isinstance(segs_data, list) else [])
    layout_doc = task_state.get("layout_document")
    eq_fmt = equation_format if equation_format is not None else (task_state.get("equation_format") if task_state else None)
    tbl_fmt = table_body_format if table_body_format is not None else (task_state.get("table_body_format") if task_state else None)
    logger.debug(
        LogModule.EXPORT,
        f"[DOWNLOAD] Layout for image grouping: segs_data_type={type(segs_data).__name__ if segs_data else None}, "
        f"seg_list_len={len(seg_list) if seg_list else 0}, layout_doc={layout_doc is not None}"
    )
    if not layout_doc or not seg_list:
        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] No layout/segments for image grouping, returning (None, None, None)")
        return (None, None, None)
    indices, path_to_block_index = get_image_block_indices_from_layout(
        seg_list, layout_doc,
        equation_format=eq_fmt,
        table_body_format=tbl_fmt,
    )
    logger.info(LogModule.EXPORT, f"[DOWNLOAD] image_block_indices from layout: len={len(indices) if indices else 0}, indices={indices[:20] if indices and len(indices) <= 20 else (indices[:20] if indices else [])}, path_mappings={len(path_to_block_index) if path_to_block_index else 0}")
    return (indices if indices else None, path_to_block_index if path_to_block_index else None, layout_doc)


def _image_data_map_from_task_state(task_state: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    image_data_map: Dict[str, Dict[str, str]] = {}
    existing_image_map = task_state.get("image_data_map")
    if isinstance(existing_image_map, dict):
        image_data_map.update({
            str(k): {
                "data": (v or {}).get("data", ""),
                "alt": (v or {}).get("alt", ""),
            }
            for k, v in existing_image_map.items()
        })
    return image_data_map


def _merge_image_data_maps(
    base: Dict[str, Dict[str, str]],
    override: Optional[Dict[str, Dict[str, str]]],
) -> Dict[str, Dict[str, str]]:
    if not override:
        return base
    merged = dict(base)
    merged.update(override)
    return merged


def _populate_image_data_map_from_extracted(
    image_data_map: Dict[str, Dict[str, str]],
    images_bytes_map: Dict[str, bytes],
) -> None:
    """Register every layout ZIP image under filename and common path key variants."""
    for img_path, img_bytes in (images_bytes_map or {}).items():
        if not img_bytes:
            continue
        norm_path = str(img_path).replace("\\", "/")
        mime = mimetypes.guess_type(norm_path)[0] or "image/png"
        data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
        filename = norm_path.split("/")[-1]
        entry = {"data": data_uri, "alt": filename}
        keys = {
            filename,
            norm_path,
            norm_path.lstrip("./"),
            f"./{norm_path.lstrip('./')}",
            f"images/{filename}",
            f"./images/{filename}",
        }
        for key in keys:
            if key and key not in image_data_map:
                image_data_map[key] = dict(entry)


def _resolve_export_format_settings(
    task_state: Dict[str, Any],
    payload: Any = None,
    equation_format: Optional[str] = None,
    table_body_format: Optional[str] = None,
) -> tuple:
    """Return normalized (equation_format, table_body_format) for export."""
    payload_obj = payload if payload is not None else task_state.get("payload")
    eq = equation_format if equation_format is not None else task_state.get("equation_format")
    tbl = table_body_format if table_body_format is not None else task_state.get("table_body_format")
    if payload_obj:
        if isinstance(payload_obj, dict):
            if eq is None:
                eq = payload_obj.get("equation_format")
            if tbl is None:
                tbl = payload_obj.get("table_body_format")
        else:
            if eq is None:
                eq = getattr(payload_obj, "equation_format", None)
            if tbl is None:
                tbl = getattr(payload_obj, "table_body_format", None)
    # PDF flow: default to image for tables, latex for equations
    orig_filename = (task_state.get("original_filename") or "").lower()
    is_pdf_flow = orig_filename.endswith(".pdf")
    default_eq = "latex" if is_pdf_flow else "text"
    default_tbl = "image" if is_pdf_flow else "html"

    eq = (eq or default_eq).lower().strip()
    tbl = (tbl or default_tbl).lower().strip()
    if eq not in ("text", "latex", "image"):
        eq = default_eq
    if tbl not in ("html", "image"):
        tbl = default_tbl
    return eq, tbl


def _format_requires_md2docx(equation_format: str, table_body_format: str) -> bool:
    return equation_format == "image" or table_body_format == "image"


def _build_image_data_map_for_format_export(
    task_state: Dict[str, Any],
    md_content: str,
    equation_format: str,
    table_body_format: str,
) -> Dict[str, Dict[str, str]]:
    """Build image_data_map for equation/table image export from layout ZIP and task cache."""
    image_data_map = _image_data_map_from_task_state(task_state)
    layout_doc = task_state.get("layout_document")
    orig_l = (task_state.get("original_filename") or "").lower()
    if not _format_requires_md2docx(equation_format, table_body_format):
        return image_data_map
    if not orig_l.endswith(".pdf") or layout_doc is None:
        return image_data_map
    zip_bytes = task_state.get("layout_source_zip")
    if not zip_bytes:
        return image_data_map
    zip_file = None
    try:
        from layout.pdf_renderer.shared.block_processor import BlockProcessor

        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        images_bytes_map = BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
        _populate_image_data_map_from_extracted(image_data_map, images_bytes_map)
        logger.info(
            LogModule.EXPORT,
            f"[DOWNLOAD] Built image_data_map with {len(image_data_map)} entries from layout_source_zip "
            f"(equation_format={equation_format}, table_body_format={table_body_format})",
        )
    except Exception as e:
        logger.warning(
            LogModule.EXPORT,
            f"[DOWNLOAD] Failed to extract images from layout_source_zip for format export: {e}",
            exc_info=True,
        )
    finally:
        if zip_file:
            try:
                zip_file.close()
            except Exception:
                pass
    return image_data_map


def _export_md_content_to_docx_bytes(
    task_state: Dict[str, Any],
    md_content: str,
    equation_format: str,
    table_body_format: str,
    payload: Any = None,
    file_stem: Optional[str] = None,
) -> bytes:
    """
    Export rebuilt markdown to DOCX via MD2DOCXExporter (supports equation/table as images).
    Used by download_file and output_generator when format requires embedded images.
    """
    from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig
    from exporter.md.md2html_exporter import MD2HTMLExporterConfig
    from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
    from translator.ai_translator.md_translator import MDTranslatorConfig
    from ir.markdown_document import MarkdownDocument
    from utils.document_rebuild import _replace_placeholders_with_images

    layout_doc = task_state.get("layout_document")
    orig_l = (task_state.get("original_filename") or "").lower()
    is_pdf_file = orig_l.endswith(".pdf")
    file_stem = file_stem or task_state.get("original_filename_stem", "translated")

    image_data_map = _build_image_data_map_for_format_export(
        task_state, md_content, equation_format, table_body_format
    )
    if image_data_map:
        task_state["image_data_map"] = image_data_map

    to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload)
    _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
        task_state, equation_format=equation_format, table_body_format=table_body_format
    )
    html_config = MD2HTMLExporterConfig(
        preserve_line_breaks=is_pdf_file,
        layout_block_bbox=task_state.get("layout_block_bbox"),
        image_block_indices=_img_bidx,
        layout_document=_layout if _img_bidx else None,
    )
    _docx_debug_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
    docx_config = MD2DOCXExporterConfig(
        table_body_format=table_body_format,
        equation_format=equation_format,
        image_data_map=image_data_map,
        font_name=docx_font_name,
        debug_output_dir=_docx_debug_dir,
    )
    if is_pdf_file and layout_doc is not None:
        try:
            from layout.base import LayoutDocument as _LD

            if isinstance(layout_doc, _LD):
                docx_config = MD2DOCXExporterConfig(
                    layout_document=layout_doc,
                    table_body_format=table_body_format,
                    equation_format=equation_format,
                    image_data_map=image_data_map,
                    font_name=docx_font_name,
                    debug_output_dir=_docx_debug_dir,
                )
        except Exception:
            pass

    translator_config = MDTranslatorConfig(skip_translate=True)
    workflow_config = MarkdownBasedWorkflowConfig(
        convert_engine="identity",
        converter_config=None,
        translator_config=translator_config,
        html_exporter_config=html_config,
        docx_exporter_config=docx_config,
    )
    workflow = MarkdownBasedWorkflow(workflow_config)

    _docx_output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
    _docx_output_dir.mkdir(parents=True, exist_ok=True)
    md_for_docx, _ = _replace_placeholders_with_images(
        md_content, image_data_map, output_dir=_docx_output_dir, update_image_data_map=True
    )
    import re as _re

    _img_refs = _re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", md_for_docx)
    _filled = 0
    for _alt, _ref in _img_refs:
        if _ref in image_data_map or _ref.startswith("data:"):
            continue
        _norm = _ref.replace("\\", "/").lstrip("./")
        _path = _docx_output_dir / _norm
        if not _path.is_file():
            _path = _docx_output_dir / "images" / (_norm.split("/")[-1])
        if _path.is_file():
            try:
                _raw = _path.read_bytes()
                _mime_type = mimetypes.guess_type(str(_path))[0] or "image/png"
                _data_uri = f"data:{_mime_type};base64,{base64.b64encode(_raw).decode('ascii')}"
                image_data_map[_ref] = {"data": _data_uri, "alt": _alt or _path.name}
                _filled += 1
            except Exception as _e:
                logger.debug(LogModule.EXPORT, f"[DOWNLOAD] DOCX image fallback read failed: {_path}: {_e}")
    if _filled:
        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Filled {_filled} image refs from output dir for DOCX export")

    workflow.document_translated = MarkdownDocument.from_bytes(
        content=md_for_docx.encode("utf-8"),
        suffix=".md",
        stem=file_stem,
    )
    return workflow.export_to_docx(config=docx_config)


def _docx_stash_download_kwargs(task_state: Dict[str, Any]) -> Dict[str, Any]:
    """kwargs for download_file when persisting DOCX with image format settings."""
    wt = resolve_task_export_workflow_type(task_state)
    orig_l = (task_state.get("original_filename") or "").lower()
    if wt != "markdown_based" or not orig_l.endswith(".pdf"):
        return {}
    eq, tbl = _resolve_export_format_settings(task_state)
    if not _format_requires_md2docx(eq, tbl):
        return {}
    return {"equation_format": eq, "table_body_format": tbl}


def _rebuild_html_from_task_state(task_state: Dict[str, Any]) -> Optional[str]:
    """
    Rebuild translated HTML for html workflow using updated html_translated_texts.
    Returns the rebuilt HTML string, or None if rebuild is not possible.
    """
    html_original_texts = task_state.get("html_original_texts")
    html_translated_texts = task_state.get("html_translated_texts")
    if not html_original_texts or not html_translated_texts:
        return None

    # Get original HTML content from workflow_instance.document_original
    workflow_instance = task_state.get("workflow_instance")
    if not workflow_instance or not hasattr(workflow_instance, "document_original"):
        return None
    doc_original = workflow_instance.document_original
    if not doc_original or not doc_original.content:
        return None

    try:
        html_content = (
            doc_original.content.decode("utf-8")
            if isinstance(doc_original.content, bytes)
            else str(doc_original.content)
        )
        from workflow.html_to_markdown_export import rebuild_html_with_translations

        rebuilt_html = rebuild_html_with_translations(
            html_content, html_original_texts, html_translated_texts
        )
        return rebuilt_html
    except Exception as e:
        logger.warning(
            LogModule.EXPORT,
            f"[DOWNLOAD] Failed to rebuild HTML from task_state: {e}",
            exc_info=True,
        )
        return None


def _file_response_for_md_download(
    md_content: str,
    task_state: Dict[str, Any],
    file_stem: str,
    embed_images: Optional[bool],
    equation_format: Optional[str],
    table_body_format: Optional[str],
    *,
    image_data_map_override: Optional[Dict[str, Dict[str, str]]] = None,
) -> FileResponse:
    """
    Single .md (data-URI images) or ZIP (.md + image files) when embed_images is False (md_zip URLs).

    Mirrors markdown_based branch so MOBI/TXT/EPUB/... segment rebuild paths do not return plain text as ZIP.
    """
    from utils.document_rebuild import _replace_placeholders_with_images
    from utils.format_convert_utils import group_consecutive_images_for_markdown

    should_embed = embed_images if embed_images is not None else True
    image_data_map = _merge_image_data_maps(
        _image_data_map_from_task_state(task_state),
        image_data_map_override,
    )

    if should_embed:
        md_out = md_content
        if image_data_map:
            md_out, _ = _replace_placeholders_with_images(md_content, image_data_map, output_dir=None)
            _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                task_state, equation_format=equation_format, table_body_format=table_body_format
            )
            md_out = group_consecutive_images_for_markdown(
                md_out,
                image_block_indices=_img_bidx,
                layout_document=_layout if _img_bidx else None,
                layout_block_bbox=task_state.get("layout_block_bbox"),
            )
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        temp_file.write(md_out)
        temp_file.close()
        filename = f"{file_stem}_translated.md"
        media_type = MEDIA_TYPES.get("md", "text/markdown; charset=utf-8")
        logger.info(
            LogModule.EXPORT,
            f"[DOWNLOAD] MD response: embedded single file, len={len(md_out)}",
        )
        return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)

    zip_temp_dir = None
    temp_dir = task_state.get("temp_dir")
    if temp_dir and os.path.isdir(temp_dir):
        zip_temp_dir = os.path.join(temp_dir, "downloads")
        os.makedirs(zip_temp_dir, exist_ok=True)
    if not zip_temp_dir:
        zip_temp_dir = tempfile.mkdtemp()

    try:
        zip_output_dir = Path(zip_temp_dir)
        md_with_image_paths, saved_image_paths = _replace_placeholders_with_images(
            md_content, image_data_map, output_dir=zip_output_dir
        )
        # Download online images for workflows that use external URLs (e.g., HTML workflow)
        md_with_image_paths, online_paths = _download_online_images_for_markdown(
            md_with_image_paths, zip_output_dir
        )
        saved_image_paths.extend(online_paths)
        _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
            task_state, equation_format=equation_format, table_body_format=table_body_format
        )
        md_with_image_paths = group_consecutive_images_for_markdown(
            md_with_image_paths,
            image_block_indices=_img_bidx,
            layout_document=_layout if _img_bidx else None,
            layout_block_bbox=task_state.get("layout_block_bbox"),
        )
        md_file_in_zip = zip_output_dir / f"{file_stem}_translated.md"
        md_file_in_zip.write_text(md_with_image_paths, encoding="utf-8")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(str(md_file_in_zip), arcname=f"{file_stem}_translated.md")
            for img_path in saved_image_paths:
                if img_path.exists():
                    arc = img_path.relative_to(zip_output_dir)
                    zip_file.write(str(img_path), arcname=str(arc).replace("\\", "/"))

        zip_buffer.seek(0)
        zip_temp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".zip", delete=False)
        zip_temp_file.write(zip_buffer.getvalue())
        zip_temp_file.close()

        filename = f"{file_stem}_translated_with_images.zip"
        media_type = "application/zip"
        logger.info(
            LogModule.EXPORT,
            f"[DOWNLOAD] MD response: ZIP (embed_images=false), md_len={len(md_with_image_paths)}, image_files={len(saved_image_paths)}",
        )
        return FileResponse(path=zip_temp_file.name, media_type=media_type, filename=filename)
    finally:
        shutil.rmtree(zip_temp_dir, ignore_errors=True)


def _download_online_images_for_markdown(
    markdown_content: str,
    output_dir: Path,
) -> Tuple[str, List[Path]]:
    """
    Download online images referenced in Markdown ![alt](url) and replace URLs with relative paths.
    Only processes http/https URLs. Skips on failure, keeping original URL.
    """
    if not markdown_content:
        return markdown_content, []

    import hashlib
    from urllib.request import urlopen, Request

    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)\)')
    saved_paths: List[Path] = []
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    downloaded_urls: dict[str, Path] = {}

    def _replace(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2).strip()

        # Only process online URLs
        if not url.startswith(('http://', 'https://')):
            return match.group(0)

        # Skip if already downloaded
        if url in downloaded_urls:
            saved_path = downloaded_urls[url]
            rel_path = saved_path.relative_to(output_dir).as_posix()
            return f'![{alt}]({rel_path})'

        try:
            req = Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
            )
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
                content_type = resp.headers.get('Content-Type', '')

                # Determine extension from Content-Type or URL
                ext = ''
                if content_type:
                    ext = mimetypes.guess_extension(content_type.split(';')[0].strip()) or ''
                if not ext:
                    url_path = url.split('?')[0].split('#')[0]
                    ext = mimetypes.guess_extension(url_path) or ''
                if not ext:
                    ext = '.jpg'

                url_hash = hashlib.sha1(url.encode()).hexdigest()[:12]
                filename = f"img_{url_hash}{ext}"
                file_path = images_dir / filename

                # Handle duplicate filenames
                counter = 1
                original_path = file_path
                while file_path.exists():
                    file_path = images_dir / f"{original_path.stem}_{counter}{ext}"
                    counter += 1

                file_path.write_bytes(data)
                downloaded_urls[url] = file_path
                saved_paths.append(file_path)

                rel_path = file_path.relative_to(output_dir).as_posix()
                logger.info(
                    LogModule.EXPORT,
                    f"[DOWNLOAD] Downloaded online image: {url} -> {rel_path}",
                )
                return f'![{alt}]({rel_path})'

        except Exception as e:
            logger.warning(
                LogModule.EXPORT,
                f"[DOWNLOAD] Failed to download online image {url}: {e}",
            )
            return match.group(0)

    new_content = img_pattern.sub(_replace, markdown_content)
    return new_content, saved_paths


def _infer_workflow_from_filename(original_filename_lower: str) -> Optional[str]:
    """Map file extension to translation workflow_type (see app.models.service payload union)."""
    if not original_filename_lower or "." not in original_filename_lower:
        return None
    ext = original_filename_lower.rsplit(".", 1)[-1].lower()
    return {
        "md": "markdown_based",
        "txt": "txt",
        "docx": "docx",
        "doc": "docx",
        "html": "html",
        "htm": "html",
        "json": "json",
        "xlsx": "xlsx",
        "xls": "xlsx",
        "pptx": "pptx",
        "ppt": "pptx",
        "srt": "srt",
        "epub": "epub",
        "mobi": "mobi",
        "pdf": "markdown_based",
        "ts": "qt_ts",
    }.get(ext)


def resolve_task_export_workflow_type(task_state: Dict[str, Any]) -> Optional[str]:
    """
    Workflow used for export palette / stash (segments metadata, then filename extension).
    """
    orig_l = (task_state.get("original_filename") or "").lower()
    segs = task_state.get("translation_segments") or {}
    meta = segs.get("metadata", {}) if isinstance(segs, dict) else {}
    wt: Optional[str] = meta.get("workflow_type") if isinstance(meta, dict) else None
    if not wt:
        wt = _infer_workflow_from_filename(orig_l)
    if not wt and orig_l.endswith(".pdf"):
        wt = "markdown_based"
    return wt


def _build_stash_export_plan(task_state: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """
    Build (stash_key, download_file_type, kwargs for download_file).

    Must stay aligned with ``completed_task_download_urls`` / GET /service/status so the
    translation queue lists every format the download route can serve on-demand.
    """
    orig_l = (task_state.get("original_filename") or "").lower()
    is_pdf = orig_l.endswith(".pdf")
    has_layout = task_state.get("layout_document") is not None
    is_fmt_conv = bool(task_state.get("is_format_conversion") or task_state.get("convert_only"))
    wt = resolve_task_export_workflow_type(task_state)

    plan: List[Tuple[str, str, Dict[str, Any]]] = []
    docx_kwargs = _docx_stash_download_kwargs(task_state)
    if wt == "markdown_based":
        allow_pdf = is_pdf and has_layout and not is_fmt_conv
        for ft in ("docx", "html", "md"):
            plan.append((ft, ft, docx_kwargs if ft == "docx" else {}))
        if allow_pdf:
            plan.append(("pdf", "pdf", {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "txt":
        for ft in ("html", "txt", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt in ("docx", "html"):
        # Same on-demand surface as markdown_based minus PDF branch (non-PDF sources).
        for ft in ("docx", "html", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "json":
        for ft in ("json", "html"):
            plan.append((ft, ft, {}))
    elif wt == "xlsx":
        plan.append(("xlsx", "xlsx", {}))
        for ft in ("html", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "pptx":
        for ft in ("pptx", "html", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "srt":
        plan.append(("srt", "srt", {}))
    elif wt == "epub":
        for ft in ("epub", "html", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "mobi":
        plan.append(("mobi", "mobi", {}))
        plan.append(("epub", "epub", {}))
        for ft in ("html", "md"):
            plan.append((ft, ft, {}))
        plan.append(("md_zip", "md", {"embed_images": False}))
    elif wt == "qt_ts":
        plan.append(("ts", "ts", {}))
    else:
        df = task_state.get("downloadable_files") or {}
        if isinstance(df, dict):
            for k in df.keys():
                if isinstance(k, str) and k:
                    plan.append((k, k, {}))
    return plan


def completed_task_download_urls(task_id: str, task_state: Dict[str, Any]) -> Dict[str, str]:
    """Relative /service/download URLs for every export in the stash plan (queue + status UI)."""
    out: Dict[str, str] = {}
    for stash_key, download_ft, kwargs in _build_stash_export_plan(task_state):
        base = f"/service/download/{task_id}/{download_ft}"
        if kwargs:
            flat: Dict[str, Any] = {}
            for k, v in kwargs.items():
                if isinstance(v, bool):
                    flat[k] = "true" if v else "false"
                elif v is not None:
                    flat[k] = v
            out[stash_key] = f"{base}?{urlencode(flat)}"
        else:
            out[stash_key] = base
    return out


def _pandoc_pdf_file_response_from_md(
    task_state: Dict[str, Any],
    task_id: str,
    md_content: str,
    equation_format: Optional[str],
    table_body_format: Optional[str],
) -> FileResponse:
    """
    Export Markdown to PDF via Pandoc + XeLaTeX (same pipeline as OutputGenerator).
    Shared by revision-download and stash-less rebuild paths.
    """
    if not md_content or not str(md_content).strip():
        raise HTTPException(
            status_code=500,
            detail="Markdown content is empty; cannot export PDF.",
        )
    output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
    output_dir.mkdir(exist_ok=True)
    file_stem = task_state.get("original_filename_stem", "translated")
    pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
    to_lang, _ = _get_to_lang_and_docx_font(task_state)
    if not to_lang:
        to_lang = "zh"
    image_data_map = task_state.get("image_data_map") or {}
    if image_data_map:
        from utils.image_placeholder_utils import _replace_placeholders_with_images

        resolved_md, _ = _replace_placeholders_with_images(md_content, image_data_map, output_dir=output_dir)
    else:
        resolved_md = md_content
    try:
        from utils.format_convert_utils import PdfExportLatexError, convert_md_to_pdf

        _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
            task_state, equation_format=equation_format, table_body_format=table_body_format
        )
        try:
            ok = convert_md_to_pdf(
                resolved_md,
                str(pdf_file_path),
                output_dir=output_dir,
                to_lang=to_lang,
                image_block_indices=_img_bidx,
                path_to_block_index=_path_to_bidx,
                layout_document=_layout if _path_to_bidx else None,
                layout_block_bbox=task_state.get("layout_block_bbox"),
            )
        except Exception as e:
            if isinstance(e, PdfExportLatexError):
                segs = (task_state.get("translation_segments") or {}).get("segments") or []
                segment_index = None
                candidates: list[int] = []
                match_basis = "unknown"

                def _best_effort_find_segment_index() -> None:
                    nonlocal segment_index, match_basis
                    if not isinstance(segs, list) or not segs:
                        return
                    md_snippet = (e.md_snippet or "").strip()
                    if md_snippet:
                        match_basis = "md_snippet"
                        lines = [ln.strip() for ln in md_snippet.splitlines() if len((ln or "").strip()) >= 16]
                        for seg in segs:
                            t = (seg or {}).get("target_text", "")
                            if not t:
                                continue
                            for ln in lines[:10]:
                                if ln and ln in t:
                                    segment_index = (seg or {}).get("segment_index")
                                    return
                    token = (getattr(e, "error_token", "") or "").strip()
                    if token:
                        match_basis = f"error_token:{token}"
                        for seg in segs:
                            t = (seg or {}).get("target_text", "")
                            if t and token in t:
                                segment_index = (seg or {}).get("segment_index")
                                return

                _best_effort_find_segment_index()
                if isinstance(segment_index, int) and segment_index >= 0:
                    candidates.append(segment_index)
                    for d in (1, 2, 3):
                        if segment_index - d >= 0:
                            candidates.append(segment_index - d)
                task_state["pdf_export_latex_issue"] = {
                    "error_type": e.error_type,
                    "line_no": e.line_no,
                    "segment_index": segment_index,
                    "candidate_segment_indices": candidates,
                    "match_basis": match_basis,
                    "error_token": getattr(e, "error_token", "") or "",
                    "md_snippet": e.md_snippet,
                    "tex_snippet": e.tex_snippet,
                    "stderr_excerpt": (e.stderr or "")[:2000],
                    "debug_tex_path": str(e.debug_tex_path) if e.debug_tex_path else None,
                    "debug_md_path": str(e.debug_md_path) if e.debug_md_path else None,
                }
                hint = f" Suspected bad segment: {segment_index}." if segment_index is not None else ""
                upstream = f" It may be caused by an earlier segment near: {candidates}." if candidates else ""
                raise HTTPException(
                    status_code=500,
                    detail="PDF generation failed due to a LaTeX compilation error."
                    + hint
                    + upstream
                    + " Please use the segment 'Fix formula' action and retry export. Check server logs for details.",
                )
            raise

        if ok and pdf_file_path.exists():
            logger.info(
                LogModule.EXPORT,
                f"[DOWNLOAD] PDF generated via pandoc (MD → XeLaTeX → PDF) task_id={task_id}",
            )
            filename = pdf_file_path.name
            media_type = MEDIA_TYPES.get("pdf", "application/pdf")
            return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
        raise HTTPException(
            status_code=500,
            detail="PDF generation via Pandoc failed (Pandoc/XeLaTeX may be missing or conversion error). Check server logs.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            LogModule.EXPORT,
            f"[DOWNLOAD] Pandoc PDF path failed: {e}",
            exc_info=True,
        )
        message = str(e) or "PDF generation via Pandoc failed (see server logs for details)."
        raise HTTPException(
            status_code=500,
            detail=message,
        )


def _markdown_based_html_file_response_from_segments(
    task_state: Dict[str, Any],
    task_id: str,
    equation_format: Optional[str],
    table_body_format: Optional[str],
) -> Optional[FileResponse]:
    """
    Build translated HTML via MarkdownBasedWorkflow + rebuilt segments (on-demand download).
    Used when no pre-generated HTML file exists (e.g. queue mode / DOCX-only cache).
    """
    from utils.document_rebuild import rebuild_markdown_document_from_segments
    from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig
    from exporter.md.md2html_exporter import MD2HTMLExporterConfig
    from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
    from translator.ai_translator.md_translator import MDTranslatorConfig

    rebuilt_doc = rebuild_markdown_document_from_segments(
        task_state,
        file_stem=task_state.get("original_filename_stem"),
        equation_format=equation_format,
        table_body_format=table_body_format,
    )
    if not rebuilt_doc or not getattr(rebuilt_doc, "content", None):
        return None
    payload_for_export = task_state.get("payload")
    to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload_for_export)
    _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
        task_state, equation_format=equation_format, table_body_format=table_body_format
    )
    original_filename = task_state.get("original_filename", "")
    is_pdf_source = original_filename.lower().endswith(".pdf")
    html_config = MD2HTMLExporterConfig(
        preserve_line_breaks=is_pdf_source,
        layout_block_bbox=task_state.get("layout_block_bbox"),
        image_block_indices=_img_bidx,
        layout_document=_layout if _img_bidx else None,
    )
    docx_config_kwargs: dict = {"font_name": docx_font_name}
    layout_doc = task_state.get("layout_document")
    if layout_doc is not None and is_pdf_source:
        try:
            from layout.base import LayoutDocument as _LD

            if isinstance(layout_doc, _LD):
                docx_config_kwargs["layout_document"] = layout_doc
        except Exception:
            pass
    if table_body_format:
        docx_config_kwargs["table_body_format"] = table_body_format
    if equation_format:
        docx_config_kwargs["equation_format"] = equation_format
    existing_img_map = task_state.get("image_data_map")
    if isinstance(existing_img_map, dict):
        docx_config_kwargs["image_data_map"] = existing_img_map
    docx_config_kwargs["debug_output_dir"] = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
    docx_config = MD2DOCXExporterConfig(**docx_config_kwargs)
    translator_config = MDTranslatorConfig(skip_translate=True)
    workflow_config = MarkdownBasedWorkflowConfig(
        convert_engine="identity",
        converter_config=None,
        translator_config=translator_config,
        html_exporter_config=html_config,
        docx_exporter_config=docx_config,
    )
    workflow = MarkdownBasedWorkflow(workflow_config)
    workflow.document_translated = rebuilt_doc
    html_content = workflow.export_to_html()
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
    temp_file.write(html_content)
    temp_file.close()
    file_stem = task_state.get("original_filename_stem", "translated")
    filename = f"{file_stem}_translated.html"
    media_type = MEDIA_TYPES.get("html", "text/html; charset=utf-8")
    logger.info(LogModule.EXPORT, f"[DOWNLOAD] HTML from segments on-demand task_id={task_id}")
    return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)


class DownloadService:
    """Service for handling file downloads."""
    
    def __init__(self, task_manager: TaskManager):
        """
        Initialize download service.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager
        self.pdf_generator = PDFGenerator(task_manager)
    
    async def download_file(
        self,
        task_id: str,
        file_type: str,
        table_body_format: Optional[str] = None,
        equation_format: Optional[str] = None,
        embed_images: Optional[bool] = None,
        ebook_engine: Optional[str] = None,
    ) -> FileResponse:
        """
        Download translation result file.

        Args:
            task_id: Task identifier
            file_type: File type to download
            table_body_format: Optional table format override
            equation_format: Optional equation format override
            embed_images: Optional flag for MD downloads
            ebook_engine: For epub/mobi: 'pandoc' or 'calibre' (optional; only used when both are available)

        Returns:
            FileResponse with file content

        Raises:
            HTTPException: If task not found or file cannot be generated
        """
        # Get task state from task manager
        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            from backend.app.services.translation.translation_result_stash import (
                get_stashed_file_path,
                load_meta,
            )

            stashed = get_stashed_file_path(task_id, file_type)
            if stashed and os.path.isfile(stashed):
                meta = load_meta(task_id)
                stem = Path((meta or {}).get("original_filename") or "translated").stem
                ext = Path(stashed).suffix or ""
                filename = f"{stem}_translated{ext}"
                media_type = MEDIA_TYPES.get(file_type, "application/octet-stream")
                logger.info(
                    LogModule.EXPORT,
                    f"[DOWNLOAD] Task {task_id}: Serving stashed {file_type} from disk (no in-memory task)",
                )
                return FileResponse(path=stashed, media_type=media_type, filename=filename)
            raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
        
        # Check if task has failed
        task_status = task_state.get("status")
        if task_status == "failed":
            error_message = task_state.get("error") or task_state.get("message") or "Task processing failed"
            raise HTTPException(
                status_code=400,
                detail=f"Task '{task_id}' has failed and cannot download files. Error: {error_message}"
            )

        payload = task_state.get("payload")

        # CRITICAL: If requested file is missing, generate only that format on-demand (no PDF when only HTML requested)
        downloadable_files = task_state.get("downloadable_files", {})
        need_generate = not downloadable_files or file_type not in downloadable_files
        if need_generate:
            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Requested file_type={file_type} not available, generating on-demand...")
            try:
                workflow = task_state.get("workflow_instance")
                payload = task_state.get("payload")
                temp_dir = task_state.get("temp_dir")
                original_filename = task_state.get("original_filename", "")

                if not workflow or not payload or not temp_dir:
                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Missing workflow/payload/temp_dir, cannot generate files on-demand")
                else:
                    from app.services.download.output_generator import OutputGenerator

                    output_dir = Path(temp_dir) / "output"
                    output_dir.mkdir(exist_ok=True)
                    file_stem = Path(original_filename).stem
                    is_format_conversion = task_state.get("is_format_conversion", False) or task_state.get("convert_only", False)

                    output_generator = OutputGenerator(self.task_manager)
                    await output_generator.generate_output_for_file_type(
                        task_id, file_type, workflow, payload, task_state, output_dir, file_stem, is_format_conversion,
                        ebook_engine=ebook_engine,
                    )
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Generated {file_type} on-demand successfully")
            except Exception as gen_error:
                logger.error(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Failed to generate on-demand: {gen_error}", exc_info=True)
                # Continue with download attempt - it may still work if file was generated by other means

        # Check if there are revised segments
        from utils.document_rebuild import (
            has_revised_segments,
            rebuild_markdown_document_from_segments,
            rebuild_docx_document_from_segments,
            convert_html_to_docx,
        )
        
        # Debug: Check translation_segments structure
        segments_data = task_state.get("translation_segments")
        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}, file_type={file_type}, segments_data exists: {segments_data is not None}")

        if segments_data:
            segments = segments_data.get("segments", [])
            modified_count = sum(1 for seg in segments if seg.get("modified", False))
            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}, total segments: {len(segments)}, modified segments: {modified_count}")
        
        # P0: Post-process title blocks to filter out false positives (body text that
        # MinerU misclassified as "title"). Only self-hosted MinerU (middle.json) provides
        # font size data in its layout.json — the Cloud API does not, so heading hierarchy
        # from font sizes is unavailable and all valid titles use H1 (default).
        _layout_doc = task_state.get("layout_document")
        if _layout_doc is not None:
            try:
                from layout.pdf_font_extractor import _is_likely_heading
                for page in _layout_doc.pages:
                    for block in page.blocks:
                        if block.type == "title" and not _is_likely_heading(block):
                            block.heading_level = 0  # false positive → body text
            except Exception as e:
                logger.debug(LogModule.EXPORT,
                    f"[DOWNLOAD] Task {task_id}: Failed to filter false-positive titles: {e}")

        # Store original has_revisions status before any fallback logic
        has_revisions_original = has_revised_segments(task_state)
        has_revisions = has_revisions_original
        workflow_type = None
        # CRITICAL: Handle backward compatibility - translation_segments might be a list (old format) or dict (new format)
        translation_segments = task_state.get("translation_segments")
        if isinstance(translation_segments, dict):
            segments_metadata = translation_segments.get("metadata", {})
        elif isinstance(translation_segments, list):
            # Old format - no metadata available
            segments_metadata = {}
        else:
            segments_metadata = {}
        if segments_metadata:
            workflow_type = segments_metadata.get("workflow_type")
        
        # CRITICAL: For DOCX workflow HTML downloads, always rebuild from segments to ensure latest edits are included
        # This is necessary because frontend edits may not set the modified flag, but we still need to use the latest segment data
        if workflow_type == "docx" and file_type == "html":
            logger.info(LogModule.EXPORT, f"[DOWNLOAD] DOCX workflow HTML download: forcing rebuild from segments to ensure latest edits (has_revisions={has_revisions})")
            has_revisions = True
        
        # Fallback: For format conversion tasks, workflow_type might not be in translation_segments
        # Try to get it from workflow_instance or task_state
        if not workflow_type:
            workflow_instance = task_state.get("workflow_instance")
            if workflow_instance:
                # Try to infer workflow_type from workflow instance type
                from workflow.md_based_workflow import MarkdownBasedWorkflow
                from workflow.docx_workflow import DocxWorkflow
                from workflow.html_workflow import HtmlWorkflow
                from workflow.txt_workflow import TXTWorkflow
                from workflow.json_workflow import JsonWorkflow
                from workflow.xlsx_workflow import XlsxWorkflow
                from workflow.pptx_workflow import PptxWorkflow
                from workflow.srt_workflow import SrtWorkflow
                from workflow.epub_workflow import EpubWorkflow
                from workflow.mobi_workflow import MobiWorkflow
                from workflow.qt_ts_workflow import QtTsWorkflow
                
                if isinstance(workflow_instance, MarkdownBasedWorkflow):
                    workflow_type = "markdown_based"
                elif isinstance(workflow_instance, DocxWorkflow):
                    workflow_type = "docx"
                elif isinstance(workflow_instance, HtmlWorkflow):
                    workflow_type = "html"
                elif isinstance(workflow_instance, TXTWorkflow):
                    workflow_type = "txt"
                elif isinstance(workflow_instance, JsonWorkflow):
                    workflow_type = "json"
                elif isinstance(workflow_instance, XlsxWorkflow):
                    workflow_type = "xlsx"
                elif isinstance(workflow_instance, PptxWorkflow):
                    workflow_type = "pptx"
                elif isinstance(workflow_instance, SrtWorkflow):
                    workflow_type = "srt"
                elif isinstance(workflow_instance, EpubWorkflow):
                    workflow_type = "epub"
                elif isinstance(workflow_instance, MobiWorkflow):
                    workflow_type = "mobi"
                elif isinstance(workflow_instance, QtTsWorkflow):
                    workflow_type = "qt_ts"
        
        # Keep this at DEBUG to avoid flooding logs; image-related logs below stay at INFO.
        logger.debug(
            LogModule.EXPORT,
            f"[DOWNLOAD] Task {task_id}, has_revisions: {has_revisions}, workflow_type: {workflow_type}",
        )
        
        # Prefer Pandoc-generated DOCX for markdown_based workflows.
        # For PDF/MD/image (markdown_based) flows, DOCX 导出优先使用 Pandoc 的 md->docx 结果，
        # 只有在未生成或文件缺失时才继续走后面的重建/回退逻辑。
        # When user requests equation_format or table_body_format (e.g. image), do not use cached DOCX; regenerate to respect format.
        if workflow_type == "markdown_based" and file_type == "docx":
            docx_info = task_state.get("downloadable_files", {}).get("docx")
            stored_eq, stored_tbl = _resolve_export_format_settings(
                task_state, payload, equation_format, table_body_format
            )
            needs_format_regen = bool(
                equation_format
                or table_body_format
                or _format_requires_md2docx(stored_eq, stored_tbl)
            )
            if needs_format_regen and docx_info:
                docx_info = None  # Force regeneration so format params are applied
            if docx_info:
                docx_path = (
                    docx_info.get("path", "")
                    if isinstance(docx_info, dict)
                    else str(docx_info)
                )
                if docx_path and os.path.exists(docx_path):
                    filename = os.path.basename(docx_path) or f"{task_state.get('original_filename_stem', 'translated')}.docx"
                    media_type = MEDIA_TYPES.get("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    logger.debug(
                        LogModule.EXPORT,
                        f"[DOWNLOAD] Using Pandoc-generated DOCX for markdown_based workflow (task {task_id}): {docx_path}",
                    )
                    return FileResponse(path=docx_path, media_type=media_type, filename=filename)
        
        # Check if this is a format conversion task
        is_format_conversion = task_state.get("is_format_conversion", False) or task_state.get("convert_only", False)
        
        # For format conversion tasks with format parameters, regenerate from layout_document
        # This allows users to choose table/equation formats before generating files
        # Also allow regeneration for any PDF file with format parameters (not just format conversion tasks)
        should_regenerate_from_layout = False
        original_filename = task_state.get("original_filename", "")
        is_pdf_file = original_filename.lower().endswith('.pdf')
        layout_doc = task_state.get("layout_document")

        # If layout_document is missing but this is a PDF with layout data,
        # try to reload from the stored ZIP so all downstream paths can use it.
        if layout_doc is None and is_pdf_file:
            zip_bytes = task_state.get("layout_source_zip")
            if zip_bytes is None:
                # Try to get from workflow attachments
                workflow_inst = task_state.get("workflow_instance")
                if workflow_inst and hasattr(workflow_inst, "attachment"):
                    try:
                        attachments = workflow_inst.attachment.get_documents()
                        if isinstance(attachments, dict) and "mineru" in attachments:
                            zip_bytes = attachments["mineru"]
                    except Exception:
                        pass
            if zip_bytes:
                try:
                    from layout.registry import load_layout_from_engine_zip
                    from utils.format_convert_utils import get_layout_block_bbox
                    layout_doc = load_layout_from_engine_zip("mineru", zip_bytes)
                    if layout_doc:
                        task_state["layout_document"] = layout_doc
                        task_state["layout_block_bbox"] = get_layout_block_bbox(layout_doc)
                        logger.info(
                            LogModule.EXPORT,
                            f"[DOWNLOAD] Reloaded layout_document from ZIP for task {task_id}: "
                            f"{layout_doc.page_count} pages"
                        )
                except Exception as reload_err:
                    logger.warning(
                        LogModule.EXPORT,
                        f"[DOWNLOAD] Failed to reload layout_document from ZIP: {reload_err}"
                    )

        # P0: Only regenerate from layout when source is layout-driven (PDF with layout path)
        segs_data = task_state.get("translation_segments")
        segs_meta = segs_data.get("metadata", {}) if isinstance(segs_data, dict) else {}
        source_input_type = task_state.get("source_input_type") or (segs_meta.get("source_input_type") if isinstance(segs_meta, dict) else None) or "text"

        # Fix source_input_type: if layout_document is available and this is a PDF,
        # but source_input_type was incorrectly left as "text" (e.g. workflow didn't
        # run layout builder), correct it now so rebuild uses layout block types.
        if layout_doc is not None and is_pdf_file and source_input_type != "layout":
            has_layout_indices = task_state.get("layout_chunk_block_map") is not None
            if has_layout_indices:
                logger.info(
                    LogModule.EXPORT,
                    f"[DOWNLOAD] Correcting source_input_type from '{source_input_type}' to 'layout' "
                    f"(PDF with layout_document and layout_chunk_block_map)"
                )
                source_input_type = "layout"
                task_state["source_input_type"] = "layout"
        
        if (equation_format or table_body_format) and is_pdf_file and layout_doc and source_input_type == "layout":
            should_regenerate_from_layout = True
            # Concise high-level log; detailed image handling logs are emitted later.
            logger.info(
                LogModule.EXPORT,
                f"[DOWNLOAD] Regenerating {file_type} from layout_document "
                f"(equation_format={equation_format}, table_body_format={table_body_format}, "
                f"is_format_conversion={is_format_conversion}, source_input_type=layout)"
            )
        elif (equation_format or table_body_format) and is_pdf_file and layout_doc and source_input_type != "layout":
            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Skipping layout regeneration: source_input_type={source_input_type} (not layout)")
        
        # If should regenerate from layout, do it now (before checking revisions)
        if should_regenerate_from_layout and workflow_type == "markdown_based":
            try:
                from layout.base import LayoutDocument as _LD
                from layout.markdown_builder import LayoutMarkdownBuilder
                from utils.document_rebuild import rebuild_markdown_document_from_segments
            
                if not isinstance(layout_doc, _LD):
                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Invalid layout_document type for task {task_id}")
                    should_regenerate_from_layout = False
                else:
                    # Check if we have translation segments (translated content)
                    # If yes, we should rebuild from translated segments with new format, not from original layout
                    segments_data = task_state.get("translation_segments")
                    has_translated_segments = segments_data and segments_data.get("segments")
                
                    if has_translated_segments and not is_format_conversion:
                        # For translation tasks, rebuild from translated segments with new format parameters
                        # This ensures we use translated content, not original content
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Found translation segments, will rebuild from translated segments with format parameters")
                    
                        # Get chunk_size and deep_split from task_state
                        chunk_size = task_state.get("segments_metadata", {}).get("chunk_size")
                        if chunk_size is None:
                            payload = task_state.get("payload")
                            if payload:
                                if isinstance(payload, dict):
                                    chunk_size = payload.get("chunk_size")
                                else:
                                    chunk_size = getattr(payload, 'chunk_size', None)
                        if chunk_size is None:
                            chunk_size = 3000  # Default
                    
                        deep_split_enabled = task_state.get("deep_split", True)
                        payload = task_state.get("payload")
                        if payload:
                            if isinstance(payload, dict):
                                deep_split_enabled = bool(payload.get("deep_split", True))
                            else:
                                deep_split_enabled = bool(getattr(payload, 'deep_split', True))
                    
                        # Validate and use format parameters
                        eq_format = (equation_format or "text").lower().strip()
                        if eq_format not in ("text", "latex", "image"):
                            eq_format = "text"
                    
                        table_format = (table_body_format or "html").lower().strip()
                        if table_format not in ("html", "image"):
                            table_format = "html"
                    
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Regenerating from translated segments with equation_format={eq_format}, table_body_format={table_format}")
                    
                        # Check if format parameters differ from translation time
                        _pl = task_state.get("payload")
                        original_eq_format = (task_state.get("equation_format") or (_pl.get("equation_format") if isinstance(_pl, dict) else (getattr(_pl, "equation_format", None) if _pl else None)) or "text")
                        if isinstance(original_eq_format, str):
                            original_eq_format = original_eq_format.lower().strip()
                        if original_eq_format not in ("text", "latex", "image"):
                            original_eq_format = "text"
                        
                        # If format changed or we have layout_document, regenerate markdown with new format
                        format_changed = (eq_format != original_eq_format) or (table_format != "html")
                        should_regenerate_from_layout = is_pdf_file and layout_doc is not None and format_changed
                        
                        if should_regenerate_from_layout:
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Format parameters changed (eq: {original_eq_format}->{eq_format}, table: html->{table_format}), regenerating markdown from layout_document")
                            
                            # CRITICAL: Check if we have translation segments (translated content)
                            # If yes, we should rebuild from translated segments with new format, not from original layout
                            segments_data = task_state.get("translation_segments")
                            has_translated_segments = segments_data and segments_data.get("segments")
                            
                            if has_translated_segments:
                                # For translation tasks, rebuild from translated segments with new format parameters
                                # This ensures we use translated content, not original content
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Found translation segments, will rebuild from translated segments with format parameters")
                                from utils.document_rebuild import rebuild_markdown_document_from_segments
                                
                                # Rebuild from translated segments (this uses target_text, not source_text)
                                rebuilt_doc = rebuild_markdown_document_from_segments(
                                    task_state,
                                    file_stem=task_state.get("original_filename_stem"),
                                    equation_format=eq_format,
                                    table_body_format=table_format,
                                )
                                
                                if rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                                    # Decode bytes to string if needed
                                    md_content = rebuilt_doc.content
                                    if isinstance(md_content, bytes):
                                        md_content = md_content.decode('utf-8')
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Rebuilt MD from translated segments with new format (length: {len(md_content)} chars)")
                                    if file_type == "pdf":
                                        task_state["_rebuilt_md_for_pdf"] = md_content
                                    # layout_result is not needed when using rebuilt_doc from segments
                                    # The markdown content already contains translated text with preserved formatting
                                    layout_result = None
                                else:
                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to rebuild from segments, falling back to layout regeneration")
                                    # Fallback to layout regeneration (but this will be original text)
                                    from layout.markdown_builder import LayoutMarkdownBuilder
                                    chunk_size = task_state.get("chunk_size", 2000) or 2000
                                    builder = LayoutMarkdownBuilder(
                                        max_chunk_chars=chunk_size,
                                        deep_split=deep_split_enabled,
                                        equation_format=eq_format,
                                        table_body_format=table_format
                                    )
                                    layout_result = builder.build(layout_doc)
                                    md_content = layout_result.markdown_text
                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Using original layout markdown (not translated) as fallback")
                            else:
                                # No translation segments available, use layout regeneration (for format conversion tasks)
                                from layout.markdown_builder import LayoutMarkdownBuilder
                                chunk_size = task_state.get("chunk_size", 2000) or 2000
                                builder = LayoutMarkdownBuilder(
                                    max_chunk_chars=chunk_size,
                                    deep_split=deep_split_enabled,
                                    equation_format=eq_format,
                                    table_body_format=table_format
                                )
                                layout_result = builder.build(layout_doc)
                                md_content = layout_result.markdown_text
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Regenerated markdown from layout_document with new format (length: {len(md_content)} chars)")
                            
                            # Extract images from layout_source_zip and build image_data_map
                            image_data_map: dict[str, dict[str, str]] = {}
                            zip_bytes = task_state.get("layout_source_zip")
                            zip_file = None
                            
                            if zip_bytes:
                                try:
                                    from layout.pdf_renderer.shared.block_processor import BlockProcessor
                                    
                                    zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
                                    images_bytes_map = BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
                                    
                                    # Convert image bytes to base64 data URIs and map by filename
                                    image_data_by_filename: dict[str, str] = {}
                                    for img_path, img_bytes in images_bytes_map.items():
                                        mime = mimetypes.guess_type(img_path)[0] or "image/png"
                                        data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
                                        # Use filename as key (extract from path)
                                        filename = img_path.split('/')[-1].split('\\')[-1]
                                        image_data_by_filename[filename] = data_uri
                                    
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Extracted {len(image_data_by_filename)} images from layout_source_zip")

                                    # Register all extracted images (required for equation_format=image hash filenames)
                                    _populate_image_data_map_from_extracted(image_data_map, images_bytes_map)
                                    
                                    # Parse markdown to find image references and map them
                                    import re
                                    
                                    # Pattern 1: ![alt](filename.jpg) - filename-based images (equations)
                                    image_pattern = r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)'
                                    matches = re.findall(image_pattern, md_content, re.IGNORECASE)
                                    
                                    for alt_text, img_ref, ext in matches:
                                        # Extract filename from path
                                        filename = img_ref.split('/')[-1].split('\\')[-1]
                                        
                                        # Look up image data by filename
                                        if filename in image_data_by_filename:
                                            image_data_map[filename] = {
                                                "data": image_data_by_filename[filename],
                                                "alt": alt_text or filename,
                                            }
                                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Mapped image: {filename} (alt: {alt_text})")
                                        else:
                                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Image data not found for filename: {filename} (alt: {alt_text})")
                                    
                                    # Pattern 2: ![alt](placeholder_id) - placeholder-based images (tables)
                                    # Examples: ![Table](layoutimg3), ![Equation](layoutimg0)
                                    placeholder_image_pattern = r'!\[([^\]]*)\]\(([a-zA-Z0-9]+)\)'
                                    placeholder_matches = re.findall(placeholder_image_pattern, md_content)
                                    
                                    # Build mapping from placeholder ID to image_path using layout_result chunks
                                    # Only if layout_result is available (not when using rebuilt_doc from segments)
                                    placeholder_to_path: dict[str, str] = {}
                                    if layout_result is not None and hasattr(layout_result, 'chunks') and layout_result.chunks:
                                        for chunk in layout_result.chunks:
                                            if hasattr(chunk, 'image_placeholder') and hasattr(chunk, 'image_path'):
                                                if chunk.image_placeholder and chunk.image_path:
                                                    placeholder_to_path[chunk.image_placeholder] = chunk.image_path
                                    else:
                                        # When using rebuilt_doc from segments, try to get placeholder mapping from existing image_data_map
                                        # or from layout_document blocks directly
                                        existing_image_map = task_state.get("image_data_map")
                                        if isinstance(existing_image_map, dict):
                                            # Extract placeholder IDs from existing image_data_map
                                            for ph_id in existing_image_map.keys():
                                                if isinstance(ph_id, str) and ph_id.startswith('layoutimg'):
                                                    placeholder_to_path[ph_id] = ph_id  # Use placeholder ID as path hint
                                    
                                    for alt_text, placeholder_id in placeholder_matches:
                                        # Check if this is a placeholder (not a filename with extension)
                                        if '.' not in placeholder_id and placeholder_id.startswith('layoutimg'):
                                            # Look up image_path from chunks
                                            image_path = placeholder_to_path.get(placeholder_id)
                                            if image_path:
                                                # Extract filename from path
                                                filename = image_path.split('/')[-1].split('\\')[-1]
                                                
                                                # Look up image data by filename
                                                if filename in image_data_by_filename:
                                                    image_data_map[placeholder_id] = {
                                                        "data": image_data_by_filename[filename],
                                                        "alt": alt_text or placeholder_id,
                                                    }
                                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Mapped placeholder image: {placeholder_id} -> {filename} (alt: {alt_text})")
                                                else:
                                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Image data not found for placeholder {placeholder_id} (path: {image_path}, alt: {alt_text})")
                                            else:
                                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Image path not found for placeholder {placeholder_id} (alt: {alt_text})")
                                    
                                    # Pattern 3: <ph-xxx> - XML-style placeholders
                                    xml_placeholder_pattern = r'<ph-([a-zA-Z0-9]+)>'
                                    xml_placeholder_matches = re.findall(xml_placeholder_pattern, md_content)
                                    for ph_id in xml_placeholder_matches:
                                        # Try to find image by placeholder ID in existing image_data_map
                                        existing_image_map = task_state.get("image_data_map")
                                        if isinstance(existing_image_map, dict) and ph_id in existing_image_map:
                                            image_data_map[ph_id] = existing_image_map[ph_id]
                                
                                except Exception as e:
                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to extract images from layout_source_zip: {e}", exc_info=True)
                                finally:
                                    if zip_file:
                                        try:
                                            zip_file.close()
                                        except Exception:
                                            pass
                            
                            # Also merge with existing image_data_map from translation (for translated images)
                            existing_image_map = task_state.get("image_data_map")
                            if isinstance(existing_image_map, dict):
                                for k, v in existing_image_map.items():
                                    if k not in image_data_map:
                                        image_data_map[str(k)] = {
                                            "data": (v or {}).get("data", ""),
                                            "alt": (v or {}).get("alt", ""),
                                        }
                            
                            if image_data_map:
                                task_state["image_data_map"] = image_data_map
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Built image_data_map with {len(image_data_map)} images for task {task_id}")
                            else:
                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] No images found in image_data_map after regeneration")
                        else:
                            # Rebuild markdown from translated segments (this gives us translated content)
                            # Use format parameters if available (eq_format and table_format are defined above)
                            rebuilt_doc = rebuild_markdown_document_from_segments(
                                task_state,
                                file_stem=task_state.get("original_filename_stem"),
                                equation_format=eq_format,
                                table_body_format=table_format,
                            )
                        
                            if not rebuilt_doc:
                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to rebuild from translated segments, falling back to layout regeneration")
                                # Fall through to layout regeneration below
                            else:
                                # Get translated markdown content from rebuilt document
                                if isinstance(rebuilt_doc.content, bytes):
                                    translated_md_content = rebuilt_doc.content.decode('utf-8')
                                else:
                                    translated_md_content = str(rebuilt_doc.content)
                            
                                # Use the translated content directly
                                md_content = translated_md_content
                                if file_type == "pdf":
                                    task_state["_rebuilt_md_for_pdf"] = md_content
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using translated content from segments (length: {len(md_content)} chars)")
                            
                                # Still need to build image_data_map for frontend preview
                                # When format parameters are used, we need to extract images from layout_source_zip
                                # to support format-switched images (tables/equations as images)
                                image_data_map: dict[str, dict[str, str]] = {}
                                
                                # If format parameters were used, extract images from layout_source_zip
                                if (equation_format or table_body_format) and is_pdf_file and layout_doc:
                                    zip_bytes = task_state.get("layout_source_zip")
                                    zip_file = None
                                    if zip_bytes:
                                        try:
                                            from layout.pdf_renderer.shared.block_processor import BlockProcessor
                                            
                                            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
                                            images_bytes_map = BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
                                            
                                            # Convert image bytes to base64 data URIs and map by filename
                                            image_data_by_filename: dict[str, str] = {}
                                            for img_path, img_bytes in images_bytes_map.items():
                                                mime = mimetypes.guess_type(img_path)[0] or "image/png"
                                                data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
                                                # Use filename as key (extract from path)
                                                filename = img_path.split('/')[-1].split('\\')[-1]
                                                image_data_by_filename[filename] = data_uri
                                            
                                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Extracted {len(image_data_by_filename)} images from layout_source_zip for format-switched content")

                                            _populate_image_data_map_from_extracted(image_data_map, images_bytes_map)
                                            
                                            # Parse markdown to find image references (from format-switched tables/equations)
                                            import re
                                            
                                            # Pattern: ![alt](filename.jpg) - filename-based images
                                            image_pattern = r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)'
                                            matches = re.findall(image_pattern, md_content, re.IGNORECASE)
                                            
                                            for alt_text, img_ref, ext in matches:
                                                # Extract filename from path
                                                filename = img_ref.split('/')[-1].split('\\')[-1]
                                                
                                                # Look up image data by filename
                                                if filename in image_data_by_filename:
                                                    image_data_map[filename] = {
                                                        "data": image_data_by_filename[filename],
                                                        "alt": alt_text or filename,
                                                    }
                                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Mapped format-switched image: {filename} (alt: {alt_text})")
                                                else:
                                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Image data not found for format-switched filename: {filename} (alt: {alt_text})")
                                        except Exception as e:
                                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to extract images from layout_source_zip for format-switched content: {e}", exc_info=True)
                                        finally:
                                            if zip_file:
                                                try:
                                                    zip_file.close()
                                                except Exception:
                                                    pass
                                
                                # Also merge with existing image_data_map from translation (for translated images)
                                existing_image_map = task_state.get("image_data_map")
                                if isinstance(existing_image_map, dict):
                                    for k, v in existing_image_map.items():
                                        if k not in image_data_map:
                                            image_data_map[str(k)] = {
                                                "data": (v or {}).get("data", ""),
                                                "alt": (v or {}).get("alt", ""),
                                            }
                            
                                # Update task_state with image_data_map for frontend preview
                                if image_data_map:
                                    task_state["image_data_map"] = image_data_map
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Built image_data_map with {len(image_data_map)} images for task {task_id} (including format-switched images)")
                        
                        # Continue with workflow creation (both paths should have md_content and image_data_map set)
                        if 'md_content' not in locals() or not md_content:
                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] md_content not set, falling through to layout regeneration")
                            # Fall through to layout regeneration below
                        elif 'image_data_map' not in locals():
                            # Ensure image_data_map is initialized
                            image_data_map = {}
                            existing_image_map = task_state.get("image_data_map")
                            if isinstance(existing_image_map, dict):
                                image_data_map.update({
                                    str(k): {
                                        "data": (v or {}).get("data", ""),
                                        "alt": (v or {}).get("alt", ""),
                                    }
                                    for k, v in existing_image_map.items()
                                })
                            if image_data_map:
                                task_state["image_data_map"] = image_data_map
                        
                        if 'md_content' in locals() and md_content:
                            # Create workflow for export
                            from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig
                            from exporter.md.md2html_exporter import MD2HTMLExporterConfig
                            from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                            from translator.ai_translator.md_translator import MDTranslatorConfig
                            from ir.markdown_document import MarkdownDocument
                            from utils.document_rebuild import _replace_placeholders_with_images
                        
                            to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload)
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] DOCX export font: to_lang={to_lang!r}, font_name={docx_font_name}")
                            # Create minimal config; add layout for side-by-side image grouping in HTML/PDF
                            _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                task_state, equation_format=eq_format, table_body_format=table_format
                            )
                            html_config = MD2HTMLExporterConfig(
                                preserve_line_breaks=is_pdf_file,
                                layout_block_bbox=task_state.get("layout_block_bbox"),
                                image_block_indices=_img_bidx,
                                layout_document=_layout if _img_bidx else None,
                            )
                            # Get table_body_format from query parameters or payload
                            table_format_for_docx = table_format if table_format else "html"
                            # Debug: write MD input to output/debug for DOCX export debugging
                            _docx_debug_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
                            docx_config = MD2DOCXExporterConfig(
                                table_body_format=table_format_for_docx,
                                equation_format=eq_format,
                                image_data_map=image_data_map,
                                font_name=docx_font_name,
                                debug_output_dir=_docx_debug_dir,
                            )
                            if is_pdf_file and layout_doc is not None:
                                try:
                                    from layout.base import LayoutDocument as _LD
                                    if isinstance(layout_doc, _LD):
                                        docx_config = MD2DOCXExporterConfig(
                                            layout_document=layout_doc,
                                            table_body_format=table_format_for_docx,
                                            equation_format=eq_format,
                                            image_data_map=image_data_map,
                                            font_name=docx_font_name,
                                            debug_output_dir=_docx_debug_dir,
                                        )
                                except Exception:
                                    pass
                        
                            translator_config = MDTranslatorConfig(skip_translate=True)
                            workflow_config = MarkdownBasedWorkflowConfig(
                                convert_engine="identity",
                                converter_config=None,
                                translator_config=translator_config,
                                html_exporter_config=html_config,
                                docx_exporter_config=docx_config
                            )
                        
                            workflow = MarkdownBasedWorkflow(workflow_config)
                        
                            # For DOCX export, first replace image placeholders with markdown image syntax
                            # so that MD2DOCXExporter can consume them (data URIs or file paths).
                            md_with_images, _ = _replace_placeholders_with_images(
                                md_content, image_data_map, output_dir=None
                            )
                            workflow.document_translated = MarkdownDocument.from_bytes(
                                content=md_with_images.encode('utf-8'),
                                suffix=".md",
                                stem=task_state.get("original_filename_stem", "translated")
                            )
                        
                            # Generate the requested file type
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = None
                        
                            if file_type == "html":
                                # CRITICAL: Replace image placeholders with data URIs before exporting to HTML
                                # This ensures images are embedded in the downloaded HTML file
                                from utils.document_rebuild import _replace_placeholders_with_images
                                md_with_images, _ = _replace_placeholders_with_images(
                                    md_content, image_data_map, output_dir=None  # Use data URIs for HTML
                                )
                            
                                # Temporarily update document_translated with images replaced
                                original_doc = workflow.document_translated
                                workflow.document_translated = MarkdownDocument.from_bytes(
                                    content=md_with_images.encode('utf-8'),
                                    suffix=".md",
                                    stem=task_state.get("original_filename_stem", "translated")
                                )
                            
                                temp_file = None
                                try:
                                    html_content = workflow.export_to_html()
                                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
                                    temp_file.write(html_content)
                                    temp_file.close()
                                    filename = f"{file_stem}_translated.html"
                                    media_type = MEDIA_TYPES.get(file_type, "text/html; charset=utf-8")
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated HTML from translated segments with equation_format={eq_format}, table_body_format={table_format}, images embedded")
                                    return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                                finally:
                                    # Restore original document
                                    workflow.document_translated = original_doc
                        
                            elif file_type == "md" or file_type == "markdown":
                                # Determine embed_images parameter (default: True for backward compatibility)
                                should_embed = embed_images if embed_images is not None else True
                            
                                if should_embed:
                                    # Embed images as data URIs (single MD file)
                                    from utils.document_rebuild import _replace_placeholders_with_images
                                    from utils.format_convert_utils import group_consecutive_images_for_markdown
                                    md_with_embedded_images, _ = _replace_placeholders_with_images(
                                        md_content, image_data_map, output_dir=None  # No output_dir = embed as data URIs
                                    )
                                    _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                        task_state, equation_format=eq_format, table_body_format=table_format
                                    )
                                    md_with_embedded_images = group_consecutive_images_for_markdown(
                                        md_with_embedded_images, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                        layout_block_bbox=task_state.get("layout_block_bbox"),
                                    )
                                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
                                    temp_file.write(md_with_embedded_images)
                                    temp_file.close()
                                    filename = f"{file_stem}_translated.md"
                                    media_type = MEDIA_TYPES.get(file_type, "text/markdown; charset=utf-8")
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD with embedded images from translated segments with equation_format={eq_format}, table_body_format={table_format}")
                                    return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                                else:
                                    # Save images to folder and create ZIP (MD file + images folder)
                                    # Use task_state temp_dir if available, otherwise create independent temp directory
                                    zip_temp_dir = None
                                    if task_state:
                                        temp_dir = task_state.get("temp_dir")
                                        if temp_dir and os.path.isdir(temp_dir):
                                            zip_temp_dir = os.path.join(temp_dir, "downloads")
                                            os.makedirs(zip_temp_dir, exist_ok=True)
                                    
                                    # Fallback: create independent temp directory if task_state temp_dir not available
                                    if not zip_temp_dir:
                                        zip_temp_dir = tempfile.mkdtemp()
                                    
                                    try:
                                        zip_output_dir = Path(zip_temp_dir)
                                    
                                        # Replace placeholders with image file paths
                                        from utils.document_rebuild import _replace_placeholders_with_images
                                        from utils.format_convert_utils import group_consecutive_images_for_markdown
                                        md_with_image_paths, saved_image_paths = _replace_placeholders_with_images(
                                            md_content, image_data_map, output_dir=zip_output_dir
                                        )
                                        _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                            task_state, equation_format=eq_format, table_body_format=table_format
                                        )
                                        md_with_image_paths = group_consecutive_images_for_markdown(
                                            md_with_image_paths, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                            layout_block_bbox=task_state.get("layout_block_bbox"),
                                        )
                                    
                                        # Write MD file to zip directory
                                        md_file_in_zip = zip_output_dir / f"{file_stem}_translated.md"
                                        with open(md_file_in_zip, 'w', encoding='utf-8') as f:
                                            f.write(md_with_image_paths)
                                    
                                        # Create ZIP file
                                        zip_buffer = io.BytesIO()
                                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                            # Add MD file
                                            zip_file.write(md_file_in_zip, md_file_in_zip.name)
                                            # Add all image files
                                            for img_path in saved_image_paths:
                                                if img_path.exists():
                                                    # Store with relative path (images/filename)
                                                    zip_file.write(img_path, img_path.relative_to(zip_output_dir))
                                    
                                        zip_buffer.seek(0)
                                        zip_bytes = zip_buffer.getvalue()
                                    
                                        # Write ZIP to temporary file
                                        zip_temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False)
                                        zip_temp_file.write(zip_bytes)
                                        zip_temp_file.close()
                                    
                                        filename = f"{file_stem}_translated_with_images.zip"
                                        media_type = "application/zip"
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD with images folder (ZIP) from translated segments with equation_format={eq_format}, table_body_format={table_format}, images_count={len(saved_image_paths)}")
                                        return FileResponse(path=zip_temp_file.name, media_type=media_type, filename=filename)
                                    finally:
                                        # Clean up temporary directory
                                        try:
                                            shutil.rmtree(zip_temp_dir, ignore_errors=True)
                                        except Exception:
                                            pass
                        
                            elif file_type == "docx":
                                # Use file-path MD (not embedded data URI) so DOCX exporter gets short refs like ![](./images/xxx.jpg)
                                _docx_output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                                _docx_output_dir.mkdir(parents=True, exist_ok=True)
                                md_for_docx, _ = _replace_placeholders_with_images(
                                    md_content, image_data_map, output_dir=_docx_output_dir, update_image_data_map=True
                                )
                                # ROOT CAUSE FIX: Rebuilt md_content can contain path-based refs (./images/xxx) from
                                # segment cache (saved from a previous export). image_data_map is built from
                                # layout_source_zip (keys = layout filenames) + existing (keys = placeholder IDs),
                                # so path-based keys are missing. _replace_placeholders only adds keys when
                                # replacing <ph-xxx>; it does not add keys for existing ![alt](./images/xxx) in content.
                                # Fill image_data_map from files in _docx_output_dir for refs in md that are missing.
                                import re as _re
                                _img_refs = _re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', md_for_docx)
                                _filled = 0
                                for _alt, _ref in _img_refs:
                                    if _ref in image_data_map or _ref.startswith("data:"):
                                        continue
                                    _norm = _ref.replace("\\", "/").lstrip("./")
                                    _path = _docx_output_dir / _norm
                                    if not _path.is_file():
                                        _path = _docx_output_dir / "images" / (_norm.split("/")[-1])
                                    if _path.is_file():
                                        try:
                                            import base64 as _b64
                                            import mimetypes as _mime
                                            _raw = _path.read_bytes()
                                            _mime_type = _mime.guess_type(str(_path))[0] or "image/png"
                                            _data_uri = f"data:{_mime_type};base64,{_b64.b64encode(_raw).decode('ascii')}"
                                            image_data_map[_ref] = {"data": _data_uri, "alt": _alt or _path.name}
                                            _filled += 1
                                        except Exception as _e:
                                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] DOCX image fallback read failed: {_path}: {_e}")
                                if _filled:
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Filled {_filled} image refs from output dir for DOCX export")
                                workflow.document_translated = MarkdownDocument.from_bytes(
                                    content=md_for_docx.encode('utf-8'),
                                    suffix=".md",
                                    stem=task_state.get("original_filename_stem", "translated")
                                )
                                docx_bytes = workflow.export_to_docx(config=docx_config)
                                temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                                temp_file.write(docx_bytes)
                                temp_file.close()
                                filename = f"{file_stem}_translated.docx"
                                media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated DOCX from translated segments with equation_format={eq_format}, table_body_format={table_format}")
                                return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    else:
                        # For format conversion tasks or when no translation segments exist,
                        # regenerate from original layout (this is the original behavior)
                        # Get chunk_size and deep_split from task_state
                        chunk_size = task_state.get("segments_metadata", {}).get("chunk_size")
                        if chunk_size is None:
                            payload = task_state.get("payload")
                            if payload:
                                if isinstance(payload, dict):
                                    chunk_size = payload.get("chunk_size")
                                else:
                                    chunk_size = getattr(payload, 'chunk_size', None)
                        if chunk_size is None:
                            chunk_size = 3000  # Default
                    
                        deep_split_enabled = task_state.get("deep_split", True)
                        payload = task_state.get("payload")
                        if payload:
                            if isinstance(payload, dict):
                                deep_split_enabled = bool(payload.get("deep_split", True))
                            else:
                                deep_split_enabled = bool(getattr(payload, 'deep_split', True))
                    
                        # Validate and use format parameters
                        eq_format = equation_format.lower() if equation_format else "text"
                        if eq_format not in ("text", "latex", "image"):
                            eq_format = "text"
                    
                        table_format = (table_body_format or "html").lower().strip()
                        if table_format not in ("html", "image"):
                            table_format = "html"
                    
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Regenerating from layout_document with equation_format={eq_format}, table_body_format={table_format}, chunk_size={chunk_size}, deep_split={deep_split_enabled}")
                    
                        builder = LayoutMarkdownBuilder(
                            max_chunk_chars=chunk_size,
                            deep_split=deep_split_enabled,
                            equation_format=eq_format,
                            table_body_format=table_format
                        )
                        layout_result = builder.build(layout_doc)
                        md_content = layout_result.markdown_text
                
                    # Build image_data_map for frontend preview (similar to preview generation)
                    image_data_map: dict[str, dict[str, str]] = {}
                    existing_image_map = task_state.get("image_data_map")
                    if isinstance(existing_image_map, dict):
                        # Copy existing entries to preserve previously loaded images
                        image_data_map.update({
                            str(k): {
                                "data": (v or {}).get("data", ""),
                                "alt": (v or {}).get("alt", ""),
                            }
                            for k, v in existing_image_map.items()
                        })
                
                    zip_bytes = task_state.get("layout_source_zip")
                    zip_file = None
                    zip_entries: list[str] = []
                    zip_entry_map: dict[str, str] = {}
                    if zip_bytes:
                        try:
                            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
                            zip_entries = zip_file.namelist()
                            zip_entry_map = {
                                name.replace("\\", "/"): name for name in zip_entries
                            }
                        except Exception as zip_error:
                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Failed to open MinerU ZIP for images: {zip_error}", )
                            zip_file = None
                
                    def _normalize_image_path(path: str | None) -> str | None:
                        if not path:
                            return None
                        return path.replace("\\", "/").lstrip("./")
                
                    placeholder_cache: dict[str, str] = {}
                
                    def _read_image_data_uri(image_path: str | None) -> str | None:
                        if not image_path:
                            return None
                        # Check zip_file and zip_entry_map are available
                        if zip_file is None or not zip_entry_map:
                            return None
                        normalized = _normalize_image_path(image_path)
                        if not normalized:
                            return None
                        if normalized in placeholder_cache:
                            return placeholder_cache[normalized]
                    
                        # Try exact match first
                        candidate = zip_entry_map.get(normalized)
                        if candidate is None:
                            # Try matching by filename (basename)
                            filename_only = os.path.basename(normalized)
                            for name, original in zip_entry_map.items():
                                # Match by exact filename
                                if name == filename_only or name.endswith('/' + filename_only) or name.endswith('\\' + filename_only):
                                    candidate = original
                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Matched image '{image_path}' to ZIP entry '{candidate}' by filename")
                                    break
                                # Also try matching by normalized path ending
                                if name.endswith(normalized):
                                    candidate = original
                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Matched image '{image_path}' to ZIP entry '{candidate}' by path ending")
                                    break
                                # Try matching by filename in images/ subdirectory (common in MinerU ZIP)
                                if name.endswith('/images/' + filename_only) or name.endswith('\\images\\' + filename_only):
                                    candidate = original
                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Matched image '{image_path}' to ZIP entry '{candidate}' by images/ subdirectory")
                                    break
                        if not candidate:
                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Image path '{image_path}' (normalized: '{normalized}') not found in ZIP entries. Available entries (first 10): {list(zip_entry_map.keys())[:10]}")
                            # Try to find by partial match (filename only, ignoring path)
                            filename_only = os.path.basename(normalized) if normalized else None
                            if filename_only:
                                for name, original in zip_entry_map.items():
                                    if name.endswith('/' + filename_only) or name.endswith('\\' + filename_only) or name == filename_only:
                                        candidate = original
                                        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Matched image '{image_path}' to ZIP entry '{candidate}' by filename-only fallback")
                                        break
                            if not candidate:
                                return None
                        # Double-check zip_file is still available before reading
                        if zip_file is None:
                            return None
                        try:
                            raw_bytes = zip_file.read(candidate)
                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Successfully read image '{image_path}' from ZIP entry '{candidate}' ({len(raw_bytes)} bytes)", )
                        except (KeyError, AttributeError) as e:
                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to read image '{candidate}' from ZIP: {e}")
                            return None
                        mime = mimetypes.guess_type(candidate)[0] or "image/png"
                        data_uri = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                        placeholder_cache[normalized] = data_uri
                        return data_uri
                
                    # Process chunks to build image_data_map (only if layout_result exists)
                    # For translated segments branch, layout_result is not generated, so skip this
                    if 'layout_result' in locals() and layout_result:
                        image_count = 0
                        for idx, chunk in enumerate(layout_result.chunks):
                            is_image = chunk.chunk_type == "image"
                            placeholder_id = None
                        
                            if is_image:
                                placeholder_id = chunk.image_placeholder or f"layoutimg{idx}"
                                alt_text = chunk.image_alt or (chunk.image_path or "Image")
                                data_uri = _read_image_data_uri(chunk.image_path)
                                image_data_map[placeholder_id] = {
                                    "data": data_uri or "",
                                    "alt": alt_text or "Image",
                                }
                                # Also add filename mapping for table images (similar to equation images)
                                # This allows HTML <img> tags with filename src to be matched
                                if chunk.image_path and data_uri:
                                    filename_key = (
                                        chunk.image_path.split('/')[-1].split('\\')[-1]
                                        if '/' in chunk.image_path or '\\' in chunk.image_path
                                        else chunk.image_path
                                    )
                                    if filename_key not in image_data_map:
                                        image_data_map[filename_key] = {
                                            "data": data_uri,
                                            "alt": chunk.image_path,  # Use full path as alt for matching
                                        }
                                        image_count += 1
                                # Map placeholder key explicitly (for <ph-layoutimg0> lookups)
                                if placeholder_id and data_uri and placeholder_id not in image_data_map:
                                    image_data_map[placeholder_id] = {
                                        "data": data_uri,
                                        "alt": chunk.image_path or alt_text or "Image",
                                    }
                                    image_count += 1
                            else:
                                # Check for markdown image syntax with filename (for equations and tables)
                                # Match ![any alt text](filename.jpg) - handles both equations and tables
                                # This handles cases where LayoutMarkdownBuilder generates ![Equation](hash.jpg) or ![Table](hash.jpg)
                                import re
                                image_pattern = r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)'
                                image_matches = re.findall(image_pattern, chunk.text)
                                for match in image_matches:
                                    alt_text = match[0] or "Image"
                                    image_filename = match[1]
                                    # Read image data from ZIP
                                    data_uri = _read_image_data_uri(image_filename)
                                    if data_uri:
                                        # Use filename as key (without path)
                                        filename_key = image_filename.split('/')[-1].split('\\')[-1] if '/' in image_filename or '\\' in image_filename else image_filename
                                        # CRITICAL: Add filename mapping for HTML <img> tags
                                        # HTML will have <img src="filename.jpg">, so we need filename as key
                                        if filename_key not in image_data_map:
                                            image_data_map[filename_key] = {
                                                "data": data_uri,
                                                "alt": image_filename,  # Use full filename as alt for matching
                                            }
                                            image_count += 1
                                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Added filename mapping for equation/table image: {filename_key} (from chunk text)", )
                                    else:
                                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to read image data for filename in chunk text: {image_filename} (zip_file={zip_file is not None}, zip_entries={len(zip_entries) if zip_entries else 0})")
                    
                        # Update task_state with image_data_map for frontend preview
                        if image_data_map:
                            task_state["image_data_map"] = image_data_map
                
                    if zip_file:
                        try:
                            zip_file.close()
                        except Exception:
                            pass
                
                    # Create workflow for export
                    from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig
                    from exporter.md.md2html_exporter import MD2HTMLExporterConfig
                    from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                    from translator.ai_translator.md_translator import MDTranslatorConfig
                    from ir.markdown_document import MarkdownDocument
                    from utils.document_rebuild import _replace_placeholders_with_images
                
                    to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload)
                    # Create minimal config; add layout for side-by-side image grouping in HTML/PDF
                    _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                        task_state, equation_format=eq_format, table_body_format=table_format
                    )
                    html_config = MD2HTMLExporterConfig(
                        preserve_line_breaks=is_pdf_file,
                        layout_block_bbox=task_state.get("layout_block_bbox"),
                        image_block_indices=_img_bidx,
                        layout_document=_layout if _img_bidx else None,
                    )
                    # Get table_body_format from query parameters (already resolved above)
                    table_format_for_docx = table_format if table_format else "html"
                    # Debug: write MD input to output/debug for DOCX export debugging
                    _docx_debug_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
                    docx_config = MD2DOCXExporterConfig(
                        table_body_format=table_format_for_docx,
                        equation_format=eq_format,
                        image_data_map=image_data_map,
                        font_name=docx_font_name,
                        debug_output_dir=_docx_debug_dir,
                    )
                    if is_pdf_file and layout_doc is not None:
                        try:
                            from layout.base import LayoutDocument as _LD
                            if isinstance(layout_doc, _LD):
                                docx_config = MD2DOCXExporterConfig(
                                    layout_document=layout_doc,
                                    table_body_format=table_format_for_docx,
                                    equation_format=eq_format,
                                    image_data_map=image_data_map,
                                    font_name=docx_font_name,
                                    debug_output_dir=_docx_debug_dir,
                                )
                        except Exception:
                            pass
                
                    translator_config = MDTranslatorConfig(skip_translate=True)
                    workflow_config = MarkdownBasedWorkflowConfig(
                        convert_engine="identity",
                        converter_config=None,
                        translator_config=translator_config,
                        html_exporter_config=html_config,
                        docx_exporter_config=docx_config
                    )
                
                    workflow = MarkdownBasedWorkflow(workflow_config)
                
                    # For DOCX export, first replace image placeholders with markdown image syntax
                    # so that MD2DOCXExporter can consume them (data URIs or file paths).
                    md_with_images, _ = _replace_placeholders_with_images(
                        md_content, image_data_map, output_dir=None
                    )
                    workflow.document_translated = MarkdownDocument.from_bytes(
                        content=md_with_images.encode('utf-8'),
                        suffix=".md",
                        stem=task_state.get("original_filename_stem", "translated")
                    )
                
                    # Generate the requested file type
                    file_stem = task_state.get("original_filename_stem", "translated")
                    temp_file = None
                
                    if file_type == "html":
                        # CRITICAL: Replace image placeholders with data URIs before exporting to HTML
                        # This ensures images are embedded in the downloaded HTML file
                        from utils.document_rebuild import _replace_placeholders_with_images
                        md_with_images, _ = _replace_placeholders_with_images(
                            md_content, image_data_map, output_dir=None  # Use data URIs for HTML
                        )
                    
                        # Temporarily update document_translated with images replaced
                        original_doc = workflow.document_translated
                        workflow.document_translated = MarkdownDocument.from_bytes(
                            content=md_with_images.encode('utf-8'),
                            suffix=".md",
                            stem=task_state.get("original_filename_stem", "translated")
                        )
                    
                        temp_file = None
                        try:
                            html_content = workflow.export_to_html()
                            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
                            temp_file.write(html_content)
                            temp_file.close()
                            filename = f"{file_stem}_translated.html"
                            media_type = MEDIA_TYPES.get(file_type, "text/html; charset=utf-8")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated HTML from layout_document with equation_format={eq_format}, table_body_format={table_format}, images embedded")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                        finally:
                            # Restore original document
                            workflow.document_translated = original_doc
                
                    elif file_type == "md" or file_type == "markdown":
                        # Determine embed_images parameter (default: True for backward compatibility)
                        should_embed = embed_images if embed_images is not None else True
                    
                        if should_embed:
                            # Embed images as data URIs (single MD file)
                            from utils.document_rebuild import _replace_placeholders_with_images
                            from utils.format_convert_utils import group_consecutive_images_for_markdown
                            md_with_embedded_images, _ = _replace_placeholders_with_images(
                                md_content, image_data_map, output_dir=None  # No output_dir = embed as data URIs
                            )
                            _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                task_state, equation_format=eq_format, table_body_format=table_format
                            )
                            md_with_embedded_images = group_consecutive_images_for_markdown(
                                md_with_embedded_images, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                layout_block_bbox=task_state.get("layout_block_bbox"),
                            )
                            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
                            temp_file.write(md_with_embedded_images)
                            temp_file.close()
                            filename = f"{file_stem}_translated.md"
                            media_type = MEDIA_TYPES.get(file_type, "text/markdown; charset=utf-8")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD with embedded images from layout_document (equation_format={eq_format}, table_body_format={table_format})")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                        else:
                            # Save images to folder and create ZIP (MD file + images folder)
                            # Use task_state temp_dir if available, otherwise create independent temp directory
                            zip_temp_dir = None
                            if task_state:
                                temp_dir = task_state.get("temp_dir")
                                if temp_dir and os.path.isdir(temp_dir):
                                    zip_temp_dir = os.path.join(temp_dir, "downloads")
                                    os.makedirs(zip_temp_dir, exist_ok=True)
                            
                            # Fallback: create independent temp directory if task_state temp_dir not available
                            if not zip_temp_dir:
                                zip_temp_dir = tempfile.mkdtemp()
                            
                            try:
                                zip_output_dir = Path(zip_temp_dir)
                            
                                # Replace placeholders with image file paths
                                from utils.document_rebuild import _replace_placeholders_with_images
                                from utils.format_convert_utils import group_consecutive_images_for_markdown
                                md_with_image_paths, saved_image_paths = _replace_placeholders_with_images(
                                    md_content, image_data_map, output_dir=zip_output_dir
                                )
                                _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                    task_state, equation_format=eq_format, table_body_format=table_format
                                )
                                md_with_image_paths = group_consecutive_images_for_markdown(
                                    md_with_image_paths, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                    layout_block_bbox=task_state.get("layout_block_bbox"),
                                )
                            
                                # Write MD file to zip directory
                                md_file_in_zip = zip_output_dir / f"{file_stem}_translated.md"
                                with open(md_file_in_zip, 'w', encoding='utf-8') as f:
                                    f.write(md_with_image_paths)
                            
                                # Create ZIP file
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                    # Add MD file
                                    zip_file.write(md_file_in_zip, md_file_in_zip.name)
                                    # Add all image files
                                    for img_path in saved_image_paths:
                                        if img_path.exists():
                                            # Store with relative path (images/filename)
                                            zip_file.write(img_path, img_path.relative_to(zip_output_dir))
                            
                                zip_buffer.seek(0)
                                zip_bytes = zip_buffer.getvalue()
                            
                                # Write ZIP to temporary file
                                zip_temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False)
                                zip_temp_file.write(zip_bytes)
                                zip_temp_file.close()
                            
                                filename = f"{file_stem}_translated_with_images.zip"
                                media_type = "application/zip"
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD with images folder (ZIP) from layout_document with equation_format={eq_format}, table_body_format={table_format}, images_count={len(saved_image_paths)}")
                                return FileResponse(path=zip_temp_file.name, media_type=media_type, filename=filename)
                            finally:
                                # Clean up temporary directory
                                try:
                                    shutil.rmtree(zip_temp_dir, ignore_errors=True)
                                except Exception:
                                    pass
                
                    elif file_type == "docx":
                        # Use file-path MD (not embedded data URI) so DOCX exporter gets short refs like ![](./images/xxx.jpg)
                        _docx_output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                        _docx_output_dir.mkdir(parents=True, exist_ok=True)
                        md_for_docx, _ = _replace_placeholders_with_images(
                            md_content, image_data_map, output_dir=_docx_output_dir, update_image_data_map=True
                        )
                        # Fill image_data_map from files in _docx_output_dir for refs in md that are missing
                        import re as _re_docx
                        _img_refs_d = _re_docx.findall(r'!\[([^\]]*)\]\(([^)]+)\)', md_for_docx)
                        _filled_d = 0
                        for _alt_d, _ref_d in _img_refs_d:
                            if _ref_d in image_data_map or _ref_d.startswith("data:"):
                                continue
                            _norm_d = _ref_d.replace("\\", "/").lstrip("./")
                            _path_d = _docx_output_dir / _norm_d
                            if not _path_d.is_file():
                                _path_d = _docx_output_dir / "images" / (_norm_d.split("/")[-1])
                            if _path_d.is_file():
                                try:
                                    import base64 as _b64_d
                                    import mimetypes as _mime_d
                                    _raw_d = _path_d.read_bytes()
                                    _mime_type_d = _mime_d.guess_type(str(_path_d))[0] or "image/png"
                                    image_data_map[_ref_d] = {"data": f"data:{_mime_type_d};base64,{_b64_d.b64encode(_raw_d).decode('ascii')}", "alt": _alt_d or _path_d.name}
                                    _filled_d += 1
                                except Exception as _e_d:
                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] DOCX image fallback read failed: {_path_d}: {_e_d}")
                        if _filled_d:
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Filled {_filled_d} image refs from output dir for DOCX export (layout path)")
                        workflow.document_translated = MarkdownDocument.from_bytes(
                            content=md_for_docx.encode('utf-8'),
                            suffix=".md",
                            stem=task_state.get("original_filename_stem", "translated")
                        )
                        # Check if any entries have empty data (warning only)
                        if image_data_map:
                            empty_data_count = sum(1 for v in image_data_map.values() if isinstance(v, dict) and not v.get("data"))
                            if empty_data_count > 0:
                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Found {empty_data_count} image entries with empty data in image_data_map")
                        docx_bytes = workflow.export_to_docx(config=docx_config)
                        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                        temp_file.write(docx_bytes)
                        temp_file.close()
                        filename = f"{file_stem}_translated.docx"
                        media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated DOCX from layout_document (equation_format={eq_format}, table_body_format={table_format})")
                        return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
            except Exception as e:
                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to regenerate from layout_document with format parameters: {e}, falling back to normal flow", exc_info=True)
                should_regenerate_from_layout = False
    
        # If requesting Markdown, DOCX, or HTML (markdown workflow) rebuild regardless of revision status.
        # HTML is included so that table_body_format / equation_format are applied to the rebuild.
        if (
            workflow_type == "markdown_based"
            and file_type in {"md", "docx", "html"}
            and task_state.get("translation_segments", {}).get("segments")
        ):
            has_revisions = True
    
        # If there are revisions (or forced for md), rebuild the document and regenerate the file
        if has_revisions and workflow_type:
            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Found revised segments for task {task_id}, rebuilding {file_type} file with revisions")
        
            try:
                # Rebuild based on workflow type
                if workflow_type == "markdown_based":
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Starting rebuild for markdown_based workflow")
                    rebuilt_doc = rebuild_markdown_document_from_segments(
                        task_state,
                        file_stem=task_state.get("original_filename_stem"),
                        equation_format=equation_format,
                        table_body_format=table_body_format,
                    )
                
                    if rebuilt_doc:
                        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Rebuilt document successful, content length: {len(rebuilt_doc.content)} bytes")
                    else:
                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] Failed to rebuild document from segments, falling back to original")
                        has_revisions = False

                    if rebuilt_doc:
                        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Successfully rebuilt MarkdownDocument, creating workflow for {file_type} export")
                        # Create minimal workflow for export
                        from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig
                        from exporter.md.md2html_exporter import MD2HTMLExporterConfig
                        from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                        from translator.ai_translator.md_translator import MDTranslatorConfig
                        from converter.converter_identity import ConverterIdentity
                        # payload may not be set in this branch; resolve from task_state
                        payload_for_export = task_state.get("payload")
                        to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload_for_export)
                        # Create minimal config (only what's needed for export); add layout for side-by-side images in HTML
                        _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                            task_state, equation_format=equation_format, table_body_format=table_body_format
                        )
                        html_config = MD2HTMLExporterConfig(
                            preserve_line_breaks=is_pdf_file,
                            layout_block_bbox=task_state.get("layout_block_bbox"),
                            image_block_indices=_img_bidx,
                            layout_document=_layout if _img_bidx else None,
                        )
                        # Build DOCX config with layout_document so tables can render
                        # as real DOCX tables instead of plain text
                        docx_config_kwargs: dict = {"font_name": docx_font_name}
                        if layout_doc is not None and is_pdf_file:
                            try:
                                from layout.base import LayoutDocument as _LD
                                if isinstance(layout_doc, _LD):
                                    docx_config_kwargs["layout_document"] = layout_doc
                            except Exception:
                                pass
                        if table_body_format:
                            docx_config_kwargs["table_body_format"] = table_body_format
                        if equation_format:
                            docx_config_kwargs["equation_format"] = equation_format
                        # Get image_data_map for DOCX images
                        existing_img_map = task_state.get("image_data_map")
                        if isinstance(existing_img_map, dict):
                            docx_config_kwargs["image_data_map"] = existing_img_map
                        docx_config_kwargs["debug_output_dir"] = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
                        docx_config = MD2DOCXExporterConfig(**docx_config_kwargs)
                        # Minimal translator config for export only: disable translating
                        translator_config = MDTranslatorConfig(skip_translate=True)
                    
                        workflow_config = MarkdownBasedWorkflowConfig(
                            convert_engine="identity",
                            converter_config=None,
                            translator_config=translator_config,
                            html_exporter_config=html_config,
                            docx_exporter_config=docx_config
                        )
                    
                        # Create workflow and set rebuilt document
                        workflow = MarkdownBasedWorkflow(workflow_config)
                        workflow.document_translated = rebuilt_doc
                        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Workflow created, document_translated content length: {len(rebuilt_doc.content)} bytes")
                    
                        # Generate the requested file type
                        file_stem = task_state.get("original_filename_stem", "rebuilt")
                        temp_file = None
                    
                        if file_type == "html":
                            html_content = workflow.export_to_html()
                            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
                            temp_file.write(html_content)
                            temp_file.close()
                            filename = f"{file_stem}_translated.html"
                            media_type = MEDIA_TYPES.get(file_type, "text/html; charset=utf-8")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated revised html file: {temp_file.name} (size: {os.path.getsize(temp_file.name)} bytes)")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    
                        elif file_type == "md":
                            md_content = workflow.export_to_markdown()
                        
                            # Determine embed_images parameter (default: True for backward compatibility)
                            should_embed = embed_images if embed_images is not None else True
                        
                            # Get image_data_map from task_state
                            image_data_map_rebuild: dict[str, dict[str, str]] = {}
                            existing_image_map = task_state.get("image_data_map")
                            if isinstance(existing_image_map, dict):
                                image_data_map_rebuild.update({
                                    str(k): {
                                        "data": (v or {}).get("data", ""),
                                        "alt": (v or {}).get("alt", ""),
                                    }
                                    for k, v in existing_image_map.items()
                                })
                        
                            if should_embed:
                                # Embed images as data URIs (single MD file)
                                from utils.document_rebuild import _replace_placeholders_with_images
                                from utils.format_convert_utils import group_consecutive_images_for_markdown
                                md_with_embedded_images, _ = _replace_placeholders_with_images(
                                    md_content, image_data_map_rebuild, output_dir=None  # No output_dir = embed as data URIs
                                )
                                _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                    task_state, equation_format=equation_format, table_body_format=table_body_format
                                )
                                md_with_embedded_images = group_consecutive_images_for_markdown(
                                    md_with_embedded_images, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                    layout_block_bbox=task_state.get("layout_block_bbox"),
                                )
                                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
                                temp_file.write(md_with_embedded_images)
                                temp_file.close()
                                filename = f"{file_stem}_translated.md"
                                media_type = MEDIA_TYPES.get(file_type, "text/markdown; charset=utf-8")
                                logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Generated revised MD file with embedded images: {temp_file.name}")
                            else:
                                # Save images to folder and create ZIP (MD file + images folder)
                                # Use task_state temp_dir if available, otherwise create independent temp directory
                                zip_temp_dir = None
                                if task_state:
                                    temp_dir = task_state.get("temp_dir")
                                    if temp_dir and os.path.isdir(temp_dir):
                                        zip_temp_dir = os.path.join(temp_dir, "downloads")
                                        os.makedirs(zip_temp_dir, exist_ok=True)
                                
                                # Fallback: create independent temp directory if task_state temp_dir not available
                                if not zip_temp_dir:
                                    zip_temp_dir = tempfile.mkdtemp()
                                
                                try:
                                    zip_output_dir = Path(zip_temp_dir)
                                
                                    # Replace placeholders with image file paths
                                    from utils.document_rebuild import _replace_placeholders_with_images
                                    from utils.format_convert_utils import group_consecutive_images_for_markdown
                                    md_with_image_paths, saved_image_paths = _replace_placeholders_with_images(
                                        md_content, image_data_map_rebuild, output_dir=zip_output_dir
                                    )
                                    _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(
                                        task_state, equation_format=equation_format, table_body_format=table_body_format
                                    )
                                    md_with_image_paths = group_consecutive_images_for_markdown(
                                        md_with_image_paths, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                                        layout_block_bbox=task_state.get("layout_block_bbox"),
                                    )
                                
                                    # Write MD file to zip directory
                                    md_file_in_zip = zip_output_dir / f"{file_stem}_translated.md"
                                    with open(md_file_in_zip, 'w', encoding='utf-8') as f:
                                        f.write(md_with_image_paths)
                                
                                    # Create ZIP file
                                    zip_buffer = io.BytesIO()
                                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                        # Add MD file
                                        zip_file.write(md_file_in_zip, md_file_in_zip.name)
                                        # Add all image files
                                        for img_path in saved_image_paths:
                                            if img_path.exists():
                                                # Store with relative path (images/filename)
                                                zip_file.write(img_path, img_path.relative_to(zip_output_dir))
                                
                                    zip_buffer.seek(0)
                                    zip_bytes = zip_buffer.getvalue()
                                
                                    # Write ZIP to temporary file
                                    temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False)
                                    temp_file.write(zip_bytes)
                                    temp_file.close()
                                
                                    filename = f"{file_stem}_translated_with_images.zip"
                                    media_type = "application/zip"
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated revised MD with images folder (ZIP): {temp_file.name}, images_count={len(saved_image_paths)}")
                                finally:
                                    # Clean up temporary directory
                                    import shutil
                                    try:
                                        shutil.rmtree(zip_temp_dir, ignore_errors=True)
                                    except Exception:
                                        pass
                    
                        elif file_type == "docx":
                            # For markdown-based workflows (PDF, MD, etc.): try Pandoc MD->DOCX first (formulas + font by lang), then MD2DOCX/HTML fallback
                            original_filename = task_state.get("original_filename", "")
                            is_pdf_file = original_filename.lower().endswith('.pdf')
                            is_md_file = original_filename.lower().endswith(('.md', '.markdown'))
                            layout_doc = task_state.get("layout_document")
                            to_lang, docx_font_name = _get_to_lang_and_docx_font(task_state, payload)
                        
                            if (is_pdf_file or is_md_file) and workflow_type == "markdown_based":
                                # Pandoc-first: try MD->DOCX via pandoc (preserves formulas, font by to_lang)
                                md_content = workflow.export_to_markdown()
                                if isinstance(md_content, bytes):
                                    md_content = md_content.decode("utf-8", errors="replace")
                                if md_content:
                                    try:
                                        from utils.format_convert_utils import convert_md_to_docx
                                        _tf = tempfile.NamedTemporaryFile(mode="wb", suffix=".docx", delete=False)
                                        _tf.close()
                                        if convert_md_to_docx(md_content, _tf.name, output_dir=None, to_lang=to_lang):
                                            try:
                                                from utils.docx_math_fragment_check import (
                                                    apply_docx_math_fragment_issues_to_task_state,
                                                )

                                                apply_docx_math_fragment_issues_to_task_state(
                                                    task_state,
                                                    task_id=task_id,
                                                    task_manager=self.task_manager,
                                                )
                                            except Exception as frag_err:
                                                logger.warning(
                                                    LogModule.EXPORT,
                                                    f"[DOWNLOAD] Task {task_id}: DOCX fragment math check failed: {frag_err}",
                                                    exc_info=False,
                                                )
                                            filename = f"{file_stem}_translated.docx"
                                            media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Exported DOCX via Pandoc (formulas preserved, font by language)")
                                            return FileResponse(path=_tf.name, media_type=media_type, filename=filename)
                                        try:
                                            os.unlink(_tf.name)
                                        except Exception:
                                            pass
                                    except Exception as pandoc_err:
                                        logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Pandoc DOCX skipped: {pandoc_err}, using MD2DOCX/HTML")
                                # Fallback: MD-to-DOCX (python-docx) or HTML-to-DOCX (pandoc)
                                try:
                                    # For PDF files with layout, use layout-based formula detection
                                    # For MD files or PDF without layout, use code-based formula detection
                                    docx_config = None
                                    if is_pdf_file and layout_doc is not None:
                                        try:
                                            from layout.base import LayoutDocument as _LD
                                            if isinstance(layout_doc, _LD):
                                                from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                                                _docx_debug_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output" / "debug"
                                                docx_config = MD2DOCXExporterConfig(
                                                    layout_document=layout_doc,
                                                    equation_format=equation_format or "text",
                                                    table_body_format=table_body_format or "html",
                                                    font_name=docx_font_name,
                                                    debug_output_dir=_docx_debug_dir,
                                                )
                                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using MD-to-DOCX export with layout-based formula detection for PDF file")
                                        except Exception as e:
                                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to create layout-based config: {e}, using code-based detection")
                                
                                    # Export using MD-to-DOCX (will use code-based detection if layout_config is None)
                                    docx_bytes = workflow.export_to_docx(config=docx_config)
                                    temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                                    temp_file.write(docx_bytes)
                                    temp_file.close()
                                    filename = f"{file_stem}_translated.docx"
                                    media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                    if is_pdf_file:
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Exported DOCX using MD-to-DOCX with layout-based formula detection")
                                    else:
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Exported DOCX using MD-to-DOCX with code-based formula detection (LaTeX formulas supported)")
                                except Exception as e:
                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] MD-to-DOCX export failed: {e}, falling back to HTML conversion (pandoc)")
                                    temp_file = None
                                    try:
                                        html_content = workflow.export_to_html()
                                        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                                        temp_file.close()
                                        convert_html_to_docx(html_content, temp_file.name, to_lang=to_lang)
                                        filename = f"{file_stem}_translated.docx"
                                        media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                    except Exception as fallback_error:
                                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] HTML-to-DOCX fallback also failed: {fallback_error}", exc_info=True)
                                        if temp_file and os.path.exists(temp_file.name):
                                            os.unlink(temp_file.name)
                                        raise
                            else:
                                # Use HTML-based conversion for other file types (uses pandoc)
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using HTML-to-DOCX conversion (pandoc) for non-markdown workflow")
                                temp_file = None
                                try:
                                    html_content = workflow.export_to_html()
                                    temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                                    temp_file.close()
                                    convert_html_to_docx(html_content, temp_file.name, to_lang=to_lang)
                                    filename = f"{file_stem}_translated.docx"
                                    media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                except Exception as html_error:
                                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] HTML-to-DOCX conversion failed: {html_error}", exc_info=True)
                                    if temp_file and os.path.exists(temp_file.name):
                                        os.unlink(temp_file.name)
                                    raise
                    
                        elif file_type == "pdf":
                            # Check workflow type first - MOBI/EPUB PDFs are generated in generate_all_outputs
                            # NOTE: When downloading, payload may be None. In that case, fall back to task_state.
                            workflow_type = getattr(payload, "workflow_type", None) if payload else None
                            if workflow_type is None:
                                workflow_type = task_state.get("workflow_type") or task_state.get("payload", {}).get("workflow_type")
                            if workflow_type in ("mobi", "epub"):
                                # For MOBI/EPUB, PDF should already be generated in generate_all_outputs
                                existing_pdf = task_state.get("downloadable_files", {}).get("pdf")
                                if existing_pdf:
                                    pdf_path = existing_pdf.get("path", "") if isinstance(existing_pdf, dict) else str(existing_pdf)
                                    if pdf_path and os.path.exists(pdf_path):
                                        filename = os.path.basename(pdf_path) or f"{file_stem}_translated.pdf"
                                        media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated PDF for MOBI/EPUB workflow: {pdf_path}")
                                        return FileResponse(path=pdf_path, media_type=media_type, filename=filename)
                                # If PDF doesn't exist, check output_dir (may have been generated but not added to downloadable_files)
                                output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                                pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
                                if pdf_file_path.exists():
                                    filename = f"{file_stem}_translated.pdf"
                                    media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Found PDF in output_dir for MOBI/EPUB: {pdf_file_path}")
                                    return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
                                else:
                                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF not found for MOBI/EPUB workflow. It should have been generated in generate_all_outputs.")
                                    raise HTTPException(
                                        status_code=404,
                                        detail="PDF file not found. PDF generation may have failed during translation. Please check the task logs."
                                    )
                            
                            # For PDF files, only use layout-based generation (high-fidelity)
                            original_filename = task_state.get("original_filename", "")
                            is_pdf_file = original_filename.lower().endswith('.pdf')
                        
                            if is_pdf_file:
                                # Check if layout_document is available (required for PDF files)
                                layout_doc = task_state.get("layout_document")
                                has_layout = False
                                if layout_doc is not None:
                                    try:
                                        from layout.base import LayoutDocument as _LD
                                        if isinstance(layout_doc, _LD):
                                            has_layout = True
                                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Layout document available for PDF generation")
                                    except Exception:
                                        pass
                            
                                if not has_layout:
                                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF file detected but layout_document not available. Cannot generate high-fidelity PDF.")
                                    raise HTTPException(
                                        status_code=404,
                                        detail="High-fidelity PDF generation requires layout information, which is not available for this task. Please ensure the file was processed with a layout-aware converter (e.g., MinerU)."
                                    )
                        
                            # Revision PDF: match OutputGenerator — Pandoc MD→PDF by default.
                            # Layout ReportLab/HTML path only runs when ENABLE_LAYOUT_PDF_GENERATION is True (see pdf_generator.py).
                            _pdf_stem = file_stem
                            output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                            output_dir.mkdir(exist_ok=True)

                            if ENABLE_LAYOUT_PDF_GENERATION:
                                try:
                                    await self.pdf_generator.generate(
                                        workflow,
                                        output_dir,
                                        _pdf_stem,
                                        task_state,
                                        task_id,
                                        table_body_format=table_body_format,
                                        equation_format=equation_format,
                                    )
                                    gen_pdf = task_state.get("downloadable_files", {}).get("pdf")
                                    if gen_pdf:
                                        pdf_path = gen_pdf.get("path", "") if isinstance(gen_pdf, dict) else str(gen_pdf)
                                        if pdf_path and os.path.exists(pdf_path):
                                            filename = os.path.basename(pdf_path) or f"{file_stem}_translated.pdf"
                                            media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                            return FileResponse(path=pdf_path, media_type=media_type, filename=filename)

                                    pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
                                    if pdf_file_path.exists():
                                        filename = f"{file_stem}_translated.pdf"
                                        media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                        return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
                                except NotImplementedError as not_impl_error:
                                    logger.warning(
                                        LogModule.EXPORT,
                                        f"[DOWNLOAD] NotImplementedError during PDF generation (Windows asyncio limitation): {not_impl_error}",
                                    )
                                    output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                                    pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
                                    gen_pdf = task_state.get("downloadable_files", {}).get("pdf")

                                    if gen_pdf and os.path.exists(gen_pdf.get("path", "")):
                                        filename = os.path.basename(gen_pdf["path"]) or f"{file_stem}_translated.pdf"
                                        media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] PDF generated successfully despite NotImplementedError")
                                        return FileResponse(path=gen_pdf["path"], media_type=media_type, filename=filename)
                                    if pdf_file_path.exists():
                                        filename = f"{file_stem}_translated.pdf"
                                        media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] PDF generated successfully despite NotImplementedError (found in output_dir)")
                                        return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
                                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF was not generated despite NotImplementedError")
                                    raise HTTPException(
                                        status_code=500,
                                        detail="PDF generation failed due to platform limitations. Please try again or contact support.",
                                    )
                                except Exception as _pdf_e:
                                    logger.error(LogModule.EXPORT, f"PDF generation on download failed: {_pdf_e}", exc_info=True)
                                    raise HTTPException(
                                        status_code=500,
                                        detail=f"High-fidelity PDF generation failed: {str(_pdf_e)}",
                                    )

                                raise HTTPException(
                                    status_code=500,
                                    detail="PDF generation failed. Please try again or contact support.",
                                )

                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Revision PDF task {task_id}: Pandoc MD→PDF "
                                f"(ENABLE_LAYOUT_PDF_GENERATION=False; same pipeline as translation export)",
                            )
                            md_raw = workflow.export_to_markdown()
                            if isinstance(md_raw, bytes):
                                md_raw = md_raw.decode("utf-8", errors="replace")
                            return _pandoc_pdf_file_response_from_md(
                                task_state,
                                task_id,
                                md_raw or "",
                                equation_format,
                                table_body_format,
                            )
                    
                        else:
                            # For unsupported file types with revisions, fall back to original
                            logger.warning(LogModule.EXPORT, f"File type {file_type} not supported for revision rebuild, using original file")
                            has_revisions = False  # Fall through to original logic
                    
                        if temp_file and os.path.exists(temp_file.name):
                            file_size = os.path.getsize(temp_file.name)
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated revised {file_type} file: {temp_file.name} (size: {file_size} bytes)")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                        else:
                            temp_file_info = temp_file.name if temp_file else 'None'
                            logger.error(LogModule.EXPORT, f"[DOWNLOAD] Failed to generate revised {file_type} file, temp_file: {temp_file}, exists: {temp_file_info}")
                            # For markdown_based workflow, if we have rebuilt_doc, try to generate MD directly from it
                            if file_type == "md" and rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                                try:
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Attempting to generate MD directly from rebuilt document content")
                                    # Decode bytes to string if needed
                                    md_content = rebuilt_doc.content
                                    if isinstance(md_content, bytes):
                                        md_content = md_content.decode('utf-8')
                                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
                                    temp_file.write(md_content)
                                    temp_file.close()
                                    filename = f"{file_stem}_translated.md"
                                    media_type = MEDIA_TYPES.get(file_type, "text/markdown; charset=utf-8")
                                    if os.path.exists(temp_file.name):
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD from rebuilt document content")
                                        return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                                except Exception as e2:
                                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] Failed to generate MD from rebuilt document: {e2}", exc_info=True)
                            # Fall through to original logic
                            has_revisions = False
                        
                elif workflow_type == "docx":
                    # DOCX workflow - always rebuild from segments to ensure latest user edits are included
                    # This ensures that any frontend modifications (even if modified flag is not set) are applied
                    # Try to get translated document from saved downloadable file
                    # If not available, try original file
                    docx_file_info = task_state.get("downloadable_files", {}).get("docx")
                    translated_doc = None
                
                    if docx_file_info and os.path.exists(docx_file_info.get("path")):
                        # Use the translated DOCX file
                        from ir.document import Document
                        translated_doc = Document.from_path(docx_file_info["path"])
                    else:
                        # Fallback to original file (shouldn't happen normally)
                        original_file_path = task_state.get("original_file_path")
                        if original_file_path and os.path.exists(original_file_path):
                            from ir.document import Document
                            translated_doc = Document.from_path(original_file_path)
                        else:
                            logger.error(LogModule.EXPORT, "Neither translated nor original DOCX file found")
                            has_revisions = False
                
                    if translated_doc:
                        try:
                            # CRITICAL: Always rebuild DOCX document from segments to ensure latest user edits are included
                            # This ensures that any frontend modifications are applied, even if modified flag is not set
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Rebuilding DOCX document from segments for task {task_id} to ensure latest edits are included")
                            rebuilt_doc = rebuild_docx_document_from_segments(task_state, translated_doc)
                        except Exception as rebuild_error:
                            logger.error(LogModule.EXPORT, f"Failed to rebuild DOCX document from segments for task {task_id}: {rebuild_error}", exc_info=True)
                            has_revisions = False
                            rebuilt_doc = None
                    
                        if rebuilt_doc:
                            try:
                                # Create minimal workflow for export
                                from workflow.docx_workflow import DocxWorkflow, DocxWorkflowConfig
                                from exporter.docx.docx2html_exporter import Docx2HTMLExporterConfig
                                from translator.ai_translator.docx_translator import DocxTranslatorConfig
                        
                                html_config = Docx2HTMLExporterConfig()
                                # Minimal translator config for export only: disable translating
                                translator_config = DocxTranslatorConfig(skip_translate=True)
                        
                                workflow_config = DocxWorkflowConfig(
                                    translator_config=translator_config,
                                    html_exporter_config=html_config
                                )
                        
                                workflow = DocxWorkflow(workflow_config)
                                workflow.document_translated = rebuilt_doc
                            except Exception as workflow_error:
                                logger.error(LogModule.EXPORT, f"Failed to create workflow for task {task_id}: {workflow_error}", exc_info=True)
                                has_revisions = False
                                workflow = None
                        
                            if workflow:
                                # Generate the requested file type
                                file_stem = task_state.get("original_filename_stem", "rebuilt")
                                temp_file = None
                        
                                if file_type == "html":
                                    try:
                                        html_content = workflow.export_to_html()
                                        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
                                        temp_file.write(html_content)
                                        temp_file.close()
                                        filename = f"{file_stem}_translated.html"
                                        media_type = MEDIA_TYPES.get(file_type, "text/html; charset=utf-8")
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated revised HTML file from DOCX: {temp_file.name} (size: {os.path.getsize(temp_file.name)} bytes)")
                                        return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                                    except Exception as html_error:
                                        logger.error(LogModule.EXPORT, f"Failed to export HTML for task {task_id}: {html_error}", exc_info=True)
                                        raise HTTPException(
                                            status_code=500,
                                            detail=f"Failed to export HTML: {str(html_error)}"
                                        )
                        
                                elif file_type == "docx":
                                    try:
                                        docx_content = workflow.export_to_docx()
                                        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                                        temp_file.write(docx_content)
                                        temp_file.close()
                                        filename = f"{file_stem}_translated.docx"
                                        media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                        
                                        # Export debug folder with segment source and target texts
                                        try:
                                            self._export_debug_segments(task_id, task_state, temp_file.name)
                                        except Exception as debug_error:
                                            logger.warning(LogModule.EXPORT, f"Failed to export debug segments for task {task_id}: {debug_error}", exc_info=True)
                                    except Exception as docx_error:
                                        logger.error(LogModule.EXPORT, f"Failed to export DOCX for task {task_id}: {docx_error}", exc_info=True)
                                        raise HTTPException(
                                            status_code=500,
                                            detail=f"Failed to export DOCX: {str(docx_error)}"
                                        )
                        
                                elif file_type == "pptx":
                                    try:
                                        # PPTX workflow: get translated content directly
                                        pptx_content = workflow.document_translated.content
                                        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.pptx', delete=False)
                                        temp_file.write(pptx_content)
                                        temp_file.close()
                                        filename = f"{file_stem}_translated.pptx"
                                        media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
                                    except Exception as pptx_error:
                                        logger.error(LogModule.EXPORT, f"Failed to export PPTX for task {task_id}: {pptx_error}", exc_info=True)
                                        raise HTTPException(
                                            status_code=500,
                                            detail=f"Failed to export PPTX: {str(pptx_error)}"
                                        )
                        
                                elif file_type == "pdf":
                                    # For PDF files, only use layout-based generation (high-fidelity, no fallback)
                                    # BUT: For MOBI/EPUB workflows, PDF should already have been generated via HTML-to-PDF.
                                    workflow_type = task_state.get("workflow_type") or task_state.get("payload", {}).get("workflow_type")
                                    if workflow_type in ("mobi", "epub"):
                                        existing_pdf = task_state.get("downloadable_files", {}).get("pdf")
                                        if existing_pdf:
                                            pdf_path = existing_pdf.get("path", "") if isinstance(existing_pdf, dict) else str(existing_pdf)
                                            if pdf_path and os.path.exists(pdf_path):
                                                filename = os.path.basename(pdf_path) or f"{file_stem}_translated.pdf"
                                                media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated PDF for MOBI/EPUB workflow (regenerate branch): {pdf_path}")
                                                return FileResponse(path=pdf_path, media_type=media_type, filename=filename)
                                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] Pre-generated PDF not found for MOBI/EPUB workflow in regenerate branch.")
                                        raise HTTPException(
                                            status_code=404,
                                            detail="PDF file not found for MOBI/EPUB workflow. It should have been generated earlier."
                                        )

                                    original_filename = task_state.get("original_filename", "")
                                    is_pdf_file = original_filename.lower().endswith('.pdf')
                                    
                                    if is_pdf_file:
                                        # Check if layout_document is available (required for PDF files)
                                        layout_doc = task_state.get("layout_document")
                                        has_layout = False
                                        if layout_doc is not None:
                                            try:
                                                from layout.base import LayoutDocument as _LD
                                                if isinstance(layout_doc, _LD):
                                                    has_layout = True
                                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Layout document available for high-fidelity PDF generation")
                                            except Exception:
                                                pass
                                        
                                        if not has_layout:
                                            logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF file detected but layout_document not available. Cannot generate high-fidelity PDF.")
                                            raise HTTPException(
                                                status_code=404,
                                                detail="High-fidelity PDF generation requires layout information, which is not available for this task. Please ensure the file was processed with a layout-aware converter (e.g., MinerU)."
                                            )
                                    
                                    # Always generate PDF via layout (no pre-generated fallback so errors surface).
                                    # Generate PDF using layout-based method (high-fidelity)
                                    try:
                                        output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                                        output_dir.mkdir(exist_ok=True)
                                        await self.pdf_generator.generate(workflow, output_dir, file_stem, task_state, task_id, table_body_format=table_body_format, equation_format=equation_format)
                                        gen_pdf = task_state.get("downloadable_files", {}).get("pdf")
                                        if gen_pdf and os.path.exists(gen_pdf.get("path", "")):
                                            filename = os.path.basename(gen_pdf["path"]) or f"{file_stem}_translated.pdf"
                                            media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                            return FileResponse(path=gen_pdf["path"], media_type=media_type, filename=filename)
                                        
                                        # Also check if PDF file exists in output_dir
                                        pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
                                        if pdf_file_path.exists():
                                            filename = f"{file_stem}_translated.pdf"
                                            media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                            return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
                                    except NotImplementedError as not_impl_error:
                                        # Windows asyncio limitation - check if PDF was still generated
                                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] NotImplementedError during PDF generation (Windows asyncio limitation): {not_impl_error}")
                                        output_dir = Path(task_state.get("temp_dir") or tempfile.gettempdir()) / "output"
                                        pdf_file_path = output_dir / f"{file_stem}_translated.pdf"
                                        gen_pdf = task_state.get("downloadable_files", {}).get("pdf")
                                        
                                        if gen_pdf and os.path.exists(gen_pdf.get("path", "")):
                                            filename = os.path.basename(gen_pdf["path"]) or f"{file_stem}_translated.pdf"
                                            media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] PDF generated successfully despite NotImplementedError")
                                            return FileResponse(path=gen_pdf["path"], media_type=media_type, filename=filename)
                                        elif pdf_file_path.exists():
                                            filename = f"{file_stem}_translated.pdf"
                                            media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] PDF generated successfully despite NotImplementedError (found in output_dir)")
                                            return FileResponse(path=str(pdf_file_path), media_type=media_type, filename=filename)
                                        else:
                                            logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF was not generated despite NotImplementedError")
                                            raise HTTPException(
                                                status_code=500,
                                                detail="PDF generation failed due to platform limitations. Please try again or contact support."
                                            )
                                    except Exception as _pdf_e:
                                        logger.error(LogModule.EXPORT, f"High-fidelity PDF generation on download failed for task {task_id}: {_pdf_e}", exc_info=True)
                                        raise HTTPException(
                                            status_code=500,
                                            detail=f"High-fidelity PDF generation failed: {str(_pdf_e)}"
                                        )
                                
                                    # If we reach here, PDF was not generated
                                    raise HTTPException(
                                        status_code=500,
                                        detail="PDF generation failed. Please try again or contact support."
                                    )
                        
                            else:
                                logger.warning(LogModule.EXPORT, f"File type {file_type} not supported for DOCX revision rebuild, using original file")
                                has_revisions = False
                        
                            if temp_file and os.path.exists(temp_file.name):
                                logger.info(LogModule.EXPORT, f"Generated revised {file_type} file from DOCX: {temp_file.name}")
                                return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                            else:
                                logger.error(LogModule.EXPORT, f"Failed to generate revised {file_type} file from DOCX, falling back to original")
                                has_revisions = False
                        else:
                            logger.error(LogModule.EXPORT, f"Failed to rebuild DOCX document, falling back to original file")
                            has_revisions = False
                    else:
                        logger.warning(LogModule.EXPORT, f"Original file not found for DOCX rebuild, using original file")
                        has_revisions = False
                else:
                    # Other workflow types - not yet implemented for revision rebuild
                    logger.info(LogModule.EXPORT, f"Revision rebuild not yet implemented for workflow type: {workflow_type}, using original file")
                    has_revisions = False
                
            except Exception as e:
                logger.error(LogModule.EXPORT, f"Error rebuilding document from segments: {e}", exc_info=True)
                # Fall through to original file logic
                has_revisions = False
    
        # Original logic: return the pre-generated file
        if not has_revisions:
            # Special handling for PDF files - only use layout-based generation (high-fidelity)
            if file_type == "pdf":
                # For PDF files, only use layout-based generation (high-fidelity, no fallback to HTML-to-PDF)
                original_filename = task_state.get("original_filename", "")
                is_pdf_file = original_filename.lower().endswith('.pdf')
            
                if is_pdf_file:
                    # Check if layout_document is available (required for PDF files)
                    layout_doc = task_state.get("layout_document")
                    has_layout = False
                    if layout_doc is not None:
                        try:
                            from layout.base import LayoutDocument as _LD
                            if isinstance(layout_doc, _LD):
                                has_layout = True
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Layout document available for high-fidelity PDF generation")
                        except Exception:
                            pass
                
                    if not has_layout:
                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] PDF file detected but layout_document not available. Cannot generate high-fidelity PDF.")
                        raise HTTPException(
                            status_code=404,
                            detail="High-fidelity PDF generation requires layout information, which is not available for this task. Please ensure the file was processed with a layout-aware converter (e.g., MinerU)."
                        )
                
                    # No pre-generated PDF: always generate via Pandoc+XeLaTeX so layout/format errors surface for fixing.
                    # Prefer pandoc path (MD → XeLaTeX → PDF) when we have rebuilt MD from segments
                    rebuilt_md = task_state.pop("_rebuilt_md_for_pdf", None)
                    if rebuilt_md and rebuilt_md.strip():
                        return _pandoc_pdf_file_response_from_md(
                            task_state,
                            task_id,
                            rebuilt_md,
                            equation_format,
                            table_body_format,
                        )

                    # Rebuild Markdown from segments + Pandoc (same as revision download when layout PDF is off)
                    try:
                        rebuilt_doc = rebuild_markdown_document_from_segments(
                            task_state,
                            file_stem=task_state.get("original_filename_stem"),
                            equation_format=equation_format,
                            table_body_format=table_body_format,
                        )
                        if rebuilt_doc and getattr(rebuilt_doc, "content", None):
                            raw = rebuilt_doc.content
                            md_text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                            if md_text.strip():
                                return _pandoc_pdf_file_response_from_md(
                                    task_state,
                                    task_id,
                                    md_text,
                                    equation_format,
                                    table_body_format,
                                )
                    except Exception as pdf_seg_err:
                        logger.error(
                            LogModule.EXPORT,
                            f"[DOWNLOAD] PDF on-demand: rebuild+pandoc failed task_id={task_id}: {pdf_seg_err}",
                            exc_info=True,
                        )

                    raise HTTPException(
                        status_code=500,
                        detail="PDF export requires rebuilt Markdown from translation segments. Ensure the task has completed translation and layout data is available, then try again."
                    )
                else:
                    # Non-PDF file requesting PDF.
                    # Special case: MOBI/EPUB workflows are allowed to download generated PDFs (HTML-to-PDF).
                    if workflow_type in ("mobi", "epub"):
                        existing_pdf = task_state.get("downloadable_files", {}).get("pdf")
                        if existing_pdf:
                            pdf_path = existing_pdf.get("path", "") if isinstance(existing_pdf, dict) else str(existing_pdf)
                            if pdf_path and os.path.exists(pdf_path):
                                file_path = pdf_path
                                filename = os.path.basename(file_path) or f"{file_stem}_translated.pdf"
                                media_type = MEDIA_TYPES.get(file_type, "application/pdf")
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Returning generated PDF for MOBI/EPUB original file: {file_path}")
                                return FileResponse(path=file_path, media_type=media_type, filename=filename)
                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] Generated PDF not found for MOBI/EPUB original file. Original filename: {original_filename}")
                        raise HTTPException(
                            status_code=404,
                            detail="Generated PDF not found for MOBI/EPUB workflow. It should have been generated earlier."
                        )
                    
                    # For other original file types, PDF download is not supported
                    raise HTTPException(
                        status_code=404,
                        detail=f"PDF download is only available for PDF files. Original file type: {original_filename}"
                    )
        
            # Special handling for MD: if there were revisions but rebuild failed, or MD file doesn't exist, try to regenerate
            elif file_type == "md" or file_type == "markdown":
                # Check if MD file exists
                file_info = task_state.get("downloadable_files", {}).get(file_type)
                md_exists = file_info and os.path.exists(file_info.get("path"))
            
                # Check if equation_format parameter is provided (for PDF files with layout)
                # If provided, regenerate MD from layout_document with the specified equation_format
                should_regenerate_from_layout = False
                if equation_format:
                    original_filename = task_state.get("original_filename", "")
                    is_pdf_file = original_filename.lower().endswith('.pdf')
                    layout_doc = task_state.get("layout_document")
                    if is_pdf_file and layout_doc:
                        should_regenerate_from_layout = True
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Regenerating MD from layout_document with equation_format={equation_format}")
            
                logger.info(LogModule.EXPORT, f"[DOWNLOAD] MD file check for task {task_id}: md_exists={md_exists}, has_revisions_original={has_revisions_original}, should_regenerate_from_layout={should_regenerate_from_layout}")
            
                # If equation_format is provided and we have layout_document, regenerate from layout
                if should_regenerate_from_layout:
                    try:
                        from layout.base import LayoutDocument as _LD
                        from layout.markdown_builder import LayoutMarkdownBuilder
                    
                        if not isinstance(layout_doc, _LD):
                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Invalid layout_document type for task {task_id}")
                            should_regenerate_from_layout = False
                        else:
                            # Get chunk_size and deep_split from task_state
                            chunk_size = task_state.get("segments_metadata", {}).get("chunk_size")
                            if chunk_size is None:
                                payload = task_state.get("payload")
                                if payload:
                                    if isinstance(payload, dict):
                                        chunk_size = payload.get("chunk_size")
                                    else:
                                        chunk_size = getattr(payload, 'chunk_size', None)
                            if chunk_size is None:
                                chunk_size = 3000  # Default
                        
                            deep_split_enabled = task_state.get("deep_split", True)
                            payload = task_state.get("payload")
                            if payload:
                                if isinstance(payload, dict):
                                    deep_split_enabled = bool(payload.get("deep_split", True))
                                else:
                                    deep_split_enabled = bool(getattr(payload, 'deep_split', True))
                        
                            # Validate equation_format
                            eq_format = (equation_format or "text").lower().strip()
                            if eq_format not in ("text", "latex", "image"):
                                eq_format = "text"
                        
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Regenerating MD from layout with equation_format={eq_format}, chunk_size={chunk_size}, deep_split={deep_split_enabled}")
                        
                            # CRITICAL: Check if we have translation segments (translated content)
                            # If yes, we should rebuild from translated segments with new format, not from original layout
                            segments_data = task_state.get("translation_segments")
                            has_translated_segments = segments_data and segments_data.get("segments")
                            
                            if has_translated_segments:
                                # For translation tasks, rebuild from translated segments with new format parameters
                                # This ensures we use translated content, not original content
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Found translation segments, will rebuild from translated segments with format parameters")
                                from utils.document_rebuild import rebuild_markdown_document_from_segments
                                
                                # Rebuild from translated segments (this uses target_text, not source_text)
                                rebuilt_doc = rebuild_markdown_document_from_segments(
                                    task_state,
                                    file_stem=task_state.get("original_filename_stem"),
                                    equation_format=eq_format,
                                    table_body_format=table_body_format.lower() if table_body_format else None,
                                )
                                
                                if rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                                    # Decode bytes to string if needed
                                    md_content = rebuilt_doc.content
                                    if isinstance(md_content, bytes):
                                        md_content = md_content.decode('utf-8')
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Rebuilt MD from translated segments (size: {len(md_content)} characters)")
                                    # layout_result is not needed when using rebuilt_doc from segments
                                    layout_result = None
                                else:
                                    logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to rebuild from segments, falling back to layout regeneration")
                                    # Fallback to layout regeneration (but this will be original text)
                                    builder = LayoutMarkdownBuilder(
                                        max_chunk_chars=chunk_size,
                                        deep_split=deep_split_enabled,
                                        equation_format=eq_format
                                    )
                                    layout_result = builder.build(layout_doc)
                                    md_content = layout_result.markdown_text
                            else:
                                # No translation segments available, use layout regeneration (for format conversion tasks)
                                builder = LayoutMarkdownBuilder(
                                    max_chunk_chars=chunk_size,
                                    deep_split=deep_split_enabled,
                                    equation_format=eq_format
                                )
                                layout_result = builder.build(layout_doc)
                                md_content = layout_result.markdown_text
                        
                            # Build image_data_map from layout_result chunks (if available)
                            # When using rebuilt_doc from segments, layout_result may be None
                            image_data_map: dict[str, dict[str, str]] = {}
                            existing_image_map = task_state.get("image_data_map")
                            if isinstance(existing_image_map, dict):
                                image_data_map.update({
                                    str(k): {
                                        "data": (v or {}).get("data", ""),
                                        "alt": (v or {}).get("alt", ""),
                                    }
                                    for k, v in existing_image_map.items()
                                })
                            
                            # Read images from MinerU ZIP
                            zip_bytes = task_state.get("layout_source_zip")
                            zip_file = None
                            zip_entry_map: dict[str, str] = {}
                            if zip_bytes:
                                try:
                                    zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
                                    zip_entries = zip_file.namelist()
                                    zip_entry_map = {
                                        name.replace("\\", "/"): name for name in zip_entries
                                    }
                                except Exception as zip_error:
                                    logger.debug(LogModule.EXPORT, f"[DOWNLOAD] Failed to open MinerU ZIP for images: {zip_error}", )
                                    zip_file = None
                            
                            def _normalize_image_path(path: str | None) -> str | None:
                                if not path:
                                    return None
                                return path.replace("\\", "/").lstrip("./")
                            
                            placeholder_cache: dict[str, str] = {}
                            
                            def _read_image_data_uri(image_path: str | None) -> str | None:
                                if not image_path or zip_file is None:
                                    return None
                                normalized = _normalize_image_path(image_path)
                                if not normalized:
                                    return None
                                if normalized in placeholder_cache:
                                    return placeholder_cache[normalized]
                                
                                candidate = zip_entry_map.get(normalized)
                                if candidate is None:
                                    filename_only = os.path.basename(normalized)
                                    for name, original in zip_entry_map.items():
                                        if name == filename_only or name.endswith('/' + filename_only) or name.endswith('\\' + filename_only):
                                            candidate = original
                                            break
                                        if name.endswith('/images/' + filename_only) or name.endswith('\\images\\' + filename_only):
                                            candidate = original
                                            break
                                if not candidate:
                                    return None
                                try:
                                    raw_bytes = zip_file.read(candidate)
                                except KeyError:
                                    return None
                                mime = mimetypes.guess_type(candidate)[0] or "image/png"
                                data_uri = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                                placeholder_cache[normalized] = data_uri
                                return data_uri
                            
                            # Process chunks to build image_data_map
                            # Only if layout_result is available (not when using rebuilt_doc from segments)
                            if layout_result is not None and hasattr(layout_result, 'chunks') and layout_result.chunks:
                                for idx, chunk in enumerate(layout_result.chunks):
                                    if chunk.chunk_type == "image":
                                        placeholder_id = chunk.image_placeholder or f"layoutimg{idx}"
                                        alt_text = chunk.image_alt or (chunk.image_path or "Image")
                                        data_uri = _read_image_data_uri(chunk.image_path)
                                        image_data_map[placeholder_id] = {
                                            "data": data_uri or "",
                                            "alt": alt_text or "Image",
                                        }
                                        if chunk.image_path and data_uri:
                                            filename_key = (
                                                chunk.image_path.split('/')[-1].split('\\')[-1]
                                                if '/' in chunk.image_path or '\\' in chunk.image_path
                                                else chunk.image_path
                                            )
                                            if filename_key not in image_data_map:
                                                image_data_map[filename_key] = {
                                                    "data": data_uri,
                                                    "alt": chunk.image_path,
                                                }
                            else:
                                # When using rebuilt_doc from segments, try to get image mapping from existing image_data_map
                                existing_image_map = task_state.get("image_data_map")
                                if isinstance(existing_image_map, dict):
                                    # Merge existing image mappings
                                    for ph_id, img_data in existing_image_map.items():
                                        if ph_id not in image_data_map:
                                            image_data_map[str(ph_id)] = {
                                                "data": (img_data or {}).get("data", ""),
                                                "alt": (img_data or {}).get("alt", str(ph_id)),
                                            }
                            
                            file_stem = task_state.get("original_filename_stem", "translated")
                            if image_data_map:
                                task_state["image_data_map"] = _merge_image_data_maps(
                                    _image_data_map_from_task_state(task_state),
                                    image_data_map,
                                )
                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Regenerated MD from layout equation_format={eq_format}, len={len(md_content)}",
                            )
                            return _file_response_for_md_download(
                                md_content,
                                task_state,
                                file_stem,
                                embed_images,
                                equation_format,
                                table_body_format,
                            )
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to regenerate MD from layout with equation_format: {e}, falling back to normal regeneration", exc_info=True)
                        should_regenerate_from_layout = False
            
                # If there were revisions or MD doesn't exist, try to regenerate
                should_regenerate = has_revisions_original or not md_exists
            
                if should_regenerate:
                    # Priority 1: Try to regenerate from segments (works for both revised and non-revised cases)
                    # This is the most reliable method as it uses the actual translation segments
                    segments_data = task_state.get("translation_segments")
                    wt_export = resolve_task_export_workflow_type(task_state)
                    # XLSX/PPTX/HTML: translated content is HTML with real <table>; segment rebuild uses
                    # flattened cell lines (HtmlExtractor / grid) and destroys GFM tables in exported MD.
                    skip_segment_md_for_tables = wt_export in ("xlsx", "pptx", "html")
                    if skip_segment_md_for_tables:
                        logger.info(
                            LogModule.EXPORT,
                            f"[DOWNLOAD] Skipping segment-based MD rebuild for {wt_export} (use HTML table path); task_id={task_id}",
                        )
                    if segments_data and not skip_segment_md_for_tables:
                        segments = segments_data.get("segments", [])
                        if segments:  # Only try if we have actual segments
                            try:
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Attempting to regenerate MD directly from segments for task {task_id} "
                                          f"(has_revisions_original: {has_revisions_original}, segments count: {len(segments)})")
                                # Format-restore stats: ratio of segments carrying separator_after
                                try:
                                    non_null_seps = sum(1 for s in segments if s.get('separator_after') is not None)
                                    total_segs = len(segments)
                                    ratio = (non_null_seps / total_segs) if total_segs else 0
                                    task_state.setdefault('format_restore_stats', {})['separator_ratio'] = ratio
                                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Format-restore separator ratio: {ratio:.2%} ({non_null_seps}/{total_segs})")
                                except Exception:
                                    pass
                                # Rebuild document directly from segments (works even without revisions)
                                rebuilt_doc = rebuild_markdown_document_from_segments(
                                    task_state,
                                    file_stem=task_state.get("original_filename_stem"),
                                    equation_format=equation_format,
                                    table_body_format=table_body_format,
                                )
                                if rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                                    # Decode bytes to string if needed
                                    md_content = rebuilt_doc.content
                                    if isinstance(md_content, bytes):
                                        md_content = md_content.decode('utf-8')
                                    if md_content:  # Ensure content is not empty
                                        file_stem = task_state.get("original_filename_stem", "translated")
                                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD from segments (size: {len(md_content)} characters)")
                                        return _file_response_for_md_download(
                                            md_content,
                                            task_state,
                                            file_stem,
                                            embed_images,
                                            equation_format,
                                            table_body_format,
                                        )
                                    else:
                                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Rebuilt document content is empty")
                            except Exception as e:
                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to regenerate MD from segments: {e}, trying HTML fallback", exc_info=True)
                        else:
                            logger.warning(LogModule.EXPORT, f"[DOWNLOAD] No segments found in segments_data, trying HTML fallback")
                    elif not segments_data:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] No segments_data found, trying HTML fallback")

                    # HTML workflow with revisions: rebuild translated HTML from html_translated_texts
                    # so that retranslated / edited segments are reflected in exported MD.
                    if wt_export == "html" and has_revisions_original:
                        try:
                            html_rebuilt = _rebuild_html_from_task_state(task_state)
                            if html_rebuilt:
                                from workflow.html_to_markdown_export import html_content_to_markdown
                                md_content = html_content_to_markdown(html_rebuilt)
                                if md_content and md_content.strip():
                                    file_stem = task_state.get("original_filename_stem", "translated")
                                    logger.info(
                                        LogModule.EXPORT,
                                        f"[DOWNLOAD] Rebuilt MD from html_translated_texts "
                                        f"(chars={len(md_content)}); task_id={task_id} wt={wt_export}",
                                    )
                                    return _file_response_for_md_download(
                                        md_content,
                                        task_state,
                                        file_stem,
                                        embed_images,
                                        equation_format,
                                        table_body_format,
                                    )
                        except Exception as e:
                            logger.warning(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] HTML workflow revision rebuild failed task_id={task_id}: {e}",
                                exc_info=True,
                            )

                    html_file_info = task_state.get("downloadable_files", {}).get("html")
                    html_path = html_file_info.get("path") if isinstance(html_file_info, dict) else None
                    if not html_path and html_file_info:
                        html_path = str(html_file_info)
                    html_on_disk = bool(html_path and os.path.isfile(html_path))
                    orig_lower = (task_state.get("original_filename") or "").lower()
                    prefer_disk_html_md_first = wt_export in ("xlsx", "pptx", "html") or orig_lower.endswith(
                        (".xlsx", ".xls", ".pptx", ".ppt", ".html", ".htm")
                    )

                    def _markdown_from_saved_html() -> Optional[str]:
                        if not html_on_disk or not html_path:
                            return None
                        try:
                            with open(html_path, "r", encoding="utf-8-sig") as f:
                                html_body = f.read()
                            from workflow.html_to_markdown_export import html_content_to_markdown

                            return html_content_to_markdown(html_body)
                        except Exception as ex:
                            logger.warning(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] MD from saved HTML failed task_id={task_id}: {ex}",
                                exc_info=True,
                            )
                            return None

                    # XLSX/PPTX: saved translated HTML is authoritative — in-memory workflow may lack full document_translated.
                    if prefer_disk_html_md_first and html_on_disk:
                        disk_md = _markdown_from_saved_html()
                        disk_stripped = (disk_md or "").strip()
                        try:
                            html_sz_check = os.path.getsize(html_path) if html_path else 0
                        except OSError:
                            html_sz_check = 0
                        md_too_small_vs_html = (
                            html_sz_check > 4000 and len(disk_stripped) < max(400, html_sz_check // 200)
                        )
                        if md_too_small_vs_html and disk_stripped:
                            logger.warning(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] disk HTML→MD looks truncated (md_chars={len(disk_stripped)} "
                                f"vs html_bytes={html_sz_check}); not using this MD; task_id={task_id} wt={wt_export}",
                            )
                        elif disk_stripped and not md_too_small_vs_html:
                            file_stem = task_state.get("original_filename_stem", "translated")
                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] MD from saved HTML (chars={len(disk_md)}); task_id={task_id} wt={wt_export}",
                            )
                            return _file_response_for_md_download(
                                disk_md,
                                task_state,
                                file_stem,
                                embed_images,
                                equation_format,
                                table_body_format,
                            )
                        if not disk_stripped:
                            logger.warning(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] saved HTML produced empty MD, trying workflow; task_id={task_id} wt={wt_export}",
                            )

                    # Priority 2: workflow export_to_markdown (may be stale for xlsx/pptx; see HTML fallback below)
                    md_content: Optional[str] = None
                    workflow_instance = task_state.get("workflow_instance")
                    if workflow_instance and hasattr(workflow_instance, "export_to_markdown"):
                        try:
                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Generating MD from workflow.export_to_markdown() for task {task_id}",
                            )
                            md_content = workflow_instance.export_to_markdown()
                        except Exception as e:
                            logger.warning(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Failed to generate MD from workflow.export_to_markdown(): {e}, trying HTML fallback",
                                exc_info=True,
                            )

                    if md_content and html_on_disk and html_path:
                        try:
                            html_sz = os.path.getsize(html_path)
                            md_sz = len((md_content or "").strip().encode("utf-8"))
                            if html_sz > 500 and md_sz < min(500, max(80, html_sz // 20)):
                                logger.warning(
                                    LogModule.EXPORT,
                                    f"[DOWNLOAD] workflow MD too small (bytes≈{md_sz}) vs saved HTML ({html_sz} bytes); "
                                    f"prefer disk HTML; task_id={task_id} wt_export={wt_export}",
                                )
                                md_content = None
                        except OSError as oe:
                            logger.debug(LogModule.EXPORT, f"[DOWNLOAD] stat HTML for MD sanity check: {oe}")

                    if md_content and (md_content if isinstance(md_content, str) else "").strip():
                        file_stem = task_state.get("original_filename_stem", "translated")
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD from workflow.export_to_markdown()")
                        return _file_response_for_md_download(
                            md_content,
                            task_state,
                            file_stem,
                            embed_images,
                            equation_format,
                            table_body_format,
                        )

                    # Priority 3: Regenerate MD from saved HTML (same pipeline as XlsxWorkflow.export_to_markdown)
                    if html_on_disk and html_path:
                        try:
                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Regenerating MD from HTML for task {task_id} "
                                f"(has_revisions_original: {has_revisions_original}, md_exists: {md_exists})",
                            )
                            text_content = _markdown_from_saved_html()
                            if text_content is None:
                                raise RuntimeError("html to markdown returned None")
                            if not (text_content or "").strip():
                                raise RuntimeError("empty markdown from saved HTML")
                            file_stem = task_state.get("original_filename_stem", "translated")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully generated MD from HTML via html_content_to_markdown")
                            return _file_response_for_md_download(
                                text_content,
                                task_state,
                                file_stem,
                                embed_images,
                                equation_format,
                                table_body_format,
                            )
                        except Exception as e:
                            logger.error(LogModule.EXPORT, f"Failed to generate MD from HTML: {e}", exc_info=True)
                            # If regeneration failed but MD exists, fall through to return existing MD
                            if md_exists:
                                logger.warning(LogModule.EXPORT, f"[DOWNLOAD] MD regeneration failed, falling back to existing MD")
                            else:
                                raise HTTPException(status_code=500, detail=f"Failed to generate MD: {str(e)}")
            
                # MD exists and no need to regenerate, return it (or ZIP when embed_images=false / md_zip)
                if md_exists:
                    if embed_images is False:
                        file_stem = task_state.get("original_filename_stem", "translated")
                        with open(file_info["path"], "r", encoding="utf-8-sig") as _mf:
                            md_body = _mf.read()
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Packaging cached MD as ZIP (embed_images=false)")
                        return _file_response_for_md_download(
                            md_body,
                            task_state,
                            file_stem,
                            embed_images,
                            equation_format,
                            table_body_format,
                        )
                    file_path = file_info["path"]
                    filename = file_info["filename"]
                    media_type = MEDIA_TYPES.get(file_type, "text/markdown; charset=utf-8")
                    return FileResponse(path=file_path, media_type=media_type, filename=filename)
                else:
                    # MD doesn't exist and we couldn't regenerate it
                    # Log detailed info for debugging
                    logger.error(LogModule.EXPORT, f"[DOWNLOAD] MD file not found for task {task_id}. "
                               f"downloadable_files keys: {list(task_state.get('downloadable_files', {}).keys())}, "
                               f"segments_data exists: {segments_data is not None}, "
                               f"html_file_info exists: {task_state.get('downloadable_files', {}).get('html') is not None}")
                    raise HTTPException(status_code=404,
                                        detail=f"Task '{task_id}' does not support downloading '{file_type}' type files. "
                                               f"MD file not found and cannot be regenerated (no segments or HTML available).")
        
            elif file_type == "html":
                html_info = task_state.get("downloadable_files", {}).get("html")
                html_path = ""
                if html_info:
                    html_path = html_info.get("path", "") if isinstance(html_info, dict) else str(html_info)
                
                # HTML workflow with revisions: rebuild translated HTML from html_translated_texts
                if workflow_type == "html" and has_revisions_original:
                    try:
                        html_rebuilt = _rebuild_html_from_task_state(task_state)
                        if html_rebuilt:
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(
                                mode="w", suffix=".html", delete=False, encoding="utf-8"
                            )
                            temp_file.write(html_rebuilt)
                            temp_file.close()
                            logger.info(
                                LogModule.EXPORT,
                                f"[DOWNLOAD] Rebuilt HTML from html_translated_texts "
                                f"(chars={len(html_rebuilt)}); task_id={task_id}",
                            )
                            return FileResponse(
                                path=temp_file.name,
                                media_type=MEDIA_TYPES.get("html", "text/html; charset=utf-8"),
                                filename=f"{file_stem}_translated.html",
                            )
                    except Exception as e:
                        logger.warning(
                            LogModule.EXPORT,
                            f"[DOWNLOAD] HTML workflow revision rebuild failed task_id={task_id}: {e}",
                            exc_info=True,
                        )
                
                if html_path and os.path.exists(html_path):
                    filename = html_info.get("filename") or os.path.basename(html_path)
                    media_type = MEDIA_TYPES.get(file_type, "text/html; charset=utf-8")
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated html: {html_path}")
                    return FileResponse(path=html_path, media_type=media_type, filename=filename)
                if workflow_type == "markdown_based":
                    html_resp = _markdown_based_html_file_response_from_segments(
                        task_state,
                        task_id,
                        equation_format,
                        table_body_format,
                    )
                    if html_resp is not None:
                        return html_resp
                    logger.error(
                        LogModule.EXPORT,
                        f"[DOWNLOAD] Task {task_id}: markdown_based HTML on-demand failed (no rebuilt document)",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Could not generate HTML from translation segments for this task.",
                    )

            # For other file types (HTML, DOCX, etc.), check if format parameters are provided
            # If format parameters are provided, regenerate the file with the new format
            # Otherwise, use the pre-generated file
            
            # Special handling for DOCX workflow: if docx file not in downloadable_files, try to get from workflow
            if workflow_type == "docx" and file_type == "docx":
                # First check downloadable_files
                file_info = task_state.get("downloadable_files", {}).get(file_type)
                if file_info and os.path.exists(file_info.get("path")):
                    file_path = file_info["path"]
                    filename = file_info.get("filename") or os.path.basename(file_path)
                    media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated {file_type} file: {file_path}")
                    return FileResponse(path=file_path, media_type=media_type, filename=filename)
                
                # If not in downloadable_files, try to get from workflow's translated document
                workflow_instance = task_state.get("workflow_instance")
                if workflow_instance and hasattr(workflow_instance, 'document_translated'):
                    try:
                        translated_doc = workflow_instance.document_translated
                        if translated_doc and hasattr(translated_doc, 'content'):
                            # Create temporary file from translated document
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                            if isinstance(translated_doc.content, bytes):
                                temp_file.write(translated_doc.content)
                            else:
                                temp_file.write(translated_doc.content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.docx"
                            media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated DOCX from workflow's translated document: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to get DOCX from workflow instance: {e}", exc_info=True)
                
                # If workflow instance doesn't have translated document, try to export from workflow
                if workflow_instance and hasattr(workflow_instance, 'export_to_docx'):
                    try:
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Attempting to export DOCX from workflow instance for task {task_id}")
                        docx_content = workflow_instance.export_to_docx()
                        if docx_content:
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                            if isinstance(docx_content, bytes):
                                temp_file.write(docx_content)
                            else:
                                temp_file.write(docx_content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.docx"
                            media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully exported DOCX from workflow: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to export DOCX from workflow instance: {e}", exc_info=True)
                
                # If workflow instance doesn't have translated document, try original file path
                original_file_path = task_state.get("original_file_path")
                if original_file_path and os.path.exists(original_file_path):
                    filename = os.path.basename(original_file_path) or f"{task_state.get('original_filename_stem', 'translated')}_translated.docx"
                    media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using original DOCX file as fallback: {original_file_path}")
                    return FileResponse(path=original_file_path, media_type=media_type, filename=filename)
                
                # Last resort: log error and raise 404 with helpful message
                logger.error(LogModule.EXPORT, f"[DOWNLOAD] Task {task_id}: Cannot find DOCX file. "
                           f"downloadable_files keys: {list(task_state.get('downloadable_files', {}).keys())}, "
                           f"workflow_instance exists: {workflow_instance is not None}, "
                           f"original_file_path: {task_state.get('original_file_path')}")
            
            # Special handling for MOBI workflow: if mobi file not in downloadable_files, try to get from workflow
            if workflow_type == "mobi" and file_type == "mobi":
                # First check downloadable_files
                file_info = task_state.get("downloadable_files", {}).get(file_type)
                if file_info and os.path.exists(file_info.get("path")):
                    file_path = file_info["path"]
                    filename = file_info.get("filename") or os.path.basename(file_path)
                    media_type = MEDIA_TYPES.get(file_type, "application/x-mobipocket-ebook")
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated {file_type} file: {file_path}")
                    return FileResponse(path=file_path, media_type=media_type, filename=filename)
                
                # If not in downloadable_files, try to get from workflow's translated document
                workflow_instance = task_state.get("workflow_instance")
                if workflow_instance and hasattr(workflow_instance, 'document_translated'):
                    try:
                        translated_doc = workflow_instance.document_translated
                        if translated_doc and hasattr(translated_doc, 'content'):
                            # Create temporary file from translated document
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.mobi', delete=False)
                            if isinstance(translated_doc.content, bytes):
                                temp_file.write(translated_doc.content)
                            else:
                                temp_file.write(translated_doc.content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.mobi"
                            media_type = MEDIA_TYPES.get(file_type, "application/x-mobipocket-ebook")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated MOBI from workflow's translated document: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to get MOBI from workflow instance: {e}", exc_info=True)
                
                # If workflow instance doesn't have translated document, try to export from workflow
                if workflow_instance and hasattr(workflow_instance, 'export_to_mobi'):
                    try:
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Attempting to export MOBI from workflow instance for task {task_id}")
                        mobi_content = workflow_instance.export_to_mobi()
                        if mobi_content:
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.mobi', delete=False)
                            if isinstance(mobi_content, bytes):
                                temp_file.write(mobi_content)
                            else:
                                temp_file.write(mobi_content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.mobi"
                            media_type = MEDIA_TYPES.get(file_type, "application/x-mobipocket-ebook")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully exported MOBI from workflow: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to export MOBI from workflow instance: {e}", exc_info=True)
            
            # Special handling for EPUB workflow: if epub file not in downloadable_files, try to get from workflow
            if workflow_type == "epub" and file_type == "epub":
                # First check downloadable_files
                file_info = task_state.get("downloadable_files", {}).get(file_type)
                if file_info and os.path.exists(file_info.get("path")):
                    file_path = file_info["path"]
                    filename = file_info.get("filename") or os.path.basename(file_path)
                    media_type = MEDIA_TYPES.get(file_type, "application/epub+zip")
                    logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated {file_type} file: {file_path}")
                    return FileResponse(path=file_path, media_type=media_type, filename=filename)
                
                # If not in downloadable_files, try to get from workflow's translated document
                workflow_instance = task_state.get("workflow_instance")
                if workflow_instance and hasattr(workflow_instance, 'document_translated'):
                    try:
                        translated_doc = workflow_instance.document_translated
                        if translated_doc and hasattr(translated_doc, 'content'):
                            # Create temporary file from translated document
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.epub', delete=False)
                            if isinstance(translated_doc.content, bytes):
                                temp_file.write(translated_doc.content)
                            else:
                                temp_file.write(translated_doc.content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.epub"
                            media_type = MEDIA_TYPES.get(file_type, "application/epub+zip")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Generated EPUB from workflow's translated document: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to get EPUB from workflow instance: {e}", exc_info=True)
                
                # If workflow instance doesn't have translated document, try to export from workflow
                if workflow_instance and hasattr(workflow_instance, 'export_to_epub'):
                    try:
                        logger.info(LogModule.EXPORT, f"[DOWNLOAD] Attempting to export EPUB from workflow instance for task {task_id}")
                        epub_content = workflow_instance.export_to_epub()
                        if epub_content:
                            file_stem = task_state.get("original_filename_stem", "translated")
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.epub', delete=False)
                            if isinstance(epub_content, bytes):
                                temp_file.write(epub_content)
                            else:
                                temp_file.write(epub_content.encode('utf-8'))
                            temp_file.close()
                            filename = f"{file_stem}_translated.epub"
                            media_type = MEDIA_TYPES.get(file_type, "application/epub+zip")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully exported EPUB from workflow: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to export EPUB from workflow instance: {e}", exc_info=True)
            
            # Special handling for TXT workflow: convert HTML or MD to DOCX on-demand
            if workflow_type == "txt" and file_type == "docx":
                logger.info(LogModule.EXPORT, f"[DOWNLOAD] TXT workflow requesting DOCX, converting from HTML or MD...")
                workflow_instance = task_state.get("workflow_instance")
                
                # Try to get HTML content from workflow
                if workflow_instance and hasattr(workflow_instance, 'export_to_html'):
                    try:
                        html_content = workflow_instance.export_to_html()
                        if html_content:
                            from utils.document_rebuild import convert_html_to_docx
                            to_lang, _ = _get_to_lang_and_docx_font(task_state, task_state.get("payload"))
                            
                            temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                            temp_file.close()
                            convert_html_to_docx(html_content, temp_file.name, to_lang=to_lang)
                            
                            if os.path.exists(temp_file.name):
                                file_stem = task_state.get("original_filename_stem", "translated")
                                filename = f"{file_stem}_translated.docx"
                                media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully converted HTML to DOCX for TXT workflow: {temp_file.name}")
                                return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as html_error:
                        logger.warning(LogModule.EXPORT, f"[DOWNLOAD] Failed to convert HTML to DOCX for TXT workflow: {html_error}, trying MD conversion", exc_info=True)
                
                # Fallback: try to convert from MD
                md_file_info = task_state.get("downloadable_files", {}).get("md")
                if md_file_info and os.path.exists(md_file_info.get("path")):
                    try:
                        from utils.document_rebuild import convert_html_to_docx
                        
                        # Read MD content and convert to HTML first, then to DOCX
                        md_path = md_file_info.get("path")
                        with open(md_path, 'r', encoding='utf-8') as f:
                            md_content = f.read()
                        
                        # Convert MD to HTML (simple conversion)
                        html_content = f"<html><body><pre>{md_content}</pre></body></html>"
                        
                        to_lang, _ = _get_to_lang_and_docx_font(task_state, task_state.get("payload"))
                        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False)
                        temp_file.close()
                        convert_html_to_docx(html_content, temp_file.name, to_lang=to_lang)
                        
                        if os.path.exists(temp_file.name):
                            file_stem = task_state.get("original_filename_stem", "translated")
                            filename = f"{file_stem}_translated.docx"
                            media_type = MEDIA_TYPES.get(file_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                            logger.info(LogModule.EXPORT, f"[DOWNLOAD] Successfully converted MD to DOCX for TXT workflow: {temp_file.name}")
                            return FileResponse(path=temp_file.name, media_type=media_type, filename=filename)
                    except Exception as md_error:
                        logger.error(LogModule.EXPORT, f"[DOWNLOAD] Failed to convert MD to DOCX for TXT workflow: {md_error}", exc_info=True)
                
                # If both HTML and MD conversion failed, raise 404
                logger.error(LogModule.EXPORT, f"[DOWNLOAD] TXT workflow: Cannot generate DOCX (HTML and MD conversion both failed)")
                raise HTTPException(
                    status_code=404,
                    detail=f"Task '{task_id}' (TXT workflow) cannot generate DOCX file. HTML and MD conversion both failed."
                )
            
            file_info = task_state.get("downloadable_files", {}).get(file_type)
        
            # Check if format parameters are provided (for HTML, MD, DOCX, PDF)
            has_format_params = (table_body_format is not None) or (equation_format is not None)
        
            # For format conversion tasks, if format parameters are provided, regenerate the file
            if is_format_conversion and has_format_params and file_type in {"html", "md", "docx"}:
                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Format parameters provided for {file_type}, regenerating file with new format")
                # This will be handled by the should_regenerate_from_layout logic above
                # But if that didn't catch it, we need to handle it here
                # For now, fall through to use pre-generated file if regeneration didn't happen
                # (The should_regenerate_from_layout logic should have handled this already)
                pass
        
            # Use pre-generated file if it exists and no format parameters are provided
            if file_info and os.path.exists(file_info.get("path")):
                file_path = file_info["path"]
                filename = file_info.get("filename") or os.path.basename(file_path)
                media_type = MEDIA_TYPES.get(file_type, "application/octet-stream")
                logger.info(LogModule.EXPORT, f"[DOWNLOAD] Using pre-generated {file_type} file: {file_path}")
                return FileResponse(path=file_path, media_type=media_type, filename=filename)
        
        # File doesn't exist
        raise HTTPException(status_code=404,
                            detail=f"Task '{task_id}' does not support downloading '{file_type}' type files, or files have been lost.")
    
    async def persist_completed_task_outputs_to_stash(self, task_id: str) -> Dict[str, Any]:
        """
        Rebuild export files from current in-memory task state and copy them into translation_result_stash
        (same as a successful download would record). Used so the queue can serve latest content after
        user edits or retry without requiring a browser download.
        """
        from backend.app.services.translation.translation_result_stash import record_generated_result

        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
        if (task_state.get("status") or "").lower() != "completed":
            raise HTTPException(
                status_code=400,
                detail="Task is not completed; cannot persist results.",
            )
        segs = task_state.get("translation_segments")
        if not isinstance(segs, dict) or not segs.get("segments"):
            raise HTTPException(
                status_code=400,
                detail="No translation segments available to export.",
            )

        plan = _build_stash_export_plan(task_state)
        if not plan:
            raise HTTPException(
                status_code=400,
                detail="Cannot determine export formats for this task.",
            )

        stashed: List[str] = []
        errors: List[str] = []

        for stash_key, download_ft, kwargs in plan:
            try:
                resp = await self.download_file(task_id, download_ft, **kwargs)
                path = getattr(resp, "path", None)
                ts = self.task_manager.get_task(task_id)
                if path and ts and os.path.isfile(str(path)):
                    record_generated_result(task_id, stash_key, str(path), ts)
                    stashed.append(stash_key)
                else:
                    errors.append(f"{stash_key}: missing or invalid output file")
            except Exception as e:
                err = f"{stash_key}: {e}"
                errors.append(err)
                logger.warning(
                    LogModule.EXPORT,
                    f"[PERSIST-STASH] task_id={task_id} {err}",
                    exc_info=True,
                )

        ok = len(stashed) > 0
        result: Dict[str, Any] = {
            "ok": ok,
            "stashed": stashed,
            "errors": errors,
        }
        if not ok:
            raise HTTPException(
                status_code=500,
                detail="Failed to persist any export to stash: " + "; ".join(errors[:5]),
            )
        logger.info(
            LogModule.EXPORT,
            f"[PERSIST-STASH] task_id={task_id} stored types={stashed}",
        )
        return result
    
    async def get_debug_file(
        self,
        task_id: str,
        file_type: str,
        table_body_format: Optional[str] = None
    ) -> FileResponse:
        """
        Get debug files for layout inspection.
        
            Args:
                task_id: Task identifier
                file_type: Debug file type ('html' or 'bbox')
                table_body_format: Optional table format override
            
            Returns:
                FileResponse with debug file content
            
        Raises:
            HTTPException: If task not found or debug file not available
        """
        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
        
        # 原始 PDF 导出调试选项已移除，避免暴露原文 PDF。
        if file_type == "original-pdf":
            raise HTTPException(
                status_code=400,
                detail="original-pdf debug export has been disabled.",
            )

        # Handle existing debug files (html, bbox)
        debug_files = task_state.get("debug_files", {})
        if not debug_files:
            raise HTTPException(status_code=404, detail=f"No debug files available for task '{task_id}'.")
        
        if file_type not in debug_files:
            raise HTTPException(status_code=404, detail=f"Debug file type '{file_type}' not available for task '{task_id}'. Available types: {list(debug_files.keys())}")
        
        file_path = debug_files[file_type]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Debug file not found: {file_path}")
        
        if file_type == "html":
            media_type = "text/html; charset=utf-8"
        elif file_type == "bbox":
            media_type = "application/json; charset=utf-8"
        else:
            media_type = "application/octet-stream"
        
        filename = os.path.basename(file_path)
        return FileResponse(path=file_path, media_type=media_type, filename=filename)
    
    def _export_debug_segments(self, task_id: str, task_state: Dict[str, Any], docx_file_path: str):
        """
        Export debug folder with segment source and target texts.
        
        Args:
            task_id: Task identifier
            task_state: Task state dictionary
            docx_file_path: Path to the exported DOCX file
        """
        try:
            # Get segments data
            segments_data = task_state.get("translation_segments")
            if not segments_data:
                logger.warning(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: No translation_segments found, skipping debug export")
                return
            
            # Handle both dict and list formats
            if isinstance(segments_data, dict):
                segments = segments_data.get("segments", [])
            elif isinstance(segments_data, list):
                segments = segments_data
            else:
                logger.warning(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: Invalid translation_segments format, skipping debug export")
                return
            
            if not segments:
                logger.warning(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: No segments found, skipping debug export")
                return
            
            # Create debug folder next to the DOCX file
            docx_path = Path(docx_file_path)
            debug_folder = docx_path.parent / f"{docx_path.stem}_debug"
            debug_folder.mkdir(exist_ok=True)
            
            logger.info(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: Exporting {len(segments)} segments to {debug_folder}")
            
            # Export each segment to a separate txt file
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                
                segment_index = segment.get("segment_index")
                if segment_index is None:
                    continue
                
                source_text = segment.get("source_text", "")
                target_text = segment.get("target_text", "")
                modified_text = segment.get("modified_text")
                is_excluded = segment.get("is_excluded", False)
                is_failed = segment.get("is_failed", False)
                exclusion_reason = segment.get("exclusion_reason")
                failure_reason = segment.get("failure_reason")
                
                # Use modified_text if available, otherwise use target_text
                final_target_text = modified_text if modified_text else target_text
                
                # Create segment file
                segment_file = debug_folder / f"segment_{segment_index:04d}.txt"
                with open(segment_file, 'w', encoding='utf-8') as f:
                    f.write(f"Segment Index: {segment_index}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    f.write("SOURCE TEXT:\n")
                    f.write("-" * 80 + "\n")
                    f.write(source_text if source_text else "(empty)\n")
                    f.write("\n\n")
                    
                    f.write("TARGET TEXT:\n")
                    f.write("-" * 80 + "\n")
                    f.write(final_target_text if final_target_text else "(empty)\n")
                    f.write("\n\n")
                    
                    # Add metadata
                    f.write("METADATA:\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"Modified: {segment.get('modified', False)}\n")
                    f.write(f"Is Excluded: {is_excluded}\n")
                    if exclusion_reason:
                        f.write(f"Exclusion Reason: {exclusion_reason}\n")
                    f.write(f"Is Failed: {is_failed}\n")
                    if failure_reason:
                        f.write(f"Failure Reason: {failure_reason}\n")
                    if segment.get("is_image"):
                        f.write(f"Is Image: True\n")
                    if segment.get("segment_info"):
                        seg_info = segment.get("segment_info", {})
                        if seg_info.get("is_table_cell"):
                            f.write(f"Table Cell: Table {seg_info.get('table_index')}, Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}\n")
                    f.write("\n")
            
            logger.info(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: Exported {len(segments)} segment files to {debug_folder}")
            
        except Exception as e:
            logger.error(LogModule.EXPORT, f"[DOWNLOAD-DEBUG] Task {task_id}: Failed to export debug segments: {e}", exc_info=True)
            # Don't raise exception - debug export failure shouldn't break download

