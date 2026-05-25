# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MCP Prompts — Reusable prompt templates for AI Agents.

Provides:
  - translate_document: Complete document translation workflow
  - manage_glossary: Glossary management workflow
"""


def register_prompts(mcp):
    """Register MCP prompts with the server."""

    @mcp.prompt(
        name="translate_document",
        description="Complete document translation workflow: analyze document → select platform → "
                    "choose glossary → submit translation → monitor progress → download result.",
    )
    def translate_document() -> str:
        return """# Document Translation Workflow

Follow these steps to translate a document using the Owlangs MCP tools:

## Step 1: Understand available resources
Start by checking available platforms and formats:
- Use `owlangs://platforms` to browse available AI platforms and their default models
- Use `owlangs://formats` to confirm your document format is supported

## Step 2: Select a specific platform (optional)
- Use `owlangs_get_platform` with the platform ID to see detailed config
- Use `owlangs_get_system_config` to check system defaults

## Step 3: Review glossaries (optional but recommended)
- Use `owlangs_list_glossaries` to find relevant glossaries
- Use `owlangs_search_glossary` to verify specific terminology
- Use `owlangs://glossaries/{id}` to view all terms in a glossary

## Step 4: Submit the translation task
Use `owlangs_translate` with these key parameters:
- `file_path` or `file_content` (base64) + `file_name` for the document
- `to_lang` for the target language
- `base_url`, `api_key`, `model_id` for the AI platform
- `glossary_ids` or `glossary` to apply terminology
- Optional: `chunk_size`, `concurrent`, `temperature`, `deep_split`, etc.

## Step 5: Monitor progress
Poll `owlangs_translate_status` with the returned `task_id` until status is "completed" or "failed".

## Step 6: Download the result
Use `owlangs_translate_download` with the `task_id` to get the translated file.

## Important Notes
- Translation runs asynchronously — always poll for completion before downloading
- Files are temporary; download results promptly after completion
- Large PDFs (>500 pages) may be rejected depending on parsing engine
- Provide both `base_url` and `api_key` for the LLM platform
"""

    @mcp.prompt(
        name="manage_glossary",
        description="Glossary management workflow: view existing glossaries → search terms → "
                    "add/update terms → generate glossary from document.",
    )
    def manage_glossary() -> str:
        return """# Glossary Management Workflow

Follow these steps to manage translation glossaries:

## Step 1: Browse existing glossaries
- Use `owlangs_list_glossaries` to see all available glossaries
- Use `owlangs://glossaries/{id}` to view terms in a specific glossary
- Use `owlangs_search_glossary` to find specific terms across glossaries

## Step 2: Add or update terms
- Use `owlangs_add_glossary_terms` with a glossary ID and a dictionary of terms
- Terms are in {"source text": "translated text"} format
- Existing terms with the same source text will be updated

## Step 3: Auto-generate glossary from a document
- Use `owlangs_generate_glossary` to analyze a document and extract key terms
- Specify `detection_mode`: "uncertain" (errors/uncertain terms) or "deep" (comprehensive)
- Optionally save results to a personal glossary with `save_to_personal=true`

## Step 4: Apply glossaries to translation
- Pass `glossary_ids=["glossary-uuid"]` to `owlangs_translate`
- Or pass a direct `glossary={"source": "translation"}` dictionary
- Both can be combined for maximum coverage
"""
