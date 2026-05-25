# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Tools — Glossary Management.

Implements:
  - owlangs_list_glossaries
  - owlangs_search_glossary
  - owlangs_add_glossary_terms
  - owlangs_generate_glossary
"""

from typing import Optional, Dict

from backend.mcp_server.service_layer import (
    list_glossaries,
    search_glossary,
    add_glossary_terms,
    generate_glossary_from_doc,
)


def register_glossary_tools(mcp):
    """Register glossary tools with the MCP server."""

    @mcp.tool(
        name="owlangs_list_glossaries",
        description="List all available glossaries. Returns glossary ID, name, owner, item count, "
                    "and description. Use the glossary ID to reference glossaries in translation "
                    "requests or to search their contents.",
    )
    def owlangs_list_glossaries(
        scope: str = "all",
    ) -> str:
        """
        Parameters:
            scope: Filter scope: "all" (all glossaries), "global" (system glossaries only), "personal" (user glossaries only).
        """
        glossaries = list_glossaries(scope)
        return _format_glossaries_response(glossaries)

    @mcp.tool(
        name="owlangs_search_glossary",
        description="Search for terms across all glossaries or within a specific glossary. "
                    "Matches against both source text and translated text. Returns matching "
                    "entries with source, translation, category, and glossary reference.",
    )
    def owlangs_search_glossary(
        query: str,
        glossary_id: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """
        Parameters:
            query: Search keyword to match against source or translated terms.
            glossary_id: Optional glossary ID to limit search scope.
            limit: Maximum number of results to return (default: 20).
        """
        results = search_glossary(query, glossary_id, limit)
        return _format_json(results)

    @mcp.tool(
        name="owlangs_add_glossary_terms",
        description="Add new terms to an existing glossary. Provide terms as a dictionary mapping "
                    "source text to translated text. Validates that keys and values are non-empty strings.",
    )
    def owlangs_add_glossary_terms(
        glossary_id: str,
        terms: Dict[str, str],
    ) -> str:
        """
        Parameters:
            glossary_id: ID of the glossary to add terms to.
            terms: Dictionary of terms in {"source text": "translated text"} format.
        """
        result = add_glossary_terms(glossary_id, terms)
        return _format_json(result)

    @mcp.tool(
        name="owlangs_generate_glossary",
        description="Automatically generate a glossary from a document using AI analysis. "
                    "The system reads the document and extracts key terms with their translations. "
                    "Optionally save the generated glossary to your personal glossary.",
    )
    async def owlangs_generate_glossary(
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        file_name: str = "",
        to_lang: str = "Chinese",
        base_url: str = "",
        api_key: str = "",
        model_id: str = "",
        detection_mode: str = "uncertain",
        save_to_personal: bool = False,
    ) -> str:
        """
        Parameters:
            file_path: Local file path (alternative to file_content).
            file_content: Base64-encoded file content (alternative to file_path).
            file_name: Original filename with extension.
            to_lang: Target language for glossary generation.
            base_url: LLM API base URL.
            api_key: LLM API key.
            model_id: Model ID for glossary generation.
            detection_mode: "uncertain" (focus on uncertain terms/errors) or "deep" (comprehensive extraction).
            save_to_personal: Whether to save the generated glossary to personal glossary.
        """
        result = await generate_glossary_from_doc(
            file_content=file_content,
            file_path=file_path,
            file_name=file_name,
            to_lang=to_lang,
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            detection_mode=detection_mode,
            save_to_personal=save_to_personal,
        )
        return _format_json(result)


def _format_glossaries_response(glossaries: list) -> str:
    lines = ["## Available Glossaries\n"]
    if not glossaries:
        lines.append("No glossaries found.\n")
    else:
        for g in glossaries:
            scope = "Global" if g.get("is_global") else "Personal"
            desc = g.get("description") or ""
            lines.append(
                f"- **{g['name']}** (`{g['id']}`) — {scope}, {g['item_count']} items"
                f"{f': {desc}' if desc else ''}"
            )
    lines.append("\n### Detailed JSON\n```json")
    import json
    lines.append(json.dumps(glossaries, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)


def _format_json(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)
