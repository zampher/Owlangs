# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Owlangs MCP Server — FastMCP initialization and tool/resource/prompt registration.

Uses the FastMCP helper from the MCP Python SDK for clean tool/resource/prompt definitions.
"""

from mcp.server.fastmcp import FastMCP

from .tools.config_tools import register_config_tools
from .tools.translate_tools import register_translate_tools
from .tools.glossary_tools import register_glossary_tools
from .tools.convert_tools import register_convert_tools
from .resources.providers import register_resources
from .prompts.templates import register_prompts

# ── Create MCP Server ──────────────────────────────────────────────────────────

mcp = FastMCP(
    "owlangs",
    instructions="Owlangs Document Translation Platform — AI-driven translation for 15+ document formats, "
                 "27+ LLM platforms, glossary management, and format conversion.",
    streamable_http_path="/mcp",
)

# ── Register Tools ─────────────────────────────────────────────────────────────

register_config_tools(mcp)
register_translate_tools(mcp)
register_glossary_tools(mcp)
register_convert_tools(mcp)

# ── Register Resources ─────────────────────────────────────────────────────────

register_resources(mcp)

# ── Register Prompts ───────────────────────────────────────────────────────────

register_prompts(mcp)
