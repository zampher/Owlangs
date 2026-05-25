# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Self, Tuple, Type

from cacher import md_based_convert_cacher
from exporter.base import ExporterConfig
from global_values.conditional_import import DOCLING_EXIST
from glossary.glossary import Glossary
from ir.document import Document
from ir.markdown_document import MarkdownDocument

# Disable docling import in lite version, but balance version needs it
if DOCLING_EXIST:
    from converter.x2md.converter_docling import ConverterDoclingConfig, ConverterDocling
from converter.converter_identity import ConverterIdentity
# Disable MinerU import in lite version, but balance version needs it
from converter.x2md.converter_mineru import ConverterMineruConfig, ConverterMineru
from converter.x2md.base import X2MarkdownConverterConfig, X2MarkdownConverter
from exporter.md.md2html_exporter import MD2HTMLExporterConfig, MD2HTMLExporter
from exporter.md.md2md_exporter import MD2MDExporter
from exporter.md.md2mdzip_exporter import MD2MDZipExporter
from exporter.md.md2docx_exporter import MD2DOCXExporterConfig, MD2DOCXExporter
from exporter.md.types import ConvertEngineType
from logger.logger import LogModule
from workflow.base import Workflow, WorkflowConfig
from workflow.interfaces import MDFormatsExportable, HTMLExportable, DocxExportable
from translator.ai_translator.md_translator import MDTranslatorConfig, MDTranslator


@dataclass(kw_only=True)
class MarkdownBasedWorkflowConfig(WorkflowConfig):
    convert_engine: ConvertEngineType
    converter_config: X2MarkdownConverterConfig | None
    translator_config: MDTranslatorConfig
    html_exporter_config: MD2HTMLExporterConfig
    docx_exporter_config: MD2DOCXExporterConfig = None  # Optional, will use default if not provided
    skip_cache: bool = False  # When True, skip using cached conversion results
    
    def __post_init__(self):
        if self.docx_exporter_config is None:
            self.docx_exporter_config = MD2DOCXExporterConfig()


