# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Service-related Pydantic models for Owlangs.

This module contains models for PDF export, document conversion,
translation workflows, and other service operations.
"""

from typing import List, Dict, Any, Optional, Literal, Union, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator, AliasChoices

from agents.agent import ThinkingMode
from exporter.md.types import ConvertEngineType
from translator import default_params


class PdfExportRequest(BaseModel):
    """Request model for PDF export functionality."""
    html_url: str
    file_name: str | None = None
    # Page settings (optional)
    format: str | None = "A4"
    margin_top: str | None = "10mm"
    margin_right: str | None = "10mm"
    margin_bottom: str | None = "10mm"
    margin_left: str | None = "10mm"


class PdfExportHtmlRequest(BaseModel):
    """Request model for PDF export from HTML content."""
    html_content: str
    file_name: str | None = None
    # Page settings (optional)
    format: str | None = "A4"
    margin_top: str | None = "10mm"
    margin_right: str | None = "10mm"
    margin_bottom: str | None = "10mm"
    margin_left: str | None = "10mm"


class ConvertRequest(BaseModel):
    """Request model for document conversion."""
    file_name: str
    file_content: str  # Base64 encoded
    convert_engine: ConvertEngineType = "identity"
    mineru_token: Optional[str] = None
    formula_ocr: bool = True
    table_ocr: bool = True
    model_version: Literal["pipeline", "vlm", "hybrid", "vlm-auto-engine", "hybrid-auto-engine", "vlm-http-client", "hybrid-http-client"] = "hybrid-auto-engine"


class ConvertResponse(BaseModel):
    """Response model for document conversion."""
    success: bool
    message: str
    markdown_content: Optional[str] = None


# GlossaryAgentConfigPayload removed - glossary generation now uses translation parameters directly


class GenerateGlossaryRequest(BaseModel):
    """Request model for standalone glossary generation."""
    file_name: str = Field(..., description="Original uploaded filename with extension.",
                           examples=["my_paper.pdf", "chapter1.txt", "data.xlsx"])
    file_content: str = Field(..., description="Base64 encoded file content.", examples=["JVBERi0xLjQK..."])
    to_lang: str = Field(default="Chinese", description="Target language for glossary generation.", 
                         examples=["Chinese", "English"])
    # Optional task_id to reuse Extract phase chunks
    task_id: Optional[str] = Field(default=None, description="Optional task ID to reuse chunks from Extract phase. If provided, will use chunks from task_state instead of extracting segments from file_content.")
    # Translation parameters (reused for glossary generation)
    base_url: Optional[str] = Field(default=None, validation_alias=AliasChoices('base_url', 'baseurl'),
                                    description="Base URL for LLM API.",
                                    examples=["https://api.openai.com/v1"])
    api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('api_key', 'key'),
                                   description="LLM API key (optional).",
                                   examples=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"])
    model_id: Optional[str] = Field(default=None,
                                    description="LLM model ID to use.",
                                    examples=["gpt-4o"])
    api_type: Optional[str] = Field(default=None, validation_alias=AliasChoices('api_type', 'api_protocol'),
                                    description="API protocol type: 'openai', 'anthropic', or 'ollama'.",
                                    examples=["openai", "anthropic", "ollama"])
    temperature: float = Field(default=0.3, description="LLM temperature parameter.")
    thinking: ThinkingMode = Field(default="disable", description="Thinking mode for the Agent.",
                                   examples=["default", "enable", "disable"])
    concurrent: int = Field(default=3, description="Number of concurrent requests.")
    timeout: int = Field(default=120, description="Time to wait for API response (seconds).")
    retry: int = Field(default=5, description="Maximum retry count after a chunk fails.")
    chunk_size: int = Field(default=0, description="Chunk size for text splitting (characters). 0 means unset, will be loaded from user settings.")
    custom_prompt: Optional[str] = Field(None, description="User-defined prompt for glossary generation.")
    detection_mode: Literal["uncertain", "deep"] = Field(default="uncertain", description="Glossary detection mode: 'uncertain' for uncertain terms only (focus on translation errors), 'deep' for comprehensive domain-specific terms extraction.")
    # Output options
    output_format: Literal["json", "csv"] = Field(default="json", description="Output format for glossary.")
    save_to_personal: bool = Field(default=False, description="Whether to save generated glossary to user's personal glossary.")


class GenerateGlossaryResponse(BaseModel):
    """Response model for glossary generation."""
    success: bool
    message: str
    glossary: Optional[Dict[str, str]] = None
    item_count: Optional[int] = None
    download_url: Optional[str] = None


class ConvertFormatRequest(BaseModel):
    """Request model for format conversion (parse + convert, no translation)."""
    file_name: str = Field(..., description="Original uploaded filename with extension.",
                           examples=["my_paper.pdf", "chapter1.docx", "data.xlsx"])
    file_content: str = Field(..., description="Base64 encoded file content.", examples=["JVBERi0xLjQK..."])
    workflow_type: Optional[str] = Field(
        default=None,
        description="Workflow type (auto-detected from file extension if not provided).",
        examples=["docx", "markdown_based", "txt", "json", "xlsx", "html", "srt", "epub"]
    )
    to_lang: Optional[str] = Field(
        default=None,
        description="Target language code for exclusion detection (e.g., 'zh', 'en'). If not provided, exclusion detection will skip language_match checks.",
        examples=["zh", "en", "ja"]
    )
    # Format conversion specific parameters (for markdown_based workflow)
    convert_engine: Optional[ConvertEngineType] = Field(default=None, description="Convert engine for PDF/images.")
    formula_ocr: Optional[bool] = Field(default=None, description="Enable formula OCR.")
    table_ocr: Optional[bool] = Field(default=None, description="Enable table OCR.")
    model_version: Optional[Literal["pipeline", "vlm", "hybrid", "vlm-auto-engine", "hybrid-auto-engine", "vlm-http-client", "hybrid-http-client"]] = Field(default=None, description="MinerU backend: pipeline, vlm-auto-engine, hybrid-auto-engine, vlm-http-client, hybrid-http-client.")
    ocr_language: Optional[str] = Field(default=None, description="OCR language code (e.g. 'auto', 'zh', 'en'). Used by MinerU for recognition.")
    mineru_token: Optional[str] = Field(default=None, description="MinerU API token.")
    deep_split: Optional[bool] = Field(
        default=None,
        description="When enabled, split text at the finest granularity (per layout block / paragraph) before translation. "
                   "If not specified, defaults based on file format: PDF/Docx=False, TXT/MD/HTML=True, others=True."
    )
    skip_cache: Optional[bool] = Field(
        default=False,
        description="When enabled, skip using cached conversion results and force re-conversion. "
                   "Useful when frontend is refreshed or new session starts."
    )
    platform_key: Optional[str] = Field(
        default=None,
        description="AI platform key for chunk_size lookup from platforms.json. "
                   "If not provided, falls back to hardcoded default of 3000."
    )


class ConvertFormatResponse(BaseModel):
    """Response model for format conversion."""
    success: bool
    message: str
    task_id: Optional[str] = None
    download_url: Optional[str] = None
    output_format: Optional[str] = None
    file_content: Optional[str] = None  # Base64-encoded file content (for URL fetch → frontend reuse)


class FetchUrlRequest(BaseModel):
    """Request model for fetching a URL and converting its content."""
    url: str = Field(..., description="URL to fetch and convert.", examples=["https://example.com/article"])
    extract_mode: Optional[Literal["full", "content"]] = Field(
        default="content",
        description="Extraction mode: 'full' keeps the complete raw HTML; 'content' extracts the main article body using trafilatura.",
    )
    workflow_type: Optional[str] = Field(
        default="html",
        description="Workflow type for processing. Defaults to 'html'.",
    )
    to_lang: Optional[str] = Field(
        default=None,
        description="Target language code for exclusion detection (e.g., 'zh', 'en').",
    )
    deep_split: Optional[bool] = Field(
        default=None,
        description="When enabled, split text at the finest granularity before translation.",
    )
    skip_cache: Optional[bool] = Field(
        default=False,
        description="When enabled, skip using cached conversion results and force re-conversion.",
    )


# Glossary Management Models (removed - using original auth routes for glossary management)


class BaseWorkflowParams(BaseModel):
    """Base parameters shared by all translation workflows."""
    skip_translate: bool = Field(default=False, description="Whether to skip translation step. If True, only document parsing and format conversion will be performed.")
    base_url: Optional[str] = Field(default=None, validation_alias=AliasChoices('base_url', 'baseurl'),
                                    description="Base URL for LLM API. Required when `skip_translate` is `False`.",
                                    examples=["https://api.openai.com/v1"])
    api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('api_key', 'key'),
                                   description="LLM API key (optional).",
                                   examples=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"])
    model_id: Optional[str] = Field(default=None,
                                    description="LLM model ID to use. Required when `skip_translate` is `False`.",
                                    examples=["gpt-4o"])
    to_lang: str = Field(default="Chinese", description="Target translation language.", 
                         examples=["Chinese", "English"])
    chunk_size: int = Field(default=0, description="Chunk size for text splitting (characters). 0 means unset, will be loaded from user settings.")
    concurrent: int = Field(default=0, description="Number of concurrent requests. 0 means unset, will be loaded from platform config or app config.")
    temperature: float = Field(default=0.3, description="LLM temperature parameter.")
    timeout: int = Field(default=default_params["timeout"], description="Time to wait for API response (seconds).")
    thinking: ThinkingMode = Field(default=default_params["thinking"], description="Thinking mode for the Agent.",
                                   examples=["default", "enable", "disable"])
    retry: int = Field(
        default=default_params["retry"],
        description="Per-chunk HTTP/API retries when a translation chunk fails (Agent send_async retry budget).",
        ge=0,
        le=20,
    )
    segment_auto_retry_rounds: int = Field(
        default=3,
        description="Queued execution mode only: maximum rounds of batch retranslate for "
        "failed segments after main translation completes (separate from chunk retry).",
        ge=1,
        le=10,
    )
    custom_prompt: Optional[str] = Field(None, description="User-defined translation prompt.", alias="custom_prompt")
    glossary_dict: Optional[Dict[str, str]] = Field(None, description="Glossary dictionary, key is original text, value is translated text.")
    glossary_generate_enable: bool = Field(default=False, description="Whether to enable automatic glossary generation.")
    # Optional linkage to a previous Convert/Extract task (used for asset reuse like images)
    convert_task_id: Optional[str] = Field(
        default=None,
        description="Optional Convert/Extract task_id to reuse cached assets (e.g., image_data_map, html templates) in Translate phase."
    )
    copy_source_only: bool = Field(
        default=False,
        description="When True (Convert toolbar flow), copy source text to target for every segment without calling the LLM.",
    )
    # Prompt controls (simple/advanced, AI-friendly minimal knobs)
    prompt_mode: Optional[Literal["off", "simple", "advanced"]] = Field(
        default="off",
        description="Prompt mode: off/simple/advanced. When off, system skeleton only."
    )
    prompt_style: Optional[Literal["literal", "fluent", "academic", "business", "technical"]] = Field(
        default=None,
        description="Style template when prompt_mode is simple/advanced."
    )
    custom_note: Optional[str] = Field(
        default=None,
        description="Short task note to complement prompt (advanced mode)."
    )
    excluded_segments: Optional[List[int]] = Field(
        default=None,
        description="Indices (0-based) of segments that should be skipped during translation."
    )
    deep_split: Optional[bool] = Field(
        default=None,
        description="When enabled, split text at the finest granularity (per layout block / paragraph) before translation. "
                   "If not specified, defaults based on file format: PDF/Docx=False, TXT/MD/HTML=True, others=True."
    )
    skip_cache: Optional[bool] = Field(
        default=False,
        description="When enabled (True), skip using cached conversion results and force re-conversion (Extract phase). "
                   "When disabled (False), use cached results if available (Convert phase)."
    )
    platform_key: Optional[str] = Field(
        default=None,
        description="AI platform key for chunk_size/concurrent lookup from platforms.json. "
                   "If not provided, falls back to hardcoded default of 3000."
    )

    @model_validator(mode='before')
    @classmethod
    def check_translation_fields(cls, values):
        # If not skipping translation (value is False or field doesn't exist), validate that related fields must exist and not be empty
        if not values.get('skip_translate'):
            # Check for standard keys or their aliases
            if not (values.get('base_url') or values.get('baseurl')):
                raise ValueError("When `skip_translate` is `False`, `base_url` or `baseurl` field is required.")
            if not values.get('model_id'):
                raise ValueError("When `skip_translate` is `False`, `model_id` field is required.")
        # If skipping translation, no validation is performed, allowing base_url and other fields to be empty
        return values

    @field_validator('excluded_segments')
    @classmethod
    def normalize_excluded_segments(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if not v:
            return None
        normalized = sorted({int(i) for i in v if i is not None and int(i) >= 0})
        return normalized or None


class MarkdownWorkflowParams(BaseWorkflowParams):
    """Parameters for Markdown-based translation workflow."""
    workflow_type: Literal['markdown_based'] = Field(..., description="Specify to use Markdown-based translation workflow.")
    convert_engine: ConvertEngineType = Field(
        "identity",
        description="Select the engine to parse files into markdown. If input file is .md, this can be `null` or not passed.",
        examples=["identity", "mineru", "docling"]
    )
    mineru_token: Optional[str] = Field(None, description="Required API token when `convert_engine` is 'mineru'.")
    formula_ocr: bool = Field(True, description="Whether to perform OCR recognition on formulas. Effective for both `mineru` and `docling`.")
    code_ocr: bool = Field(True, description="Whether to perform OCR recognition on code blocks. Only effective for `docling` engine.")
    model_version: Literal["pipeline", "vlm", "hybrid", "vlm-auto-engine", "hybrid-auto-engine", "vlm-http-client", "hybrid-http-client"] = Field("hybrid-auto-engine",
                                                               description="MinerU backend: pipeline, vlm-auto-engine, hybrid-auto-engine, vlm-http-client, or hybrid-http-client.")
    ocr_language: Optional[str] = Field(None, description="OCR language (e.g. 'auto', 'zh', 'en'). Only effective for `mineru` engine.")

    @field_validator('mineru_token')
    def check_mineru_token(cls, v, values):
        # Relaxed validation: if not provided, will be injected from local sensitive configuration on server side
        return v


class TextWorkflowParams(BaseWorkflowParams):
    """Parameters for plain text translation workflow."""
    workflow_type: Literal['txt'] = Field(..., description="Specify to use plain text translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class JsonWorkflowParams(BaseWorkflowParams):
    """Parameters for JSON translation workflow."""
    workflow_type: Literal['json'] = Field(..., description="Specify to use JSON translation workflow.")
    json_paths: Optional[List[str]] = Field(
        default=None,
        description="A list of jsonpath-ng expressions to specify JSON fields to be translated.",
        examples=[["$.product.name", "$.product.description", "$.features[*]"]]
    )
    segment_per_request: bool = Field(
        default=False,
        description="When True, send one segment per API request (avoids one bad segment e.g. @@locale breaking a chunk)."
    )


class XlsxWorkflowParams(BaseWorkflowParams):
    """Parameters for XLSX translation workflow."""
    workflow_type: Literal['xlsx'] = Field(..., description="Specify to use XLSX translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )
    translate_regions: Optional[List[str]] = Field(
        None,
        description="Specify translation range list. Example: ['Sheet1!A1:B10', 'C:D', 'E5']. If sheet name is not specified (like 'C:D'), applies to all sheets. If None, translates all text in the entire file."
    )


class DocxWorkflowParams(BaseWorkflowParams):
    """Parameters for DOCX translation workflow."""
    workflow_type: Literal['docx'] = Field(..., description="Specify to use DOCX translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class SrtWorkflowParams(BaseWorkflowParams):
    """Parameters for SRT subtitle translation workflow."""
    workflow_type: Literal['srt'] = Field(..., description="Specify to use SRT subtitle translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class EpubWorkflowParams(BaseWorkflowParams):
    """Parameters for EPUB translation workflow."""
    workflow_type: Literal['epub'] = Field(..., description="Specify to use EPUB translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class MobiWorkflowParams(BaseWorkflowParams):
    """Parameters for MOBI translation workflow."""
    workflow_type: Literal['mobi'] = Field(..., description="Specify to use MOBI translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class HtmlWorkflowParams(BaseWorkflowParams):
    """Parameters for HTML translation workflow."""
    workflow_type: Literal['html'] = Field(..., description="Specify to use HTML translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        " ",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )


class PptxWorkflowParams(BaseWorkflowParams):
    """Parameters for PPTX translation workflow."""
    workflow_type: Literal['pptx'] = Field(..., description="Specify to use PPTX translation workflow.")
    insert_mode: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="Insert mode for translated text. 'replace': replace original text, 'append': append after original text, 'prepend': prepend before original text."
    )
    separator: str = Field(
        "\n",
        description="Separator used to separate original text and translated text when insert_mode is 'append' or 'prepend'."
    )
    translate_notes: bool = Field(
        False,
        description="Whether to translate notes pages."
    )
    translate_master: bool = Field(
        False,
        description="Whether to translate master slides (usually not recommended)."
    )
    translate_tables: bool = Field(
        True,
        description="Whether to translate tables."
    )
    translate_textboxes: bool = Field(
        True,
        description="Whether to translate text boxes."
    )


class QtTsWorkflowParams(BaseWorkflowParams):
    """Parameters for Qt .ts translation workflow."""
    workflow_type: Literal['qt_ts'] = Field(..., description="Specify to use Qt .ts translation workflow.")
    skip_existing_translations: bool = Field(
        True,
        description="Skip messages that already have translations"
    )
    translate_unfinished: bool = Field(
        True,
        description="Translate messages marked as unfinished (type='unfinished')"
    )
    translate_vanished: bool = Field(
        True,
        description="Translate messages marked as vanished (type='vanished')"
    )
    translate_obsolete: bool = Field(
        True,
        description="Translate messages marked as obsolete (type='obsolete')"
    )


# Combine workflow parameters using Discriminated Union
TranslatePayload = Annotated[
    Union[
        MarkdownWorkflowParams, TextWorkflowParams, JsonWorkflowParams, XlsxWorkflowParams, 
        DocxWorkflowParams, PptxWorkflowParams, SrtWorkflowParams, EpubWorkflowParams, MobiWorkflowParams, HtmlWorkflowParams, QtTsWorkflowParams
    ],
    Field(discriminator='workflow_type')
]


class TranslateServiceRequest(BaseModel):
    """Main request model for translation service."""
    file_name: str = Field(..., description="Original uploaded filename with extension.",
                           examples=["my_paper.pdf", "chapter1.txt", "data.xlsx", "video.srt", "my_book.epub",
                                     "index.html"])
    file_content: str = Field(..., description="Base64 encoded file content.", examples=["JVBERi0xLjQK..."])
    payload: TranslatePayload = Field(..., description="Payload containing workflow type and corresponding parameters.")
    smart_glossary_matching: Optional[bool] = Field(None, description="Override system smart glossary matching switch. If null, use global config.")
    execution_mode: Literal["immediate", "queued"] = Field(
        default="immediate",
        description="immediate: start processing now (legacy). queued: wait for in-process worker pool.",
    )
    relative_path: Optional[str] = Field(
        default=None,
        description="File's relative directory path within the import root (folder or ZIP). "
                    "E.g., 'subdir/chapter1'. Null/empty means root level.",
        examples=[None, "subdir/chapter1"],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "file_name": "annual_report_203.pdf",
                    "file_content": "JVBERi0xLjcKJeLjz9MKMSAwIG9iago8PC9...",
                    "payload": {
                        "workflow_type": "markdown_based",
                        "skip_translate": False,
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "sk-your-api-key-here",
                        "model_id": "gpt-4o",
                        "to_lang": "Chinese",
                        "chunk_size": default_params["chunk_size"],
                        "concurrent": default_params["concurrent"],
                        "temperature": 0.3,
                        "timeout": default_params["timeout"],
                        "thinking": default_params["thinking"],
                        "retry": default_params["retry"],
                        "segment_auto_retry_rounds": 3,
                        "convert_engine": "mineru",
                        "formula_ocr": True,
                        "table_ocr": True,
                        "model_version": "hybrid-auto-engine"
                    }
                }
            ]
        }
