# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Translation configuration module for managing translation-related default settings.

This module provides centralized configuration for translation parameters,
especially deep_split defaults based on file formats.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any
from pathlib import Path

# Use unified_logger for consistent logging format
try:
    from logger import unified_logger as logger
    from logger.logger import LogModule
except ImportError:
    # Fallback when logger package not available: provide LogModule.CONFIG and adapter so call sites work
    _std = logging.getLogger(__name__)

    class _LogModuleFallback:
        CONFIG = "CONFIG"

    LogModule = _LogModuleFallback()

    class _LoggerAdapter:
        def info(self, module, message, **kwargs):
            _std.info(f"[{module}] {message}", **kwargs)

        def warning(self, module, message, **kwargs):
            _std.warning(f"[{module}] {message}", **kwargs)

        def error(self, module, message, **kwargs):
            _std.error(f"[{module}] {message}", **kwargs)

        def debug(self, module, message, **kwargs):
            _std.debug(f"[{module}] {message}", **kwargs)

    logger = _LoggerAdapter()


@dataclass
class DeepSplitDefaults:
    """Default deep_split values for different file formats."""
    # Format-specific defaults
    pdf: bool = False  # PDF files: False (layout-based, don't split too fine)
    docx: bool = False  # DOCX files: False (layout-based, don't split too fine)
    txt: bool = True  # TXT files: True (text-based, split by paragraph)
    md: bool = True  # Markdown files: True (text-based, split by paragraph)
    html: bool = True  # HTML files: True (text-based, split by paragraph)
    # Other formats default to True
    default: bool = True  # Default for unknown formats
    
    # Workflow-specific defaults (fallback when file extension is unknown)
    markdown_based: Optional[bool] = None  # None means use file extension
    docx_workflow: bool = False
    txt_workflow: bool = True
    html_workflow: bool = True
    
    def get_by_extension(self, extension: str) -> bool:
        """Get deep_split default by file extension."""
        ext_lower = extension.lower().lstrip('.')
        if ext_lower == 'pdf':
            return self.pdf
        elif ext_lower == 'docx':
            return self.docx
        elif ext_lower in ['txt']:
            return self.txt
        elif ext_lower in ['md', 'markdown']:
            return self.md
        elif ext_lower in ['html', 'htm']:
            return self.html
        else:
            return self.default
    
    def get_by_workflow(self, workflow_type: str) -> Optional[bool]:
        """Get deep_split default by workflow type. Returns None if should use file extension."""
        workflow_lower = workflow_type.lower()
        if workflow_lower == 'docx':
            return self.docx_workflow
        elif workflow_lower == 'txt':
            return self.txt_workflow
        elif workflow_lower == 'html':
            return self.html_workflow
        elif workflow_lower == 'markdown_based':
            return self.markdown_based  # None means use file extension
        elif workflow_lower == 'pdf':
            return self.pdf
        else:
            return None  # Use default


