# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Service Layer Adapter

Provides a unified interface for MCP tools to call existing Owlangs services.
Handles path setup, lazy imports, error wrapping, and data transformation.
"""

import asyncio
import base64
import os
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_owlangs_root() -> str:
    """Get Owlangs project root directory."""
    root = os.environ.get("OWLANGS_ROOT")
    if root:
        return os.path.abspath(root)
    # Auto-detect from package location: backend/mcp_server/service_layer.py -> project root
    return str(Path(__file__).resolve().parent.parent.parent)


def _ensure_path(path: str):
    """Add a path to sys.path if not already present."""
    if path and path not in sys.path:
        sys.path.insert(0, path)


def setup_path():
    """Ensure all Owlangs paths are in sys.path for imports to work."""
    root = _get_owlangs_root()
    _ensure_path(root)
    os.environ.setdefault("OWLANGS_ROOT", root)

    # Add backend/ directory to sys.path for imports like `from ir.document import Document`
    # and `from utils.xxx import ...` that expect backend/ to be on sys.path.
    backend_dir = os.path.join(root, "backend")
    _ensure_path(backend_dir)

    # Pre-register the `utils` module alias BEFORE glossary imports.
    # backend/utils/__init__.py registers itself as sys.modules['utils'] when imported.
    # This must happen before any import of glossary modules, otherwise Python may
    # resolve `import utils` to backend/app/utils/ instead of backend/utils/.
    try:
        import backend.utils  # noqa: F401 — registers sys.modules["utils"]
        import backend.logger  # noqa: F401 — registers sys.modules["logger"]
        # Pre-register critical utils submodules so backend.app can import them
        import backend.utils.resource_utils  # noqa: F401 — registers sys.modules["utils.resource_utils"]
    except ImportError:
        pass


# Initialize module-level path setup so backend imports work in MCP context
setup_path()


# ── Translation Tools ──────────────────────────────────────────────────────────

def _resolve_platform_config(
    base_url: str, api_key: str, model_id: str
) -> tuple:
    """
    Resolve LLM platform configuration from backend defaults when not explicitly provided.

    When base_url is empty, looks up the default platform from the backend's
    platform configuration (platforms.json) and its API key (secrets.json),
    so the AI agent does not need to supply credentials manually.
    """
    if base_url:
        return base_url, api_key, model_id

    from backend.config.config_loader import get_unified_config

    try:
        cfg = get_unified_config()
        platform_id = cfg.ai_platforms_default_platform
        if not platform_id:
            return base_url, api_key, model_id

        platform_cfg = cfg.get_ai_platform_config(platform_id) or {}
        resolved_url = platform_cfg.get("url", "") or ""
        resolved_model = platform_cfg.get("model", "") or ""
        resolved_key = cfg.get_platform_api_key(platform_id) or ""

        return (
            resolved_url or base_url,
            resolved_key or api_key,
            resolved_model or model_id,
        )
    except Exception:
        return base_url, api_key, model_id


async def translate_file(
    file_content: Optional[str],
    file_path: Optional[str],
    file_name: str,
    to_lang: str,
    base_url: str = "",
    api_key: str = "",
    model_id: str = "",
    glossary: Optional[Dict[str, str]] = None,
    glossary_ids: Optional[List[str]] = None,
    glossary_generate: bool = False,
    convert_engine: Optional[str] = None,
    chunk_size: int = 0,
    concurrent: int = 3,
    temperature: float = 0.3,
    custom_prompt: Optional[str] = None,
    prompt_mode: Optional[str] = None,
    prompt_style: Optional[str] = None,
    deep_split: Optional[bool] = None,
    execution_mode: str = "immediate",
    skip_translate: bool = False,
) -> Dict[str, Any]:
    """Submit a document translation task."""
    from backend.app.services.translation import TranslationService
    from backend.app.services.task import task_manager
    from backend.app.models.service import (
        MarkdownWorkflowParams, DocxWorkflowParams, TextWorkflowParams,
        JsonWorkflowParams, XlsxWorkflowParams, HtmlWorkflowParams,
        SrtWorkflowParams, EpubWorkflowParams, MobiWorkflowParams,
        PptxWorkflowParams, QtTsWorkflowParams,
    )

    # Read file bytes
    file_bytes = _resolve_file_content(file_content, file_path)
    if file_bytes is None:
        return {"success": False, "message": "Either file_path or file_content is required"}

    # Resolve LLM platform from backend config when not explicitly provided
    base_url, api_key, model_id = _resolve_platform_config(base_url, api_key, model_id)

    # Build payload (workflow params model)
    payload = _build_translation_payload(
        file_name=file_name,
        to_lang=to_lang,
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        skip_translate=skip_translate,
        convert_engine=convert_engine,
        chunk_size=chunk_size,
        concurrent=concurrent,
        temperature=temperature,
        custom_prompt=custom_prompt,
        prompt_mode=prompt_mode,
        prompt_style=prompt_style,
        deep_split=deep_split,
        glossary_dict=glossary,
        glossary_generate_enable=glossary_generate,
    )

    task_id = uuid.uuid4().hex[:8]
    service = TranslationService(task_manager)

    try:
        response = await service.start_translation_task(
            task_id=task_id,
            payload=payload,
            file_contents=file_bytes,
            original_filename=file_name,
            execution_mode=execution_mode,
            owner_username=None,  # MCP is unauthenticated
        )

        # If glossary_ids provided, store them in task state for reference
        if glossary_ids and task_manager.get_task(task_id):
            task_manager.update_task(task_id, {
                "mcp_glossary_ids": glossary_ids,
            })

        return {
            "task_started": True,
            "task_id": task_id,
            "execution_mode": execution_mode,
            "message": "Translation task started successfully",
        }
    except Exception as e:
        return {
            "task_started": False,
            "task_id": task_id,
            "message": f"Failed to start translation task: {str(e)}",
        }


async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get translation task status."""
    from backend.app.services.task import task_manager

    task_state = task_manager.get_task(task_id)
    if task_state is None:
        return {
            "task_id": task_id,
            "status": "not_found",
            "message": "Task ID not found",
        }

    return {
        "task_id": task_id,
        "status": task_state.get("status", "unknown"),
        "progress": task_state.get("progress", 0),
        "message": task_state.get("message", ""),
        "is_processing": task_state.get("is_processing", False),
        "download_ready": task_state.get("download_ready", False),
        "error": task_state.get("error"),
    }


