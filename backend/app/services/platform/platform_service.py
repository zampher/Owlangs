# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Platform Service

Handles platform detection, configuration, and token limits.
"""

from typing import Optional, Dict, Any

from logger import unified_logger as logger
from logger.logger import LogModule


class PlatformService:
    """Service for platform-related operations."""
    
    def determine_platform_key(
        self,
        base_url: str,
        model_id: str,
        task_state: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Determine platform key from base_url and model_id by matching against configured platforms.
        
        Args:
            base_url: Base URL of the AI platform
            model_id: Model ID
            task_state: Task state dictionary (optional, for accessing payload)
        
        Returns:
            Platform key if found, None otherwise
        """
        try:
            # Check if base_url is None or empty
            if not base_url:
                return None
            
            base_url_lower = base_url.lower()
            
            # First, try to match against configured platforms (exact match priority)
            try:
                from backend.config.config_loader import get_unified_config
                unified_config = get_unified_config()
                # Try to match by URL - check if configured URL contains the given base_url
                for platform_key, platform_config in unified_config.platforms.platforms.items():
                    if platform_config.url:
                        config_url_lower = platform_config.url.lower()
                        # Match if base_url is contained in config URL or vice versa
                        if base_url_lower in config_url_lower or config_url_lower in base_url_lower:
                            # If model_id is provided, try to match; otherwise accept URL match
                            if not model_id or platform_config.model == model_id:
                                return platform_key
                            # If model doesn't match but URL is exact, still use this platform
                            # (user may have changed model but kept same endpoint)
                            if base_url_lower == config_url_lower:
                                return platform_key
            except Exception:
                pass
            
            # If no exact match, try common platform mappings based on URL patterns
            if 'api.openai.com' in base_url_lower:
                return 'openai'
            elif 'api.deepseek.com' in base_url_lower:
                return 'deepseek'
            elif 'doubao' in base_url_lower:
                return 'doubao'
            elif 'qianwen' in base_url_lower or 'dashscope' in base_url_lower:
                return 'qianwen'
            elif 'api.anthropic.com' in base_url_lower:
                return 'anthropic'
            elif 'gemini' in base_url_lower or 'google' in base_url_lower:
                return 'gemini'
            elif ':11434' in base_url_lower or 'ollama' in base_url_lower:
                return 'ollama'
            
            return None
        except Exception as e:
            logger.warning(LogModule.SYSTEM, f"Failed to determine platform key: {e}")
            return None
    
    def get_max_tokens(
        self,
        base_url: str,
        model_id: str,
        platform_key: Optional[str] = None
    ) -> Optional[int]:
        """
        Get max_tokens from platform configuration based on base_url and model_id.
        
        Args:
            base_url: Base URL of the AI platform
            model_id: Model ID
            platform_key: Optional platform key (if already determined)
        
        Returns:
            max_tokens value from platform config, or None if not found
        """
        try:
            from backend.config.config_loader import get_unified_config
            unified_config = get_unified_config()
            
            # If platform_key is provided, use it directly
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config:
                    max_tokens = platform_config.max_tokens
                    # Warn if max_tokens is too small (likely configuration error)
                    if max_tokens and max_tokens < 1024:
                        logger.warning(
                            LogModule.SYSTEM,
                            f"[MAX_TOKENS] Platform '{platform_key}' has suspiciously low max_tokens={max_tokens} (< 1024). "
                            f"This may cause API responses to be truncated. Please check platform configuration."
                        )
                    return max_tokens
            
            # Otherwise, try to determine platform key
            platform_key = self.determine_platform_key(base_url, model_id)
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config:
                    max_tokens = platform_config.max_tokens
                    # Warn if max_tokens is too small (likely configuration error)
                    if max_tokens and max_tokens < 1024:
                        logger.warning(
                            LogModule.SYSTEM,
                            f"[MAX_TOKENS] Platform '{platform_key}' has suspiciously low max_tokens={max_tokens} (< 1024). "
                            f"This may cause API responses to be truncated. Please check platform configuration."
                        )
                    return max_tokens
            
            # If no platform found, return None (will use API default)
            return None
        except Exception as e:
            logger.warning(LogModule.SYSTEM, f"[MAX_TOKENS] Failed to get max_tokens from platform config: {e}")
            return None
    
    def get_thinking_mode(
        self,
        base_url: str,
        model_id: str,
        platform_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Get thinking mode from platform configuration based on base_url and model_id.
        
        Args:
            base_url: Base URL of the AI platform
            model_id: Model ID
            platform_key: Optional platform key (if already determined)
        
        Returns:
            thinking_mode value from platform config ("enable", "disable", "default"), or None if not found or not supported
        """
        try:
            from backend.config.config_loader import get_unified_config
            unified_config = get_unified_config()
            
            # If platform_key is provided, use it directly
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config and platform_config.thinking_mode_supported:
                    return platform_config.thinking_mode
            
            # Otherwise, try to determine platform key first
            if not platform_key:
                platform_key = self.determine_platform_key(base_url, model_id)
            
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config and platform_config.thinking_mode_supported:
                    return platform_config.thinking_mode
            
            return None
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"Failed to get thinking_mode: {e}")
            return None
    
    def get_api_protocol(
        self,
        base_url: str,
        model_id: str,
        platform_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Get API protocol from platform configuration.
        
        Args:
            base_url: Base URL of the AI platform
            model_id: Model ID
            platform_key: Optional platform key (if already determined)
        
        Returns:
            api_protocol value from platform config ("openai", "ollama", "anthropic"), 
            or None if not found
        """
        try:
            from backend.config.config_loader import get_unified_config
            unified_config = get_unified_config()
            
            # If platform_key is provided, use it directly
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config:
                    return getattr(platform_config, 'api_protocol', 'openai')
            
            # Otherwise, try to determine platform key
            platform_key = self.determine_platform_key(base_url, model_id)
            if platform_key:
                platform_config = unified_config.platforms.get_platform_config(platform_key)
                if platform_config:
                    return getattr(platform_config, 'api_protocol', 'openai')
            
            return None
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"Failed to get api_protocol: {e}")
            return None


# Global singleton instance
platform_service = PlatformService()