@dataclass
class TranslationConfig:
    """Translation configuration class"""
    deep_split_defaults: DeepSplitDefaults = field(default_factory=DeepSplitDefaults)
    
    @classmethod
    def load_from_file(cls, config_file: str = "translation_config.json") -> "TranslationConfig":
        """Load translation configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                logger.debug(LogModule.CONFIG, f"[TRANSLATION_CONFIG] Loading translation configuration from: {config_path}")
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
                            f"[TRANSLATION_CONFIG] Merged existing translation_config.json with template structure: {config_path}",
                        )
                        data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"[TRANSLATION_CONFIG] Failed to merge translation_config.json with template: {merge_err}",
                    )

                config = cls()
                config.update_from_dict(data)
                # Print loaded configuration
                defaults = config.deep_split_defaults
                logger.debug(
                    LogModule.CONFIG,
                    f"[TRANSLATION_CONFIG] Loaded deep_split defaults: "
                    f"pdf={defaults.pdf}, docx={defaults.docx}, txt={defaults.txt}, "
                    f"md={defaults.md}, html={defaults.html}, default={defaults.default}"
                )
                logger.debug(LogModule.CONFIG, "[TRANSLATION_CONFIG] Translation configuration loaded successfully")
                return config
            else:
                config = cls()
                defaults = config.deep_split_defaults
                logger.info(
                    LogModule.CONFIG,
                    f"[TRANSLATION_CONFIG] Config file not found at {config_path}, using code defaults: "
                    f"pdf={defaults.pdf}, docx={defaults.docx}, txt={defaults.txt}, "
                    f"md={defaults.md}, html={defaults.html}, default={defaults.default}"
                )
                return config
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"Failed to load translation configuration: {e}, using defaults")
            return cls()
    
    def save_to_file(self, config_file: str = "translation_config.json") -> bool:
        """Save translation configuration to file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_dict = self.get_config_dict()
            target_path = get_config_file_path(config_file)
            
            # Ensure configs directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            logger.info(LogModule.CONFIG, f"Translation configuration saved to: {target_path}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to save translation configuration: {e}")
            return False
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        if 'deep_split_defaults' in data:
            ds_data = data['deep_split_defaults']
            self.deep_split_defaults = DeepSplitDefaults(**ds_data)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        return {
            'deep_split_defaults': asdict(self.deep_split_defaults)
        }
    
    def get_default_deep_split(self, filename: str, workflow_type: Optional[str] = None) -> bool:
        """
        Get default deep_split value based on file format.
        
        Priority:
        1. File extension (most reliable for PDF/Docx)
        2. Workflow type (if file extension doesn't match known patterns)
        3. Default value
        
        Args:
            filename: Original filename with extension
            workflow_type: Optional workflow type (e.g., 'markdown_based', 'docx')
            
        Returns:
            bool: Default deep_split value
        """
        suffix = Path(filename).suffix
        workflow = workflow_type or ""
        
        # Priority 1: Check file extension FIRST (most reliable for PDF/Docx)
        # PDF files may use markdown_based workflow, but should still use deep_split=False
        ext_default = self.deep_split_defaults.get_by_extension(suffix)
        
        # If we have a definitive answer from extension, use it
        if suffix.lower() in ['.pdf', '.docx', '.txt', '.md', '.markdown', '.html', '.htm']:
            logger.debug(
                LogModule.CONFIG,
                f"[TRANSLATION_CONFIG] get_default_deep_split: filename={filename}, "
                f"extension={suffix}, workflow={workflow}, result={ext_default} (from extension)"
            )
            return ext_default
        
        # Priority 2: Fallback to workflow type if extension doesn't match known patterns
        if workflow:
            workflow_default = self.deep_split_defaults.get_by_workflow(workflow)
            if workflow_default is not None:
                logger.debug(
                    LogModule.CONFIG,
                    f"[TRANSLATION_CONFIG] get_default_deep_split: filename={filename}, "
                    f"extension={suffix}, workflow={workflow}, result={workflow_default} (from workflow)"
                )
                return workflow_default
        
        # Priority 3: Use default
        default_value = self.deep_split_defaults.default
        logger.debug(
            LogModule.CONFIG,
            f"[TRANSLATION_CONFIG] get_default_deep_split: filename={filename}, "
            f"extension={suffix}, workflow={workflow}, result={default_value} (from default)"
        )
        return default_value


# Global translation configuration instance
_translation_config: Optional[TranslationConfig] = None


def get_translation_config() -> TranslationConfig:
    """Get translation configuration (singleton)"""
    global _translation_config
    if _translation_config is None:
        _translation_config = TranslationConfig.load_from_file()
    return _translation_config


def save_translation_config() -> bool:
    """Save translation configuration"""
    global _translation_config
    if _translation_config is not None:
        return _translation_config.save_to_file()
    return False


def clear_translation_config_cache() -> None:
    """Clear translation configuration cache to force reload"""
    global _translation_config
    _translation_config = None


# Convenience function for getting default deep_split
def get_default_deep_split(filename: str, workflow_type: Optional[str] = None) -> bool:
    """
    Get default deep_split value based on file format.
    
    This is the main entry point for getting deep_split defaults.
    It uses the centralized configuration system.
    
    Args:
        filename: Original filename with extension
        workflow_type: Optional workflow type
        
    Returns:
        bool: Default deep_split value
    """
    config = get_translation_config()
    result = config.get_default_deep_split(filename, workflow_type)
    # Log with detailed information for debugging
    config_source = 'file' if _translation_config is not None else 'code_defaults'
    # Use INFO level to ensure it's visible
    logger.debug(
        LogModule.CONFIG,
        f"[TRANSLATION_CONFIG] get_default_deep_split called: filename={filename}, "
        f"workflow_type={workflow_type}, result={result}, config_source={config_source}"
    )
    return result