async def download_result(
    task_id: str,
    file_type: str = "target",
) -> Dict[str, Any]:
    """Download translation result as base64-encoded content."""
    import io

    from backend.app.services.task import task_manager
    from backend.app.services.download import DownloadService

    task_state = task_manager.get_task(task_id)
    if task_state is None:
        return {"success": False, "message": f"Task ID '{task_id}' not found."}

    service = DownloadService(task_manager)
    try:
        from fastapi.responses import FileResponse
        response = await service.download_file(task_id, file_type)

        if isinstance(response, FileResponse):
            file_path = response.path
            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                return {
                    "success": True,
                    "file_content": base64.b64encode(content).decode("utf-8"),
                    "file_name": response.filename or f"{task_id}_{file_type}",
                }
        elif hasattr(response, "body_iterator"):
            # StreamingResponse
            content_chunks = []
            async for chunk in response.body_iterator:
                content_chunks.append(chunk)
            content = b"".join(content_chunks) if content_chunks else b""
            filename = f"{task_id}_{file_type}"
            # Try to extract filename from content-disposition
            content_disposition = response.headers.get("content-disposition", "")
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[-1].strip('"\'')
            return {
                "success": True,
                "file_content": base64.b64encode(content).decode("utf-8") if content else "",
                "file_name": filename,
            }

        return {"success": False, "message": "Unexpected response type from download service"}
    except Exception as e:
        return {"success": False, "message": f"Download failed: {str(e)}"}


