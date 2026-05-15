# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field, fields
from typing import Optional, Dict, Any
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule


def platform_type_uses_llm_chunk_concurrent(platform_type: Optional[str]) -> bool:
    """
    Per-platform chunk_size / concurrent in platforms.json apply only to LLM translation platforms.

    Parser platforms (e.g. MinerU) do not use these fields; omit them from disk and from resolution.
    """
    return (platform_type or "llm") == "llm"


@dataclass
class AIPlatformConfig:
    """AI Platform configuration (API keys stored separately in secrets.json)"""
    name: str = ""
    url: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.3
    temperature_min: float = 0.0  # Minimum temperature value for this platform (0.0 or 0.1)
    temperature_max: float = 2.0  # Maximum temperature value for this platform (1.0 or 2.0)
    thinking_mode_supported: bool = False  # Whether this platform supports thinking mode
    thinking_mode: str = "disable"  # Thinking mode: "enable", "disable", "default"
    recommended_tokens: Optional[int] = None
    performance_note: Optional[str] = None
    platform_type: str = "llm"  # "llm", "parser", "converter"
    parser_subtype: Optional[str] = None  # "cloud", "local" for parser type platforms (e.g., MinerU)
    api_protocol: str = "openai"  # API protocol: "openai", "ollama", "anthropic"
    requires_api_key: bool = True  # Whether API key is required for this platform (disable for local deployments)
    description: Optional[str] = None
    token_link: Optional[str] = None
    api_endpoints: Dict[str, str] = field(default_factory=dict)
    chunk_size: int = 3000  # Per-platform chunk size (tokens). Overrides global app_config setting.
    concurrent: int = 5  # Per-platform concurrent requests. Overrides global app_config setting.


