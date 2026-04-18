# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class UIConfig:
    """UI configuration class. _schema_version = JSON format version; version kept for backward compat."""
    _schema_version: int = 2
    version: str = "2.0.0"
    i18n: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def load_from_file(cls, config_file: str = "ui.json") -> "UIConfig":
        """Load UI configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                logger.info(LogModule.CONFIG, f"Loading UI configuration from: {config_path}")
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
                            f"Merged existing ui.json with template structure: {config_path}",
                        )
                        data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to merge ui.json with template: {merge_err}",
                    )

                config = cls()
                config.update_from_dict(data)
                logger.debug(LogModule.CONFIG, "UI configuration loaded successfully")
                return config
            else:
                # Try to create from template
                from utils.path_utils import get_template_file_path
                template_path = get_template_file_path(f"{config_file}.template")
                if template_path.exists():
                    logger.info(LogModule.CONFIG, f"UI config file not found, creating from template: {template_path}")
                    import shutil
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, config_path)
                    # Load the newly created file
                    with open(config_path, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                        config = cls()
                        config.update_from_dict(data)
                        return config
                logger.warning(LogModule.CONFIG, f"UI config file not found at {config_path}, using defaults")
                return cls()
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to load UI configuration: {e}")
            return cls()
    
    def save_to_file(self, config_file: str = "ui.json") -> bool:
        """Save UI configuration to file"""
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
            logger.info(LogModule.CONFIG, f"UI configuration saved to: {target_path}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to save UI configuration to {target_path}: {e}")
            return False
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        if '_schema_version' in data:
            self._schema_version = int(data['_schema_version'])
            self.version = str(self._schema_version)

        if 'i18n' in data:
            self.i18n = data['i18n']
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        return {
            '_schema_version': self._schema_version,
            'i18n': self.i18n
        }


# Global UI configuration instance
_ui_config: Optional[UIConfig] = None
_ui_config_loading: bool = False  # Flag to prevent concurrent loading


def get_ui_config() -> UIConfig:
    """Get UI configuration with caching to avoid duplicate loading"""
    global _ui_config, _ui_config_loading
    if _ui_config is None and not _ui_config_loading:
        _ui_config_loading = True
        try:
            _ui_config = UIConfig.load_from_file()
        finally:
            _ui_config_loading = False
    return _ui_config


def save_ui_config() -> bool:
    """Save UI configuration"""
    global _ui_config
    if _ui_config is not None:
        return _ui_config.save_to_file()
    return False


def clear_ui_config_cache() -> None:
    """Clear UI configuration cache to force reload"""
    global _ui_config
    _ui_config = None

