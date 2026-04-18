# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Chunk Size Service

Handles chunk size determination from payload or global settings.
"""

from typing import Any, Optional

from logger import unified_logger as logger
from logger.logger import LogModule


class ChunkSizeService:
    """Service for determining chunk size for translation tasks."""
    
    def get_chunk_size(
        self,
        payload: Any,
        task_id: Optional[str] = None,
        fallback: int = 3000
    ) -> int:
        """
        Get chunk_size from global user profile (priority) or payload.
        Always prioritize global user profile over payload to ensure consistency with frontend global settings.
        
        Args:
            payload: Payload object (dict or object)
            task_id: Optional task ID for logging
            fallback: Fallback value if chunk_size is 0 or not found (default: 3000)
        
        Returns:
            chunk_size value (never returns 0, always returns fallback if unset)
        """
        # Priority 1: Get from app_config.json (translator_chunk_token_size) - matches frontend global settings
        chunk_size = None
        try:
            from backend.config.app_config import get_app_config, AppConfig
            import json
            from pathlib import Path
            
            # Try method 1: Use get_app_config() to get the loaded config object
            try:
                app_config = get_app_config()
                if hasattr(app_config, 'translator_chunk_token_size'):
                    chunk_size = app_config.translator_chunk_token_size
            except Exception as e1:
                if task_id:
                    logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Failed to get from app_config object: {e1}")
            
            # Try method 2: Directly read from app_config.json file using unified path resolution
            if not chunk_size or chunk_size == 0:
                try:
                    cfg_path = AppConfig._resolve_app_config_path("app_config.json")
                    if cfg_path.exists():
                        with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                            data = json.load(f)
                            chunk_size = data.get('translator_chunk_token_size')
                except Exception as e2:
                    if task_id:
                        logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Failed to read from app_config.json: {e2}")
            
            if chunk_size and chunk_size != 0:
                if task_id:
                    logger.info(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Using chunk_size={chunk_size} from app_config.json (translator_chunk_token_size, priority)")
                return chunk_size
        except Exception as e:
            if task_id:
                logger.warning(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Failed to get chunk_size from app_config.json: {e}", exc_info=True)
        
        # Priority 2: Get from payload if global profile not available or is 0
        # Helper function to get payload attribute (supports both dict and object)
        def _get_payload_attr(key: str, default=None):
            if isinstance(payload, dict):
                return payload.get(key, default)
            else:
                return getattr(payload, key, default)
        
        chunk_size = _get_payload_attr('chunk_size', 0)
        
        # If chunk_size from payload is 0 or None, use fallback
        if chunk_size == 0 or chunk_size is None:
            chunk_size = fallback
            if task_id:
                logger.warning(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: chunk_size is 0 or None, using fallback value {fallback}")
        elif task_id:
            logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Using chunk_size={chunk_size} from payload")
        
        return chunk_size


# Global singleton instance
chunk_size_service = ChunkSizeService()

