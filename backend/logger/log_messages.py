# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Log message internationalization manager
Handles both backend log generation and frontend log display
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
# Removed unused import: get_global_config


class LogMessageManager:
    """Manages log message internationalization for both frontend and backend"""
    
    def __init__(self):
        self.current_language = "en"  # Default to English
        self.log_messages = {}
        self._load_log_messages()
    
    def _load_log_messages(self):
        """Load log messages from JSON files (English only)"""
        i18n_dir = Path(__file__).parent.parent / "i18n"
        
        # Load English only
        en_file = i18n_dir / "log_i18n_en.json"
        if en_file.exists():
            with open(en_file, 'r', encoding='utf-8-sig') as f:
                self.log_messages["en"] = json.load(f)
    
    def set_language(self, language: str):
        """Set current language for log messages (always English)"""
        # Always use English for logs regardless of UI language
        self.current_language = "en"
    
    def get_message(self, key: str, **kwargs) -> str:
        """
        Get localized log message
        
        Args:
            key: Message key (e.g., 'backend.app.startup.completed')
            **kwargs: Format parameters for the message
            
        Returns:
            Localized message string
        """
        def get_nested_value(obj, key_path):
            """Get value from nested dictionary using dot-separated key"""
            keys = key_path.split('.')
            current = obj
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return None
            return current
        
        # Try current language first
        if self.current_language in self.log_messages:
            messages = self.log_messages[self.current_language]
            message = get_nested_value(messages, key)
            if message:
                return message.format(**kwargs) if kwargs else message
        
        # Fallback to English
        if "en" in self.log_messages:
            messages = self.log_messages["en"]
            message = get_nested_value(messages, key)
            if message:
                return message.format(**kwargs) if kwargs else message
        
        # If key not found, return the key itself
        return key
    
    def get_available_languages(self) -> list:
        """Get list of available languages"""
        return list(self.log_messages.keys())
    
    def get_all_messages_for_frontend(self) -> Dict[str, Dict[str, str]]:
        """
        Get all log messages for frontend consumption
        Returns only frontend messages in English
        """
        frontend_messages = {}
        if 'en' in self.log_messages and 'frontend' in self.log_messages['en']:
            frontend_messages['en'] = self.log_messages['en']['frontend']
        return frontend_messages


# Global instance
_log_manager = LogMessageManager()


def get_log_message(key: str, **kwargs) -> str:
    """Get localized log message (convenience function)"""
    return _log_manager.get_message(key, **kwargs)


def set_log_language(language: str):
    """Set log language (convenience function)"""
    _log_manager.set_language(language)


def get_available_languages() -> list:
    """Get available languages (convenience function)"""
    return _log_manager.get_available_languages()


def get_frontend_log_messages() -> Dict[str, Dict[str, str]]:
    """Get all log messages for frontend (convenience function)"""
    return _log_manager.get_all_messages_for_frontend()


def initialize_log_language():
    """Initialize log language (always English)"""
    # Always use English for logs
    set_log_language("en")
