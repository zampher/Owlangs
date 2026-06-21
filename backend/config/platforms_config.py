# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field, fields
from typing import List, Optional, Dict, Any
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
    parser_engine: Optional[str] = None  # "mineru", "paddle" — which parser engine
    parser_subtype: Optional[str] = None  # "cloud", "local" for parser type platforms (e.g., MinerU)
    # PaddleOCR-specific parameters
    use_doc_orientation_classify: bool = False
    restructure_pages: bool = False
    api_protocol: str = "openai"  # API protocol: "openai", "ollama", "anthropic"
    requires_api_key: bool = True  # Whether API key is required for this platform (disable for local deployments)
    description: Optional[str] = None
    token_link: Optional[str] = None
    api_endpoints: Dict[str, str] = field(default_factory=dict)
    chunk_size: int = 3000  # Per-platform chunk size (tokens). Overrides global app_config setting.
    concurrent: int = 5  # Per-platform concurrent requests. Overrides global app_config setting.
    timeout: Optional[int] = None  # Per-platform read timeout (seconds). Overrides global default.
    write_timeout: Optional[int] = None  # Per-platform write timeout (seconds). Overrides global default.
    test_connect_timeout: Optional[int] = None  # Per-platform connect-test client timeout (seconds). Default 30.
    test_request_timeout: Optional[int] = None  # Per-platform connect-test sub-request timeout (seconds). Default 10.
    # Maximum number of segments per translation batch (0 = unlimited).
    # Default: 100 for cloud LLMs, 10 for local LLMs (e.g., Ollama).
    # Available options: 1, 3, 5, 10, 20, 50, 100, 200, 500, 1000, 0 (unlimited)
    segment_limit: int = 100


