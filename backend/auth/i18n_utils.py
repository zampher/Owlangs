# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Simple i18n utility for authentication messages
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class AuthI18nManager:
    """Simple i18n manager for authentication messages"""
    
    def __init__(self):
        self.current_language = "en"  # Default to English
        self.messages = {}
        self._load_messages()
    
    def _load_messages(self):
        """Load i18n messages from JSON files"""
        i18n_dir = Path(__file__).parent.parent / "i18n"
        
        # Load password messages
        password_file = i18n_dir / "i18nPassword.json"
        if password_file.exists():
            with open(password_file, 'r', encoding='utf-8-sig') as f:
                self.messages = json.load(f)
    
    def set_language(self, language: str):
        """Set current language"""
        if language in self.messages:
            self.current_language = language
    
    def get_message(self, key: str, **kwargs) -> str:
        """
        Get localized message
        
        Args:
            key: Message key (e.g., 'changePasswordSuccess')
            **kwargs: Format parameters for the message
            
        Returns:
            Localized message string
        """
        try:
            message = self.messages.get(self.current_language, {}).get(key, key)
            
            # Simple string formatting
            if kwargs:
                try:
                    message = message.format(**kwargs)
                except (KeyError, ValueError):
                    # If formatting fails, return the message as-is
                    pass
            
            return message
        except Exception:
            return key
    
    def get_password_message(self, key: str, **kwargs) -> str:
        """Get password-related message"""
        return self.get_message(key, **kwargs)


# Global instance
_auth_i18n_manager = AuthI18nManager()


def get_auth_i18n() -> AuthI18nManager:
    """Get global auth i18n manager instance"""
    return _auth_i18n_manager


def get_password_message(key: str, **kwargs) -> str:
    """Convenience function to get password message"""
    return _auth_i18n_manager.get_password_message(key, **kwargs)
