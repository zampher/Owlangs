# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class AuthConfig:
    """Authentication configuration"""
    # Open-source / passwordless default: web works without login; config still needs admin session
    required: bool = False
    session_timeout: int = 3600


@dataclass
class ParsingEngineDefinition:
    """Parsing engine definition"""
    name: str = ""
    api_url: Optional[str] = None
    model_version: Optional[str] = None
    type: Optional[str] = None


@dataclass
class ParsingEngineConfig:
    """Parsing engine configuration"""
    default_engine: str = "mineru"
    engines: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    default_engine_settings: Dict[str, Any] = field(default_factory=lambda: {
        "formula_ocr": False,
        "table_ocr": True,
        "skip_translate": False
    })


@dataclass
class ExclusionDefaultsConfig:
    """Default exclusion settings for the Extract phase.
    
    Each key maps to an ExclusionReason value. ``True`` means the reason is
    auto-excluded by default; ``False`` means detected-only (user decides).
    """
    image: bool = True
    formula: bool = True
    reference: bool = False
    identifier: bool = True
    structural: bool = False
    table: bool = False
    chart: bool = False  # Chart content (Figure, chart blocks) - default not excluded
    language_match: bool = False
    # When False, language_match detection is disabled globally (no detection or marking).
    # When True, language_match detection is enabled but still respects per-reason auto-exclude flags.
    language_match_exclusion_detection: bool = False


@dataclass
class FeaturesConfig:
    """Features configuration"""
    smart_glossary_matching_enabled: bool = True
    default_language: str = "en"
    show_ads: bool = False  # When True, show AD placeholders on home and in Flow
    ai_platform_startup_tests: bool = True  # When True, run AI platform connectivity tests at startup
    # When True, after translation completes (markdown_based), run Pandoc-per-segment DOCX check
    # and LLM repair for failing LaTeX fragments (uses llm_config_for_repair).
    auto_docx_math_fragment_llm_repair: bool = False


@dataclass
class PdfConfig:
    """PDF processing configuration"""
    disable_markdown_fallback: bool = True  # If true, PDF files will not use markdown-based extraction as fallback
    use_reportlab: bool = False  # If true, use ReportLab for direct PDF generation (high-fidelity), otherwise use HTML → PDF
    fallback_to_html: bool = True  # If ReportLab fails, fallback to HTML → PDF
    pdf_split_enabled: bool = True  # If true, large PDFs will be split before conversion
    pdf_split_max_pages: int = 100  # Maximum pages per PDF split chunk
    pdf_split_max_workers: int = 2  # Max concurrent workers for split PDF conversion
    request_retry_count: int = 2  # Number of retries for MinerU API requests


@dataclass
class ModuleLoggingConfig:
    """Module logging configuration"""
    enabled_modules: Optional[Dict[str, str]] = None
    disabled_modules: Optional[Dict[str, str]] = None
    default_enabled: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    max_file_size_mb: int = 10
    backup_count: int = 7
    json: bool = False
    filter_health_check_logs: bool = True
    truncate: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None
    third_party_loggers: Optional[Dict[str, Any]] = None
    # Content display mode for source/target text in logs:
    #   - "none": Hide content completely, show "[Content hidden]" (default, recommended for production)
    #   - "partial": Show truncated content (first 500 chars) with total length info
    #   - "full": Show full content (use with caution, may expose sensitive data)
    content_display: str = "none"  # Default: hide content
    # Module logging configuration
    enable_module_logging: bool = False  # Default: disabled
    module_logging: Optional[ModuleLoggingConfig] = None


