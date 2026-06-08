# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Module log manager for controlling module-based logging.

This module implements delayed initialization to avoid startup issues.
Configuration is only loaded when module logging is first used.
"""

from typing import Dict, Optional, Set
from enum import Enum
from .logger import LogModule


class ModuleLogManager:
    """
    Manages module logging enable/disable states.
    
    Uses delayed initialization to avoid startup issues:
    - Configuration is only loaded when first accessed
    - Safe fallback to defaults if configuration read fails
    - Does not block system startup
    """
    
    def __init__(self):
        """Initialize manager with delayed configuration loading."""
        self._initialized = False
        self._module_states: Dict[str, Dict[str, bool]] = {}
        self._enabled = False  # Module logging is disabled by default
    
    def _ensure_initialized(self):
        """Ensure configuration is loaded (lazy initialization)."""
        if self._initialized:
            return
        
        try:
            self._load_config()
        except Exception:
            # Safe fallback: use defaults (all modules disabled)
            self._module_states = {}
            self._enabled = False
        finally:
            self._initialized = True
    
    def _load_config(self):
        """Load module logging configuration from config file."""
        try:
            from backend.config.config_loader import get_unified_config
            config = get_unified_config()
            
            # Check if module logging is enabled
            logging_config = config.system.logging
            self._enabled = getattr(logging_config, 'enable_module_logging', False)
            
            if not self._enabled:
                # Module logging is disabled, use defaults
                self._module_states = {}
                return
            
            # Get module logging configuration
            module_config = getattr(logging_config, 'module_logging', None)
            if not module_config:
                # No module config, use defaults (all disabled)
                self._module_states = {}
                return
            
            # Initialize all modules - default to False (whitelist mode)
            # Only modules explicitly listed in enabled_modules will be enabled
            default_enabled = getattr(module_config, 'default_enabled', False)
            for module in LogModule:
                self._module_states[module.value] = {
                    'DEBUG': False,  # Default: disabled (whitelist mode)
                    'TRACE': False  # Default: disabled (whitelist mode)
                }
            
            # Apply enabled_modules (whitelist - only explicitly listed modules are enabled)
            enabled_modules = getattr(module_config, 'enabled_modules', {})
            if isinstance(enabled_modules, dict):
                for module_name, levels in enabled_modules.items():
                    if module_name in self._module_states:
                        # levels can be string or list
                        if isinstance(levels, str):
                            levels_list = [levels.upper()]
                        elif isinstance(levels, list):
                            levels_list = [l.upper() for l in levels]
                        else:
                            continue
                        
                        for level in levels_list:
                            if level in ('DEBUG', 'TRACE'):
                                self._module_states[module_name][level] = True
                                # TRACE includes DEBUG
                                if level == 'TRACE':
                                    self._module_states[module_name]['DEBUG'] = True
            
            # Apply disabled_modules (overrides enabled_modules)
            disabled_modules = getattr(module_config, 'disabled_modules', {})
            if isinstance(disabled_modules, dict):
                for module_name, levels in disabled_modules.items():
                    if module_name in self._module_states:
                        # levels can be string or list
                        if isinstance(levels, str):
                            levels_list = [levels.upper()]
                        elif isinstance(levels, list):
                            levels_list = [l.upper() for l in levels]
                        else:
                            continue
                        
                        for level in levels_list:
                            if level in ('DEBUG', 'TRACE'):
                                self._module_states[module_name][level] = False
            
            # Apply default_enabled to modules not explicitly listed (if default_enabled is True)
            # This allows "blacklist mode" where all modules are enabled by default except disabled ones
            if default_enabled:
                enabled_module_names = set(enabled_modules.keys()) if isinstance(enabled_modules, dict) else set()
                disabled_module_names = set(disabled_modules.keys()) if isinstance(disabled_modules, dict) else set()
                
                for module in LogModule:
                    module_name = module.value
                    # Only apply default to modules not in enabled_modules or disabled_modules
                    if module_name not in enabled_module_names and module_name not in disabled_module_names:
                        self._module_states[module_name] = {
                            'DEBUG': True,
                            'TRACE': True
                        }
            
        except Exception:
            # Configuration read failed, use safe defaults
            self._module_states = {}
            self._enabled = False
    
    def is_enabled(self, module: LogModule, level: str) -> bool:
        """
        Check if specified module and level is enabled.
        
        Args:
            module: LogModule enum value
            level: Log level string ('DEBUG', 'TRACE', 'INFO', etc.)
            
        Returns:
            True if enabled, False otherwise
            
        Note:
            - INFO and above levels are always enabled (not module-specific)
            - DEBUG and TRACE are controlled by module settings
        """
        # INFO and above levels are always enabled
        if level.upper() in ("INFO", "WARNING", "ERROR", "SUCCESS", "CRITICAL"):
            return True
        
        # If module logging is not enabled, allow all DEBUG/TRACE
        if not self._enabled:
            return True  # Default: allow all when module logging is disabled
        
        # Ensure configuration is loaded
        self._ensure_initialized()
        
        # Check module-specific setting
        module_states = self._module_states.get(module.value, {})
        return module_states.get(level.upper(), False)
    
    def get_module_status(self) -> Dict[str, Dict[str, bool]]:
        """
        Get all module states.
        
        Returns:
            Dictionary mapping module names to their level states
        """
        self._ensure_initialized()
        return self._module_states.copy()
    
    def is_module_logging_enabled(self) -> bool:
        """Check if module logging feature is enabled."""
        self._ensure_initialized()
        return self._enabled


# Create global instance (delayed initialization)
module_log_manager = ModuleLogManager()
