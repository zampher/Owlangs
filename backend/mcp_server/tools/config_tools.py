# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Tools — Configuration and Platform Information.

Implements:
  - owlangs_list_platforms
  - owlangs_get_platform
  - owlangs_list_supported_formats
  - owlangs_get_system_config
"""

from typing import Optional

from backend.mcp_server.service_layer import (
    list_platforms,
    get_platform_detail,
    list_supported_formats,
    get_system_config,
)


def register_config_tools(mcp):
    """Register configuration/platform tools with the MCP server."""

    @mcp.tool(
        name="owlangs_list_platforms",
        description="List all available AI translation platforms and their default configurations. "
                    "Returns platform ID, name, model, URL, API protocol, chunk size, concurrent limits, "
                    "and whether an API key is required. The default platform is listed first.",
    )
    def owlangs_list_platforms(
        lang: Optional[str] = None,
    ) -> str:
        """
        Parameters:
            lang: Optional language filter (zh/en/ja/ko) to filter platform display names.
        """
        platforms = list_platforms(lang)
        return _format_platforms_response(platforms)

    @mcp.tool(
        name="owlangs_get_platform",
        description="Get detailed configuration for a specific AI translation platform by its ID. "
                    "Returns all settings including URL, model, temperature range, chunk size, "
                    "concurrent requests, max tokens, thinking mode support, and API protocol.",
    )
    def owlangs_get_platform(
        platform_id: str,
    ) -> str:
        """
        Parameters:
            platform_id: Platform ID (e.g., 'openai', 'deepseek', 'anthropic', 'gemini').
        """
        detail = get_platform_detail(platform_id)
        if detail is None:
            return f'{{"error": "Platform not found: {platform_id}"}}'
        return _format_json(detail)

    @mcp.tool(
        name="owlangs_list_supported_formats",
        description="List all supported document formats for translation and conversion. "
                    "Returns file extensions, workflow types, and descriptions.",
    )
    def owlangs_list_supported_formats() -> str:
        """List supported document formats."""
        formats = list_supported_formats()
        return _format_json(formats)

    @mcp.tool(
        name="owlangs_get_system_config",
        description="Get system-level configuration including Quick Settings defaults. "
                    "Returns translation config (deep_split defaults per format, default convert engine), "
                    "smart glossary matching status, and default language.",
    )
    def owlangs_get_system_config() -> str:
        """Get system configuration."""
        config = get_system_config()
        return _format_json(config)


def _format_platforms_response(platforms: list) -> str:
    """Format platforms list as readable markdown + JSON."""
    lines = ["## Available AI Translation Platforms\n"]
    for p in platforms:
        api_key_note = " (API key required)" if p.get("requires_api_key") else ""
        lines.append(
            f"- **{p['name']}** (`{p['id']}`): {p['model']} — {p['url']}"
            f"{api_key_note}"
        )
    lines.append("\n### Detailed JSON\n```json")
    import json
    lines.append(json.dumps(platforms, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)


def _format_json(data) -> str:
    """Format data as JSON string."""
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)
