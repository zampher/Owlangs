# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Chunk Size Service

Handles chunk size determination from payload or global settings.
"""

from typing import Any, Optional

from logger import unified_logger as logger
from logger.logger import LogModule
from backend.config.platforms_config import platform_type_uses_llm_chunk_concurrent


class ChunkSizeService:
    """Service for determining chunk size for translation tasks."""
    
    def get_chunk_size(
        self,
        payload: Any,
        task_id: Optional[str] = None,
        fallback: int = 3000
    ) -> int:
        """
        Get chunk_size with priority:
        1. Payload explicit chunk_size (user override per task)
        2. Selected platform's config chunk_size (from platforms.json)
        3. Fallback value
        
        Args:
            payload: Payload object (dict or object)
            task_id: Optional task ID for logging
            fallback: Fallback value if chunk_size is 0 or not found (default: 3000)
        
        Returns:
            chunk_size value (never returns 0, always returns fallback if unset)
        """
        # Helper function to get payload attribute (supports both dict and object)
        def _get_payload_attr(key: str, default=None):
            if isinstance(payload, dict):
                return payload.get(key, default)
            else:
                return getattr(payload, key, default)
        
        # Priority 1: Payload explicit override
        payload_chunk_size = _get_payload_attr('chunk_size', 0)
        if payload_chunk_size and payload_chunk_size != 0:
            if task_id:
                logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Using chunk_size={payload_chunk_size} from payload (explicit override)")
            return int(payload_chunk_size)

        # Priority 2: Selected platform's config
        platform_key = _get_payload_attr('platform_key')
        if platform_key:
            try:
                from backend.config.platforms_config import get_platforms_config
                platforms_config = get_platforms_config()
                platform_cfg = platforms_config.platforms.get(platform_key)
                if (
                    platform_cfg
                    and hasattr(platform_cfg, "chunk_size")
                    and platform_type_uses_llm_chunk_concurrent(platform_cfg.platform_type)
                ):
                    platform_chunk_size = platform_cfg.chunk_size
                    if platform_chunk_size and platform_chunk_size != 0:
                        if task_id:
                            logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Using chunk_size={platform_chunk_size} from platform '{platform_key}' config")
                        return int(platform_chunk_size)
            except Exception as e:
                if task_id:
                    logger.debug(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: Failed to get chunk_size from platform config: {e}")
        
        # Priority 2: Fallback
        if task_id:
            logger.warning(LogModule.CONFIG, f"[CHUNK_SIZE] Task {task_id}: No chunk_size found in payload or platform config. Using fallback={fallback}")
        return fallback


# Global singleton instance
chunk_size_service = ChunkSizeService()