@dataclass
class PlatformsConfig:
    """Platforms configuration class. _schema_version = JSON format version; version kept for backward compat."""
    _schema_version: int = 1
    version: str = "2.0.0"
    default_platform: str = "deepseek"
    platforms: Dict[str, AIPlatformConfig] = field(default_factory=dict)
    # Preserved field order from the original JSON for each platform key.
    # Used by get_config_dict() to write keys in the same order they were read.
    _platform_field_orders: Dict[str, List[str]] = field(default_factory=dict, init=False)
    
    @classmethod
    def load_from_file(cls, config_file: str = "platforms.json") -> "PlatformsConfig":
        """Load platforms configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                logger.debug(LogModule.CONFIG, f"Loading platforms configuration from: {config_path}")
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
                # If migration added defaults for old platforms, persist back to disk
                if getattr(config, '_needs_migration', False):
                    try:
                        config.save_to_file()
                        logger.info(LogModule.CONFIG, f"Saved migrated platforms.json (timeout/write_timeout defaults): {config_path}")
                    except Exception as save_err:
                        logger.warning(LogModule.CONFIG, f"Failed to save migrated platforms.json: {save_err}")
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
            needs_migration = False
            for platform_key, platform_data in platforms_data.items():
                if platform_key == 'default_platform':
                    continue
                if isinstance(platform_data, dict):
                    pdata = dict(platform_data)
                    # Preserve original JSON field order for consistent write-back
                    self._platform_field_orders[platform_key] = list(pdata.keys())
                    ptype = pdata.get("platform_type", "llm")
                    # Normalize legacy platform_type values (e.g. 'pdf_parser' → 'parser')
                    if ptype == 'pdf_parser':
                        ptype = 'parser'
                        pdata['platform_type'] = 'parser'
                    if not platform_type_uses_llm_chunk_concurrent(ptype):
                        pdata.pop("chunk_size", None)
                        pdata.pop("timeout", None)
                        pdata.pop("write_timeout", None)
                        pdata.pop("test_connect_timeout", None)
                        pdata.pop("test_request_timeout", None)
                        pdata.pop("segment_limit", None)
                    allowed = {f.name for f in fields(AIPlatformConfig)}
                    unknown = sorted(k for k in pdata if k not in allowed)
                    if unknown:
                        logger.debug(
                            LogModule.CONFIG,
                            f"Platforms '{platform_key}': ignoring keys not defined on AIPlatformConfig: {unknown}",
                        )
                    pdata_filtered = {k: v for k, v in pdata.items() if k in allowed}
                    # Migrate: fill default timeout/write_timeout for old LLM platforms missing these fields
                    if ptype == 'llm':
                        if pdata_filtered.get('timeout') is None:
                            pdata_filtered['timeout'] = 300
                            needs_migration = True
                        if pdata_filtered.get('test_connect_timeout') is None:
                            pdata_filtered['test_connect_timeout'] = 30
                            needs_migration = True
                        if pdata_filtered.get('test_request_timeout') is None:
                            pdata_filtered['test_request_timeout'] = 10
                            needs_migration = True
                        # Migrate: convert old single_segment_retry_mode to new segment_limit
                        old_ssr = pdata_filtered.pop('single_segment_retry_mode', None)
                        if 'segment_limit' not in pdata_filtered and old_ssr is not None:
                            if isinstance(old_ssr, bool):
                                pdata_filtered['segment_limit'] = 1 if old_ssr else 100
                            elif old_ssr == 'single':
                                pdata_filtered['segment_limit'] = 1
                            elif old_ssr == 'fixed_5':
                                pdata_filtered['segment_limit'] = 5
                            elif old_ssr == 'fixed_10':
                                pdata_filtered['segment_limit'] = 10
                            # 'chunk_size' (default) → use default 100, no need to set
                            needs_migration = True
                            logger.info(
                                LogModule.CONFIG,
                                f"Migrated '{platform_key}': single_segment_retry_mode='{old_ssr}' → segment_limit={pdata_filtered.get('segment_limit', 100)}"
                            )
                    # Migrate: populate parser_engine for parser platforms missing it.
                    # PaddleOCR support was added in a later version; older configs have
                    # parser_engine=null for all parser platforms.  Infer from the
                    # platform key so the frontend can show the correct model dropdown.
                    if ptype == 'parser' and pdata_filtered.get('parser_engine') is None:
                        _known_engines = ('mineru', 'paddle')
                        for _eng in _known_engines:
                            if platform_key == _eng or platform_key.startswith(f'{_eng}_'):
                                pdata_filtered['parser_engine'] = _eng
                                needs_migration = True
                                logger.info(
                                    LogModule.CONFIG,
                                    f"Migrated '{platform_key}': parser_engine → '{_eng}'",
                                )
                                break
                    self.platforms[platform_key] = AIPlatformConfig(**pdata_filtered)
            if needs_migration:
                self._needs_migration = True
                logger.info(LogModule.CONFIG, "Migrated old platforms.json: added default timeout/write_timeout for LLM platforms")
    
    # Field order for consistent JSON serialization (matches platforms.json structure)
    # Fields exclusive to LLM platforms (not used by parser/converter platforms)
    _LLM_ONLY_FIELDS = {
        # NOTE: "model" is NOT here — it is used by both LLM and parser
        # platforms (e.g., MinerU model version, PaddleOCR model flavor).
        "max_tokens",
        "temperature",
        "temperature_min",
        "temperature_max",
        "thinking_mode_supported",
        "thinking_mode",
        "recommended_tokens",
        "api_protocol",
        "chunk_size",
        "timeout",
        "write_timeout",
        "test_connect_timeout",
        "test_request_timeout",
        "segment_limit",
    }

    # Field order for consistent JSON serialization (matches platforms.json structure)
    # Fields are grouped by platform type:
    # - Common fields: name, url, platform_type, parser_subtype, requires_api_key, description, token_link, api_endpoints, performance_note
    # - LLM-only fields: model, max_tokens, temperature, thinking_mode, chunk_size, concurrent, timeout, etc.
    _PLATFORM_FIELD_ORDER = [
        # Common fields (all platform types)
        "name",
        "url",
        "platform_type",
        "parser_engine",
        "parser_subtype",
        "requires_api_key",
        "description",
        "token_link",
        "api_endpoints",
        "performance_note",
        "concurrent",
        # Parser-platform fields (PaddleOCR-specific; ignored for LLM)
        "use_doc_orientation_classify",
        "restructure_pages",
        # LLM / shared model field
        "model",
        "max_tokens",
        "temperature",
        "temperature_min",
        "temperature_max",
        "thinking_mode_supported",
        "thinking_mode",
        "recommended_tokens",
        "api_protocol",
        "chunk_size",
        "timeout",
        "write_timeout",
        "test_connect_timeout",
        "test_request_timeout",
        "segment_limit",
    ]

    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary with consistent field ordering.

        For non-LLM platforms (parser/converter), LLM-only fields are omitted
        to keep the configuration clean and avoid confusion.

        Field order is taken from the preserved original JSON order when
        available, falling back to _PLATFORM_FIELD_ORDER for platforms that
        were added programmatically (no load-time order to preserve).
        """
        from collections import OrderedDict

        config_dict: OrderedDict[str, Any] = OrderedDict()
        config_dict['_schema_version'] = self._schema_version
        config_dict['default_platform'] = self.default_platform
        config_dict['platforms'] = OrderedDict()

        # Convert platforms to dictionary format
        for platform_key, platform_config in self.platforms.items():
            # Build ordered dict with consistent field order
            plat_dict: OrderedDict[str, Any] = OrderedDict()
            plat_raw = asdict(platform_config)

            # Determine if this is an LLM platform
            is_llm_platform = platform_type_uses_llm_chunk_concurrent(platform_config.platform_type)

            # Use preserved original field order when available;
            # fall back to _PLATFORM_FIELD_ORDER for programmatically-added platforms.
            field_order = self._platform_field_orders.get(platform_key)
            if field_order is None:
                field_order = self._PLATFORM_FIELD_ORDER

            # Add fields in the preserved order
            seen: set = set()
            for field_name in field_order:
                if field_name not in plat_raw:
                    continue
                if not is_llm_platform and field_name in self._LLM_ONLY_FIELDS:
                    seen.add(field_name)
                    continue
                plat_dict[field_name] = plat_raw[field_name]
                seen.add(field_name)

            # Append any fields present in the dataclass but missing from the
            # order list (e.g. new fields added during migration that weren't
            # in the original JSON).
            for field_name in plat_raw:
                if field_name not in seen:
                    if not is_llm_platform and field_name in self._LLM_ONLY_FIELDS:
                        continue
                    plat_dict[field_name] = plat_raw[field_name]

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
    if _platforms_config is None:
        logger.warning(LogModule.CONFIG, "platforms.json save skipped: _platforms_config is None (not loaded or was cleared)")
        return False
    return _platforms_config.save_to_file()


def clear_platforms_config_cache() -> None:
    """Clear platforms configuration cache to force reload"""
    global _platforms_config
    _platforms_config = None

