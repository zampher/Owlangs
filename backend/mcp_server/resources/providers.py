# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Resources — Read-only data access via URI patterns.

Provides resource URIs:
  - owlangs://platforms              → platform list
  - owlangs://platforms/{id}         → specific platform detail
  - owlangs://glossaries             → glossary overview
  - owlangs://glossaries/{id}        → specific glossary terms
  - owlangs://formats                → supported document formats
  - owlangs://task/{task_id}/status  → task status
  - owlangs://task/{task_id}/logs    → task logs
"""

import json
from typing import Optional

from backend.mcp_server.service_layer import (
    list_platforms,
    get_platform_detail,
    list_glossaries,
    list_supported_formats,
    get_task_status,
)


def register_resources(mcp):
    """Register MCP resources with the server."""

    # ── Platforms ──────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="owlangs://platforms",
        name="Platforms List",
        description="List of all available AI translation platforms with their default configurations.",
        mime_type="application/json",
    )
    async def platforms_resource() -> str:
        platforms = list_platforms()
        return json.dumps(platforms, ensure_ascii=False, indent=2)

    @mcp.resource(
        uri="owlangs://platforms/{platform_id}",
        name="Platform Detail",
        description="Detailed configuration for a specific AI translation platform.",
        mime_type="application/json",
    )
    async def platform_detail_resource(platform_id: str) -> str:
        detail = get_platform_detail(platform_id)
        if detail is None:
            return json.dumps({"error": f"Platform not found: {platform_id}"}, ensure_ascii=False)
        return json.dumps(detail, ensure_ascii=False, indent=2)

    # ── Glossaries ─────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="owlangs://glossaries",
        name="Glossaries Overview",
        description="List of available glossaries with metadata (id, name, item count, description).",
        mime_type="application/json",
    )
    async def glossaries_resource() -> str:
        glossaries = list_glossaries("all")
        return json.dumps(glossaries, ensure_ascii=False, indent=2)

    @mcp.resource(
        uri="owlangs://glossaries/{glossary_id}",
        name="Glossary Content",
        description="All terms in a specific glossary as source → translation pairs.",
        mime_type="application/json",
    )
    async def glossary_content_resource(glossary_id: str) -> str:
        from backend.glossary.manager import get_glossary_manager
        manager = get_glossary_manager()
        content = manager.get_glossary_content_with_languages(glossary_id)
        if content is None:
            return json.dumps({"error": f"Glossary not found: {glossary_id}"}, ensure_ascii=False)
        # Simplify: return src -> dst pairs
        simplified = {}
        for src, entry in content.items():
            if isinstance(entry, dict):
                simplified[src] = entry.get("dst", "")
            else:
                simplified[src] = str(entry)
        return json.dumps(simplified, ensure_ascii=False, indent=2)

    # ── Formats ────────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="owlangs://formats",
        name="Supported Formats",
        description="All supported document formats with extensions, workflow types, and descriptions.",
        mime_type="application/json",
    )
    async def formats_resource() -> str:
        formats = list_supported_formats()
        return json.dumps(formats, ensure_ascii=False, indent=2)

    # ── Task Status ────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="owlangs://task/{task_id}/status",
        name="Task Status",
        description="Current status and progress of a translation or conversion task.",
        mime_type="application/json",
    )
    async def task_status_resource(task_id: str) -> str:
        status = await get_task_status(task_id)
        return json.dumps(status, ensure_ascii=False, indent=2)

    @mcp.resource(
        uri="owlangs://task/{task_id}/logs",
        name="Task Logs",
        description="Detailed log entries for a translation or conversion task.",
        mime_type="application/json",
    )
    async def task_logs_resource(task_id: str) -> str:
        from backend.app.services.task import task_manager
        logs = task_manager.get_logs(task_id)
        return json.dumps(logs, ensure_ascii=False, indent=2)