@dataclass
class SystemConfig:
    """System configuration class. _schema_version = JSON format version. App version is only in backend/__init__.py."""
    _schema_version: int = 1
    auth: AuthConfig = field(default_factory=AuthConfig)
    parsing_engine: ParsingEngineConfig = field(default_factory=ParsingEngineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    pdf: PdfConfig = field(default_factory=PdfConfig)
    exclusion_defaults: ExclusionDefaultsConfig = field(default_factory=ExclusionDefaultsConfig)
    
    @classmethod
    def load_from_file(cls, config_file: str = "system.json") -> "SystemConfig":
        """Load system configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                logger.debug(LogModule.CONFIG, f"Loading system configuration from: {config_path}")
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)

                # Merge template structure on upgrade without overwriting user values.
                try:
                    from utils.path_utils import get_template_file_path
                    from backend.utils.template_merge_utils import maybe_merge_json_file_with_template

                    template_path = get_template_file_path(f"{config_file}.template")
                    merged = maybe_merge_json_file_with_template(
                        current_path=config_path,
                        template_path=template_path,
                        write_back=True,
                    )
                    if isinstance(merged, dict) and merged != data:
                        logger.info(
                            LogModule.CONFIG,
                            f"Merged existing system.json with template structure: {config_path}",
                        )
                        data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to merge system.json with template: {merge_err}",
                    )

                # Migrate: strip legacy engines dict from parsing_engine (model info now lives in platforms.json)
                if isinstance(data.get('parsing_engine'), dict):
                    data['parsing_engine'].pop('engines', None)

                config = cls()
                config.update_from_dict(data)
                logger.debug(LogModule.CONFIG, "System configuration loaded successfully")
                return config
            else:
                    # Try to create from template
                from utils.path_utils import get_template_file_path
                template_path = get_template_file_path(f"{config_file}.template")
                if template_path.exists():
                    logger.info(LogModule.CONFIG, f"System config file not found, creating from template: {template_path}")
                    import shutil
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, config_path)
                    # Load the newly created file
                    with open(config_path, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                        config = cls()
                        config.update_from_dict(data)
                        return config
                logger.warning(LogModule.CONFIG, f"System config file not found at {config_path}, using defaults")
                return cls()
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to load system configuration: {e}")
            return cls()
    
    def save_to_file(self, config_file: str = "system.json") -> bool:
        """Save system configuration to file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_dict = self.get_config_dict()
            target_path = get_config_file_path(config_file)
            
            # Ensure configs directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            # Set appropriate permissions for system directories
            try:
                if str(target_path).startswith("/etc/"):
                    os.chmod(target_path, 0o640)
            except Exception:
                pass
            logger.info(LogModule.CONFIG, f"System configuration saved to: {target_path}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to save system configuration to {target_path}: {e}")
            return False
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        if '_schema_version' in data:
            self._schema_version = int(data['_schema_version'])
        # app_version is not stored here; single source is backend/__init__.py

        if 'auth' in data:
            auth_data = data['auth']
            self.auth = AuthConfig(**auth_data)
        
        if 'parsing_engine' in data:
            pe_data = data['parsing_engine']
            self.parsing_engine = ParsingEngineConfig(
                default_engine=pe_data.get('default_engine', 'mineru'),
                default_engine_settings=pe_data.get('default_engine_settings', {
                    "formula_ocr": False,
                    "table_ocr": True,
                    "skip_translate": False
                })
            )
        
        if 'logging' in data:
            logging_data = data['logging'].copy()  # Make a copy to avoid modifying original
            
            # Handle module_logging separately if present
            module_logging_data = logging_data.pop('module_logging', None)
            module_logging = None
            if module_logging_data:
                module_logging = ModuleLoggingConfig(**module_logging_data)
            
            # Create LoggingConfig with remaining data
            self.logging = LoggingConfig(**logging_data)
            
            # Set module_logging if it was provided
            if module_logging is not None:
                self.logging.module_logging = module_logging
        
        if 'features' in data:
            features_data = data['features'].copy()
            # Default show_ads to False for existing configs that do not have the key
            if 'show_ads' not in features_data:
                features_data['show_ads'] = False
            if 'auto_docx_math_fragment_llm_repair' not in features_data:
                features_data['auto_docx_math_fragment_llm_repair'] = False
            self.features = FeaturesConfig(**features_data)
        
        if 'pdf' in data:
            pdf_data = data['pdf']
            self.pdf = PdfConfig(**pdf_data)
        
        if 'exclusion_defaults' in data:
            ed_data = data['exclusion_defaults']
            self.exclusion_defaults = ExclusionDefaultsConfig(**ed_data)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        return {
            '_schema_version': self._schema_version,
            'auth': asdict(self.auth),
            'parsing_engine': {
                'default_engine': self.parsing_engine.default_engine,
                'default_engine_settings': dict(self.parsing_engine.default_engine_settings),
            },
            'logging': asdict(self.logging),
            'features': asdict(self.features),
            'pdf': asdict(self.pdf),
            'exclusion_defaults': asdict(self.exclusion_defaults),
        }


# Global system configuration instance
_system_config: Optional[SystemConfig] = None
_system_config_loading: bool = False  # Flag to prevent concurrent loading


def get_system_config() -> SystemConfig:
    """Get system configuration with caching to avoid duplicate loading"""
    global _system_config, _system_config_loading
    if _system_config is None:
        if not _system_config_loading:
            _system_config_loading = True
            try:
                _system_config = SystemConfig.load_from_file()
            finally:
                _system_config_loading = False
        else:
            # If already loading, return a default instance to avoid blocking
            # This should rarely happen, but provides a fallback
            return SystemConfig()
    return _system_config


def save_system_config() -> bool:
    """Save system configuration"""
    global _system_config
    if _system_config is None:
        logger.warning(LogModule.CONFIG, "system.json save skipped: _system_config is None (not loaded or was cleared)")
        return False
    return _system_config.save_to_file()


def clear_system_config_cache() -> None:
    """Clear system configuration cache to force reload"""
    global _system_config
    _system_config = None

