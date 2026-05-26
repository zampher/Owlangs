# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Tools — Document Translation.

Implements:
  - owlangs_translate
  - owlangs_translate_status
  - owlangs_translate_download
  - owlangs_translate_cancel
  - owlangs_translate_batch_zip
  - owlangs_translate_batch_download
"""

from typing import Optional, Dict, List

from backend.mcp_server.service_layer import (
    translate_file,
    get_task_status,
    download_result,
    cancel_task,
    translate_batch_zip,
    download_batch_results,
)


def register_translate_tools(mcp):
    """Register translation tools with the MCP server."""

    @mcp.tool(
        name="owlangs_translate",
        description="Submit a document translation task. Provide either file_path (local file) or "
                    "file_content (base64-encoded). The system auto-detects the document format from "
                    "the file extension and uses the appropriate workflow. Returns a task_id for "
                    "status polling and result download. Supported formats: PDF, DOCX, PPTX, XLSX, "
                    "TXT, MD, HTML, JSON, SRT, EPUB, MOBI, SRT, TS, and images (OCR).",
    )
    async def owlangs_translate(
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        file_name: str = "",
        to_lang: str = "Chinese",
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
    ) -> str:
        """
        Parameters:
            file_path: Local file path to the document to translate. Use forward slashes.
            file_content: Base64-encoded file content (alternative to file_path).
            file_name: Original filename with extension (e.g., "my_document.pdf"). Required when using file_content.
            to_lang: Target language (e.g., "Chinese", "English", "Japanese", "French", "German", "Spanish").
            base_url: LLM API base URL (e.g., "https://api.openai.com/v1").
            api_key: LLM API key.
            model_id: Model ID (e.g., "gpt-4o", "deepseek-chat", "claude-sonnet-4-20250514").
            glossary: Optional glossary dictionary in {"source": "translation"} format.
            glossary_ids: Optional list of existing glossary IDs to apply.
            glossary_generate: Whether to auto-generate glossary from the document (default: false).
            convert_engine: Document parsing engine: "identity", "mineru", or "docling" (auto-detected if not set).
            chunk_size: Chunk size in characters (0 = use platform default).
            concurrent: Number of concurrent translation requests (default: 3).
            temperature: LLM temperature parameter (default: 0.3).
            custom_prompt: Custom translation prompt override.
            prompt_mode: Prompt mode: "off", "simple", or "advanced".
            prompt_style: Translation style: "literal", "fluent", "academic", "business", "technical".
            deep_split: Enable fine-grained text splitting (default: auto based on format).
            execution_mode: "immediate" (start now) or "queued" (wait in queue, default). Queued mode
                          auto-retries failed segments and is recommended for AI Agent use.
            skip_translate: If true, only convert format without translating (default: false).
        """
        result = await translate_file(
            file_content=file_content,
            file_path=file_path,
            file_name=file_name,
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
        return _format_json(result)

    @mcp.tool(
        name="owlangs_translate_status",
        description="Query the status of a translation task. Returns current status, progress "
                    "percentage, and descriptive message. Common statuses: queued, extracting, "
                    "translating, exporting, completed, failed, cancelled.",
    )
    async def owlangs_translate_status(
        task_id: str,
    ) -> str:
        """
        Parameters:
            task_id: The task ID returned by owlangs_translate.
        """
        result = await get_task_status(task_id)
        return _format_json(result)

    @mcp.tool(
        name="owlangs_translate_download",
        description="Download the result of a completed translation task. Returns the file content "
                    "as base64-encoded data along with the filename. Specify file_type to choose "
                    "between translated output, side-by-side comparison, or source document.",
    )
    async def owlangs_translate_download(
        task_id: str,
        file_type: str = "target",
    ) -> str:
        """
        Parameters:
            task_id: The task ID returned by owlangs_translate.
            file_type: File type to download: "target" (translated only), "compare" (side-by-side), or "source" (original).
        """
        result = await download_result(task_id, file_type)
        return _format_json(result)

    @mcp.tool(
        name="owlangs_translate_cancel",
        description="Cancel a running translation task. Tasks in terminal states (completed, failed, "
                    "cancelled) cannot be cancelled.",
    )
    async def owlangs_translate_cancel(
        task_id: str,
    ) -> str:
        """
        Parameters:
            task_id: The task ID to cancel.
        """
        result = await cancel_task(task_id)
        return _format_json(result)

    @mcp.tool(
        name="owlangs_translate_batch_zip",
        description="Upload a ZIP archive containing multiple documents and translate all supported "
                    "files. The system extracts the ZIP, detects each file's format, and submits "
                    "individual translation tasks. Returns a list of task_ids for status polling "
                    "and download. Supported formats inside ZIP: PDF, DOCX, PPTX, XLSX, TXT, MD, "
                    "HTML, JSON, SRT, EPUB, MOBI, TS, CSV, and images (OCR).",
    )
    async def owlangs_translate_batch_zip(
        zip_content: str,
        zip_file_name: str = "documents.zip",
        to_lang: str = "Chinese",
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
    ) -> str:
        """
        Parameters:
            zip_content: Base64-encoded ZIP file content.
            zip_file_name: Original ZIP filename (default: "documents.zip").
            to_lang: Target language (e.g., "Chinese", "English", "Japanese", "French", "German", "Spanish").
            base_url: LLM API base URL.
            api_key: LLM API key.
            model_id: Model ID (e.g., "gpt-4o", "deepseek-chat").
            glossary: Optional glossary dictionary in {"source": "translation"} format.
            glossary_ids: Optional list of existing glossary IDs to apply.
            glossary_generate: Whether to auto-generate glossary from the document.
            convert_engine: Document parsing engine: "identity", "mineru", or "docling".
            chunk_size: Chunk size in characters (0 = use platform default).
            concurrent: Number of concurrent translation requests (default: 3).
            temperature: LLM temperature parameter (default: 0.3).
            custom_prompt: Custom translation prompt override.
            prompt_mode: Prompt mode: "off", "simple", or "advanced".
            prompt_style: Translation style: "literal", "fluent", "academic", "business", "technical".
            deep_split: Enable fine-grained text splitting.
            execution_mode: "immediate" or "queued" (default).
            skip_translate: If true, only convert format without translating (default: false).
        """
        result = await translate_batch_zip(
            zip_content=zip_content,
            zip_file_name=zip_file_name,
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
        return _format_json(result)

    @mcp.tool(
        name="owlangs_translate_batch_download",
        description="Download results from multiple completed translation tasks in a single ZIP. "
                    "Specify a list of task_ids and the desired file_type (e.g., 'html', 'md', "
                    "'docx', 'pdf'). Tasks that do not support the requested format are skipped "
                    "and listed in _manifest.json inside the ZIP.",
    )
    async def owlangs_translate_batch_download(
        task_ids: List[str],
        file_type: str = "target",
    ) -> str:
        """
        Parameters:
            task_ids: List of task IDs returned by owlangs_translate or owlangs_translate_batch_zip.
            file_type: File type to download for each task: "target" (translated), "html", "md",
                      "docx", "pdf", "txt", "json", etc. Default: "target".
        """
        result = await download_batch_results(
            task_ids=task_ids,
            file_type=file_type,
        )
        return _format_json(result)


def _format_json(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)
