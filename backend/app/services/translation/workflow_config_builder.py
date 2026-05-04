# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Workflow Config Builder

Builds workflow configurations from payload and task state.
"""

from typing import Any, Dict, Optional
from workflow.base import WorkflowConfig

from logger import unified_logger as logger
from logger import unified_logger
from logger.logger import LogModule
from backend.app.services.platform.platform_service import platform_service
from backend.app.services.translation.chunk_size_service import chunk_size_service
from backend.app.services.translation.prompt_service import prompt_service
from translator import default_params

# Translator configs
from translator.ai_translator.docx_translator import DocxTranslatorConfig
from translator.ai_translator.txt_translator import TXTTranslatorConfig
from translator.ai_translator.md_translator import MDTranslatorConfig
from translator.ai_translator.json_translator import JsonTranslatorConfig
from translator.ai_translator.xlsx_translator import XlsxTranslatorConfig
from translator.ai_translator.html_translator import HtmlTranslatorConfig
from translator.ai_translator.srt_translator import SrtTranslatorConfig
from translator.ai_translator.epub_translator import EpubTranslatorConfig
from translator.ai_translator.mobi_translator import MobiTranslatorConfig
from translator.ai_translator.qt_ts_translator import QtTsTranslatorConfig
from translator.ai_translator.pptx_translator import PptxTranslatorConfig

# Exporter configs
from exporter.docx.docx2html_exporter import Docx2HTMLExporterConfig
from exporter.txt.txt2html_exporter import TXT2HTMLExporterConfig
from exporter.md.md2html_exporter import MD2HTMLExporterConfig
from exporter.js.json2html_exporter import Json2HTMLExporterConfig
from exporter.xlsx.xlsx2html_exporter import Xlsx2HTMLExporterConfig
from exporter.srt.srt2html_exporter import Srt2HTMLExporterConfig
from exporter.epub.epub2html_exporter import Epub2HTMLExporterConfig
from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig
from exporter.qt_ts.qt_ts2html_exporter import QtTs2HTMLExporterConfig

# Workflow configs
from workflow.docx_workflow import DocxWorkflowConfig
from workflow.txt_workflow import TXTWorkflowConfig
from workflow.md_based_workflow import MarkdownBasedWorkflowConfig
from workflow.json_workflow import JsonWorkflowConfig
from workflow.xlsx_workflow import XlsxWorkflowConfig
from workflow.html_workflow import HtmlWorkflowConfig
from workflow.srt_workflow import SrtWorkflowConfig
from workflow.epub_workflow import EpubWorkflowConfig
from workflow.mobi_workflow import MobiWorkflowConfig
from workflow.qt_ts_workflow import QtTsWorkflowConfig
from workflow.pptx_workflow import PptxWorkflowConfig, Pptx2HTMLExporterConfig

# Converter configs
from converter.x2md.converter_mineru import ConverterMineruConfig
from converter.x2md.converter_docling import ConverterDoclingConfig

# Config
from backend.config.secrets_manager import SecretsManager


class WorkflowConfigBuilder:
    """Builder for creating workflow configurations."""
    
    def __init__(self, task_id: str, task_state: Dict[str, Any]):
        """
        Initialize config builder.
        
        Args:
            task_id: Task identifier
            task_state: Task state dictionary
        """
        self.task_id = task_id
        self.task_state = task_state

    def _get_concurrent_from_config_or_payload(self, payload: Any) -> int:
        """
        Get concurrent value with priority:
        1. Payload explicit concurrent (user override per task)
        2. Selected platform's config concurrent
        3. Global app_config.json translator_concurrent (backward compat)
        4. default_params
        """
        # Priority 1: Payload explicit override
        payload_val = payload.get('concurrent', None) if isinstance(payload, dict) else getattr(payload, 'concurrent', None)
        if payload_val is not None and payload_val > 0:
            logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using concurrent={payload_val} from payload (explicit override)")
            return int(payload_val)
        
        # Priority 2: Selected platform's config
        platform_key = payload.get('platform_key') if isinstance(payload, dict) else getattr(payload, 'platform_key', None)
        if platform_key:
            try:
                from backend.config.platforms_config import get_platforms_config
                platforms_config = get_platforms_config()
                platform_cfg = platforms_config.platforms.get(platform_key)
                if platform_cfg and hasattr(platform_cfg, 'concurrent'):
                    platform_concurrent = platform_cfg.concurrent
                    if platform_concurrent is not None and platform_concurrent > 0:
                        logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using concurrent={platform_concurrent} from platform '{platform_key}' config")
                        return int(platform_concurrent)
            except Exception as e:
                logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Failed to get concurrent from platform config: {e}")
        
        # Priority 3: Global app_config.json (backward compatibility)
        concurrent = None
        try:
            from backend.config.app_config import get_app_config, AppConfig
            try:
                app_config = get_app_config()
                if hasattr(app_config, 'translator_concurrent'):
                    concurrent = app_config.translator_concurrent
            except Exception:
                pass
            if concurrent is None or concurrent <= 0:
                try:
                    cfg_path = AppConfig._resolve_app_config_path("app_config.json")
                    if cfg_path.exists():
                        with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                            data = json.load(f)
                            concurrent = data.get('translator_concurrent')
                except Exception:
                    pass
            if concurrent is not None and concurrent > 0:
                logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using concurrent={concurrent} from app_config.json (backward compat)")
                return int(concurrent)
        except Exception as e:
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Failed to get concurrent from app_config: {e}")
        
        # Priority 4: default_params
        default_concurrent = int(default_params.get("concurrent", 10))
        logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using concurrent={default_concurrent} from default_params")
        return default_concurrent

    def _get_connect_timeout_from_config_or_payload(self, payload: Any) -> int:
        """Get connect_timeout from app_config.translator_connect_timeout (priority), then payload, then default 15."""
        connect_timeout = None
        try:
            from backend.config.app_config import get_app_config, AppConfig
            import json
            try:
                app_config = get_app_config()
                if hasattr(app_config, 'translator_connect_timeout'):
                    connect_timeout = app_config.translator_connect_timeout
            except Exception as e1:
                logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Failed to get connect_timeout from app_config: {e1}")
            if connect_timeout is None or connect_timeout <= 0:
                try:
                    cfg_path = AppConfig._resolve_app_config_path("app_config.json")
                    if cfg_path.exists():
                        with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                            data = json.load(f)
                            connect_timeout = data.get('translator_connect_timeout')
                except Exception as e2:
                    logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Failed to read connect_timeout from app_config.json: {e2}")
            if connect_timeout is not None and connect_timeout > 0:
                return int(connect_timeout)
        except Exception as e:
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Fallback connect_timeout: {e}")
        payload_val = payload.get('connect_timeout', None) if isinstance(payload, dict) else getattr(payload, 'connect_timeout', None)
        if payload_val is not None and payload_val > 0:
            return int(payload_val)
        return 15

    def build_translator_args(
        self,
        payload: Any,
        synthesized_prompt: str,
        apply_glossary: bool = True
    ) -> Dict[str, Any]:
        """
        Build translator arguments from payload.
        
        Args:
            payload: Task payload
            synthesized_prompt: Synthesized prompt string
            apply_glossary: Whether to apply smart glossary matching
            
        Returns:
            Dictionary of translator arguments
        """
        # CRITICAL: Handle both dict and object payloads for timeout
        # If payload is dict, use .get() method; otherwise use getattr()
        # This ensures timeout from frontend settings (120 seconds) is correctly passed to EPUB/MOBI translators
        if isinstance(payload, dict):
            timeout = payload.get('timeout', 1200)
        else:
            timeout = getattr(payload, 'timeout', 1200)
        
        # Log timeout value for diagnostics (especially for EPUB/MOBI workflows)
        logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Extracted timeout={timeout}s from payload (type={type(payload).__name__})")

        # Concurrent: prefer app_config.translator_concurrent (same priority as chunk_size), then payload, then default
        concurrent = self._get_concurrent_from_config_or_payload(payload)
        logger.info(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using concurrent={concurrent} for translator (translator_concurrent threshold)")
        connect_timeout = self._get_connect_timeout_from_config_or_payload(payload)
        logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Using connect_timeout={connect_timeout}s from app_config (translator_connect_timeout)")

        translator_args = {
            'task_id': self.task_id,  # CRITICAL: Pass task_id so apply_smart_glossary_matching can access task_state
            'skip_translate': getattr(payload, 'skip_translate', False),
            'base_url': getattr(payload, 'base_url', ''),
            'api_key': getattr(payload, 'api_key', ''),
            'model_id': getattr(payload, 'model_id', ''),
            'to_lang': getattr(payload, 'to_lang', 'en'),
            'custom_prompt': synthesized_prompt,
            'temperature': getattr(payload, 'temperature', 0.3),
            'thinking': getattr(payload, 'thinking', 'disable'),  # Default to 'disable' if not provided
            'chunk_size': chunk_size_service.get_chunk_size(payload, self.task_id),
            'deep_split': getattr(payload, 'deep_split', False),
            'concurrent': concurrent,
            'connect_timeout': connect_timeout,
            'timeout': timeout,  # Use the timeout value we extracted above (handles both dict and object payloads)
            'retry': getattr(payload, 'retry', default_params["retry"])
        }
        
        # Apply smart glossary matching if requested
        if apply_glossary:
            translator_args = self._apply_smart_glossary_matching(translator_args, payload)
        
        # Store platform key in task_state for segment recording
        base_url = translator_args.get('base_url', '')
        model_id = translator_args.get('model_id', '')
        platform_key = platform_service.determine_platform_key(base_url, model_id, self.task_state)
        if platform_key:
            self.task_state["platform_key"] = platform_key
        
        # Get max_tokens from platform configuration
        max_tokens = platform_service.get_max_tokens(base_url, model_id, platform_key)
        if max_tokens:
            translator_args['max_tokens'] = max_tokens
            logger.debug(LogModule.CONFIG, f"[TRANSLATOR_CONFIG] Task {self.task_id}: Added max_tokens={max_tokens} to translator_args from platform config")
        
        # Get thinking mode from platform configuration if not provided in payload or is default
        payload_thinking = getattr(payload, 'thinking', None)
        if payload_thinking is None or payload_thinking == 'disable' or payload_thinking == default_params.get("thinking", "disable"):
            thinking_mode = platform_service.get_thinking_mode(base_url, model_id, platform_key)
            if thinking_mode:
                # Use platform's thinking mode configuration
                translator_args['thinking'] = thinking_mode
                logger.debug(LogModule.CONFIG, f"[TRANSLATOR_CONFIG] Task {self.task_id}: Using thinking={thinking_mode} from platform config")
        
        # Get API protocol from platform configuration
        api_protocol = platform_service.get_api_protocol(base_url, model_id, platform_key)
        if api_protocol:
            translator_args['api_type'] = api_protocol
            logger.debug(LogModule.CONFIG, f"[TRANSLATOR_CONFIG] Task {self.task_id}: Using api_protocol={api_protocol} from platform config")
        
        # Save prompt snapshot to task state
        try:
            self.task_state["prompt_snapshot"] = translator_args.get('custom_prompt', '')
        except Exception:
            pass
        
        return translator_args
    
    def _apply_smart_glossary_matching(self, translator_args: Dict[str, Any], payload: Any) -> Dict[str, Any]:
        """
        Apply smart glossary matching to translator args.
        
        Args:
            translator_args: Translator arguments dictionary
            payload: Task payload
            
        Returns:
            Updated translator arguments dictionary
        """
        return prompt_service.apply_smart_glossary_matching(translator_args, payload)
    
    def build_workflow_config(
        self,
        workflow_type: str,
        payload: Any,
        synthesized_prompt: Optional[str] = None
    ) -> Optional[WorkflowConfig]:
        """
        Build workflow configuration based on workflow type.
        
        Args:
            workflow_type: Workflow type identifier
            payload: Task payload
            synthesized_prompt: Optional synthesized prompt string (if None, will be synthesized)
            
        Returns:
            WorkflowConfig instance or None if type not supported
        """
        # Synthesize prompt if not provided
        if synthesized_prompt is None:
            synthesized_prompt = prompt_service.synthesize_prompt(payload)
        
        translator_args = self.build_translator_args(payload, synthesized_prompt)
        
        logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Building workflow config for task {self.task_id}, workflow_type={workflow_type}, type={type(workflow_type)}")
        
        try:
            if workflow_type == "docx":
                logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Task {self.task_id}: Calling _build_docx_config")
                return self._build_docx_config(translator_args)
            elif workflow_type == "txt":
                return self._build_txt_config(translator_args)
            elif workflow_type == "markdown_based":
                return self._build_markdown_based_config(translator_args, payload)
            elif workflow_type == "json":
                return self._build_json_config(translator_args, payload)
            elif workflow_type == "xlsx":
                return self._build_xlsx_config(translator_args)
            elif workflow_type == "html":
                return self._build_html_config(translator_args)
            elif workflow_type == "srt":
                return self._build_srt_config(translator_args)
            elif workflow_type == "epub":
                return self._build_epub_config(translator_args)
            elif workflow_type == "mobi":
                return self._build_mobi_config(translator_args)
            elif workflow_type == "qt_ts":
                return self._build_qt_ts_config(translator_args, payload)
            elif workflow_type == "pptx":
                return self._build_pptx_config(translator_args, payload)
            else:
                logger.warning(LogModule.CONFIG, f"[CONFIG-BUILDER] Unsupported workflow type: {workflow_type}")
                return None
        except Exception as e:
            logger.error(LogModule.CONFIG, f"[CONFIG-BUILDER] Failed to build config for {workflow_type}: {e}", exc_info=True)
            return None
    
    def _build_docx_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build DOCX workflow configuration."""
        try:
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Building DOCX config for task {self.task_id}, translator_args keys: {list(translator_args.keys())}")
            
            # Remove task_id from translator_args as it's not a valid parameter for DocxTranslatorConfig
            # task_id is only used for accessing task_state in apply_smart_glossary_matching
            config_args = translator_args.copy()
            config_args.pop('task_id', None)
            
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Creating DocxTranslatorConfig for task {self.task_id}")
            translator_config = DocxTranslatorConfig(**config_args)
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Creating Docx2HTMLExporterConfig for task {self.task_id}")
            html_exporter_config = Docx2HTMLExporterConfig(cdn=True)
            
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Creating DocxWorkflowConfig for task {self.task_id}")
            config = DocxWorkflowConfig(
                translator_config=translator_config,
                html_exporter_config=html_exporter_config,
                logger=unified_logger
            )
            logger.debug(LogModule.CONFIG, f"[CONFIG-BUILDER] Successfully built DOCX config for task {self.task_id}")
            return config
        except Exception as e:
            logger.error(LogModule.CONFIG, f"[CONFIG-BUILDER] Failed to build DOCX config for task {self.task_id}: {e}", exc_info=True)
            raise
    
    def _build_txt_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build TXT workflow configuration."""
        # Remove task_id from translator_args as it's not a valid parameter for TXTTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = TXTTranslatorConfig(**config_args)
        html_exporter_config = TXT2HTMLExporterConfig(cdn=True)
        
        return TXTWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_markdown_based_config(self, translator_args: Dict[str, Any], payload: Any) -> WorkflowConfig:
        """Build Markdown-based workflow configuration."""
        # Remove task_id from translator_args as it's not a valid parameter for MDTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = MDTranslatorConfig(**config_args)
        html_exporter_config = MD2HTMLExporterConfig(cdn=True)
        
        # Build converter configuration based on convert_engine
        convert_engine = payload.get('convert_engine', 'mineru') if isinstance(payload, dict) else getattr(payload, 'convert_engine', 'mineru')
        converter_config = None
        
        if convert_engine == 'mineru':
            from converter.x2md.converter_mineru import ConverterMineruConfig
            from backend.config.secrets_manager import SecretsManager
            secrets = SecretsManager()
            # Prefer current token from SecretsManager so Re-Extract uses updated key after user fixes it
            mineru_token = (secrets.get_mineru_token() or '').strip()
            if not mineru_token:
                mineru_token = (payload.get('mineru_token', '') or '') if isinstance(payload, dict) else (getattr(payload, 'mineru_token', '') or '')
                if isinstance(mineru_token, str):
                    mineru_token = mineru_token.strip()
                logger.debug(LogModule.CONFIG, f"MinerU API Key from secrets: empty, from payload: {'provided' if mineru_token else 'empty'}")
            else:
                logger.debug(LogModule.CONFIG, f"MinerU API Key from secrets: provided (used for conversion/Re-Extract)")
            if not mineru_token:
                logger.warning(LogModule.CONFIG, "[WARNING] MinerU API Key not found in secrets. Please configure in Settings -> AI Platform -> MinerU.")
            
            formula_ocr = getattr(payload, 'formula_ocr', True) if not isinstance(payload, dict) else payload.get('formula_ocr', True)
            model_version = getattr(payload, 'model_version', 'vlm') if not isinstance(payload, dict) else payload.get('model_version', 'vlm')
            ocr_language = (payload.get('ocr_language') if isinstance(payload, dict) else getattr(payload, 'ocr_language', None)) or None
            if not (ocr_language and str(ocr_language).strip()):
                ocr_language = "auto"
            else:
                ocr_language = str(ocr_language).strip()
            from backend.config.config_loader import get_unified_config
            unified = get_unified_config()
            pdf_cfg = unified.system.pdf
            logger.debug(LogModule.CONFIG, f"Creating ConverterMineruConfig: API Key={'***' if mineru_token else 'empty'}, formula_ocr={formula_ocr}, model_version={model_version}, ocr_language={ocr_language}")
            if not mineru_token:
                logger.warning(LogModule.CONFIG, "[WARNING] MinerU API Key is empty! Conversion will fail. Please configure MinerU API Key in Settings -> AI Platform -> MinerU.")
            converter_config = ConverterMineruConfig(
                mineru_token=mineru_token,
                formula_ocr=formula_ocr,
                model_version=model_version,
                ocr_language=ocr_language,
                pdf_split_enabled=pdf_cfg.pdf_split_enabled,
                pdf_split_max_pages=pdf_cfg.pdf_split_max_pages,
                pdf_split_max_workers=pdf_cfg.pdf_split_max_workers,
                request_retry_count=pdf_cfg.request_retry_count,
            )
        elif convert_engine == 'mineru_local':
            from converter.x2md.converter_mineru import ConverterMineruConfig
            from backend.config.config_loader import get_unified_config
            unified = get_unified_config()
            platform_cfg = unified.get_ai_platform_config('mineru_local')
            base_url = (platform_cfg or {}).get('url') or 'http://localhost:8080/api/v4'
            mineru_token = (unified.get_platform_api_key('mineru_local') or '').strip()
            formula_ocr = getattr(payload, 'formula_ocr', True) if not isinstance(payload, dict) else payload.get('formula_ocr', True)
            model_version = getattr(payload, 'model_version', 'vlm') if not isinstance(payload, dict) else payload.get('model_version', 'vlm')
            ocr_language = (payload.get('ocr_language') if isinstance(payload, dict) else getattr(payload, 'ocr_language', None)) or None
            if not (ocr_language and str(ocr_language).strip()):
                ocr_language = "auto"
            else:
                ocr_language = str(ocr_language).strip()
            pdf_cfg = unified.system.pdf
            logger.debug(LogModule.CONFIG, f"Creating ConverterMineruConfig (local): base_url={base_url}, model_version={model_version}, ocr_language={ocr_language}")
            table_ocr = getattr(payload, 'table_ocr', True)
            converter_config = ConverterMineruConfig(
                mineru_token=mineru_token,
                formula_ocr=formula_ocr,
                table_ocr=table_ocr,
                model_version=model_version,
                ocr_language=ocr_language,
                base_url=base_url.strip().rstrip('/'),
                pdf_split_enabled=pdf_cfg.pdf_split_enabled,
                pdf_split_max_pages=pdf_cfg.pdf_split_max_pages,
                pdf_split_max_workers=pdf_cfg.pdf_split_max_workers,
                request_retry_count=pdf_cfg.request_retry_count,
            )
        elif convert_engine == 'docling':
            converter_config = ConverterDoclingConfig(
                formula_ocr=getattr(payload, 'formula_ocr', True),
                code_ocr=getattr(payload, 'code_ocr', True)
            )
        # For 'identity' engine, converter_config remains None
        
        # Get skip_cache from payload (for format conversion requests)
        skip_cache = getattr(payload, 'skip_cache', False)
        logger.info(
            LogModule.CONFIG,
            f"[IMPORT] Task {self.task_id}: skip_cache from payload: {skip_cache} "
            f"(type: {type(skip_cache)}, payload has skip_cache: {hasattr(payload, 'skip_cache')})"
        )
        
        return MarkdownBasedWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            convert_engine=convert_engine,
            converter_config=converter_config,
            skip_cache=skip_cache,
            logger=unified_logger
        )
    
    def _build_json_config(self, translator_args: Dict[str, Any], payload: Any) -> WorkflowConfig:
        """Build JSON workflow configuration."""
        from translator.ai_translator.json_translator import JsonTranslatorConfig
        from exporter.js.json2html_exporter import Json2HTMLExporterConfig
        from workflow.json_workflow import JsonWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for JsonTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        # Extract json_paths from payload
        if isinstance(payload, dict):
            json_paths = payload.get('json_paths', None) or []
            segment_per_request = payload.get('segment_per_request', False)
        else:
            json_paths = getattr(payload, 'json_paths', None) or []
            segment_per_request = getattr(payload, 'segment_per_request', False)
        config_args['json_paths'] = json_paths
        config_args['segment_per_request'] = segment_per_request

        translator_config = JsonTranslatorConfig(**config_args)
        html_exporter_config = Json2HTMLExporterConfig(cdn=True)
        
        return JsonWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_xlsx_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build XLSX workflow configuration."""
        from translator.ai_translator.xlsx_translator import XlsxTranslatorConfig
        from exporter.xlsx.xlsx2html_exporter import Xlsx2HTMLExporterConfig
        from workflow.xlsx_workflow import XlsxWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for XlsxTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = XlsxTranslatorConfig(**config_args)
        html_exporter_config = Xlsx2HTMLExporterConfig(cdn=True)
        
        return XlsxWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_html_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build HTML workflow configuration."""
        # Remove task_id from translator_args as it's not a valid parameter for HtmlTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = HtmlTranslatorConfig(**config_args)
        
        return HtmlWorkflowConfig(
            translator_config=translator_config,
            logger=unified_logger
        )
    
    def _build_srt_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build SRT workflow configuration."""
        from translator.ai_translator.srt_translator import SrtTranslatorConfig
        from exporter.srt.srt2html_exporter import Srt2HTMLExporterConfig
        from workflow.srt_workflow import SrtWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for SrtTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = SrtTranslatorConfig(**config_args)
        html_exporter_config = Srt2HTMLExporterConfig(cdn=True)
        
        return SrtWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_epub_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build EPUB workflow configuration."""
        from translator.ai_translator.epub_translator import EpubTranslatorConfig
        from exporter.epub.epub2html_exporter import Epub2HTMLExporterConfig
        from workflow.epub_workflow import EpubWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for EpubTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = EpubTranslatorConfig(**config_args)
        html_exporter_config = Epub2HTMLExporterConfig(cdn=True)
        
        return EpubWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_mobi_config(self, translator_args: Dict[str, Any]) -> WorkflowConfig:
        """Build MOBI workflow configuration."""
        from translator.ai_translator.mobi_translator import MobiTranslatorConfig
        from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig
        from workflow.mobi_workflow import MobiWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for MobiTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = MobiTranslatorConfig(**config_args)
        html_exporter_config = Mobi2HTMLExporterConfig(cdn=True)
        
        return MobiWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_qt_ts_config(self, translator_args: Dict[str, Any], payload: Any = None) -> WorkflowConfig:
        """Build Qt TS workflow configuration."""
        from translator.ai_translator.qt_ts_translator import QtTsTranslatorConfig
        from exporter.qt_ts.qt_ts2html_exporter import QtTs2HTMLExporterConfig
        from workflow.qt_ts_workflow import QtTsWorkflowConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for QtTsTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        # CRITICAL: Apply QT_TS-specific options from payload so "Skip existing translations" etc. take effect
        if payload is not None:
            skip_existing = payload.get('skip_existing_translations') if isinstance(payload, dict) else getattr(payload, 'skip_existing_translations', None)
            if skip_existing is not None:
                config_args['skip_existing_translations'] = skip_existing
            translate_unfinished = payload.get('translate_unfinished') if isinstance(payload, dict) else getattr(payload, 'translate_unfinished', None)
            if translate_unfinished is not None:
                config_args['translate_unfinished'] = translate_unfinished
            translate_vanished = payload.get('translate_vanished') if isinstance(payload, dict) else getattr(payload, 'translate_vanished', None)
            if translate_vanished is not None:
                config_args['translate_vanished'] = translate_vanished
            translate_obsolete = payload.get('translate_obsolete') if isinstance(payload, dict) else getattr(payload, 'translate_obsolete', None)
            if translate_obsolete is not None:
                config_args['translate_obsolete'] = translate_obsolete
            if any(k in config_args for k in ('skip_existing_translations', 'translate_unfinished', 'translate_vanished', 'translate_obsolete')):
                logger.info(
                    LogModule.CONFIG,
                    f"[CONFIG-BUILDER] Task {self.task_id}: QT_TS options from payload: "
                    f"skip_existing_translations={config_args.get('skip_existing_translations')}, "
                    f"translate_unfinished={config_args.get('translate_unfinished')}, "
                    f"translate_vanished={config_args.get('translate_vanished')}, "
                    f"translate_obsolete={config_args.get('translate_obsolete')}"
                )
        
        translator_config = QtTsTranslatorConfig(**config_args)
        html_exporter_config = QtTs2HTMLExporterConfig(cdn=True)
        
        return QtTsWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            logger=unified_logger
        )
    
    def _build_pptx_config(self, translator_args: Dict[str, Any], payload: Any) -> WorkflowConfig:
        """Build PPTX workflow configuration."""
        from translator.ai_translator.pptx_translator import PptxTranslatorConfig
        from workflow.pptx_workflow import PptxWorkflowConfig, Pptx2HTMLExporterConfig
        
        # Remove task_id from translator_args as it's not a valid parameter for PptxTranslatorConfig
        config_args = translator_args.copy()
        config_args.pop('task_id', None)
        
        translator_config = PptxTranslatorConfig(**config_args)
        html_exporter_config = Pptx2HTMLExporterConfig()
        
        # Get translate_notes and translate_master from payload if available
        translate_notes = getattr(payload, 'translate_notes', False)
        translate_master = getattr(payload, 'translate_master', False)
        
        return PptxWorkflowConfig(
            translator_config=translator_config,
            html_exporter_config=html_exporter_config,
            translate_notes=translate_notes,
            translate_master=translate_master,
            logger=unified_logger
        )