async def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a running translation task."""
    from backend.app.services.task import task_manager

    task_state = task_manager.get_task(task_id)
    if task_state is None:
        return {"success": False, "message": f"Task ID '{task_id}' not found."}

    status = task_state.get("status", "")
    if status in ("completed", "failed", "cancelled"):
        return {"success": False, "message": f"Task is already in terminal state: {status}"}

    # Cancel the background task if running
    current_ref = task_state.get("current_task_ref")
    if current_ref is not None:
        try:
            current_ref.cancel()
        except Exception:
            pass

    task_manager.update_task(task_id, {
        "status": "cancelled",
        "message": "Task cancelled by user",
        "is_processing": False,
        "download_ready": False,
    })
    task_manager.add_log(task_id, "info", "Task cancelled by user via MCP")

    return {"success": True, "message": "Task cancelled successfully"}


# ── Platform / Config Tools ────────────────────────────────────────────────────

def list_platforms(lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all available AI translation platforms."""
    from backend.config.platforms_config import get_platforms_config

    config = get_platforms_config()
    platforms = []
    for key, cfg in config.platforms.items():
        platforms.append({
            "id": key,
            "name": cfg.name,
            "model": cfg.model,
            "url": cfg.url,
            "api_protocol": cfg.api_protocol,
            "chunk_size": cfg.chunk_size,
            "concurrent": cfg.concurrent,
            "requires_api_key": cfg.requires_api_key,
            "platform_type": cfg.platform_type,
            "description": cfg.description,
        })

    # Sort: default platform first, then alphabetically
    def sort_key(p):
        return (0 if p["id"] == config.default_platform else 1, p["id"])

    platforms.sort(key=sort_key)
    return platforms