class MarkdownBasedWorkflow(Workflow[MarkdownBasedWorkflowConfig, Document, MarkdownDocument],
                            HTMLExportable[MD2HTMLExporterConfig],
                            MDFormatsExportable[ExporterConfig],
                            DocxExportable[MD2DOCXExporterConfig]):
    _converter_factory: dict[
        ConvertEngineType, Tuple[Type[X2MarkdownConverter|ConverterIdentity], Type[X2MarkdownConverterConfig]] | None] = {
        "identity": (ConverterIdentity, None)
    }
    
    # Add optional converters (balance version needs)
    if DOCLING_EXIST:
        _converter_factory["docling"] = (ConverterDocling, ConverterDoclingConfig)
    _converter_factory["mineru"] = (ConverterMineru, ConverterMineruConfig)
    _converter_factory["mineru_local"] = (ConverterMineru, ConverterMineruConfig)

    def __init__(self, config: MarkdownBasedWorkflowConfig):
        super().__init__(config=config)
        self.convert_engine = config.convert_engine
        # Attach task_state for MinerU reuse between Extract/Convert/Translate phases
        # This attribute is populated by TranslationService when running inside task workflow.
        self._task_state = None
        # Optional in-memory MinerU ZIP for layout reuse
        self._layout_source_zip = getattr(self, "_layout_source_zip", None)
        # Optional layout document from converter (for high-fidelity PDF generation)
        self.layout_document = None
        if config.logger:
            for sub_config in [self.config.converter_config, self.config.translator_config,
                               self.config.html_exporter_config]:
                if sub_config:
                    sub_config.logger = config.logger

    def _get_document_md(self, convert_engine: ConvertEngineType, convert_config: X2MarkdownConverterConfig):
        if self.document_original is None:
            raise RuntimeError("File has not been read yet. Call read_path or read_bytes first.")

        # Debug logging
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, f"_get_document_md: convert_engine={convert_engine}, convert_config={type(convert_config).__name__ if convert_config else 'None'}, skip_cache={getattr(self.config, 'skip_cache', False)}")

        # First, check if we have a previous MinerU result that can be reused
        # This happens when we're in Convert stage after Extract stage, where
        # the MinerU result was already obtained in Extract stage
        # CRITICAL: Always check for mineru_extract_dir or mineru_zip_path FIRST,
        # regardless of skip_cache or zip_bytes availability, to avoid re-uploading
        # and re-downloading from MinerU server
        reused_mineru_result = None
        if convert_engine in ("mineru", "mineru_local"):
            try:
                import os
                
                # CRITICAL: Check mineru_extract_dir or mineru_zip_path FIRST
                # These are the fastest paths and don't require zip_bytes in memory
                extracted_dir = None
                mineru_zip_path = None
                zip_bytes = None
                
                if hasattr(self, "_task_state") and self._task_state:
                    if self.config.logger:
                        self.config.logger.debug(LogModule.WORKFLOW, f"[MINERU] Task state contains keys: {list(self._task_state.keys())}")
                    
                    # Check mineru_extract_dir first (fastest path)
                    if "mineru_extract_dir" in self._task_state:
                        extracted_dir = self._task_state["mineru_extract_dir"]
                        if self.config.logger:
                            self.config.logger.debug(LogModule.WORKFLOW, f"[MINERU] Found mineru_extract_dir in task_state: {extracted_dir}")
                        
                        if os.path.exists(extracted_dir):
                            if self.config.logger:
                                self.config.logger.info(
                                    LogModule.WORKFLOW,
                                    f"[MINERU] Successfully found existing extracted MinerU directory at {extracted_dir}, "
                                    f"will reuse it directly (skipping MinerU server upload/download)"
                                )
                        else:
                            if self.config.logger:
                                self.config.logger.warning(
                                    LogModule.WORKFLOW,
                                    f"[MINERU] mineru_extract_dir exists in task_state but directory does not exist: {extracted_dir}"
                                )
                            extracted_dir = None
                    
                    # Check mineru_zip_path as fallback
                    if not extracted_dir and "mineru_zip_path" in self._task_state:
                        mineru_zip_path = self._task_state["mineru_zip_path"]
                        if self.config.logger:
                            self.config.logger.debug(LogModule.WORKFLOW, f"[MINERU] Found mineru_zip_path in task_state: {mineru_zip_path}")
                        
                        if os.path.exists(mineru_zip_path):
                            if self.config.logger:
                                self.config.logger.info(
                                    LogModule.WORKFLOW,
                                    f"[MINERU] Found MinerU ZIP file at {mineru_zip_path}, "
                                    f"will reuse it instead of re-uploading to MinerU server"
                                )
                        else:
                            if self.config.logger:
                                self.config.logger.warning(
                                    LogModule.WORKFLOW,
                                    f"[MINERU] mineru_zip_path exists in task_state but file does not exist: {mineru_zip_path}"
                                )
                            mineru_zip_path = None
                
                # If we found extracted_dir or mineru_zip_path, proceed with reuse
                # Otherwise, check for zip_bytes in memory
                if extracted_dir or mineru_zip_path:
                    if self.config.logger:
                        self.config.logger.info(LogModule.WORKFLOW, "[MINERU] Attempting to reuse existing MinerU result from Extract phase")
                else:
                    # Fallback: Check if we have a MinerU attachment available
                    mineru_doc = self.attachment.attachment_dict.get("mineru")
                    
                    if mineru_doc and hasattr(mineru_doc, "content") and mineru_doc.content:
                        zip_bytes = mineru_doc.content
                        if self.config.logger:
                            self.config.logger.debug(LogModule.WORKFLOW, "[MINERU] Found MinerU attachment, will reuse it instead of re-uploading")
                    else:
                        # Fallback: Try to get from layout_source_zip if available
                        if hasattr(self, "_layout_source_zip") and self._layout_source_zip:
                            zip_bytes = self._layout_source_zip
                            if self.config.logger:
                                self.config.logger.debug(LogModule.WORKFLOW, "[MINERU] Found layout_source_zip, will reuse it instead of re-uploading")
                        elif hasattr(self, "_task_state") and self._task_state and "layout_source_zip" in self._task_state:
                            zip_bytes = self._task_state["layout_source_zip"]
                            if self.config.logger:
                                self.config.logger.debug(LogModule.WORKFLOW, "[MINERU] Found layout_source_zip in task_state, will reuse it instead of re-uploading")
                
                # If we have any reusable resource (extracted_dir, mineru_zip_path, or zip_bytes), proceed
                if extracted_dir or mineru_zip_path or zip_bytes:
                    # Reuse the existing MinerU result instead of re-uploading
                    from converter.x2md.converter_mineru import get_md_from_zip_url_with_inline_images
                    import io
                    
                    # Priority 1: Use extracted_dir if available (fastest path, no ZIP extraction needed)
                    if extracted_dir:
                        # Extract Markdown content directly from extracted directory
                        from utils.markdown_utils import embed_inline_image_from_dir
                        filename_in_zip = "full.md"
                        if self.config.logger:
                            self.config.logger.info(LogModule.WORKFLOW, f"[MINERU] Reading Markdown content from extracted directory: {extracted_dir}")
                        md_content = embed_inline_image_from_dir(extracted_dir, filename_in_zip)
                        
                        # Load layout_document from ZIP file (still need ZIP bytes for layout parsing)
                        # Try to get ZIP bytes from task_state, mineru_zip_path, or attachment
                        if not zip_bytes:
                            if hasattr(self, "_task_state") and self._task_state:
                                zip_bytes = self._task_state.get("layout_source_zip")
                                # If not in memory, try to read from mineru_zip_path (use the one we already found)
                                if not zip_bytes and mineru_zip_path and os.path.exists(mineru_zip_path):
                                    try:
                                        with open(mineru_zip_path, 'rb') as f:
                                            zip_bytes = f.read()
                                        if self.config.logger:
                                            self.config.logger.debug(LogModule.WORKFLOW, f"[MINERU] Read ZIP bytes from mineru_zip_path: {mineru_zip_path}")
                                    except Exception as read_error:
                                        if self.config.logger:
                                            self.config.logger.warning(LogModule.WORKFLOW, f"[MINERU] Failed to read ZIP from mineru_zip_path: {read_error}")
                            
                            if not zip_bytes:
                                mineru_doc = self.attachment.attachment_dict.get("mineru")
                                if mineru_doc and hasattr(mineru_doc, "content") and mineru_doc.content:
                                    zip_bytes = mineru_doc.content
                        
                        # Create a MarkdownDocument from the extracted content
                        from ir.markdown_document import MarkdownDocument
                        reused_mineru_result = MarkdownDocument(
                            stem=self.document_original.stem,
                            suffix=".md",
                            content=md_content.encode('utf-8')
                        )
                        
                        # Load layout_document from the ZIP file if available
                        if zip_bytes:
                            try:
                                from layout.registry import load_layout_from_engine_zip
                                self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
                                if self.config.logger and self.layout_document:
                                    self.config.logger.info(
                                        LogModule.WORKFLOW,
                                        f"[MINERU] Loaded layout_document from ZIP bytes ({self.layout_document.page_count} pages)"
                                    )
                            except Exception as layout_error:
                                if self.config.logger:
                                    self.config.logger.warning(
                                        LogModule.WORKFLOW,
                                        f"[MINERU] Failed to load layout_document from ZIP bytes: {layout_error}. "
                                        f"Markdown content is still available."
                                    )
                    # Priority 2: Use mineru_zip_path if available (read from disk)
                    elif mineru_zip_path:
                        if self.config.logger:
                            self.config.logger.info(LogModule.WORKFLOW, f"[MINERU] Reading MinerU ZIP from disk: {mineru_zip_path}")
                        
                        # Read ZIP bytes from file
                        try:
                            with open(mineru_zip_path, 'rb') as f:
                                zip_bytes = f.read()
                            if self.config.logger:
                                self.config.logger.debug(LogModule.WORKFLOW, f"[MINERU] Read ZIP bytes from mineru_zip_path: {len(zip_bytes)} bytes")
                        except Exception as read_error:
                            if self.config.logger:
                                self.config.logger.warning(LogModule.WORKFLOW, f"[MINERU] Failed to read ZIP from mineru_zip_path: {read_error}")
                            raise
                        
                        # Extract Markdown content from the ZIP file
                        with io.BytesIO(zip_bytes) as zip_file:
                            md_content, _ = get_md_from_zip_url_with_inline_images(zip_file_obj=zip_file)
                        
                        # Create a MarkdownDocument from the extracted content
                        from ir.markdown_document import MarkdownDocument
                        reused_mineru_result = MarkdownDocument(
                            stem=self.document_original.stem,
                            suffix=".md",
                            content=md_content.encode('utf-8')
                        )
                        
                        # Load layout_document from the ZIP file
                        from layout.registry import load_layout_from_engine_zip
                        self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
                        
                        if self.config.logger:
                            self.config.logger.info(
                                LogModule.WORKFLOW,
                                f"[MINERU] Successfully reused MinerU ZIP from disk: "
                                f"Markdown content extracted, layout_document loaded ({self.layout_document.page_count} pages)"
                            )
                    
                    # Priority 3: Use zip_bytes if available (already in memory)
                    elif zip_bytes:
                        if self.config.logger:
                            self.config.logger.info(LogModule.WORKFLOW, "[MINERU] Using ZIP bytes from memory for Markdown extraction")
                        # Mock a file-like object from the ZIP bytes
                        with io.BytesIO(zip_bytes) as zip_file:
                            # Extract Markdown content from the ZIP file
                            md_content, _ = get_md_from_zip_url_with_inline_images(zip_file_obj=zip_file)
                        
                        # Create a MarkdownDocument from the extracted content
                        from ir.markdown_document import MarkdownDocument
                        reused_mineru_result = MarkdownDocument(
                            stem=self.document_original.stem,
                            suffix=".md",
                            content=md_content.encode('utf-8')
                        )
                        
                        # Load layout_document from the ZIP file
                        from layout.registry import load_layout_from_engine_zip
                        self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
                        
                        if self.config.logger:
                            self.config.logger.info(
                                LogModule.WORKFLOW,
                                f"[MINERU] Successfully reused MinerU ZIP from memory: "
                                f"Markdown content extracted, layout_document loaded ({self.layout_document.page_count} pages)"
                            )
                    
                    # Add the reused result to cache
                    if reused_mineru_result:
                        md_based_convert_cacher.cache_result(reused_mineru_result, self.document_original, convert_engine, convert_config)
                        if self.config.logger:
                            self.config.logger.info(
                                LogModule.WORKFLOW,
                                f"[MINERU] Cached reused MinerU result for future use"
                            )
            except Exception as e:
                if self.config.logger:
                    self.config.logger.warning(
                        LogModule.WORKFLOW,
                        f"[MINERU] Failed to reuse existing MinerU result: {e}. "
                        f"Will proceed with normal conversion..."
                    )
        
        # If we successfully reused a MinerU result, return it
        if reused_mineru_result:
            return reused_mineru_result
        
        # Get cached parsed file (skip if skip_cache is True)
        document_cached = None
        if not getattr(self.config, 'skip_cache', False):
            document_cached = md_based_convert_cacher.get_cached_result(self.document_original, convert_engine,
                                                                        convert_config)
        else:
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, "Skipping cache (skip_cache=True)")
        
        if document_cached:
            self.attachment.add_document("md_cached",document_cached)
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, "Using cached document")
            
            # IMPORTANT: When using cache, try to load layout_document from MinerU attachment
            # This is critical for PDF generation, as layout_document is not cached
            # Note: When using cache, attachment_dict may be empty, so we need to check
            # if MinerU attachment exists in attachment_dict first, and if not, try to
            # load from layout_source_zip if available (from previous conversion)
            if convert_engine in ("mineru", "mineru_local") and self.layout_document is None:
                try:
                    # First, check if MinerU attachment exists in attachment_dict
                    mineru_doc = self.attachment.attachment_dict.get("mineru")
                    zip_bytes = None
                    
                    if mineru_doc and hasattr(mineru_doc, "content") and mineru_doc.content:
                        zip_bytes = mineru_doc.content
                    else:
                        # Fallback: Try to get from layout_source_zip if available
                        # This can happen when the same file was converted before
                        # and the ZIP was saved in task_state
                        if hasattr(self, "_layout_source_zip") and self._layout_source_zip:
                            zip_bytes = self._layout_source_zip
                            if self.config.logger:
                                self.config.logger.debug(
                                    LogModule.WORKFLOW,
                                    "[LAYOUT] Using layout_source_zip from workflow instance for cached conversion"
                                )
                    
                    if zip_bytes:
                        from layout.registry import load_layout_from_engine_zip
                        self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
                        if self.layout_document and self.config.logger:
                            self.config.logger.info(
                                LogModule.WORKFLOW,
                                f"[LAYOUT] Loaded layout_document from MinerU attachment (cached): "
                                f"{self.layout_document.page_count} pages, "
                                f"{sum(1 for _ in self.layout_document.iter_blocks())} blocks"
                            )
                        elif self.config.logger:
                            # CRITICAL: For PDF files, layout_document is required for segmentation
                            # If we cannot load it from cached conversion, this is a fatal error
                            error_msg = "Failed to parse layout_document from MinerU ZIP (cached conversion). PDF segmentation requires layout information."
                            self.config.logger.error(LogModule.WORKFLOW, f"[LAYOUT] {error_msg}")
                            raise RuntimeError(error_msg)
                    else:
                        # CRITICAL: For PDF files, layout_document is required for segmentation
                        # If MinerU attachment is not available in cached conversion, we need to re-run conversion
                        # to get the layout_document. This can happen when cache is shared across different tasks.
                        if self.config.logger:
                            self.config.logger.warning(
                                LogModule.WORKFLOW,
                                "[LAYOUT] MinerU attachment not available for cached conversion. "
                                "PDF segmentation requires layout information from MinerU ZIP. "
                                "Will re-run MinerU conversion to get layout_document."
                            )
                        # Return None to skip cached document and re-run conversion
                        # This ensures layout_document is available for PDF segmentation
                        return None
                except RuntimeError:
                    # Re-raise RuntimeError (our own errors)
                    raise
                except Exception as layout_load_error:
                    # CRITICAL: For PDF files, layout_document is required for segmentation
                    # If we cannot load it from cached conversion, this is a fatal error
                    error_msg = f"Failed to load layout_document from MinerU attachment (cached conversion): {layout_load_error}. PDF segmentation requires layout information."
                    if self.config.logger:
                        self.config.logger.error(LogModule.WORKFLOW, f"[LAYOUT] {error_msg}")
                    raise RuntimeError(error_msg) from layout_load_error
            
            return document_cached

        # Parse file if not cached and no reused result
        # NOTE:
        # - For Extract/Convert/Translate phases we now prefer reusing MinerU results from:
        #   1) mineru_extract_dir / mineru_zip_path / layout_source_zip on task_state
        #   2) MinerU attachment on workflow.attachment
        # - If none of the above are available, we fall back to calling MinerU directly.
        #   Previously this raised a hard error to force running Extract first, but that
        #   caused translation failures when the user skipped the explicit Extract step.
        #   To keep the UX robust while still encouraging reuse, we only log a warning
        #   instead of blocking the workflow.
        skip_cache = getattr(self.config, 'skip_cache', False)
        if convert_engine in ("mineru", "mineru_local") and not skip_cache and not reused_mineru_result and not document_cached:
            if self.config.logger:
                self.config.logger.warning(
                    LogModule.WORKFLOW,
                    "[MINERU] No cached or Extract-phase MinerU result found. "
                    "Falling back to direct MinerU conversion (this may re-upload the file)."
                )
        
        if convert_engine in self._converter_factory:
            converter_class, config_class = self._converter_factory[convert_engine]
            if config_class and not isinstance(convert_config, config_class):
                if self.config.logger:
                    self.config.logger.error(LogModule.WORKFLOW, f"[ERROR] Type mismatch: expected {config_class.__name__}, got {type(convert_config).__name__}")
                raise TypeError(
                    f"The correct convert_config was not passed. It should be of type {config_class.__name__}, but it is currently of type {type(convert_config).__name__}.")
            
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, f"Creating converter: {converter_class.__name__}")
            
            converter = converter_class(convert_config)
            
            # Set up progress callback for split-PDF extraction
            if (
                convert_engine in ("mineru", "mineru_local")
                and hasattr(converter, "progress_callback")
                and hasattr(self, "_task_state")
                and self._task_state is not None
            ):
                def _extract_progress_callback(current: int, total: int, message: str) -> None:
                    if self._task_state is not None:
                        # Map split progress to 0-25% overall range
                        progress = min(25, int((current / total) * 25))
                        self._task_state["progress"] = progress
                        self._task_state["message"] = f"Extracting PDF... {current}/{total} parts ({progress}%)"
                        self._task_state["extract_pdf_part_current"] = current
                        self._task_state["extract_pdf_part_total"] = total
                
                converter.progress_callback = _extract_progress_callback
            
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, f"Starting conversion with {convert_engine} engine...")
            
            document_md = converter.convert(self.document_original)
            
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, "Conversion completed successfully")
            
            # Clear PDF split part markers so frontend doesn't keep showing part info
            # in later stages (e.g. Detect Language, Translation)
            if hasattr(self, "_task_state") and self._task_state is not None:
                self._task_state.pop("extract_pdf_part_current", None)
                self._task_state.pop("extract_pdf_part_total", None)
                
            if hasattr(converter,"attachments"):
                for attachment in converter.attachments:
                    self.attachment.add_attachment(attachment)
            
            # Capture layout document from converter if available (for high-fidelity PDF)
            if hasattr(converter, "layout_document") and converter.layout_document is not None:
                self.layout_document = converter.layout_document
                if self.config.logger:
                    self.config.logger.debug(
                        LogModule.WORKFLOW,
                        f"[LAYOUT] Captured layout_document from converter: "
                        f"{self.layout_document.page_count} pages"
                    )
            
            # Get cached parsed file
            md_based_convert_cacher.cache_result(document_md, self.document_original, convert_engine, convert_config)

            return document_md
        else:
            raise ValueError(f"Parsing engine {convert_engine} does not exist")

    def _pre_translate(self, document: Document):
        convert_engine: ConvertEngineType = "identity" if document.suffix == ".md" else self.convert_engine
        convert_config = self.config.converter_config
        
        # Debug logging
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, f"_pre_translate: convert_engine={convert_engine}, convert_config={type(convert_config).__name__ if convert_config else 'None'}")
            if convert_config and hasattr(convert_config, 'mineru_token'):
                self.config.logger.debug(LogModule.WORKFLOW, f"_pre_translate: mineru_token={'***' if convert_config.mineru_token else 'empty'}")
        
        # Only create default config if convert_config is None and we have a specific engine
        # This should not happen if the backend properly created the config
        if convert_config is None and convert_engine != "identity":
            if convert_engine in ("mineru", "mineru_local"):
                from converter.x2md.converter_mineru import ConverterMineruConfig
                from backend.config.config_loader import get_unified_config
                pdf_cfg = get_unified_config().system.pdf
                # Use default values if not provided in config
                convert_config = ConverterMineruConfig(
                    mineru_token="",  # Will be injected from local config
                    formula_ocr=True,
                    model_version="vlm",
                    pdf_split_enabled=pdf_cfg.pdf_split_enabled,
                    pdf_split_max_pages=pdf_cfg.pdf_split_max_pages,
                    pdf_split_max_workers=pdf_cfg.pdf_split_max_workers,
                    request_retry_count=pdf_cfg.request_retry_count,
                )
            elif convert_engine == "docling":
                from converter.x2md.converter_docling import ConverterDoclingConfig
                convert_config = ConverterDoclingConfig(
                    formula_ocr=True,
                    code_ocr=True
                )
        
        translator_config = self.config.translator_config
        translator = MDTranslator(translator_config)
        return convert_engine, convert_config, translator_config, translator

    def translate(self) -> Self:
        convert_engine, convert_config, translator_config, translator = self._pre_translate(self.document_original)
        document_md = self._get_document_md(convert_engine, convert_config)
        translator.translate(document_md)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document_md
        return self

    async def translate_async(self, progress_callback=None, task_id: str = None, 
                              original_filename: str = None, workflow_type: str = None) -> Self:
        convert_engine, convert_config, translator_config, translator = self._pre_translate(self.document_original)
        
        # Convert document to markdown (this is the time-consuming part for PDFs)
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, "Starting document conversion...")
        
        # For MinerU conversion, update progress periodically while waiting
        # This provides visual feedback during the potentially long conversion process
        progress_task = None
        
        # Define progress update function (used for both initial and re-conversion)
        async def update_conversion_progress(task_state_ref, task_id_str):
            """Update progress from 10% to 90% (1% per second) during MinerU conversion"""
            current_progress = task_state_ref.get("progress", 10)
            start_progress = max(current_progress, 10)  # Start from current or 10%
            max_progress = 90  # Don't exceed 90% until conversion actually completes
            
            for progress in range(start_progress + 1, max_progress + 1):
                await asyncio.sleep(1)  # Wait 1 second between updates
                
                # Check if conversion has completed (progress might have been updated by other code)
                if task_state_ref.get("progress", 0) >= 90:
                    break
                
                # Update progress
                task_state_ref["progress"] = progress
                task_state_ref["message"] = f"Converting document with MinerU... ({progress}%)"
                
                if self.config.logger:
                    self.config.logger.debug(LogModule.WORKFLOW, f"[PROGRESS] Updated progress to {progress}% during MinerU conversion (task_id={task_id_str})")
        
        if convert_engine in ("mineru", "mineru_local") and task_id:
            try:
                from backend.app.services.task import task_manager
                task_state_ref = task_manager.get_task(task_id)
                if task_state_ref:
                    # Start background task to update progress from 10% to 90% (1% per second)
                    # This simulates progress while waiting for MinerU server response
                    progress_task = asyncio.create_task(update_conversion_progress(task_state_ref, task_id))
                    if self.config.logger:
                        self.config.logger.debug(LogModule.WORKFLOW, f"[PROGRESS] Started progress update task for MinerU conversion (task_id={task_id})")
            except Exception as e:
                if self.config.logger:
                    self.config.logger.warning(LogModule.WORKFLOW, f"[PROGRESS] Failed to start progress update task: {e}")
                progress_task = None
        
        try:
            document_md = await asyncio.to_thread(self._get_document_md, convert_engine, convert_config)
        finally:
            # Cancel progress update task if it's still running
            if progress_task and not progress_task.done():
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
                if self.config.logger:
                    self.config.logger.debug(LogModule.WORKFLOW, f"[PROGRESS] Cancelled progress update task after conversion completed")
        
        # CRITICAL: If document_md is None, it means cached document was skipped due to missing layout_document
        # We need to re-run conversion without cache to get the layout_document
        if document_md is None:
            if self.config.logger:
                self.config.logger.warning(
                    LogModule.WORKFLOW,
                    "[TRANSLATE] Cached document skipped due to missing layout_document. "
                    "Re-running conversion without cache..."
                )
            # Temporarily set skip_cache to True to force re-conversion
            original_skip_cache = getattr(self.config, 'skip_cache', False)
            self.config.skip_cache = True
            
            # Restart progress update task for re-conversion (if using MinerU)
            if convert_engine in ("mineru", "mineru_local") and task_id:
                try:
                    from backend.app.services.task import task_manager
                    task_state_ref_reconv = task_manager.get_task(task_id)
                    if task_state_ref_reconv:
                        # Reset progress and restart update task
                        task_state_ref_reconv["progress"] = 10
                        task_state_ref_reconv["message"] = "Re-running conversion without cache..."
                        progress_task = asyncio.create_task(update_conversion_progress(task_state_ref_reconv, task_id))
                        if self.config.logger:
                            self.config.logger.debug(LogModule.WORKFLOW, f"[PROGRESS] Restarted progress update task for re-conversion (task_id={task_id})")
                except Exception as e:
                    if self.config.logger:
                        self.config.logger.warning(LogModule.WORKFLOW, f"[PROGRESS] Failed to restart progress update task: {e}")
                    progress_task = None
            
            try:
                document_md = await asyncio.to_thread(self._get_document_md, convert_engine, convert_config)
                if document_md is None:
                    error_msg = "Failed to convert document even after re-running without cache. This should not happen."
                    if self.config.logger:
                        self.config.logger.error(LogModule.WORKFLOW, f"[TRANSLATE] {error_msg}")
                    raise RuntimeError(error_msg)
            finally:
                # Cancel progress update task if it's still running
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass
                # Restore original skip_cache value
                self.config.skip_cache = original_skip_cache
        
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, "Document conversion completed, starting translation...")
        
        # Update progress after conversion completes (if using MinerU)
        if convert_engine in ("mineru", "mineru_local") and task_id:
            try:
                from backend.app.services.task import task_manager
                task_state_ref_temp = task_manager.get_task(task_id)
                if task_state_ref_temp:
                    # Set progress to 30% after conversion completes (before translation starts)
                    if task_state_ref_temp.get("progress", 0) < 30:
                        task_state_ref_temp["progress"] = 30
                        task_state_ref_temp["message"] = "Document conversion completed, starting translation..."
                        if self.config.logger:
                            self.config.logger.debug(LogModule.WORKFLOW, f"[PROGRESS] Updated progress to 30% after MinerU conversion completed")
            except Exception:
                pass

        task_state_ref = None
        layout_chunks_cached = None
        layout_markdown_cached = None
        layout_chunk_map_cached = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state_ref = task_manager.get_task(task_id)
                if task_state_ref:
                    layout_chunks_cached = task_state_ref.get("layout_prepared_chunks")
                    layout_markdown_cached = task_state_ref.get("layout_markdown_source")
                    layout_chunk_map_cached = task_state_ref.get("layout_chunk_block_map")
            except Exception:
                task_state_ref = None

        # For PDF inputs with layout information, rebuild markdown text directly
        # from the layout document so that translation chunks align with layout blocks.
        if (
            original_filename
            and original_filename.lower().endswith(".pdf")
            and self.layout_document is not None
            and self.config.translator_config
        ):
            try:
                layout_markdown_text = layout_markdown_cached
                if layout_markdown_text is None:
                    from layout.markdown_builder import LayoutMarkdownBuilder

                    chunk_size = getattr(self.config.translator_config, "chunk_size", 2000) or 2000
                    deep_split_enabled = getattr(self.config.translator_config, "deep_split", True)
                    # Get equation_format from task_state payload (default: "text")
                    equation_format = "text"
                    if task_state_ref:
                        payload = task_state_ref.get("payload")
                        if payload:
                            try:
                                if isinstance(payload, dict):
                                    equation_format = (payload.get("equation_format") or "text").lower()
                                else:
                                    equation_format = (getattr(payload, "equation_format", None) or "text").lower()
                            except Exception:
                                equation_format = "text"
                    if equation_format not in ("text", "image"):
                        equation_format = "text"
                    builder = LayoutMarkdownBuilder(
                        max_chunk_chars=chunk_size, 
                        deep_split=deep_split_enabled,
                        equation_format=equation_format
                    )
                    layout_result = builder.build(self.layout_document)
                    layout_markdown_text = layout_result.markdown_text

                    if task_state_ref is not None:
                        # Do not overwrite layout_prepared_chunks when already present (e.g. inherited from convert).
                        # Reusing Extract-phase chunks preserves is_excluded and segment_indices; overwriting would drop them and cause wrong exclusions.
                        if task_state_ref.get("layout_prepared_chunks") is None:
                            task_state_ref["layout_prepared_chunks"] = [
                                {
                                    "text": chunk.text,
                                    "chunk_type": chunk.chunk_type,
                                    "block_indices": chunk.block_indices,
                                    "image_path": chunk.image_path,
                                    "placeholder_id": chunk.image_placeholder
                                    if chunk.chunk_type == "image"
                                    else None,
                                    "is_image": chunk.chunk_type == "image",
                                }
                                for chunk in layout_result.chunks
                            ]
                            task_state_ref["layout_chunk_block_map"] = [
                                chunk.block_indices for chunk in layout_result.chunks
                            ]
                            task_state_ref["layout_markdown_source"] = layout_markdown_text
                            # P0: Mark layout-driven so export/rebuild use only layout block types (no text heuristics)
                            task_state_ref["source_input_type"] = "layout"
                            if self.config.logger:
                                self.config.logger.debug(
                                    LogModule.WORKFLOW,
                                    f"[LAYOUT] Prepared {len(layout_result.chunks)} layout chunks for task {task_id}; source_input_type=layout"
                                )
                        else:
                            # Reuse inherited chunks; use their layout_markdown_source for document_md so translation aligns with Extract
                            existing_md = task_state_ref.get("layout_markdown_source")
                            if existing_md:
                                layout_markdown_text = existing_md
                            if self.config.logger:
                                self.config.logger.debug(
                                    LogModule.WORKFLOW,
                                    f"[LAYOUT] Task {task_id}: Reusing existing layout_prepared_chunks (e.g. from convert), not overwriting"
                                )

                document_md = MarkdownDocument(
                    content=layout_markdown_text.encode("utf-8"),
                    suffix=".md",
                    stem=self.document_original.stem,
                )
            except Exception as layout_error:
                if self.config.logger:
                    self.config.logger.warning(
                        LogModule.WORKFLOW,
                        f"[LAYOUT] Failed to build layout-based markdown, falling back to MinerU markdown: {layout_error}"
                    )
        
        # CRITICAL: Ensure document_md is not None before translation
        if document_md is None:
            error_msg = "Document conversion failed: document_md is None. This should not happen."
            if self.config.logger:
                self.config.logger.error(LogModule.WORKFLOW, f"[TRANSLATE] {error_msg}")
            raise RuntimeError(error_msg)

        # CRITICAL: For single-phase PDF translation (no convert_task_id), source_chunks_cache
        # is empty because _prepare_markdown_based_preview was skipped (document was still
        # binary at that point). Populate it now from the converted markdown so the
        # segment-based translator can run.
        if task_state_ref is not None:
            cache = task_state_ref.get("source_chunks_cache") or {}
            if not cache.get("segments"):
                try:
                    raw = document_md.content
                    md_content = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                    if md_content.strip():
                        from extractor.markdown_based_extractor import MarkdownBasedExtractor
                        chunk_size = getattr(translator_config, "chunk_size", 2500) or 2500
                        deep_split = getattr(translator_config, "deep_split", True) or True
                        extractor = MarkdownBasedExtractor(
                            md_content,
                            chunk_size=chunk_size,
                            deep_split=deep_split,
                        )
                        result = extractor.extract()
                        if result.total_segments > 0:
                            import hashlib, time
                            content_hash = hashlib.sha1(md_content.encode("utf-8")).hexdigest()
                            task_state_ref["source_chunks_cache"] = {
                                "content_hash": content_hash,
                                "chunk_size": chunk_size,
                                "segments": result.segments,
                                "total_segments": result.total_segments,
                                "created_at": time.time(),
                            }
                            if self.config.logger:
                                self.config.logger.info(
                                    LogModule.WORKFLOW,
                                    f"[TRANSLATE] Populated source_chunks_cache from converted markdown: "
                                    f"{result.total_segments} segments (task_id={task_id})"
                                )
                except Exception as e:
                    if self.config.logger:
                        self.config.logger.warning(
                            LogModule.WORKFLOW,
                            f"[TRANSLATE] Failed to populate source_chunks_cache from converted markdown: {e}"
                        )

        # Translate the markdown document with progress callback and segment recording
        await translator.translate_async(
            document_md, 
            progress_callback=progress_callback,
            task_id=task_id,
            original_filename=original_filename,
            workflow_type=workflow_type
        )
        
        # P0: Default to text-driven when not set (MD/TXT or PDF without layout path)
        if task_state_ref and "source_input_type" not in task_state_ref:
            task_state_ref["source_input_type"] = "text"
            if self.config.logger:
                self.config.logger.debug(LogModule.WORKFLOW, "[LAYOUT] source_input_type=text (no layout path)")
        
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, "Translation completed")
        
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document_md
        return self

    def convert_without_translation(self) -> MarkdownDocument:
        """
        Convert source document to Markdown without invoking the translator.
        Useful for pure format-conversion tasks (skip_translate=True).
        """
        convert_engine, convert_config, *_ = self._pre_translate(self.document_original)
        document_md = self._get_document_md(convert_engine, convert_config)
        self.document_translated = document_md
        return document_md

    async def convert_without_translation_async(self) -> MarkdownDocument:
        """
        Async helper to convert source document to Markdown only.
        """
        convert_engine, convert_config, *_ = self._pre_translate(self.document_original)
        document_md = await asyncio.to_thread(self._get_document_md, convert_engine, convert_config)
        self.document_translated = document_md
        return document_md

    def export_to_html(self, config: MD2HTMLExporterConfig | None = None) -> str:
        config = config or self.config.html_exporter_config
        # Ensure logger is set for debugging
        if config and self.config.logger:
            config.logger = self.config.logger
        if self.config.logger:
            self.config.logger.debug(LogModule.WORKFLOW, f"[MD_WORKFLOW] export_to_html called with config cdn={config.cdn if config else 'None'}")
        docu = self._export(MD2HTMLExporter(config))
        # Robust decoding with fallback encodings
        if isinstance(docu.content, str):
            return docu.content
        elif isinstance(docu.content, bytes):
            try:
                return docu.content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return docu.content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    # Try common encodings
                    for encoding in ['gbk', 'gb2312', 'latin-1', 'cp1252']:
                        try:
                            return docu.content.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    # Final fallback: UTF-8 with error replacement
                    return docu.content.decode('utf-8', errors='replace')
        else:
            raise ValueError(f"Unexpected content type: {type(docu.content)}")

    def export_to_markdown(self, config: ExporterConfig | None = None) -> str:
        docu = self._export(MD2MDExporter())
        # Robust decoding with fallback encodings
        if isinstance(docu.content, str):
            return docu.content
        elif isinstance(docu.content, bytes):
            try:
                return docu.content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return docu.content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    # Try common encodings
                    for encoding in ['gbk', 'gb2312', 'latin-1', 'cp1252']:
                        try:
                            return docu.content.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    # Final fallback: UTF-8 with error replacement
                    return docu.content.decode('utf-8', errors='replace')
        else:
            raise ValueError(f"Unexpected content type: {type(docu.content)}")

    def export_to_markdown_zip(self, config: ExporterConfig | None = None) -> bytes:
        docu = self._export(MD2MDZipExporter())
        return docu.content

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     config: MD2HTMLExporterConfig | None = None) -> Self:
        config = config or self.config.html_exporter_config
        self._save(exporter=MD2HTMLExporter(config=config), name=name, output_dir=output_dir)
        return self

    def save_as_markdown(self, name: str = None, output_dir: Path | str = "./output",
                         _: ExporterConfig | None = None) -> Self:

        self._save(exporter=MD2MDExporter(), name=name, output_dir=output_dir)
        return self

    def save_as_markdown_zip(self, name: str = None, output_dir: Path | str = "./output",
                             _: ExporterConfig | None = None) -> Self:

        self._save(exporter=MD2MDZipExporter(), name=name, output_dir=output_dir)
        return self

    def export_to_docx(self, config: MD2DOCXExporterConfig | None = None) -> bytes:
        """Export markdown document to DOCX format."""
        config = config or self.config.docx_exporter_config
        docu = self._export(MD2DOCXExporter(config))
        return docu.content

    def save_as_docx(self, name: str = None, output_dir: Path | str = "./output",
                     config: MD2DOCXExporterConfig | None = None) -> Self:
        """Save markdown document as DOCX file."""
        config = config or self.config.docx_exporter_config
        self._save(exporter=MD2DOCXExporter(config=config), name=name, output_dir=output_dir)
        return self
