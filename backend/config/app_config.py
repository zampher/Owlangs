# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class AppConfig:
    """Application configuration class, manages all UI settings"""

    # Schema version for backward compatibility during future migrations
    _schema_version: int = 1

    # Basic settings
    ui_language: str = "zh"
    
    # Workflow settings
    translator_last_workflow: str = "markdown_based"
    translator_auto_workflow_enabled: bool = True
    
    # Format-specific settings
    translator_txt_insert_mode: str = "replace"
    translator_txt_separator: str = "\\n"
    translator_xlsx_insert_mode: str = "replace"
    translator_xlsx_separator: str = "\\n"
    translator_xlsx_translate_regions: str = ""
    translator_docx_insert_mode: str = "replace"
    translator_docx_separator: str = "\\n"
    translator_srt_insert_mode: str = "replace"
    translator_srt_separator: str = "\\n"
    translator_epub_insert_mode: str = "replace"
    translator_epub_separator: str = "\\n"
    translator_html_insert_mode: str = "replace"
    translator_html_separator: str = " "
    translator_json_paths: str = ""
    
    # Parsing settings
    translator_convert_engine: str = "mineru"
    translator_mineru_token: str = ""
    translator_mineru_model_version: str = "vlm"
    translator_formula_ocr: bool = False
    translator_table_ocr: bool = True
    
    # AI translation settings
    translator_skip_translate: bool = False
    translator_platform_last_platform: str = "https://api.openai.com/v1"
    translator_platform_custom_base_url: str = ""
    translator_thinking_mode: str = "disable"
    translator_target_language: str = "Chinese"
    translator_custom_language: str = ""
    translator_custom_prompt: str = ""
    translator_temperature: float = 0.3
    translator_top_p: float = 1.0
    translator_frequency_penalty: float = 0.0
    translator_presence_penalty: float = 0.0
    translator_chunk_token_size: int = 8000  # DEPRECATED: Use per-platform chunk_size in platforms.json instead. This global field is kept as backward-compat fallback when a platform lacks its own chunk_size.
    translator_concurrent: int = 15  # DEPRECATED: Use per-platform concurrent in platforms.json instead. This global field is kept as backward-compat fallback when a platform lacks its own concurrent.
    translator_connect_timeout: int = 15  # HTTP connect timeout (seconds) to reduce first-attempt ConnectTimeout
    translator_timeout: int = 120
    translator_retry: int = 2
    translator_segment_auto_retry_rounds: int = 2  # Queued mode: post-translation failed-segment batch rounds

    # Platform-specific API settings (dynamically save keys and models for different platforms)
    platform_api_keys: Dict[str, str] = field(default_factory=dict)
    platform_models: Dict[str, str] = field(default_factory=dict)
    
    # Glossary settings
    glossary_agent_last_platform: str = "https://api.openai.com/v1"
    glossary_agent_platform_custom_baseurl: str = ""
    glossary_agent_config_choice: str = "same"
    glossary_agent_thinking_mode: str = "disable"
    glossary_agent_top_p: float = 1.0
    glossary_agent_frequency_penalty: float = 0.0
    glossary_agent_presence_penalty: float = 0.0
    glossary_agent_to_lang: str = "English"
    
    # Glossary platform-specific API settings
    glossary_platform_api_keys: Dict[str, str] = field(default_factory=dict)
    glossary_platform_models: Dict[str, str] = field(default_factory=dict)
    
    # Anonymization settings
    anonymize_engine: str = "presidio"  # "presidio" or "simple" (use presidio with local models)
    anonymize_fallback_enabled: bool = True  # Auto fallback to simple engine if presidio fails
    # Optional: default enabled entities when frontend has no user config; DATE_TIME excluded by default
    anonymize_enabled_entities: List[str] = field(default_factory=lambda: [
        "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD",
        "IBAN_CODE", "IP_ADDRESS", "LOCATION", "URL"
    ])
    
    # System settings
    active_task_ids: List[str] = field(default_factory=list)
    theme: str = "auto"
    frontend_type: str = "web"
    
    @classmethod
    def _resolve_app_config_path(cls, config_file: str = "app_config.json") -> Path:
        """Resolve the actual read path for app_config.json using unified path resolution.
        
        This method now uses the same priority logic as get_config_file_path() to ensure
        consistency between frontend and backend configuration reading.
        
        Priority order (same as get_config_file_path):
        1. OWLANGS_CONFIG_PATH/configs (if env var set)
        2. Project root/configs (development - if exists)
        3. C:\\ProgramData\\Owlangs\\configs (Windows deployment - if no project configs)
        4. System config directory (runtime/deployment)
        5. Executable directory/configs (packaged)
        6. Current directory/configs (fallback)
        
        If an absolute path is passed, return it directly.
        """
        p = Path(config_file)
        if p.is_absolute():
            logger.info(LogModule.CONFIG, f"[AppConfig] Using absolute path: {p}")
            return p

        # Use unified config path resolution (same as get_config_file_path)
        try:
            from utils.path_utils import get_config_file_path
            unified_path = get_config_file_path(config_file)
            logger.debug(LogModule.CONFIG, f"[AppConfig] Using unified config path: {unified_path}")
            return unified_path
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"[AppConfig] Failed to use unified config path, falling back to legacy logic: {e}")
            # Fallback to legacy logic if unified path fails
            # 0) Environment-configured directory (cross-platform override)
            env_dir = os.environ.get("OWLANGS_CONFIG_PATH")
            # Windows default runtime configuration directory
            if not env_dir and os.name == "nt":
                env_dir = r"C:\\ProgramData\\Owlangs"
            if env_dir:
                env_cfg = Path(env_dir) / config_file
                if env_cfg.exists():
                    logger.info(LogModule.CONFIG, f"[AppConfig] Using env dir config: {env_cfg}")
                    return env_cfg

            # 1) System directory priority (non-Windows)
            if os.name != "nt":
                system_dir = Path("/etc/Owlangs")
                system_cfg = system_dir / config_file
                if system_dir.exists() and system_cfg.exists():
                    logger.info(LogModule.CONFIG, f"[AppConfig] Using system config: {system_cfg}")
                    return system_cfg

            # 2) Executable directory (PyInstaller) or current working directory
            try:
                if getattr(__import__('sys'), 'frozen', False):
                    import sys as _sys
                    exe_dir = Path(os.path.dirname(_sys.executable))
                    exe_cfg = exe_dir / config_file
                    if exe_cfg.exists():
                        logger.info(LogModule.CONFIG, f"[AppConfig] Using executable directory config: {exe_cfg}")
                        return exe_cfg
                    cwd_cfg = Path.cwd() / config_file
                    if cwd_cfg.exists():
                        logger.info(LogModule.CONFIG, f"[AppConfig] Using working directory config: {cwd_cfg}")
                        return cwd_cfg
                    # Default return to expected path in executable directory (may be used for subsequent writes)
                    return exe_cfg
            except Exception:
                pass

            # 3) Project root directory (development environment)
            project_root = Path(__file__).resolve().parents[2]
            return project_root / config_file

    @classmethod
    def load_from_file(cls, config_file: str = "app_config.json") -> "AppConfig":
        """Load configuration from file, following system priority path resolution"""
        try:
            cfg_path = cls._resolve_app_config_path(config_file)
            if cfg_path.exists():
                logger.info(LogModule.CONFIG, f"Loading application configuration from file: {cfg_path}")
                with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)

                # Merge template structure on upgrade without overwriting user values.
                try:
                    from utils.path_utils import get_template_file_path
                    from backend.utils.template_merge_utils import maybe_merge_json_file_with_template

                    template_path = get_template_file_path(f"{config_file}.template")
                    merged = maybe_merge_json_file_with_template(
                        current_path=cfg_path,
                        template_path=template_path,
                        write_back=True,
                    )
                    if isinstance(merged, dict) and merged != data:
                        logger.info(
                            LogModule.CONFIG,
                            f"Merged existing app_config.json with template structure: {cfg_path}",
                        )
                        data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to merge app_config.json with template: {merge_err}",
                    )

                config = cls()
                config.update_from_dict(data)
                logger.debug(LogModule.CONFIG, "Application configuration loaded successfully")
                return config
            else:
                # Try to create from template for runtime consistency.
                try:
                    from utils.path_utils import get_template_file_path
                    template_path = get_template_file_path(f"{config_file}.template")
                    if template_path.exists():
                        import shutil
                        cfg_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(template_path, cfg_path)
                        logger.info(LogModule.CONFIG, f"Created app_config.json from template: {template_path} -> {cfg_path}")
                        data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                        config = cls()
                        config.update_from_dict(data if isinstance(data, dict) else {})
                        return config
                except Exception:
                    pass

                logger.info(LogModule.CONFIG, f"Configuration file {cfg_path} does not exist, using default configuration")
                return cls()
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to load application configuration: {e}")
            return cls()
    
    def save_to_file(self, config_file: str = "app_config.json") -> bool:
        """Save configuration to file (system directory priority, fallback to working directory on failure)"""
        config_data = asdict(self)
        # Use system-appropriate paths
        from utils.path_utils import get_owlangs_paths
        paths = get_owlangs_paths()
        
        candidates = [
            Path(paths["app_config"]),
            self._resolve_app_config_path(config_file),
            Path.cwd() / "app_config.json"
        ]

        last_error = None
        for path in candidates:
            try:
                if not path.parent.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4, ensure_ascii=False)
                try:
                    # Set appropriate permissions for system directories
                    if str(path).startswith("/etc/"):
                        os.chmod(path, 0o660)
                except Exception:
                    pass
                logger.info(LogModule.CONFIG, f"Application configuration saved successfully: {path}")
                return True
            except Exception as e:
                last_error = e
                logger.warning(LogModule.CONFIG, f"Write failed, trying next location: {path} -> {e}")
                continue

        logger.error(LogModule.CONFIG, f"Failed to save application configuration: {last_error}")
        return False
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary with type coercion."""
        # Get expected types from dataclass annotations for safe coercion
        expected_types = getattr(self.__class__, '__annotations__', {})

        for key, value in data.items():
            if key == '_schema_version':
                self._schema_version = int(value)
                continue
            # Skip comment/note fields (fields starting with underscore)
            if key.startswith('_'):
                continue
            if hasattr(self, key):
                if key in ['platform_api_keys', 'platform_models', 'glossary_platform_api_keys', 'glossary_platform_models']:
                    # Handle dictionary type fields
                    if isinstance(value, dict):
                        setattr(self, key, value)
                elif key == 'active_task_ids':
                    # Handle list type fields
                    if isinstance(value, list):
                        setattr(self, key, value)
                else:
                    # Coerce primitive types when JSON provides a different type
                    expected = expected_types.get(key)
                    coerced = value
                    if expected is not None and value is not None:
                        try:
                            if expected is float and isinstance(value, str):
                                coerced = float(value)
                            elif expected is int and isinstance(value, str):
                                coerced = int(value)
                            elif expected is bool and isinstance(value, str):
                                coerced = value.lower() in ('true', '1', 'yes', 'on')
                        except Exception:
                            coerced = value
                    setattr(self, key, coerced)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        return asdict(self)
    
    def update_platform_api_key(self, platform: str, api_key: str) -> None:
        """Update platform API key"""
        self.platform_api_keys[platform] = api_key
    
    def update_platform_model(self, platform: str, model: str) -> None:
        """Update platform model"""
        self.platform_models[platform] = model
    
    def get_platform_api_key(self, platform: str) -> str:
        """Get platform API key"""
        return self.platform_api_keys.get(platform, "")
    
    def get_platform_model(self, platform: str) -> str:
        """Get platform model"""
        return self.platform_models.get(platform, "")
    
    def update_glossary_platform_api_key(self, platform: str, api_key: str) -> None:
        """Update glossary platform API key"""
        self.glossary_platform_api_keys[platform] = api_key
    
    def update_glossary_platform_model(self, platform: str, model: str) -> None:
        """Update glossary platform model"""
        self.glossary_platform_models[platform] = model
    
    def get_glossary_platform_api_key(self, platform: str) -> str:
        """Get glossary platform API key"""
        return self.glossary_platform_api_keys.get(platform, "")
    
    def get_glossary_platform_model(self, platform: str) -> str:
        """Get glossary platform model"""
        return self.glossary_platform_models.get(platform, "")

    @classmethod
    def get_config(cls, config_file: str = "app_config.json") -> "AppConfig":
        """Get configuration, resolve path by priority and load"""
        return cls.load_from_file(config_file)


# Global configuration instance
_app_config = None

def get_app_config() -> AppConfig:
    """Get global application configuration (cached singleton)"""
    global _app_config
    if _app_config is None:
        _app_config = AppConfig.get_config()
    return _app_config


def clear_app_config_cache() -> None:
    """Clear cached AppConfig so that it will be reloaded from disk on next access"""
    global _app_config
    _app_config = None

def save_app_config() -> bool:
    """Save global application configuration"""
    global _app_config
    if _app_config is not None:
        return _app_config.save_to_file()
    return False