@dataclass
class PlatformsConfig:
    """Platforms configuration class. _schema_version = JSON format version; version kept for backward compat."""
    _schema_version: int = 1
    version: str = "2.0.0"
    default_platform: str = "deepseek"
    platforms: Dict[str, AIPlatformConfig] = field(default_factory=dict)
    
    @classmethod
    def load_from_file(cls, config_file: str = "platforms.json") -> "PlatformsConfig":
        """Load platforms configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                logger.info(LogModule.CONFIG, f"Loading platforms configuration from: {config_path}")
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)

                # When upgrading, platforms.json.template may add new platforms/fields.
                # Merge template structure into existing platforms.json without overwriting user values.
                try:
                    from utils.path_utils import get_template_file_path

                    template_path = get_template_file_path(f"{config_file}.template")
                    if template_path.exists() and isinstance(data, dict):
                        from backend.utils.template_merge_utils import maybe_merge_json_file_with_template

                        merged = maybe_merge_json_file_with_template(
                            current_path=config_path,
                            template_path=template_path,
                            write_back=True,
                        )
                        if isinstance(merged, dict) and merged != data:
                            logger.info(
                                LogModule.CONFIG,
                                f"Merged existing platforms.json with template structure: {config_path}",
                            )
                            data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to merge platforms.json with template: {merge_err}",
                    )

                config = cls()
                config.update_from_dict(data)
                logger.debug(LogModule.CONFIG, "Platforms configuration loaded successfully")
                return config
            else:
                # Try to create from template
                from utils.path_utils import get_template_file_path
                template_path = get_template_file_path(f"{config_file}.template")
                if template_path.exists():
                    logger.info(LogModule.CONFIG, f"Platforms config file not found, creating from template: {template_path}")
                    import shutil
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, config_path)
                    # Load the newly created file
                    with open(config_path, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                        config = cls()
                        config.update_from_dict(data)
                        return config
                logger.warning(LogModule.CONFIG, f"Platforms config file not found at {config_path}, using defaults")
                return cls()
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to load platforms configuration: {e}")
            return cls()
    
    def save_to_file(self, config_file: str = "platforms.json") -> bool:
        """Save platforms configuration to file"""
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
            logger.info(LogModule.CONFIG, f"Platforms configuration saved to: {target_path}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to save platforms configuration to {target_path}: {e}")
            return False
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        if '_schema_version' in data:
            self._schema_version = int(data['_schema_version'])
            self.version = str(self._schema_version)

        if 'default_platform' in data:
            self.default_platform = data['default_platform']
        
        if 'platforms' in data:
            platforms_data = data['platforms']
            self.platforms = {}
            for platform_key, platform_data in platforms_data.items():
                if platform_key == 'default_platform':
                    continue
                if isinstance(platform_data, dict):
                    pdata = dict(platform_data)
                    ptype = pdata.get("platform_type", "llm")
                    if not platform_type_uses_llm_chunk_concurrent(ptype):
                        pdata.pop("chunk_size", None)
                        pdata.pop("concurrent", None)
                    allowed = {f.name for f in fields(AIPlatformConfig)}
                    unknown = sorted(k for k in pdata if k not in allowed)
                    if unknown:
                        logger.debug(
                            LogModule.CONFIG,
                            f"Platforms '{platform_key}': ignoring keys not defined on AIPlatformConfig: {unknown}",
                        )
                    pdata_filtered = {k: v for k, v in pdata.items() if k in allowed}
                    self.platforms[platform_key] = AIPlatformConfig(**pdata_filtered)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        config_dict = {
            '_schema_version': self._schema_version,
            'default_platform': self.default_platform,
            'platforms': {}
        }
        
        # Convert platforms to dictionary format (omit LLM-only keys for parser/converter platforms)
        for platform_key, platform_config in self.platforms.items():
            plat_dict = asdict(platform_config)
            if not platform_type_uses_llm_chunk_concurrent(platform_config.platform_type):
                plat_dict.pop("chunk_size", None)
                plat_dict.pop("concurrent", None)
            config_dict["platforms"][platform_key] = plat_dict

        return config_dict
    
    def get_platform_config(self, platform: str) -> Optional[AIPlatformConfig]:
        """Get AI platform configuration. Backward compat: 'custom' is treated as 'local'."""
        key = "local" if platform == "custom" else platform
        return self.platforms.get(key)
    
    def update_platform_config(self, platform: str, config: AIPlatformConfig) -> None:
        """Update AI platform configuration"""
        self.platforms[platform] = config
    
    def get_platform_name(self, platform: str) -> str:
        """Get platform display name"""
        platform_config = self.get_platform_config(platform)
        return platform_config.name if platform_config else platform
    
    def get_platform_max_tokens(self, platform: str) -> int:
        """Get platform max tokens"""
        platform_config = self.get_platform_config(platform)
        return platform_config.max_tokens if platform_config else 4096
    
    def get_platform_temperature(self, platform: str) -> float:
        """Get platform temperature"""
        platform_config = self.get_platform_config(platform)
        return platform_config.temperature if platform_config else 0.3
    
    def get_platform_temperature_min(self, platform: str) -> float:
        """Get platform minimum temperature"""
        platform_config = self.get_platform_config(platform)
        return platform_config.temperature_min if platform_config else 0.0
    
    def get_platform_temperature_max(self, platform: str) -> float:
        """Get platform maximum temperature"""
        platform_config = self.get_platform_config(platform)
        return platform_config.temperature_max if platform_config else 2.0
    
    def get_platform_thinking_mode_supported(self, platform: str) -> bool:
        """Get whether platform supports thinking mode"""
        platform_config = self.get_platform_config(platform)
        return platform_config.thinking_mode_supported if platform_config else False
    
    def get_platform_thinking_mode(self, platform: str) -> str:
        """Get platform thinking mode"""
        platform_config = self.get_platform_config(platform)
        return platform_config.thinking_mode if platform_config else "disable"


# Global platforms configuration instance
_platforms_config: Optional[PlatformsConfig] = None
_platforms_config_loading: bool = False  # Flag to prevent concurrent loading


def get_platforms_config() -> PlatformsConfig:
    """Get platforms configuration with caching to avoid duplicate loading"""
    global _platforms_config, _platforms_config_loading
    if _platforms_config is None and not _platforms_config_loading:
        _platforms_config_loading = True
        try:
            _platforms_config = PlatformsConfig.load_from_file()
        finally:
            _platforms_config_loading = False
    return _platforms_config


def save_platforms_config() -> bool:
    """Save platforms configuration"""
    global _platforms_config
    if _platforms_config is not None:
        return _platforms_config.save_to_file()
    return False


def clear_platforms_config_cache() -> None:
    """Clear platforms configuration cache to force reload"""
    global _platforms_config
    _platforms_config = None

