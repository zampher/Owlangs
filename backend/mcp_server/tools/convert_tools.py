# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Tools — Document Format Conversion.

Implements:
  - owlangs_convert_document
"""

from typing import Optional

from backend.mcp_server.service_layer import convert_document


def register_convert_tools(mcp):
    """Register document conversion tools with the MCP server."""

    @mcp.tool(
        name="owlangs_convert_document",
        description="Convert a document from one format to another without translation. "
                    "This performs document parsing and format conversion only (no LLM calls). "
                    "Useful for extracting text from PDFs, converting between formats, or "
                    "previewing document structure. Returns a task_id for monitoring and download.",
    )
    async def owlangs_convert_document(
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        file_name: str = "",
        convert_engine: Optional[str] = None,
        formula_ocr: Optional[bool] = None,
        table_ocr: Optional[bool] = None,
    ) -> str:
        """
        Parameters:
            file_path: Local file path to the document (alternative to file_content).
            file_content: Base64-encoded file content (alternative to file_path).
            file_name: Original filename with extension.
            convert_engine: Parsing engine: "identity", "mineru", or "docling" (auto if not set).
            formula_ocr: Enable formula OCR recognition (default: system config).
            table_ocr: Enable table OCR recognition (default: system config).
        """
        result = await convert_document(
            file_content=file_content,
            file_path=file_path,
            file_name=file_name,
            convert_engine=convert_engine,
            formula_ocr=formula_ocr,
            table_ocr=table_ocr,
        )
        return _format_json(result)


def _format_json(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)
