# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

# Keep legacy import paths working.
# When the project is executed via ``python -m backend.*`` or inside a PyInstaller bundle,
# the real module path is ``backend.config.*``. Some modules still import ``config.*``.
import sys as _sys

if __name__ != "config":
    _sys.modules.setdefault("config", _sys.modules[__name__])

# Legacy imports (for backward compatibility)
from .app_config import AppConfig, get_app_config, save_app_config, clear_app_config_cache
# Note: GlobalConfig is deprecated, use UnifiedConfig from config_loader instead

# New config structure imports
from .system_config import SystemConfig, get_system_config, save_system_config
from .platforms_config import PlatformsConfig, get_platforms_config, save_platforms_config
from .ui_config import UIConfig, get_ui_config, save_ui_config
from .secrets_manager import SecretsManager, get_secrets_manager
from .local_config import LocalConfig
from .config_loader import get_unified_config, save_unified_config, clear_unified_config_cache, load_all_configs
from .translation_config import (
    TranslationConfig, DeepSplitDefaults,
    get_translation_config, save_translation_config,
    clear_translation_config_cache, get_default_deep_split
)

__all__ = [
    # Legacy exports (for backward compatibility)
    "AppConfig",
    "get_app_config", 
    "save_app_config",
    "clear_app_config_cache",
    # UnifiedConfig (replaces GlobalConfig)
    "get_unified_config",
    "save_unified_config",
    "clear_unified_config_cache",
    # New config structure exports
    "SystemConfig",
    "PlatformsConfig",
    "UIConfig",
    "LocalConfig",
    "SecretsManager",
    "get_system_config",
    "save_system_config",
    "get_platforms_config",
    "save_platforms_config",
    "get_ui_config",
    "save_ui_config",
    "get_secrets_manager",
    "get_unified_config",
    "load_all_configs",
    # Translation config exports
    "TranslationConfig",
    "DeepSplitDefaults",
    "get_translation_config",
    "save_translation_config",
    "clear_translation_config_cache",
    "get_default_deep_split",
]
