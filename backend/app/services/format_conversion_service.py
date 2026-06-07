# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Format conversion service for Owlangs.

This service handles standalone format conversion (parse + convert, no translation),
reusing translation workflow logic with skip_translate=True.
"""

from __future__ import annotations
import os
import time
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.app.models.service import ConvertFormatRequest, ConvertFormatResponse, FetchUrlRequest
from backend.app.services.task import task_manager
from backend.app.utils.encoding_utils import decode_with_detection
from backend.app.config.pagination_config import SOURCE_PREVIEW_SEGMENTS_LIMIT
from translator import default_params
from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core import ExclusionReason
from backend.config.platforms_config import platform_type_uses_llm_chunk_concurrent

if TYPE_CHECKING:
    from backend.app.services.translation import TranslationService


class FormatConversionService:
    """Service for converting document formats without translation."""
    
    def __init__(self):
        # Use unified_logger instead of standard logging
        pass
    
    def _resolve_chunk_size(self, obj, fallback: int = 3000, task_id: Optional[str] = None, log_prefix: str = "[FORMAT_CONVERSION]") -> int:
        """
        Resolve chunk_size with priority:
        1. obj.chunk_size (explicit override)
        2. Platform config (via obj.platform_key from platforms.json)
        3. fallback
        """
        # Priority 1: Explicit override from obj
        chunk_size = None
        if obj is not None:
            if hasattr(obj, 'chunk_size') and getattr(obj, 'chunk_size') is not None and getattr(obj, 'chunk_size') != 0:
                chunk_size = getattr(obj, 'chunk_size')
            elif isinstance(obj, dict) and obj.get('chunk_size') is not None and obj.get('chunk_size') != 0:
                chunk_size = obj.get('chunk_size')
        if chunk_size:
            logger.info(LogModule.WORKFLOW, f"{log_prefix} Using chunk_size={chunk_size} from explicit override")
            return int(chunk_size)
        
        # Priority 2: Platform config
        platform_key = None
        if obj is not None:
            if hasattr(obj, 'platform_key'):
                platform_key = getattr(obj, 'platform_key')
            elif isinstance(obj, dict):
                platform_key = obj.get('platform_key')
        if platform_key:
            try:
                from backend.config.platforms_config import get_platforms_config
                platforms_config = get_platforms_config()
                platform_cfg = platforms_config.platforms.get(platform_key)
                if (
                    platform_cfg
                    and hasattr(platform_cfg, "chunk_size")
                    and platform_type_uses_llm_chunk_concurrent(platform_cfg.platform_type)
                ):
                    platform_chunk_size = platform_cfg.chunk_size
                    if platform_chunk_size and platform_chunk_size != 0:
                        logger.info(LogModule.WORKFLOW, f"{log_prefix} Using chunk_size={platform_chunk_size} from platform '{platform_key}' config")
                        return int(platform_chunk_size)
            except Exception as e:
                logger.debug(LogModule.WORKFLOW, f"{log_prefix} Failed to get chunk_size from platform config: {e}")
        
        # Priority 3: fallback
        logger.warning(LogModule.WORKFLOW, f"{log_prefix} No chunk_size found in payload or platform config, using fallback={fallback}")
        return fallback
    
    def _get_workflow_type_from_extension(self, file_name: str) -> str:
        """Determine workflow type based on file extension."""
        ext = Path(file_name).suffix.lower()
        ext_to_workflow = {
            '.pdf': 'markdown_based',
            '.docx': 'docx',
            '.doc': 'docx',
            '.pptx': 'pptx',
            '.ppt': 'pptx',
            '.txt': 'txt',
            '.md': 'markdown_based',
            '.html': 'html',
            '.htm': 'html',
            '.xlsx': 'xlsx',
            '.xls': 'xlsx',
            '.csv': 'xlsx',
            '.srt': 'srt',
            '.epub': 'epub',
            '.mobi': 'mobi',
            '.azw': 'mobi',  # Kindle format
            '.json': 'json',
            '.ts': 'qt_ts',  # Qt translation source file
            '.png': 'markdown_based',
            '.jpg': 'markdown_based',
            '.jpeg': 'markdown_based',
        }
        workflow_type = ext_to_workflow.get(ext, 'markdown_based')
        logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Detected workflow_type={workflow_type} for extension={ext}")
        return workflow_type
    
    def _create_translation_payload(self, request: ConvertFormatRequest) -> dict:
        """Create a translation payload with skip_translate=True."""
        # Auto-detect workflow type if not provided
        if request.workflow_type:
            workflow_type = request.workflow_type
            logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Using workflow_type={workflow_type} from request for file={request.file_name}")
        else:
            workflow_type = self._get_workflow_type_from_extension(request.file_name)
            logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Auto-detected workflow_type={workflow_type} from extension for file={request.file_name}")
        
        # Ensure workflow_type is explicitly set in the payload to prevent fallback
        logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Final workflow_type={workflow_type} for file={request.file_name}")
        
        # Import workflow parameter models
        from app.models.service import (
            DocxWorkflowParams,
            MarkdownWorkflowParams,
            TextWorkflowParams,
            JsonWorkflowParams,
            XlsxWorkflowParams,
            HtmlWorkflowParams,
            SrtWorkflowParams,
            EpubWorkflowParams,
            MobiWorkflowParams,
            PptxWorkflowParams,
            QtTsWorkflowParams,
        )
        
        # Create base parameters with skip_translate=True
        # CRITICAL: Use to_lang from request if provided, otherwise use None
        # This ensures exclusion detection uses the correct target language
        # If to_lang is None, language_match detection will be skipped (prevents incorrect detection)
        to_lang = getattr(request, 'to_lang', None) if hasattr(request, 'to_lang') else None
        # CRITICAL: Store to_lang in base_params, but use None if not provided
        # The model may require a value, but we'll use None for exclusion detection
        base_params = {
            'skip_translate': True,
            'to_lang': to_lang if to_lang else None,  # Use request to_lang if provided, otherwise None (prevents incorrect language_match detection)
        }
        # CRITICAL: Log to_lang for debugging
        if to_lang:
            logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Using to_lang={to_lang} from request for exclusion detection")
        else:
            logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] to_lang not provided in request, will skip language_match detection during extraction")
        
        # Add workflow-specific parameters for markdown_based
        if workflow_type == 'markdown_based':
            from backend.config.config_loader import get_unified_config
            global_cfg = get_unified_config()
            parsing_engine = global_cfg.parsing_engine if hasattr(global_cfg, 'parsing_engine') else None
            
            # Get parsing engine settings
            # parsing_engine can be a dict or an object, handle both cases
            convert_engine = request.convert_engine
            if convert_engine is None:
                if isinstance(parsing_engine, dict):
                    convert_engine = parsing_engine.get('convert_engine', 'mineru')
                elif parsing_engine:
                    convert_engine = getattr(parsing_engine, 'convert_engine', 'mineru')
                else:
                    convert_engine = 'mineru'
                logger.debug(
                    LogModule.WORKFLOW,
                    f"[FORMAT_CONVERSION] convert_engine not in request; using server default "
                    f"convert_engine={convert_engine}",
                )
            # Images: always use MinerU for OCR (extract text for translation)
            _name = (request.file_name or "").lower()
            file_ext = ("." + _name.rsplit(".", 1)[-1]) if "." in _name else ""
            if file_ext in (".jpg", ".jpeg", ".png"):
                convert_engine = "mineru"
                logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Image file detected ({file_ext}), using MinerU for OCR to extract text")
            
            formula_ocr = request.formula_ocr
            if formula_ocr is None:
                if isinstance(parsing_engine, dict):
                    formula_ocr = parsing_engine.get('formula_ocr', True)
                elif parsing_engine:
                    formula_ocr = getattr(parsing_engine, 'formula_ocr', True)
                else:
                    formula_ocr = True
            
            table_ocr = request.table_ocr
            if table_ocr is None:
                if isinstance(parsing_engine, dict):
                    table_ocr = parsing_engine.get('table_ocr', True)
                elif parsing_engine:
                    table_ocr = getattr(parsing_engine, 'table_ocr', True)
                else:
                    table_ocr = True
            
            model_version = request.model_version
            if model_version is None:
                if isinstance(parsing_engine, dict):
                    model_version = parsing_engine.get('mineru_model_version', 'hybrid-auto-engine')
                elif parsing_engine:
                    model_version = getattr(parsing_engine, 'mineru_model_version', 'hybrid-auto-engine')
                else:
                    model_version = 'hybrid-auto-engine'
                # Prefer hybrid for images (better OCR/layout); keep vlm/pipeline if explicitly set
                if file_ext in (".jpg", ".jpeg", ".png"):
                    model_version = "hybrid-auto-engine"
                    logger.info(LogModule.WORKFLOW, "[FORMAT_CONVERSION] Image file: using MinerU hybrid backend for OCR")
            elif file_ext in (".jpg", ".jpeg", ".png") and model_version not in ("hybrid-auto-engine", "hybrid-http-client", "hybrid", "pipeline"):
                logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Image file with model_version={model_version}; consider 'hybrid' for better OCR")
            # OCR language: explicit request.ocr_language, else to_lang as hint (e.g. zh/en), else auto
            ocr_language = getattr(request, "ocr_language", None)
            if not (ocr_language and str(ocr_language).strip()):
                to_lang = getattr(request, "to_lang", None) or (base_params.get("to_lang") if isinstance(base_params.get("to_lang"), str) else None)
                if to_lang and len(str(to_lang).strip()) <= 6:
                    ocr_language = str(to_lang).strip().lower()
                else:
                    ocr_language = "auto"
            else:
                ocr_language = str(ocr_language).strip()
            logger.debug(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] MinerU ocr_language={ocr_language} (from request or to_lang)")

            # Use centralized configuration for deep_split defaults (file_ext set above for image check)
            from backend.config.translation_config import get_default_deep_split
            logger.info(
                LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] Determining deep_split for markdown_based workflow: "
                f"filename={request.file_name}, extension={file_ext}"
            )
            default_deep_split = get_default_deep_split(request.file_name, 'markdown_based')
            user_deep_split = getattr(request, 'deep_split', None)
            final_deep_split = user_deep_split if user_deep_split is not None else default_deep_split
            logger.info(
                LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] deep_split for markdown_based workflow: "
                f"filename={request.file_name}, extension={file_ext}, "
                f"default={default_deep_split}, user_provided={user_deep_split}, final={final_deep_split}"
            )
            
            # Get chunk_size with full priority chain (request > platform config > app_config > fallback)
            chunk_size = self._resolve_chunk_size(request, fallback=3000, log_prefix="[FORMAT_CONVERSION]")
            
            # Get skip_cache from request (Extract phase: True, Convert phase: False)
            skip_cache = getattr(request, 'skip_cache', False)
            logger.info(
                LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] skip_cache from request: {skip_cache} "
                f"(type: {type(skip_cache)}, request has skip_cache: {hasattr(request, 'skip_cache')})"
            )
            
            markdown_params = {
                **base_params,
                'workflow_type': 'markdown_based',
                'convert_engine': convert_engine,
                'formula_ocr': formula_ocr,
                'table_ocr': table_ocr,
                'model_version': model_version,
                'ocr_language': ocr_language,
                'deep_split': final_deep_split,
                'skip_cache': skip_cache,
                'platform_key': getattr(request, 'platform_key', None),
            }
            logger.info(
                LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] Created markdown_params with skip_cache={skip_cache} "
                f"for file={request.file_name}"
            )
            # Add chunk_size if we got it and it's not 0, otherwise use fallback 3000
            if chunk_size is not None and chunk_size != 0:
                markdown_params['chunk_size'] = chunk_size
                logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Added chunk_size={chunk_size} to markdown_based workflow params")
            else:
                markdown_params['chunk_size'] = 3000  # Fallback value
                logger.warning(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] No valid chunk_size provided, using fallback value 3000 for markdown_based workflow")
            
            # Add MinerU token if needed (mineru: required; mineru_local: optional)
            mineru_token = ''
            if markdown_params['convert_engine'] == 'mineru':
                if request.mineru_token and request.mineru_token.strip():
                    mineru_token = request.mineru_token.strip()
                else:
                    from backend.config.secrets_manager import SecretsManager
                    secrets = SecretsManager()
                    mineru_token = secrets.get_mineru_token() or ''
                    mineru_token = mineru_token.strip() if mineru_token else ''
                markdown_params['mineru_token'] = mineru_token
                if not mineru_token:
                    logger.warning(LogModule.WORKFLOW, "MinerU API Key is empty! Format conversion will fail. Please configure MinerU API Key in Settings -> AI Platform -> MinerU.")
                else:
                    logger.debug(LogModule.WORKFLOW, f"MinerU token provided (length: {len(mineru_token)}) for format conversion")
            elif markdown_params['convert_engine'] == 'mineru_local':
                # Get MinerU Local token from secrets (optional for local deployment)
                from backend.config.secrets_manager import SecretsManager
                secrets = SecretsManager()
                mineru_token = secrets.get_mineru_local_token() or ''
                mineru_token = mineru_token.strip() if mineru_token else ''
                # Request-provided token takes precedence
                if request.mineru_token and request.mineru_token.strip():
                    mineru_token = request.mineru_token.strip()
                markdown_params['mineru_token'] = mineru_token
                logger.debug(LogModule.WORKFLOW, f"Local MinerU token: {'provided' if mineru_token else 'empty (optional)'}")

            return MarkdownWorkflowParams(**markdown_params)
        
        # For other workflows, use simpler parameters
        workflow_class_map = {
            'docx': DocxWorkflowParams,
            'pptx': PptxWorkflowParams,
            'txt': TextWorkflowParams,
            'json': JsonWorkflowParams,
            'xlsx': XlsxWorkflowParams,
            'html': HtmlWorkflowParams,
            'srt': SrtWorkflowParams,
            'epub': EpubWorkflowParams,
            'mobi': MobiWorkflowParams,
            'qt_ts': QtTsWorkflowParams,
        }
        
        workflow_class = workflow_class_map.get(workflow_type)
        logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Looking up workflow_class for workflow_type={workflow_type}, found={workflow_class is not None}")
        logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Available workflow types in map: {list(workflow_class_map.keys())}")
        logger.info(LogModule.WORKFLOW, f"[FORMAT_CONVERSION] Requested workflow_type type: {type(workflow_type)}, value: {repr(workflow_type)}")
        if workflow_class:
            # Use centralized configuration for deep_split defaults
            from backend.config.translation_config import get_default_deep_split
            from pathlib import Path
            file_ext = Path(request.file_name).suffix.lower()
            logger.info(LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] Determining deep_split for {workflow_type} workflow: "
                f"filename={request.file_name}, extension={file_ext}"
            )
            default_deep_split = get_default_deep_split(request.file_name, workflow_type)
            user_deep_split = getattr(request, 'deep_split', None)
            final_deep_split = user_deep_split if user_deep_split is not None else default_deep_split
            logger.info(LogModule.WORKFLOW,
                f"[FORMAT_CONVERSION] deep_split for {workflow_type} workflow: "
                f"filename={request.file_name}, extension={file_ext}, "
                f"default={default_deep_split}, user_provided={user_deep_split}, final={final_deep_split}"
            )
            
            # Get chunk_size with full priority chain (request > platform config > app_config > fallback)
            chunk_size = self._resolve_chunk_size(request, fallback=3000, log_prefix="[FORMAT_CONVERSION]")
            
            params = {
                **base_params,
                'workflow_type': workflow_type,
                'deep_split': final_deep_split,
                'platform_key': getattr(request, 'platform_key', None),
            }
            # Add chunk_size if we got it and it's not 0, otherwise use fallback 3000
            if chunk_size is not None and chunk_size != 0:
                params['chunk_size'] = chunk_size
                logger.info(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] Added chunk_size={chunk_size} to {workflow_type} workflow params")
            else:
                params['chunk_size'] = 3000  # Fallback value
                logger.warning(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] No valid chunk_size provided, using fallback value 3000 for {workflow_type} workflow")
            result = workflow_class(**params)
            logger.info(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] Created {workflow_type} workflow params: workflow_type={result.workflow_type}, skip_translate={result.skip_translate}")
            return result
        
        # Fallback to markdown_based
        logger.error(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] CRITICAL: Unknown workflow type: {workflow_type} (type: {type(workflow_type)}, repr: {repr(workflow_type)}), falling back to markdown_based")
        logger.error(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] Available workflow types: {list(workflow_class_map.keys())}")
        logger.error(LogModule.WORKFLOW,f"[FORMAT_CONVERSION] File extension: {Path(request.file_name).suffix.lower()}")
        # Use centralized configuration for deep_split defaults
        from backend.config.translation_config import get_default_deep_split
        from pathlib import Path
        file_ext = Path(request.file_name).suffix.lower()
        logger.info(LogModule.WORKFLOW,
            f"[FORMAT_CONVERSION] Determining deep_split for fallback markdown_based workflow: "
            f"filename={request.file_name}, extension={file_ext}"
        )
        default_deep_split = get_default_deep_split(request.file_name, 'markdown_based')
        user_deep_split = getattr(request, 'deep_split', None)
        final_deep_split = user_deep_split if user_deep_split is not None else default_deep_split
        logger.info(LogModule.WORKFLOW,
            f"[FORMAT_CONVERSION] deep_split for fallback markdown_based workflow: "
            f"filename={request.file_name}, extension={file_ext}, "
            f"default={default_deep_split}, user_provided={user_deep_split}, final={final_deep_split}"
        )
        
        # Get chunk_size: priority: request > user settings > fallback 3000
        chunk_size = None
        # Get chunk_size with full priority chain (request > platform config > app_config > fallback)
        chunk_size = self._resolve_chunk_size(request, fallback=3000, log_prefix="[FORMAT_CONVERSION]")
        
        fallback_params = {
            **base_params,
            'workflow_type': 'markdown_based',
            'deep_split': final_deep_split,
            'chunk_size': chunk_size,
            'platform_key': getattr(request, 'platform_key', None),
        }
        return MarkdownWorkflowParams(**fallback_params)
    
    async def convert_format(self, request: ConvertFormatRequest) -> ConvertFormatResponse:
        """
        Convert document format without translation.
        
        Args:
            request: Format conversion request
            
        Returns:
            ConvertFormatResponse with task_id for async processing
        """
        try:
            import base64
            import uuid
            
            logger.info(LogModule.WORKFLOW,f"[IMPORT] Format conversion started: filename={request.file_name}, "
                           f"file_content_length={len(request.file_content) if request.file_content else 0} chars (base64), "
                           f"workflow_type={request.workflow_type}, convert_engine={request.convert_engine}")
            
            # Decode file content
            try:
                file_contents = base64.b64decode(request.file_content)
                logger.info(LogModule.WORKFLOW,f"[IMPORT] File decoded successfully: decoded_size={len(file_contents)} bytes")
            except Exception as e:
                logger.error(LogModule.WORKFLOW,f"[IMPORT] Failed to decode Base64 file content: filename={request.file_name}, error={e}", exc_info=True)
                return ConvertFormatResponse(
                    success=False,
                    message=f"Invalid Base64 file content: {e}"
                )
            
            # Generate task ID
            task_id = uuid.uuid4().hex[:8]
            logger.info(LogModule.WORKFLOW,f"[IMPORT] Generated task_id: {task_id}")
            
            # Create payload with skip_translate=True
            try:
                payload = self._create_translation_payload(request)
                payload_workflow_type = getattr(payload, 'workflow_type', 'unknown')
                logger.info(LogModule.WORKFLOW,f"[IMPORT] Payload created: workflow_type={payload_workflow_type}, "
                               f"skip_translate={getattr(payload, 'skip_translate', False)}, "
                               f"filename={request.file_name}")
                
                # Verify workflow_type matches file extension
                file_ext = Path(request.file_name).suffix.lower()
                if file_ext == '.pptx' and payload_workflow_type != 'pptx':
                    logger.error(LogModule.WORKFLOW,f"[IMPORT] MISMATCH: File extension is .pptx but workflow_type is {payload_workflow_type}! This will cause incorrect workflow routing.")
                elif file_ext == '.pptx' and payload_workflow_type == 'pptx':
                    logger.info(LogModule.WORKFLOW,f"[IMPORT] VERIFIED: File extension .pptx correctly mapped to workflow_type=pptx")
            except Exception as e:
                logger.error(LogModule.WORKFLOW,f"[IMPORT] Failed to create translation payload: task_id={task_id}, filename={request.file_name}, error={e}", exc_info=True)
                return ConvertFormatResponse(
                    success=False,
                    message=f"Failed to create translation payload: {str(e)}"
                )
            
            # Start translation task (which will skip translation)
            try:
                from backend.app.services.translation import TranslationService
                translation_service = TranslationService(task_manager)
                response_data = await translation_service.start_translation_task(
                    task_id=task_id,
                    payload=payload,
                    file_contents=file_contents,
                    original_filename=request.file_name
                )
                logger.info(LogModule.WORKFLOW,f"[IMPORT] Format conversion task started: task_id={task_id}, response={response_data}")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(LogModule.WORKFLOW,f"[IMPORT] Failed to start translation task: task_id={task_id}, filename={request.file_name}, error={e}", exc_info=True)
                return ConvertFormatResponse(
                    success=False,
                    message=f"Failed to start translation task: {str(e)}"
                )
            
            # Mark task as format conversion task
            if task_manager.get_task(task_id) is not None:
                task_manager.update_task(task_id, {
                    "is_format_conversion": True,
                    "convert_only": True,
                    "status_message": "Format conversion in progress..."
                })
            
            return ConvertFormatResponse(
                success=True,
                message="Format conversion task started successfully",
                task_id=task_id
            )
            
        except Exception as e:
            logger.error(LogModule.WORKFLOW,f"Format conversion failed: {e}")
            return ConvertFormatResponse(
                success=False,
                message=f"Format conversion failed: {str(e)}"
            )
    
    async def fetch_url(self, request: FetchUrlRequest) -> ConvertFormatResponse:
        """
        Fetch a URL, download its HTML content, and start a format conversion task.

        Args:
            request: Fetch URL request with extraction mode and parameters.

        Returns:
            ConvertFormatResponse with task_id for async processing.
        """
        try:
            import base64
            import uuid
            from backend.app.utils.url_fetcher import fetch_url_content, extract_main_content

            url = request.url.strip()
            logger.info(
                LogModule.WORKFLOW,
                f"[IMPORT] URL fetch started: url={url}, extract_mode={request.extract_mode}",
            )

            # 1. Download raw HTML
            try:
                raw_bytes = fetch_url_content(url)
            except Exception as e:
                logger.error(
                    LogModule.WORKFLOW,
                    f"[IMPORT] Failed to fetch URL: {url}, error={e}",
                    exc_info=True,
                )
                return ConvertFormatResponse(
                    success=False,
                    message=f"Failed to fetch URL: {str(e)}"
                )

            # 2. Extract content based on mode
            if request.extract_mode == "full":
                raw_html = decode_with_detection(raw_bytes)
                from backend.app.utils.url_fetcher import _sanitize_full_html
                html_content = _sanitize_full_html(raw_html, url=url)
                logger.info(LogModule.WORKFLOW, f"[IMPORT] Using full HTML (sanitized): {len(html_content)} chars")
            else:
                # Default to content extraction
                html_content = extract_main_content(raw_bytes, url=url)
                logger.info(LogModule.WORKFLOW, f"[IMPORT] Extracted main content: {len(html_content)} chars")

            # 3. Encode as base64 to reuse existing pipeline
            file_contents = html_content.encode("utf-8")
            file_content_b64 = base64.b64encode(file_contents).decode("ascii")

            # 4. Generate task ID
            task_id = uuid.uuid4().hex[:8]

            # 5. Build a pseudo ConvertFormatRequest and reuse existing logic
            from backend.app.models.service import ConvertFormatRequest
            pseudo_request = ConvertFormatRequest(
                file_name="fetched.html",
                file_content=file_content_b64,
                workflow_type=request.workflow_type or "html",
                to_lang=request.to_lang,
                deep_split=request.deep_split,
                skip_cache=request.skip_cache,
            )

            # 6. Reuse existing convert_format logic
            result = await self.convert_format(pseudo_request)

            # 7. Mark original URL in task state for reference
            if result.success and task_manager.get_task(result.task_id) is not None:
                task_manager.update_task(result.task_id, {
                    "source_url": url,
                    "extract_mode": request.extract_mode or "content",
                })
                logger.info(
                    LogModule.WORKFLOW,
                    f"[IMPORT] URL fetch task started: task_id={result.task_id}, url={url}",
                )

            # 8. Include the fetched HTML content so the frontend can populate
            #    pickedFile.bytes without re-downloading or re-uploading empty bytes.
            if result.success:
                result.file_content = file_content_b64
                logger.info(
                    LogModule.WORKFLOW,
                    f"[IMPORT] URL fetch returning file_content: "
                    f"{len(file_content_b64)} chars base64, task_id={result.task_id}",
                )

            return result

        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"URL fetch failed: {e}", exc_info=True)
            return ConvertFormatResponse(
                success=False,
                message=f"URL fetch failed: {str(e)}"
            )

    async def resplit_source(
        self,
        task_id: str,
        chunk_size: Optional[int] = None,
        excluded_segment_indices: Optional[str] = None,
        ocr_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-split source text segments with a new chunk size.
        
        Args:
            task_id: Unique task identifier
            chunk_size: Override chunk size (optional)
            excluded_segment_indices: Comma-separated list of segment indices to exclude (optional)
            
        Returns:
            Dictionary with resplit result
            
        Raises:
            HTTPException: If task not found or original file not available
        """
        st = task_manager.get_task(task_id)
        if st is None:
            raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
        original_file_path = st.get("original_file_path")
        if not original_file_path or not os.path.exists(original_file_path):
            raise HTTPException(status_code=400, detail="Original file not available for re-splitting.")
        
        # CRITICAL: resplit_source is a re-extract operation
        # Clear existing exclusion data to regenerate it
        segments_metadata = st.get("segments_metadata", {})
        segments_metadata["excluded_segments"] = {}
        segments_metadata["excluded_segment_indices"] = []
        # NOTE: We preserve user_unexcluded_segments to prevent re-detection
        # of segments that user explicitly unexcluded
        logger.info(
            LogModule.WORKFLOW,
            f"[RESPLIT] Task {task_id}: Re-extract operation, cleared excluded_segments and excluded_segment_indices. "
            f"Preserved user_unexcluded_segments: {segments_metadata.get('user_unexcluded_segments', [])}"
        )
        
        # Get workflow type from payload or task state
        payload = st.get("payload")
        workflow_type = getattr(payload, 'workflow_type', None) if payload else None
        if not workflow_type:
            # Try to infer from original filename
            suffix = Path(original_file_path).suffix.lower()
            if suffix == '.pdf':
                workflow_type = 'pdf'
            elif suffix in ['.md', '.markdown']:
                workflow_type = 'markdown_based'
            elif suffix == '.txt':
                workflow_type = 'txt'
            elif suffix == '.json':
                workflow_type = 'json'
            elif suffix in ['.xlsx', '.xls']:
                workflow_type = 'xlsx'
            elif suffix in ['.docx', '.doc']:
                workflow_type = 'docx'
            elif suffix in ['.html', '.htm']:
                workflow_type = 'html'
            elif suffix == '.srt':
                workflow_type = 'srt'
            elif suffix in ['.pptx', '.ppt']:
                workflow_type = 'pptx'
            else:
                workflow_type = 'markdown_based'  # Default fallback
        
        # If an explicit OCR language is provided, update payload so that
        # subsequent MinerU conversions (including Re-extract) use the new value.
        if ocr_language is not None and str(ocr_language).strip():
            if isinstance(payload, dict):
                payload["ocr_language"] = str(ocr_language).strip()
            else:
                # SimpleNamespace or pydantic-like object
                try:
                    setattr(payload, "ocr_language", str(ocr_language).strip())
                except Exception:
                    pass
            st["payload"] = payload

        # Resolve chunk size: priority: query parameter > platform config > app_config.json > payload > cache > default
        if chunk_size is None or chunk_size == 0:
            # Priority 1: Platform config (via payload platform_key)
            if payload:
                platform_key = payload.get("platform_key") if isinstance(payload, dict) else getattr(payload, 'platform_key', None)
                if platform_key:
                    try:
                        from backend.config.platforms_config import get_platforms_config
                        platforms_config = get_platforms_config()
                        platform_cfg = platforms_config.platforms.get(platform_key)
                        if (
                            platform_cfg
                            and hasattr(platform_cfg, "chunk_size")
                            and platform_type_uses_llm_chunk_concurrent(platform_cfg.platform_type)
                        ):
                            platform_chunk_size = platform_cfg.chunk_size
                            if platform_chunk_size and platform_chunk_size != 0:
                                chunk_size = int(platform_chunk_size)
                                logger.info(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Using chunk_size={chunk_size} from platform '{platform_key}' config")
                    except Exception as e:
                        logger.debug(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Failed to get chunk_size from platform config: {e}")
        
        # Priority 2: Get from payload
        if chunk_size is None or chunk_size == 0:
            if payload:
                if isinstance(payload, dict):
                    chunk_size = payload.get("chunk_size")
                else:
                    chunk_size = getattr(payload, 'chunk_size', None)
        
        # Priority 4: Get from cache
        if chunk_size is None or chunk_size == 0:
            chunk_size = st.get("source_chunks_cache", {}).get("chunk_size")
        
        # Priority 5: Use default
        if chunk_size is None or chunk_size == 0:
            chunk_size = default_params.get("chunk_size", 3000)
            logger.warning(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: chunk_size is None or 0, using fallback value {chunk_size}")
        
        # CRITICAL: If excluded_segment_indices are provided via query parameter,
        # update segments_metadata before processing to ensure they are included
        # This allows frontend to mark segments as excluded (e.g., references) and have them
        # automatically excluded when regenerating chunks during Re-extract
        if excluded_segment_indices:
            try:
                # Parse comma-separated list of indices
                excluded_indices_list = [int(x.strip()) for x in excluded_segment_indices.split(',') if x.strip().isdigit()]
                if excluded_indices_list:
                    if "segments_metadata" not in st:
                        st["segments_metadata"] = {}
                    existing_excluded = set(st["segments_metadata"].get("excluded_segment_indices", []))
                    merged_excluded = sorted(list(existing_excluded.union(excluded_indices_list)))
                    st["segments_metadata"]["excluded_segment_indices"] = merged_excluded
                    logger.info(LogModule.EXPORT,f"[RESPLIT] Task {task_id}: Updated segments_metadata with {len(excluded_indices_list)} excluded segment indices from query parameter (total: {len(merged_excluded)})")
            except Exception as e:
                logger.warning(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Failed to parse excluded_segment_indices from query parameter: {e}")
        
        # Update chunk_size in task_state for PDF workflow
        if workflow_type == 'pdf':
            if payload:
                if isinstance(payload, dict):
                    payload["chunk_size"] = chunk_size
                else:
                    setattr(payload, 'chunk_size', chunk_size)
            st["segments_metadata"] = st.get("segments_metadata", {})
            st["segments_metadata"]["chunk_size"] = chunk_size
        
        try:
            # Handle MinerU layout-based workflows (PDF or image/markdown_based with MinerU)
            # We treat both pdf and markdown_based tasks that have MinerU layout data
            # (layout_document/layout_source_zip/attachments['mineru']) as layout-based.
            is_layout_based = workflow_type == "pdf" or (
                workflow_type == "markdown_based"
                and (
                    st.get("layout_document") is not None
                    or st.get("layout_source_zip") is not None
                    or "mineru" in st.get("attachments", {})
                )
            )
            if is_layout_based:
                layout_doc = st.get("layout_document")
                
                # If layout_document is not available, try to load from layout_source_zip or attachments
                if layout_doc is None:
                    logger.info(LogModule.WORKFLOW, f"[RESPLIT] layout_document not in task_state, attempting to load from layout_source_zip or attachments")
                    # Try layout_source_zip first
                    layout_source_zip = st.get("layout_source_zip")
                    if layout_source_zip:
                        try:
                            from layout.registry import load_layout_from_engine_zip
                            layout_doc = load_layout_from_engine_zip("mineru", layout_source_zip)
                            if layout_doc:
                                # Store in task_state for future use
                                st["layout_document"] = layout_doc
                                logger.info(LogModule.WORKFLOW, f"[RESPLIT] Loaded layout_document from layout_source_zip for task {task_id}")
                        except Exception as load_error:
                            logger.warning(LogModule.WORKFLOW, f"[RESPLIT] Failed to load layout_document from layout_source_zip: {load_error}")
                    
                    # If still not available, try attachments
                    if layout_doc is None:
                        attachments = st.get("attachments", {})
                        if "mineru" in attachments:
                            mineru_attachment = attachments["mineru"]
                            zip_bytes = None
                            if hasattr(mineru_attachment, "content"):
                                zip_bytes = mineru_attachment.content
                            elif hasattr(mineru_attachment, "document") and hasattr(mineru_attachment.document, "content"):
                                zip_bytes = mineru_attachment.document.content
                            
                            if zip_bytes:
                                try:
                                    from layout.registry import load_layout_from_engine_zip
                                    layout_doc = load_layout_from_engine_zip("mineru", zip_bytes)
                                    if layout_doc:
                                        # Store in task_state for future use
                                        st["layout_document"] = layout_doc
                                        # Also store layout_source_zip for future use
                                        st["layout_source_zip"] = zip_bytes
                                        logger.info(LogModule.WORKFLOW, f"[RESPLIT] Loaded layout_document from MinerU attachment for task {task_id}")
                                except Exception as load_error:
                                    logger.warning(LogModule.WORKFLOW, f"[RESPLIT] Failed to load layout_document from MinerU attachment: {load_error}")
                
                # Always restart MinerU conversion for markdown_based MinerU workflows
                # when Re-extract is triggered so that updated OCR language (ocr_language)
                # can take effect. Existing layout_document (if any) will be replaced.
                logger.info(
                    LogModule.WORKFLOW,
                    f"[RESPLIT] Restarting MinerU conversion for task {task_id} "
                    f"to apply updated OCR language and regenerate layout document...",
                )
                # Clear old error so UI shows "Re-extracting..." instead of previous failure message; new error will be set if this run fails
                task_manager.update_task(task_id, {
                    "status": "processing",
                    "progress": 10,
                    "message": "Re-extracting...",
                    "error": "",
                })
                
                # Read original file
                if not original_file_path or not os.path.exists(original_file_path):
                    raise HTTPException(
                        status_code=400,
                        detail="Original file not available. Cannot restart MinerU conversion without original file."
                    )
                if not payload:
                    raise HTTPException(
                        status_code=400,
                        detail="Task payload not found. Cannot restart MinerU conversion without original task parameters."
                    )
                
                try:
                    with open(original_file_path, "rb") as f:
                        file_contents = f.read()

                    # CRITICAL: Refresh convert_engine from current global settings so Re-extract
                    # uses the latest platform configuration (e.g., user switched from local to cloud MinerU)
                    from backend.config.config_loader import get_unified_config
                    global_cfg = get_unified_config()
                    parsing_engine_cfg = global_cfg.parsing_engine if hasattr(global_cfg, 'parsing_engine') else None
                    
                    if parsing_engine_cfg and isinstance(parsing_engine_cfg, dict):
                        current_convert_engine = parsing_engine_cfg.get('convert_engine')
                        if current_convert_engine:
                            if isinstance(payload, dict):
                                payload['convert_engine'] = current_convert_engine
                                # Also refresh related settings from global config
                                payload['formula_ocr'] = parsing_engine_cfg.get('formula_ocr', payload.get('formula_ocr', True))
                                payload['table_ocr'] = parsing_engine_cfg.get('table_ocr', payload.get('table_ocr', True))
                                payload['model_version'] = parsing_engine_cfg.get('mineru_model_version', payload.get('model_version', 'hybrid-auto-engine'))
                                # Clear cached workflow_config so it gets rebuilt with updated settings
                                payload['workflow_config'] = None
                            else:
                                setattr(payload, 'convert_engine', current_convert_engine)
                                if hasattr(payload, 'workflow_config'):
                                    setattr(payload, 'workflow_config', None)
                            st["payload"] = payload
                            logger.info(
                                LogModule.WORKFLOW,
                                f"[RESPLIT] Updated payload convert_engine to '{current_convert_engine}' from global settings for task {task_id}"
                            )
                    
                    # Build workflow config: use stored config if present, else build from task_state payload
                    workflow_config = None
                    if payload:
                        if isinstance(payload, dict):
                            workflow_config = payload.get("workflow_config")
                        else:
                            workflow_config = getattr(payload, "workflow_config", None)

                    # Payload for factory must support getattr (config builder expects object-style)
                    payload_for_factory = payload
                    if payload is not None and isinstance(payload, dict):
                        from types import SimpleNamespace

                        payload_for_factory = SimpleNamespace(**payload)

                    from backend.app.services.translation import TranslationService

                    translation_service = TranslationService(task_manager)
                    workflow_type_str = "markdown_based"
                    workflow = translation_service.workflow_factory.create_workflow(
                        workflow_type_str,
                        config=workflow_config,
                        task_id=task_id,
                        task_state=st,
                        payload=payload_for_factory if workflow_config is None else None,
                        synthesized_prompt=None,
                    )

                    if not workflow:
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to create workflow for MinerU conversion.",
                        )

                    # Read file into workflow
                    file_stem = Path(original_file_path).stem
                    file_suffix = Path(original_file_path).suffix
                    workflow.read_bytes(
                        content=file_contents, stem=file_stem, suffix=file_suffix
                    )
                    workflow._file_read = True

                    # Execute MinerU conversion
                    from app.services.translation.workflow_executor import WorkflowExecutor

                    workflow_executor = WorkflowExecutor(task_manager)
                    await workflow_executor.execute_convert(
                        task_id=task_id,
                        workflow=workflow,
                        payload=payload,
                        task_state=st,
                    )

                    # After conversion, try to load layout_document again
                    layout_doc = st.get("layout_document")
                    if layout_doc is None:
                        # Try to load from layout_source_zip or attachments again
                        layout_source_zip = st.get("layout_source_zip")
                        if layout_source_zip:
                            try:
                                from layout.registry import load_layout_from_engine_zip

                                layout_doc = load_layout_from_engine_zip(
                                    "mineru", layout_source_zip
                                )
                                if layout_doc:
                                    st["layout_document"] = layout_doc
                                    logger.info(
                                        LogModule.EXPORT,
                                        f"[RESPLIT] Loaded layout_document after MinerU conversion for task {task_id}",
                                    )
                            except Exception as load_error:
                                logger.warning(
                                    LogModule.WORKFLOW,
                                    f"[RESPLIT] Failed to load layout_document after MinerU conversion: {load_error}",
                                )

                        # If still not available, try attachments
                        if layout_doc is None:
                            attachments = st.get("attachments", {})
                            if "mineru" in attachments:
                                mineru_attachment = attachments["mineru"]
                                zip_bytes = None
                                if hasattr(mineru_attachment, "content"):
                                    zip_bytes = mineru_attachment.content
                                elif hasattr(mineru_attachment, "document") and hasattr(
                                    mineru_attachment.document, "content"
                                ):
                                    zip_bytes = mineru_attachment.document.content

                                if zip_bytes:
                                    try:
                                        from layout.registry import (
                                            load_layout_from_engine_zip,
                                        )

                                        layout_doc = load_layout_from_engine_zip(
                                            "mineru", zip_bytes
                                        )
                                        if layout_doc:
                                            st["layout_document"] = layout_doc
                                            st["layout_source_zip"] = zip_bytes
                                            logger.info(
                                                LogModule.WORKFLOW,
                                                f"[RESPLIT] Loaded layout_document from MinerU attachment after conversion for task {task_id}",
                                            )
                                    except Exception as load_error:
                                        logger.warning(
                                            LogModule.WORKFLOW,
                                            f"[RESPLIT] Failed to load layout_document from MinerU attachment after conversion: {load_error}",
                                        )

                    if layout_doc is None:
                        raise HTTPException(
                            status_code=500,
                            detail=(
                                "MinerU conversion completed but layout document is still not available. "
                                "Please check MinerU configuration and try again."
                            ),
                        )

                    logger.info(
                        LogModule.WORKFLOW,
                        f"[RESPLIT] MinerU conversion completed successfully for task {task_id}. Proceeding with re-split...",
                    )
                except Exception as mineru_error:
                    logger.error(
                        LogModule.WORKFLOW,
                        f"[RESPLIT] Failed to restart MinerU conversion for task {task_id}: {mineru_error}",
                        exc_info=True,
                    )
                    err_msg = str(mineru_error)
                    # Build user-friendly error message for common MinerU failures.
                    if 'field "language" is invalid' in err_msg:
                        # MinerU 不支持当前 language 选项（例如传入了错误的 OCR 语言代码）。
                        message_text = (
                            "MinerU OCR failed: the selected source language is not supported by "
                            "the current MinerU backend. Please switch source language to "
                            "a supported code (e.g. 'en', 'zh') or use 'Auto', then try Re-extract again."
                        )
                    elif (
                        "UNEXPECTED_EOF_WHILE_READING" in err_msg
                        or "EOF occurred in violation of protocol" in err_msg
                    ):
                        # 网络 / 代理相关的 EOF 问题
                        message_text = (
                            f"Task error: {err_msg}. Please check your network connection and "
                            "try disabling VPN/proxy, then retry Re-extract."
                        )
                    else:
                        message_text = (
                            f"Task error: {err_msg}"
                            if not err_msg.startswith("Task error:")
                            else err_msg
                        )
                    task_manager.update_task(
                        task_id,
                        {
                            "status": "failed",
                            "progress": 10,
                            "message": message_text,
                            "error": err_msg,
                        },
                    )
                    # Expose a concise, user-friendly detail message so frontend
                    # can display it instead of a generic 500 description.
                    raise HTTPException(
                        status_code=500,
                        detail=message_text,
                    )
                
                # Use LayoutMarkdownBuilder to regenerate segments and chunks
                from layout.markdown_builder import LayoutMarkdownBuilder
                
                # Get deep_split from task_state or payload, default to True
                deep_split_enabled = True  # Default
                source = "default"
                if "deep_split" in st:
                    deep_split_enabled = bool(st["deep_split"])
                    source = "task_state"
                elif payload:
                    if isinstance(payload, dict):
                        deep_split_enabled = bool(payload.get("deep_split", True))
                    else:
                        deep_split_enabled = bool(getattr(payload, 'deep_split', True))
                    source = "payload"
                
                # Get equation_format from payload (default: "text")
                equation_format = "text"
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
                logger.info(
                    LogModule.WORKFLOW,
                    f"[RESPLIT] Task {task_id}: Re-building layout extract with deep_split={deep_split_enabled} "
                    f"(from {source}), chunk_size={chunk_size}, equation_format={equation_format}"
                )
                builder = LayoutMarkdownBuilder(
                    max_chunk_chars=chunk_size, 
                    deep_split=deep_split_enabled,
                    equation_format=equation_format
                )
                layout_result = builder.build(layout_doc)
                logger.info(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: LayoutMarkdownBuilder generated {len(layout_result.chunks)} chunks (deep_split={deep_split_enabled})")
                
                if not layout_result.chunks:
                    raise HTTPException(
                        status_code=404,
                        detail="No segments generated from layout document."
                    )
                
                # Process chunks from LayoutMarkdownBuilder to create segments and chunks
                # This is the same logic as service_get_layout_extract
                all_segments = []
                block_type_map = {}
                block_image_map = {}
                
                # CRITICAL: Read pre-existing excluded_segment_indices from segments_metadata
                # This allows frontend to mark segments as excluded (e.g., references) and have them
                # automatically excluded when regenerating chunks during Re-extract
                segments_metadata = st.get("segments_metadata", {})
                pre_existing_excluded_indices = set(segments_metadata.get("excluded_segment_indices", []))
                if pre_existing_excluded_indices:
                    logger.info(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Found {len(pre_existing_excluded_indices)} pre-existing excluded segment indices in segments_metadata: {sorted(pre_existing_excluded_indices)}")
                
                # First pass: collect block metadata from layout_doc
                for page in layout_doc.pages:
                    for block in page.blocks:
                        block_type = getattr(block, "type", "unknown") or "unknown"
                        block_index = getattr(block, "index", None)
                        image_path = getattr(block, "image_path", None)
                        if block_index is not None:
                            block_type_map[block_index] = block_type
                            if image_path:
                                block_image_map[block_index] = image_path
                
                # Import unified exclusion detection utility
                from utils.translation_segments import _is_image_segment
                
                # Utility: fix line-break hyphenation inside chunk_text.
                # Example: "funda-\nmentalism" -> "fundamentalism".
                import re as _re

                def _fix_hyphenation(text: str) -> str:
                    if not text:
                        return text
                    # Collapse common patterns where a word is split across lines with a hyphen.
                    # 1) word-<newline>word  -> wordword
                    text = _re.sub(r"([A-Za-z]{2,})-\s*\n\s*([A-Za-z]{2,})", r"\1\2", text)
                    # 2) unchang- ing / Indus- trial 这种中间多了空格的情况：
                    #    先把 "word- <space>word" 合成 "wordword"
                    text = _re.sub(r"([A-Za-z]{2,})-\s+([A-Za-z]{2,})", r"\1\2", text)
                    return text

                # Process chunks from LayoutMarkdownBuilder
                for chunk_idx, chunk in enumerate(layout_result.chunks):
                    chunk_text = _fix_hyphenation(chunk.text)
                    chunk_block_indices = chunk.block_indices if hasattr(chunk, 'block_indices') else []
                    
                    is_image = False
                    is_header = False
                    is_footer = False
                    block_type = "text"
                    block_index = None
                    image_path = None
                    placeholder_id = None
                    
                    if chunk.chunk_type == "image":
                        is_image = True
                        image_path = chunk.image_path
                        if chunk.image_placeholder:
                            placeholder_id = chunk.image_placeholder
                        else:
                            placeholder_id = f"img-{chunk_idx}"
                    
                    for block_idx in chunk_block_indices:
                        if block_idx in block_type_map:
                            block_type = block_type_map[block_idx]
                            block_index = block_idx
                            if block_type == "image":
                                # Only mark as image if chunk text is actually a placeholder
                                # Image captions have actual text content, so they should not be marked as image
                                import re
                                placeholder_pattern = r'^<ph-[^>]+>$'
                                if re.match(placeholder_pattern, chunk_text.strip()):
                                    is_image = True
                                    if not image_path:
                                        image_path = block_image_map.get(block_idx)
                            elif block_type == "header":
                                is_header = True
                            elif block_type == "footer":
                                is_footer = True
                    
                    is_excluded = False
                    # CRITICAL: First check if this segment was pre-marked as excluded (e.g., by frontend user choice)
                    # This allows frontend to mark segments as excluded (e.g., references) and have them
                    # automatically excluded when regenerating chunks during Re-extract
                    # NOTE: chunk_idx is the index in layout_result.chunks, which corresponds to the index in all_segments
                    # Frontend passes segment indices from segmentsData array, which matches all_segments indices
                    if chunk_idx in pre_existing_excluded_indices:
                        is_excluded = True
                        logger.debug(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Segment {chunk_idx} was pre-marked as excluded (e.g., by user choice for references). block_type={block_type}, chunk_text preview={chunk_text[:50] if chunk_text else 'empty'}...")
                    elif is_image:
                        is_excluded = True
                    else:
                        # Get target language from payload for language-based exclusion
                        target_lang = None
                        if payload:
                            if isinstance(payload, dict):
                                target_lang = payload.get("to_lang") or payload.get("target_lang")
                            else:
                                target_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', None)
                        # Use detect_exclusion_reason instead of should_exclude_text
                        from exclusion.core import detect_exclusion_reason, ExclusionReason
                        detected_result = detect_exclusion_reason(
                            text=chunk_text,
                            block_type=block_type,
                            target_lang=target_lang,
                            is_image=is_image,
                            is_table=False
                        )
                        if detected_result:
                            detected_reason, _ = detected_result
                            # Only exclude non-optional types (TABLE is optional and not auto-excluded)
                            if not ExclusionReason.is_optional(detected_reason):
                                is_excluded = True
                    
                    segment_data = {
                        "text": chunk_text,
                        "block_type": block_type,
                        "block_index": block_index,
                        "layout_block_indices": list(chunk_block_indices)
                        if chunk_block_indices
                        else ([block_index] if block_index is not None else []),
                        "chunk_index": chunk_idx,
                        "segment_index": chunk_idx,  # CRITICAL: Store original segment index for proper mapping
                        "is_image": is_image,
                        "is_header": is_header,
                        "is_footer": is_footer,
                        "is_excluded": is_excluded,
                    }
                    
                    if is_image:
                        if not placeholder_id:
                            placeholder_id = f"img-{block_index or chunk_idx}"
                        segment_data["placeholder_id"] = placeholder_id
                        segment_data["image_path"] = image_path or "Image"
                        if chunk.chunk_type == "image":
                            segment_data["text"] = f"<ph-{placeholder_id}>"
                    
                    all_segments.append(segment_data)
                
                # Build chunks from segments (same logic as service_get_layout_extract)
                # CRITICAL: We need to build TWO sets of chunks:
                # 1. all_chunks: Only non-excluded chunks (for translation)
                # 2. all_chunks_with_excluded: All chunks including excluded (for layout_prepared_chunks)
                # This ensures MDTranslator can correctly map chunks to original segments
                all_chunks = []  # Only non-excluded chunks (for translation)
                all_chunks_with_excluded = []  # All chunks including excluded (for layout_prepared_chunks)
                current_chunk_parts = []
                current_chunk_chars = 0
                current_chunk_segment_indices = []
                current_chunk_parts_with_excluded = []
                current_chunk_chars_with_excluded = 0
                current_chunk_segment_indices_with_excluded = []
                
                for seg_idx, segment_data in enumerate(all_segments):
                    segment_text = segment_data.get("text", "")
                    segment_chars = len(segment_text)
                    is_excluded = segment_data.get("is_excluded", False)
                    
                    # CRITICAL: Use original segment index from segment_data, not enumerate index
                    # segment_data["segment_index"] contains the original segment index in all_segments
                    # This ensures proper mapping even if segments are filtered or reordered
                    original_segment_index = segment_data.get("segment_index", seg_idx)
                    
                    # CRITICAL: Build chunks with excluded segments for layout_prepared_chunks
                    # This ensures MDTranslator can correctly map chunks to original segments
                    # Excluded segments are added as separate chunks (one segment per chunk)
                    if is_excluded:
                        # Flush current chunk (if any) before adding excluded segment as separate chunk
                        if current_chunk_parts_with_excluded:
                            chunk_text_with_excluded = "\n\n".join(current_chunk_parts_with_excluded)
                            all_chunks_with_excluded.append({
                                "text": chunk_text_with_excluded,
                                "segment_indices": current_chunk_segment_indices_with_excluded.copy(),
                                "chunk_index": len(all_chunks_with_excluded),
                                "is_excluded": False,
                            })
                            current_chunk_parts_with_excluded = []
                            current_chunk_chars_with_excluded = 0
                            current_chunk_segment_indices_with_excluded = []
                        
                        # Add excluded segment as a separate chunk
                        all_chunks_with_excluded.append({
                            "text": segment_text,
                            "segment_indices": [original_segment_index],
                            "chunk_index": len(all_chunks_with_excluded),
                            "is_excluded": True,
                        })
                        # Excluded segments are not added to all_chunks (for translation)
                        continue
                    
                    should_start_new_chunk = False
                    if current_chunk_chars > 0 and current_chunk_chars + segment_chars > chunk_size:
                        should_start_new_chunk = True
                    
                    if should_start_new_chunk and current_chunk_parts:
                        chunk_text = "\n\n".join(current_chunk_parts)
                        all_chunks.append({
                            "text": chunk_text,
                            "segment_indices": current_chunk_segment_indices.copy(),
                            "chunk_index": len(all_chunks),
                        })
                        # Also add to all_chunks_with_excluded
                        all_chunks_with_excluded.append({
                            "text": chunk_text,
                            "segment_indices": current_chunk_segment_indices_with_excluded.copy(),
                            "chunk_index": len(all_chunks_with_excluded),
                            "is_excluded": False,
                        })
                        current_chunk_parts = []
                        current_chunk_chars = 0
                        current_chunk_segment_indices = []
                        current_chunk_parts_with_excluded = []
                        current_chunk_chars_with_excluded = 0
                        current_chunk_segment_indices_with_excluded = []
                    
                    # CRITICAL: Use original_segment_index instead of seg_idx to ensure proper mapping
                    if segment_text.strip():
                        current_chunk_parts.append(segment_text)
                        current_chunk_chars += segment_chars
                        current_chunk_segment_indices.append(original_segment_index)
                        # Also add to chunks_with_excluded
                        current_chunk_parts_with_excluded.append(segment_text)
                        current_chunk_chars_with_excluded += segment_chars
                        current_chunk_segment_indices_with_excluded.append(original_segment_index)
                
                if current_chunk_parts:
                    chunk_text = "\n\n".join(current_chunk_parts)
                    all_chunks.append({
                        "text": chunk_text,
                        "segment_indices": current_chunk_segment_indices.copy(),
                        "chunk_index": len(all_chunks),
                    })
                    # Also add to all_chunks_with_excluded
                    all_chunks_with_excluded.append({
                        "text": chunk_text,
                        "segment_indices": current_chunk_segment_indices_with_excluded.copy(),
                        "chunk_index": len(all_chunks_with_excluded),
                        "is_excluded": False,
                    })
                elif current_chunk_parts_with_excluded:
                    # Flush last chunk for all_chunks_with_excluded (if any)
                    chunk_text_with_excluded = "\n\n".join(current_chunk_parts_with_excluded)
                    all_chunks_with_excluded.append({
                        "text": chunk_text_with_excluded,
                        "segment_indices": current_chunk_segment_indices_with_excluded.copy(),
                        "chunk_index": len(all_chunks_with_excluded),
                        "is_excluded": False,
                    })
                
                # Build preview segments (for source_preview API)
                preview_segments = [chunk.text for chunk in layout_result.chunks]
                content_hash = hashlib.sha1(layout_result.markdown_text.encode("utf-8")).hexdigest()
                
                # CRITICAL: Update source_chunks_cache with all_segments to ensure correct indexing
                # This ensures that source_segments in record_translation_segments matches actual_segment_index
                # source_chunks_cache["segments"] should be a list of strings, where segments[i] corresponds to segment_index=i
                # Build cache_segments by extracting text from all_segments in order
                cache_segments = []
                max_segment_index = -1
                for seg in all_segments:
                    seg_idx = seg.get("segment_index", len(cache_segments))
                    seg_text = seg.get("text", "")
                    # Ensure cache_segments has enough elements (handle non-contiguous indices)
                    while len(cache_segments) <= seg_idx:
                        cache_segments.append("")
                    cache_segments[seg_idx] = seg_text
                    if seg_idx > max_segment_index:
                        max_segment_index = seg_idx
                
                # Trim empty trailing elements (if any segments were skipped)
                # But keep all valid segments up to max_segment_index
                cache_segments = cache_segments[:max_segment_index + 1] if max_segment_index >= 0 else []
                
                # Update preview and cache
                st["source_preview"] = {
                    "segments": preview_segments[:SOURCE_PREVIEW_SEGMENTS_LIMIT],
                    "total_segments": len(preview_segments),
                    "ready": True,
                }
                st["source_chunks_cache"] = {
                    "content_hash": content_hash,
                    "chunk_size": chunk_size,
                    "segments": cache_segments,  # CRITICAL: Indexed by segment_index, matches all_segments
                    "total_segments": len(cache_segments),
                    "created_at": time.time(),
                }
                from utils.translation_segments import build_segment_layout_block_map
                st["segment_layout_block_map"] = build_segment_layout_block_map(all_segments)
                st["segments_metadata"] = {
                    "source": workflow_type,
                    "workflow_type": workflow_type,
                    "chunk_size": chunk_size,
                    "content_hash": content_hash,
                }
                
                # Clear failed state so frontend gets status=completed and can show segments
                task_manager.update_task(task_id, {
                    "status": "completed",
                    "progress": 100,
                    "message": "Re-extract completed successfully",
                    "error": "",
                })
                
                task_manager.add_log(task_id, "success", f"Source re-split completed: {len(preview_segments)} segments, {len(all_chunks)} chunks using PDF layout extractor with chunk_size={chunk_size}")
                
                logger.info(LogModule.WORKFLOW, f"[RESPLIT] Task {task_id}: Re-split completed - {len(preview_segments)} segments, {len(all_chunks)} chunks, chunk_size={chunk_size}")

                # Debug: write latest Re-extract segments to a temp file so that
                # we can compare MinerU OCR results across different source languages.
                try:
                    from pathlib import Path as _Path
                    import tempfile as _tempfile

                    # Use system temp directory and include task_id in file name.
                    debug_dir = _Path(_tempfile.gettempdir())
                    debug_path = debug_dir / f"owlangs_resplit_{task_id}_segments.txt"

                    with debug_path.open("w", encoding="utf-8") as f:
                        f.write(f"Task ID: {task_id}\n")
                        f.write(f"Workflow type: {workflow_type}\n")
                        f.write(f"Segments count: {len(preview_segments)}\n")
                        f.write(f"Chunks count: {len(all_chunks)}\n")
                        f.write("\n=== Segments ===\n")
                        for idx, seg in enumerate(preview_segments):
                            # Each segment is a dict-like structure; prefer 'text' field when present.
                            if isinstance(seg, dict):
                                text = seg.get("text") or seg.get("source") or ""
                            else:
                                text = str(seg)
                            safe_text = text.replace("\r\n", "\n").replace("\r", "\n")
                            f.write(f"[{idx}] {safe_text}\n")

                    logger.info(
                        LogModule.WORKFLOW,
                        f"[RESPLIT] Task {task_id}: wrote debug segments to {debug_path}",
                    )
                except Exception as debug_error:
                    logger.debug(
                        LogModule.WORKFLOW,
                        f"[RESPLIT] Task {task_id}: failed to write debug segments file: {debug_error}",
                    )

                return JSONResponse(content={
                    "task_id": task_id,
                    "total_segments": len(preview_segments),
                    "total_chunks": len(all_chunks),
                    # chunk_size removed from response - frontend should use global settings instead
                    "segments": preview_segments[:50],
                    "workflow_type": workflow_type,
                })
            
            # Non-PDF workflows (existing logic)
            file_bytes = Path(original_file_path).read_bytes()
            content_hash = hashlib.sha1(file_bytes).hexdigest()
            
            # Use appropriate extractor based on workflow type
            segments = []
            separators_after = []
            segment_info = []
            
            if workflow_type == 'markdown_based':
                from utils.markdown_splitter import split_markdown_text
                decoded = decode_with_detection(file_bytes)
                deep_split_enabled = bool(st.get("deep_split", True))
                logger.info(
                    LogModule.WORKFLOW,
                    f"[RESPLIT] Task {task_id}: Using deep_split={deep_split_enabled} "
                    f"from task_state for markdown_based workflow (chunk_size={chunk_size})"
                )
                segments = split_markdown_text(decoded, max_block_size=chunk_size, deep_split=deep_split_enabled)
            elif workflow_type == 'txt':
                from utils.markdown_splitter import split_text_into_paragraphs
                decoded = decode_with_detection(file_bytes)
                segments = split_text_into_paragraphs(decoded, max_block_size=chunk_size)
            elif workflow_type == 'html':
                from extractor.html_extractor import HtmlExtractor
                decoded = decode_with_detection(file_bytes)
                logger.debug(LogModule.WORKFLOW, f"[ENCODE] resplit workflow=html, first100={decoded[:100]!r}")
                deep_split_enabled = bool(st.get("deep_split", True))
                logger.info(
                    LogModule.WORKFLOW,
                    f"[RESPLIT] Task {task_id}: Using deep_split={deep_split_enabled} "
                    f"from task_state for html workflow (chunk_size={chunk_size})"
                )
                result = HtmlExtractor(decoded, chunk_size=chunk_size, deep_split=deep_split_enabled).extract()
                segments = result.segments
                separators_after = result.separators_after
                segment_info = result.segment_info
            elif workflow_type == 'docx':
                from extractor.docx_extractor import DocxExtractor
                result = DocxExtractor(file_bytes, chunk_size=chunk_size).extract()
                segments = result.segments
                separators_after = result.separators_after
                segment_info = result.segment_info
            elif workflow_type == 'json':
                from extractor.json_extractor import JsonExtractor
                decoded = decode_with_detection(file_bytes)
                logger.debug(LogModule.WORKFLOW, f"[ENCODE] resplit workflow=json, first100={decoded[:100]!r}")
                json_paths = getattr(payload, 'json_paths', None) or [] if payload else []
                result = JsonExtractor(decoded, json_paths=json_paths, chunk_size=chunk_size).extract()
                segments = result.segments
                separators_after = result.separators_after
                segment_info = result.segment_info
            elif workflow_type == 'xlsx':
                from extractor.xlsx_extractor import XlsxExtractor
                translate_regions = getattr(payload, 'translate_regions', None) or [] if payload else []
                result = XlsxExtractor(file_bytes, translate_regions=translate_regions, chunk_size=chunk_size).extract()
                segments = result.segments
                separators_after = result.separators_after
                segment_info = result.segment_info
            elif workflow_type == 'srt':
                from extractor.srt_extractor import SrtExtractor
                try:
                    decoded = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    decoded = file_bytes.decode('utf-8', errors='replace')
                result = SrtExtractor(decoded, chunk_size=chunk_size).extract()
                segments = result.segments
                separators_after = result.separators_after
                segment_info = result.segment_info
            else:
                # Fallback to markdown splitter for unknown types
                from utils.markdown_splitter import split_markdown_text
                try:
                    decoded = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    decoded = file_bytes.decode('utf-8', errors='replace')
                deep_split_enabled = bool(st.get("deep_split", True))
                logger.info(
                    LogModule.WORKFLOW,
                    f"[RESPLIT] Task {task_id}: Using deep_split={deep_split_enabled} "
                    f"from task_state for txt workflow (chunk_size={chunk_size})"
                )
                segments = split_markdown_text(decoded, max_block_size=chunk_size, deep_split=deep_split_enabled)
            
            # Build default excluded segments (for ARB JSON metadata, etc.)
            excluded_segments: Dict[str, str] = {}
            excluded_segment_indices: list[int] = []

            # For ARB files with JSON workflow, mark ARB metadata keys (starting with "@")
            # as user-selected exclusions at Extract phase, so they are treated as
            # "User Exclusion" (not translation failures) in later status checks.
            if workflow_type == 'json' and original_file_path.lower().endswith('.arb'):
                try:
                    for idx, info in enumerate(segment_info or []):
                        if not isinstance(info, dict):
                            continue
                        paths = info.get('paths') or []
                        if not paths:
                            continue
                        path_str = paths[0]
                        if isinstance(path_str, str) and path_str.startswith('$.@'):
                            excluded_segments[str(idx)] = ExclusionReason.USER_SELECTED.value
                            excluded_segment_indices.append(idx)
                    if excluded_segment_indices:
                        logger.info(
                            LogModule.EXCLUSION,
                            f"[FORMAT_CONVERSION] Marked {len(excluded_segment_indices)} ARB metadata segments "
                            f"as user-selected exclusions based on JSON paths starting with '$.@': "
                            f"indices={excluded_segment_indices}",
                        )
                except Exception as e:
                    logger.warning(
                        LogModule.EXCLUSION,
                        f"[FORMAT_CONVERSION] Failed to mark ARB metadata segments as user-selected exclusions: {e}",
                        exc_info=True,
                    )

            # Update preview and cache
            preview_limit = 200
            st["source_preview"] = {
                "segments": segments[:preview_limit],
                "total_segments": len(segments),
                "ready": True,
            }
            st["source_chunks_cache"] = {
                "content_hash": content_hash,
                "chunk_size": chunk_size,
                "segments": segments,
                "total_segments": len(segments),
                "created_at": time.time(),
            }
            # Update segments metadata
            st["segments_metadata"] = {
                "source": workflow_type,
                "workflow_type": workflow_type,
                "chunk_size": chunk_size,
                "content_hash": content_hash,
                "separators_after": separators_after,
                "segment_info": segment_info,
            }

            # Attach ARB metadata exclusions if any
            if excluded_segments:
                st["segments_metadata"]["excluded_segments"] = excluded_segments
                st["segments_metadata"]["excluded_segment_indices"] = excluded_segment_indices
            
            task_manager.add_log(task_id, "success", f"Source re-split completed: {len(segments)} segments using {workflow_type} extractor")
            
            return JSONResponse(content={
                "task_id": task_id,
                "total_segments": len(segments),
                "segments": segments[:50],
                "workflow_type": workflow_type,
            })
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"Failed to re-split source for task {task_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to re-split: {e}")


# Service instance
format_conversion_service = FormatConversionService()


