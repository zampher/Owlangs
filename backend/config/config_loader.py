# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unified configuration loader
Provides unified interface for accessing configuration from structured config files.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from backend.logger import unified_logger as logger
from backend.logger.logger import LogModule

# Import all config modules
from .system_config import get_system_config, SystemConfig, ExclusionDefaultsConfig
from .platforms_config import get_platforms_config, PlatformsConfig, platform_type_uses_llm_chunk_concurrent
from .secrets_manager import get_secrets_manager
from .local_config import LocalConfig
def load_all_configs() -> dict:
    """Load all configurations"""
    
    # Load all configs
    configs = {
        'system': get_system_config(),
        'platforms': get_platforms_config(),
        'secrets': get_secrets_manager(),
        'local': LocalConfig.load_from_file(),
    }
    
    return configs


# Backward compatibility: provide a unified config interface
class UnifiedConfig:
    """Unified configuration interface for backward compatibility"""
    
    def __init__(self):
        self.system = get_system_config()
        self.platforms = get_platforms_config()
        self.secrets = get_secrets_manager()
        self.local = LocalConfig.get_config()  # Use get_config() to leverage caching
    
    # Legacy properties for backward compatibility
    @property
    def auth_required(self) -> bool:
        """Get auth_required setting"""
        return self.system.auth.required
    
    @property
    def default_language(self) -> str:
        """Get default language"""
        return self.system.features.default_language
    
    @property
    def smart_glossary_matching_enabled(self) -> bool:
        """Get smart glossary matching enabled"""
        return self.system.features.smart_glossary_matching_enabled
    
    @property
    def exclusion_defaults(self) -> ExclusionDefaultsConfig:
        """Get exclusion default settings from system config"""
        return self.system.exclusion_defaults

    # Cloud MinerU only supports vlm-auto-engine; legacy 'vlm' is equivalent.
    _MINERU_CLOUD_MODEL_NORMALIZE = {'vlm': 'vlm-auto-engine'}

    @property
    def parsing_engine(self) -> dict:
        """Get parsing engine configuration (for backward compatibility).

        model_version is read from platforms.json (source of truth for MinerU config).
        """
        default_engine = self.system.parsing_engine.default_engine
        mineru_model_version = self._get_model_version_from_platforms(default_engine)
        return {
            'convert_engine': default_engine,
            'mineru_model_version': mineru_model_version,
            'formula_ocr': self.system.parsing_engine.default_engine_settings.get('formula_ocr', False),
            'table_ocr': self.system.parsing_engine.default_engine_settings.get('table_ocr', True),
            'skip_translate': self.system.parsing_engine.default_engine_settings.get('skip_translate', False),
            'pdf_split_enabled': self.system.pdf.pdf_split_enabled,
            'pdf_split_max_pages': self.system.pdf.pdf_split_max_pages,
            'pdf_split_max_workers': self.system.pdf.pdf_split_max_workers,
            'request_retry_count': self.system.pdf.request_retry_count,
        }

    def _get_model_version_from_platforms(self, engine_key: str) -> str:
        """Read model version from platforms.json for the given engine key."""
        platform = self.platforms.platforms.get(engine_key)
        if platform and platform.model:
            model = platform.model
            # Normalize: cloud MinerU only supports vlm-auto-engine
            if engine_key == 'mineru':
                model = self._MINERU_CLOUD_MODEL_NORMALIZE.get(model, model)
            return model
        return 'hybrid-auto-engine'
    
    @property
    def ai_platforms(self) -> dict:
        """Get AI platforms configuration (for backward compatibility)"""
        platforms_dict = {}
        for key, platform in self.platforms.platforms.items():
            # Ensure numeric fields are properly typed
            max_tokens = int(platform.max_tokens) if platform.max_tokens is not None else 4096
            temperature = float(platform.temperature) if platform.temperature is not None else 0.3
            temperature_min = float(platform.temperature_min) if platform.temperature_min is not None else 0.0
            temperature_max = float(platform.temperature_max) if platform.temperature_max is not None else 2.0
            recommended_tokens = int(platform.recommended_tokens) if platform.recommended_tokens is not None else None
            
            platforms_dict[key] = {
                'name': platform.name,
                'url': platform.url,
                'model': platform.model,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'temperature_min': temperature_min,
                'temperature_max': temperature_max,
                'thinking_mode_supported': bool(platform.thinking_mode_supported),
                'thinking_mode': platform.thinking_mode,
                'recommended_tokens': recommended_tokens,
                'performance_note': platform.performance_note,
                'platform_type': platform.platform_type,
                'parser_subtype': platform.parser_subtype,
                'description': platform.description,
                'token_link': platform.token_link,
                'requires_api_key': bool(platform.requires_api_key),
                'api_protocol': platform.api_protocol,
                'api_endpoints': dict(platform.api_endpoints) if platform.api_endpoints else {},
            }
            if platform_type_uses_llm_chunk_concurrent(platform.platform_type):
                platforms_dict[key]['chunk_size'] = (
                    int(platform.chunk_size) if platform.chunk_size is not None else 3000
                )
                platforms_dict[key]['concurrent'] = (
                    int(platform.concurrent) if platform.concurrent is not None else 5
                )
                platforms_dict[key]['timeout'] = (
                    int(platform.timeout) if platform.timeout is not None else None
                )
                platforms_dict[key]['write_timeout'] = (
                    int(platform.write_timeout) if platform.write_timeout is not None else None
                )
        platforms_dict['default_platform'] = self.platforms.default_platform
        return platforms_dict
    
    def get_platform_api_key(self, platform: str) -> str:
        """Get platform API key. Backward compat: 'custom' -> 'local'; also try 'custom' when key is 'local'."""
        key = "local" if platform == "custom" else platform
        keys = self.secrets.get_api_keys()
        return keys.get(key, "") or (keys.get("custom", "") if key == "local" else "")
    
    def get_ai_platform_config(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get AI platform configuration (for backward compatibility)"""
        platform_obj = self.platforms.get_platform_config(platform)
        if platform_obj:
            base = {
                'name': platform_obj.name,
                'url': platform_obj.url,
                'model': platform_obj.model,
                'max_tokens': platform_obj.max_tokens,
                'temperature': platform_obj.temperature,
                'temperature_min': platform_obj.temperature_min,
                'temperature_max': platform_obj.temperature_max,
                'thinking_mode_supported': platform_obj.thinking_mode_supported,
                'thinking_mode': platform_obj.thinking_mode,
                'recommended_tokens': platform_obj.recommended_tokens,
                'performance_note': platform_obj.performance_note,
                'platform_type': platform_obj.platform_type,
                'api_protocol': platform_obj.api_protocol,
                'description': platform_obj.description,
                'token_link': platform_obj.token_link,
                'requires_api_key': platform_obj.requires_api_key,
                'api_endpoints': platform_obj.api_endpoints,
            }
            if platform_type_uses_llm_chunk_concurrent(platform_obj.platform_type):
                base['chunk_size'] = (
                    int(platform_obj.chunk_size) if platform_obj.chunk_size is not None else 3000
                )
                base['concurrent'] = (
                    int(platform_obj.concurrent) if platform_obj.concurrent is not None else 5
                )
            return base
        return None
    
    @property
    def ai_platforms_default_platform(self) -> str:
        """Get default platform (for backward compatibility)"""
        return self.platforms.default_platform
    
    def get_config_dict(self, include_api_keys: bool = False, flatten: bool = True) -> Dict[str, Any]:
        """Get configuration as dictionary (for backward compatibility)"""
        config_dict = {}
        
        # System config
        config_dict['auth_required'] = self.auth_required
        config_dict['default_language'] = self.default_language
        config_dict['smart_glossary_matching_enabled'] = self.smart_glossary_matching_enabled
        config_dict['parsing_engine'] = self.parsing_engine
        
        # Exclusion defaults
        from dataclasses import asdict
        config_dict['exclusion_defaults'] = asdict(self.exclusion_defaults)
        
        # AI platforms
        config_dict['ai_platforms'] = self.ai_platforms
        config_dict['ai_platforms_default_platform'] = self.ai_platforms_default_platform
        
        # Flatten parsing_engine for backward compatibility
        if flatten:
            parsing_engine = config_dict['parsing_engine']
            config_dict['translator_convert_engine'] = parsing_engine['convert_engine']
            config_dict['translator_mineru_model_version'] = parsing_engine['mineru_model_version']
            config_dict['translator_formula_ocr'] = parsing_engine['formula_ocr']
            config_dict['translator_table_ocr'] = parsing_engine['table_ocr']
            config_dict['translator_skip_translate'] = parsing_engine['skip_translate']
            config_dict['translator_pdf_split_enabled'] = parsing_engine['pdf_split_enabled']
            config_dict['translator_pdf_split_max_pages'] = parsing_engine['pdf_split_max_pages']
            config_dict['translator_pdf_split_max_workers'] = parsing_engine['pdf_split_max_workers']
            config_dict['translator_request_retry_count'] = parsing_engine['request_retry_count']
        
        return config_dict
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary (for backward compatibility)"""
        from .system_config import save_system_config
        from .platforms_config import save_platforms_config
        
        # Handle parsing engine settings
        if 'parsing_engine' in data:
            parsing_data = data['parsing_engine']
            # Update system config parsing engine
            if 'convert_engine' in parsing_data:
                self.system.parsing_engine.default_engine = parsing_data['convert_engine']
            if 'mineru_model_version' in parsing_data:
                new_version = parsing_data['mineru_model_version']
                # Normalize: cloud MinerU only supports vlm-auto-engine
                if new_version == 'vlm':
                    new_version = 'vlm-auto-engine'
                # Update platforms.json (source of truth for MinerU model)
                default_engine = self.system.parsing_engine.default_engine
                if default_engine in self.platforms.platforms:
                    self.platforms.platforms[default_engine].model = new_version
                    save_platforms_config()
            if 'formula_ocr' in parsing_data:
                self.system.parsing_engine.default_engine_settings['formula_ocr'] = parsing_data['formula_ocr']
            if 'table_ocr' in parsing_data:
                self.system.parsing_engine.default_engine_settings['table_ocr'] = parsing_data['table_ocr']
            if 'skip_translate' in parsing_data:
                self.system.parsing_engine.default_engine_settings['skip_translate'] = parsing_data['skip_translate']
            if 'pdf_split_enabled' in parsing_data:
                self.system.pdf.pdf_split_enabled = bool(parsing_data['pdf_split_enabled'])
            if 'pdf_split_max_pages' in parsing_data:
                self.system.pdf.pdf_split_max_pages = int(parsing_data['pdf_split_max_pages'])
            if 'pdf_split_max_workers' in parsing_data:
                self.system.pdf.pdf_split_max_workers = int(parsing_data['pdf_split_max_workers'])
            if 'request_retry_count' in parsing_data:
                self.system.pdf.request_retry_count = int(parsing_data['request_retry_count'])
        
        # Handle AI platforms
        if 'ai_platforms' in data:
            ai_platforms_data = data['ai_platforms']
            # Update platforms config
            for platform_key, platform_data in ai_platforms_data.items():
                if platform_key == 'default_platform':
                    # Update default platform
                    if isinstance(platform_data, str):
                        self.platforms.default_platform = platform_data
                    continue
                if isinstance(platform_data, dict):
                    # Update or add platform
                    platform_obj = self.platforms.get_platform_config(platform_key)
                    if platform_obj:
                        # Update existing platform
                        for key, value in platform_data.items():
                            if hasattr(platform_obj, key):
                                setattr(platform_obj, key, value)
                    else:
                        # Add new platform (would need to use platforms config's add method if available)
                        logger.warning(LogModule.CONFIG, f"Cannot add new platform {platform_key} via update_from_dict, use platforms config directly")
        
        # Handle default_language
        if 'default_language' in data:
            self.system.features.default_language = data['default_language']
        
        # Handle smart_glossary_matching_enabled
        if 'smart_glossary_matching_enabled' in data:
            self.system.features.smart_glossary_matching_enabled = data['smart_glossary_matching_enabled']
        # Handle show_ads (AD placeholders on home and in Flow)
        if 'show_ads' in data:
            self.system.features.show_ads = bool(data['show_ads'])
        if 'features' in data and isinstance(data['features'], dict) and 'show_ads' in data['features']:
            self.system.features.show_ads = bool(data['features']['show_ads'])
        
        # Handle auth_required
        if 'auth_required' in data:
            self.system.auth.required = data['auth_required']
        
        # Handle exclusion_defaults (dict of reason_key -> bool)
        if 'exclusion_defaults' in data:
            ed = data['exclusion_defaults']
            if isinstance(ed, dict):
                cfg = self.system.exclusion_defaults
                for attr in ('image', 'formula', 'reference', 'identifier',
                             'structural', 'table', 'language_match'):
                    if attr in ed:
                        setattr(cfg, attr, bool(ed[attr]))
    
    def save_to_file(self, config_file: Optional[str] = None) -> bool:
        """Save unified configuration to files (for backward compatibility)
        
        Args:
            config_file: Ignored parameter (kept for backward compatibility).
                        This method always saves to the new config structure
                        (system.json, platforms.json).
        
        Returns:
            True if all config files were saved successfully, False otherwise.
        """
        from .system_config import save_system_config
        from .platforms_config import save_platforms_config

        ok1 = save_system_config()
        ok2 = save_platforms_config()
        success = ok1 and ok2

        if success:
            logger.info(LogModule.CONFIG, "Unified configuration saved to new config structure (system.json, platforms.json)")
        else:
            failed = []
            if not ok1: failed.append("system.json")
            if not ok2: failed.append("platforms.json")
            logger.warning(LogModule.CONFIG, f"Some configuration files failed to save: {', '.join(failed)}")
        
        return success
    
    def update_platform_api_key(self, platform: str, api_key: str) -> None:
        """Update platform API key (for backward compatibility)
        
        Note: This is a no-op for UnifiedConfig as API keys are managed by SecretsManager.
        The actual update should be done via secrets_manager.update_platform_api_key().
        This method exists only for backward compatibility.
        """
        # API keys are managed by SecretsManager, not UnifiedConfig
        # This method exists for backward compatibility but doesn't do anything
        # Callers should use secrets_manager.update_platform_api_key() directly
        logger.debug(LogModule.CONFIG, f"update_platform_api_key called for {platform} (no-op, use secrets_manager directly)")


# Global unified config instance
_unified_config: Optional[UnifiedConfig] = None
_unified_config_loading: bool = False  # Flag to prevent concurrent loading


def get_unified_config() -> UnifiedConfig:
    """Get unified configuration with caching to avoid duplicate loading (for backward compatibility)"""
    global _unified_config, _unified_config_loading
    if _unified_config is None and not _unified_config_loading:
        _unified_config_loading = True
        try:
            _unified_config = UnifiedConfig()
        finally:
            _unified_config_loading = False
    return _unified_config


def save_unified_config() -> bool:
    """Save unified configuration (for backward compatibility)"""
    global _unified_config
    if _unified_config is not None:
        return _unified_config.save_to_file()
    return False


def clear_unified_config_cache() -> None:
    """Clear unified configuration cache to force reload (for backward compatibility)"""
    global _unified_config
    _unified_config = None