def get_platform_detail(platform_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed configuration for a specific platform."""
    from backend.config.platforms_config import get_platforms_config

    config = get_platforms_config()
    cfg = config.platforms.get(platform_id)
    if cfg is None:
        return None

    return {
        "id": platform_id,
        "name": cfg.name,
        "url": cfg.url,
        "model": cfg.model,
        "api_protocol": cfg.api_protocol,
        "requires_api_key": cfg.requires_api_key,
        "temperature": cfg.temperature,
        "temperature_min": cfg.temperature_min,
        "temperature_max": cfg.temperature_max,
        "chunk_size": cfg.chunk_size,
        "concurrent": cfg.concurrent,
        "max_tokens": cfg.max_tokens,
        "thinking_mode_supported": cfg.thinking_mode_supported,
        "thinking_mode": cfg.thinking_mode,
        "platform_type": cfg.platform_type,
        "description": cfg.description,
    }


def list_supported_formats() -> List[Dict[str, Any]]:
    """List supported document formats and their workflow types."""
    formats = [
        {"extension": ".pdf", "workflow_type": "markdown_based", "description": "PDF Document"},
        {"extension": ".docx", "workflow_type": "docx", "description": "Word Document"},
        {"extension": ".doc", "workflow_type": "docx", "description": "Word Document (legacy)"},
        {"extension": ".pptx", "workflow_type": "pptx", "description": "PowerPoint Presentation"},
        {"extension": ".ppt", "workflow_type": "pptx", "description": "PowerPoint Presentation (legacy)"},
        {"extension": ".xlsx", "workflow_type": "xlsx", "description": "Excel Spreadsheet"},
        {"extension": ".xls", "workflow_type": "xlsx", "description": "Excel Spreadsheet (legacy)"},
        {"extension": ".csv", "workflow_type": "xlsx", "description": "CSV File"},
        {"extension": ".txt", "workflow_type": "txt", "description": "Plain Text"},
        {"extension": ".md", "workflow_type": "markdown_based", "description": "Markdown"},
        {"extension": ".html", "workflow_type": "html", "description": "HTML File"},
        {"extension": ".htm", "workflow_type": "html", "description": "HTML File (legacy)"},
        {"extension": ".json", "workflow_type": "json", "description": "JSON File"},
        {"extension": ".srt", "workflow_type": "srt", "description": "SRT Subtitle"},
        {"extension": ".epub", "workflow_type": "epub", "description": "EPUB E-book"},
        {"extension": ".mobi", "workflow_type": "mobi", "description": "MOBI E-book"},
        {"extension": ".azw", "workflow_type": "mobi", "description": "Kindle E-book"},
        {"extension": ".ts", "workflow_type": "qt_ts", "description": "Qt Translation File"},
        {"extension": ".png", "workflow_type": "markdown_based", "description": "PNG Image (OCR)"},
        {"extension": ".jpg", "workflow_type": "markdown_based", "description": "JPEG Image (OCR)"},
        {"extension": ".jpeg", "workflow_type": "markdown_based", "description": "JPEG Image (OCR)"},
    ]
    return formats


def get_system_config() -> Dict[str, Any]:
    """Get system configuration / Quick Settings defaults."""
    from backend.config.config_loader import get_unified_config
    from backend.config.translation_config import get_default_deep_split

    unified_config = get_unified_config()

    # Build translation config summary
    translation_config = {
        "deep_split_defaults": {
            "pdf": get_default_deep_split("file.pdf", "markdown_based"),
            "docx": get_default_deep_split("file.docx", "docx"),
            "txt": get_default_deep_split("file.txt", "txt"),
            "md": get_default_deep_split("file.md", "markdown_based"),
            "html": get_default_deep_split("file.html", "html"),
        },
        "default_convert_engine": getattr(unified_config, "parsing_engine", None),
    }

    # Parse parsing_engine config
    parsing_engine = getattr(unified_config, "parsing_engine", None)
    if isinstance(parsing_engine, dict):
        translation_config["default_convert_engine"] = parsing_engine.get("convert_engine", "mineru")
    elif parsing_engine:
        translation_config["default_convert_engine"] = getattr(parsing_engine, "convert_engine", "mineru")

    return {
        "translation_config": translation_config,
        "smart_glossary_matching_enabled": getattr(unified_config, "smart_glossary_matching_enabled", False),
        "default_language": getattr(unified_config, "default_language", "Chinese"),
    }


# ── Glossary Tools ─────────────────────────────────────────────────────────────

def list_glossaries(scope: str = "all") -> List[Dict[str, Any]]:
    """List available glossaries."""
    from backend.glossary.manager import get_glossary_manager

    manager = get_glossary_manager()
    glossaries = []

    if scope in ("all", "global"):
        for g in manager.get_global_glossaries():
            glossaries.append({
                "id": g.id,
                "name": g.name,
                "owner": getattr(g, "owner", ""),
                "is_global": True,
                "item_count": g.item_count,
                "description": getattr(g, "description", ""),
            })

    if scope in ("all", "personal"):
        # MCP operates without user context; list all personal glossaries as anonymous placeholder
        pass

    return glossaries


def search_glossary(
    query: str,
    glossary_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search glossary terms."""
    from backend.glossary.manager import get_glossary_manager

    manager = get_glossary_manager()
    results = []
    query_lower = query.lower()

    glossaries_to_search = []

    if glossary_id:
        # Search specific glossary
        content = manager.get_glossary_content_with_languages(glossary_id)
        if content:
            glossaries_to_search = [(glossary_id, content)]
    else:
        # Search all global glossaries
        for g in manager.get_global_glossaries():
            content = manager.get_glossary_content_with_languages(g.id)
            if content:
                glossaries_to_search.append((g.id, content))

    for gid, content in glossaries_to_search:
        for src, entry in content.items():
            if isinstance(entry, dict):
                dst = entry.get("dst", "")
                category = entry.get("category", "")
            else:
                dst = str(entry) if entry else ""
                category = ""

            if query_lower in src.lower() or query_lower in dst.lower():
                results.append({
                    "src": src,
                    "dst": dst,
                    "category": category,
                    "glossary_id": gid,
                })
                if len(results) >= limit:
                    return results

    return results[:limit]


def add_glossary_terms(glossary_id: str, terms: Dict[str, str]) -> Dict[str, Any]:
    """Add terms to a glossary."""
    from backend.glossary.manager import get_glossary_manager

    manager = get_glossary_manager()

    # Validate terms
    is_valid, msg = manager.validate_glossary_dict(terms)
    if not is_valid:
        return {"success": False, "message": msg}

    try:
        # Get existing content, merge with new terms
        existing = manager.get_glossary_content_with_languages(glossary_id)
        if existing is None:
            existing = {}

        # Convert existing to the languages format if needed
        merged = {}
        for src, entry in existing.items():
            if isinstance(entry, dict):
                merged[src] = entry
            else:
                merged[src] = {"dst": str(entry), "category": ""}

        # Merge new terms
        for src, dst in terms.items():
            merged[src] = {"dst": dst, "category": ""}

        # Save
        success = manager.save_glossary_with_languages(glossary_id, merged, updated_by="mcp")
        if success:
            manager.update_glossary_version(glossary_id, updated_by="mcp")
            return {"success": True, "message": f"Added {len(terms)} terms to glossary"}
        else:
            return {"success": False, "message": "Failed to save glossary terms"}
    except Exception as e:
        return {"success": False, "message": f"Failed to add terms: {str(e)}"}


async def generate_glossary_from_doc(
    file_content: Optional[str],
    file_path: Optional[str],
    file_name: str,
    to_lang: str,
    base_url: str,
    api_key: str,
    model_id: str,
    detection_mode: str = "uncertain",
    save_to_personal: bool = False,
) -> Dict[str, Any]:
    """Generate glossary from a document automatically."""
    from backend.app.services.glossary_generation_service import glossary_generation_service
    from backend.app.models.service import GenerateGlossaryRequest

    file_bytes = _resolve_file_content(file_content, file_path)
    if file_bytes is None:
        return {"success": False, "message": "Either file_path or file_content is required"}

    request = GenerateGlossaryRequest(
        file_name=file_name,
        file_content=base64.b64encode(file_bytes).decode("utf-8"),
        to_lang=to_lang,
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        detection_mode=detection_mode,
        save_to_personal=save_to_personal,
    )

    try:
        response = await glossary_generation_service.generate_glossary(request, username="mcp_user")
        return {
            "success": response.success,
            "message": response.message,
            "glossary": response.glossary,
            "item_count": response.item_count,
        }
    except Exception as e:
        return {"success": False, "message": f"Glossary generation failed: {str(e)}"}


# ── Document Conversion Tools ──────────────────────────────────────────────────

async def convert_document(
    file_content: Optional[str],
    file_path: Optional[str],
    file_name: str,
    convert_engine: Optional[str] = None,
    formula_ocr: Optional[bool] = None,
    table_ocr: Optional[bool] = None,
) -> Dict[str, Any]:
    """Convert document format without translation."""
    from backend.app.services.format_conversion_service import format_conversion_service
    from backend.app.models.service import ConvertFormatRequest

    file_bytes = _resolve_file_content(file_content, file_path)
    if file_bytes is None:
        return {"success": False, "message": "Either file_path or file_content is required"}

    request = ConvertFormatRequest(
        file_name=file_name,
        file_content=base64.b64encode(file_bytes).decode("utf-8"),
        convert_engine=convert_engine,
        formula_ocr=formula_ocr,
        table_ocr=table_ocr,
    )

    try:
        response = await format_conversion_service.convert_format(request)
        return {
            "success": response.success,
            "message": response.message,
            "task_id": response.task_id,
        }
    except Exception as e:
        return {"success": False, "message": f"Document conversion failed: {str(e)}"}


async def translate_batch_zip(
    zip_content: Optional[str],
    zip_file_name: str,
    to_lang: str,
    base_url: str = "",
    api_key: str = "",
    model_id: str = "",
    glossary: Optional[Dict[str, str]] = None,
    glossary_ids: Optional[List[str]] = None,
    glossary_generate: bool = False,
    convert_engine: Optional[str] = None,
    chunk_size: int = 0,
    concurrent: int = 3,
    temperature: float = 0.3,
    custom_prompt: Optional[str] = None,
    prompt_mode: Optional[str] = None,
    prompt_style: Optional[str] = None,
    deep_split: Optional[bool] = None,
    execution_mode: str = "queued",
    skip_translate: bool = False,
) -> Dict[str, Any]:
    """
    Upload a ZIP of documents, extract supported files, submit each as a
    translation task.  Returns a list of (task_id, file_name).
    """
    zip_bytes = _resolve_file_content(zip_content, None)
    if zip_bytes is None:
        return {"success": False, "message": "zip_content is required (base64-encoded)"}

    import io
    temp_dir = tempfile.mkdtemp(prefix="mcp_batch_")
    tasks: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            for name in names:
                # Skip directories / macOS metadata
                if name.endswith("/") or name.startswith("__MACOSX") or name.startswith("."):
                    continue
                ext = Path(name).suffix.lower()
                supported_exts = {
                    ".pdf", ".md", ".png", ".jpg", ".jpeg",
                    ".docx", ".doc", ".pptx", ".ppt",
                    ".xlsx", ".xls", ".csv", ".txt",
                    ".html", ".htm", ".json", ".srt",
                    ".epub", ".mobi", ".azw", ".ts",
                }
                if ext not in supported_exts:
                    errors.append({"file": name, "reason": f"Unsupported extension: {ext}"})
                    continue

                file_bytes = zf.read(name)
                file_b64 = base64.b64encode(file_bytes).decode("utf-8")

                result = await translate_file(
                    file_content=file_b64,
                    file_path=None,
                    file_name=Path(name).name,
                    to_lang=to_lang,
                    base_url=base_url,
                    api_key=api_key,
                    model_id=model_id,
                    glossary=glossary,
                    glossary_ids=glossary_ids,
                    glossary_generate=glossary_generate,
                    convert_engine=convert_engine,
                    chunk_size=chunk_size,
                    concurrent=concurrent,
                    temperature=temperature,
                    custom_prompt=custom_prompt,
                    prompt_mode=prompt_mode,
                    prompt_style=prompt_style,
                    deep_split=deep_split,
                    execution_mode=execution_mode,
                    skip_translate=skip_translate,
                )
                if result.get("task_started") and result.get("task_id"):
                    tasks.append({
                        "task_id": result["task_id"],
                        "file_name": Path(name).name,
                    })
                else:
                    errors.append({
                        "file": name,
                        "reason": result.get("message", "Unknown error"),
                    })
    except Exception as e:
        return {"success": False, "message": f"Failed to process ZIP: {str(e)}"}

    return {
        "success": True,
        "total": len(tasks) + len(errors),
        "submitted": len(tasks),
        "failed": len(errors),
        "tasks": tasks,
        "errors": errors,
    }


async def download_batch_results(
    task_ids: List[str],
    file_type: str = "target",
) -> Dict[str, Any]:
    """
    Download results from multiple tasks, pack into a single ZIP.
    Skips tasks that do not support the requested format.
    Returns: { success, file_content (base64), file_name, manifest }.
    """
    import io

    from backend.app.services.task import task_manager

    buf = io.BytesIO()
    manifest: Dict[str, Dict[str, str]] = {}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for task_id in task_ids:
            try:
                result = await download_result(task_id, file_type)
                if not result.get("success"):
                    manifest[task_id] = {
                        "status": "skipped",
                        "reason": result.get("message", "Unknown error"),
                    }
                    continue

                raw = result.get("file_content", "")
                file_name = result.get("file_name", f"{task_id}_{file_type}")
                try:
                    raw_bytes = base64.b64decode(raw) if raw else b""
                except Exception:
                    manifest[task_id] = {"status": "skipped", "reason": "Base64 decode failed"}
                    continue

                if not raw_bytes:
                    manifest[task_id] = {"status": "skipped", "reason": "Empty content"}
                    continue

                # Determine extension from file_type
                ext = file_type if file_type != "target" else Path(file_name).suffix.lstrip(".")

                # Build clean filename: {original_name}_translated.{ext}
                ts = task_manager.get_task(task_id)
                original_filename = ""
                if ts:
                    original_filename = ts.get("original_filename") or ""
                if original_filename:
                    base_name = Path(original_filename).stem
                else:
                    base_name = Path(file_name).stem
                is_conv = False
                if ts:
                    is_conv = bool(ts.get("is_format_conversion") or ts.get("convert_only"))
                suffix = "converted" if is_conv else "translated"
                safe_name = f"{base_name}_{suffix}.{ext}" if ext else f"{base_name}_{suffix}"

                zf.writestr(safe_name, raw_bytes)
                manifest[task_id] = {"status": "success", "file": safe_name}
            except Exception as e:
                manifest[task_id] = {"status": "skipped", "reason": str(e)}

        zf.writestr("_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    buf.seek(0)
    zip_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "success": True,
        "file_content": zip_b64,
        "file_name": "batch_results.zip",
        "manifest": manifest,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_file_content(
    file_content: Optional[str],
    file_path: Optional[str],
) -> Optional[bytes]:
    """Resolve file bytes from either base64 content or local file path."""
    if file_content:
        try:
            return base64.b64decode(file_content)
        except Exception:
            # Try as raw text (for small text files)
            return file_content.encode("utf-8")

    if file_path:
        expanded = os.path.expanduser(file_path)
        if os.path.isfile(expanded):
            with open(expanded, "rb") as f:
                return f.read()
        # Try relative to CWD
        cwd_path = os.path.join(os.getcwd(), file_path)
        if os.path.isfile(cwd_path):
            with open(cwd_path, "rb") as f:
                return f.read()

    return None


def _build_translation_payload(
    file_name: str,
    to_lang: str,
    base_url: str,
    api_key: str,
    model_id: str,
    skip_translate: bool = False,
    convert_engine: Optional[str] = None,
    chunk_size: int = 0,
    concurrent: int = 3,
    temperature: float = 0.3,
    custom_prompt: Optional[str] = None,
    prompt_mode: Optional[str] = None,
    prompt_style: Optional[str] = None,
    deep_split: Optional[bool] = None,
    glossary_dict: Optional[Dict[str, str]] = None,
    glossary_generate_enable: bool = False,
) -> Any:
    """Build the appropriate workflow params model based on file extension."""
    ext = Path(file_name).suffix.lower()

    # Determine workflow type
    ext_to_type = {
        ".pdf": "markdown_based", ".md": "markdown_based",
        ".png": "markdown_based", ".jpg": "markdown_based", ".jpeg": "markdown_based",
        ".docx": "docx", ".doc": "docx",
        ".pptx": "pptx", ".ppt": "pptx",
        ".xlsx": "xlsx", ".xls": "xlsx", ".csv": "xlsx",
        ".txt": "txt",
        ".html": "html", ".htm": "html",
        ".json": "json",
        ".srt": "srt",
        ".epub": "epub",
        ".mobi": "mobi", ".azw": "mobi",
        ".ts": "qt_ts",
    }
    workflow_type = ext_to_type.get(ext, "markdown_based")

    # Shared base params
    base = {
        "skip_translate": skip_translate,
        "to_lang": to_lang,
        "base_url": base_url,
        "api_key": api_key,
        "model_id": model_id,
        "chunk_size": chunk_size if chunk_size > 0 else 0,
        "concurrent": concurrent,
        "temperature": temperature,
        "custom_prompt": custom_prompt,
        "prompt_mode": prompt_mode or "off",
        "prompt_style": prompt_style,
        "deep_split": deep_split,
        "glossary_dict": glossary_dict,
        "glossary_generate_enable": glossary_generate_enable,
    }

    from backend.app.models.service import (
        MarkdownWorkflowParams, DocxWorkflowParams, TextWorkflowParams,
        JsonWorkflowParams, XlsxWorkflowParams, HtmlWorkflowParams,
        SrtWorkflowParams, EpubWorkflowParams, MobiWorkflowParams,
        PptxWorkflowParams, QtTsWorkflowParams,
    )

    if workflow_type == "markdown_based":
        if convert_engine is None:
            from backend.config.config_loader import get_unified_config
            global_cfg = get_unified_config()
            pe = getattr(global_cfg, "parsing_engine", None)
            if isinstance(pe, dict):
                convert_engine = pe.get("convert_engine", "mineru")
            elif pe:
                convert_engine = getattr(pe, "convert_engine", "mineru")
            else:
                convert_engine = "mineru"
        payload = MarkdownWorkflowParams(
            workflow_type="markdown_based",
            convert_engine=convert_engine,
            **{k: v for k, v in base.items() if k in (
                "skip_translate", "to_lang", "base_url", "api_key", "model_id",
                "chunk_size", "concurrent", "temperature", "custom_prompt",
                "prompt_mode", "prompt_style", "deep_split", "glossary_dict",
                "glossary_generate_enable",
            )}
        )
    elif workflow_type == "docx":
        payload = DocxWorkflowParams(workflow_type="docx", **base)
    elif workflow_type == "pptx":
        payload = PptxWorkflowParams(workflow_type="pptx", **base)
    elif workflow_type == "xlsx":
        payload = XlsxWorkflowParams(workflow_type="xlsx", **base)
    elif workflow_type == "txt":
        payload = TextWorkflowParams(workflow_type="txt", **base)
    elif workflow_type == "html":
        payload = HtmlWorkflowParams(workflow_type="html", **base)
    elif workflow_type == "json":
        payload = JsonWorkflowParams(workflow_type="json", **base)
    elif workflow_type == "srt":
        payload = SrtWorkflowParams(workflow_type="srt", **base)
    elif workflow_type == "epub":
        payload = EpubWorkflowParams(workflow_type="epub", **base)
    elif workflow_type == "mobi":
        payload = MobiWorkflowParams(workflow_type="mobi", **base)
    elif workflow_type == "qt_ts":
        payload = QtTsWorkflowParams(workflow_type="qt_ts", **base)
    else:
        payload = MarkdownWorkflowParams(
            workflow_type="markdown_based",
            convert_engine=convert_engine or "identity",
            **{k: v for k, v in base.items() if k in (
                "skip_translate", "to_lang", "base_url", "api_key", "model_id",
                "chunk_size", "concurrent", "temperature", "custom_prompt",
                "prompt_mode", "prompt_style", "deep_split", "glossary_dict",
                "glossary_generate_enable",
            )}
        )

    return payload
