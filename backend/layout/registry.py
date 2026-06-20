# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Layout registry for unified layout loading interface.

This module provides a registry pattern to load layout documents from different
engines (MinerU, Docling, etc.) in a unified way, enabling future extensibility.
"""

import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Callable

from logger import unified_logger as logger
from logger.logger import LogModule
from layout.base import LayoutDocument

# Registry of layout loaders by engine name
_layout_loaders: Dict[str, Callable[[bytes], Optional[LayoutDocument]]] = {}


def register_layout_loader(engine: str, loader_func: Callable[[bytes], Optional[LayoutDocument]]):
    """
    Register a layout loader function for an engine.
    
    Args:
        engine: Engine name (e.g., 'mineru', 'docling')
        loader_func: Function that takes ZIP bytes and returns LayoutDocument or None
    """
    _layout_loaders[engine] = loader_func
    logger.debug(LogModule.LAYOUT, f"Registered layout loader for engine: {engine}")


def load_layout_from_engine_zip(engine: str, zip_bytes: bytes) -> Optional[LayoutDocument]:
    """
    Load layout document from engine ZIP bytes.
    
    Args:
        engine: Engine name (e.g., 'mineru', 'docling')
        zip_bytes: ZIP file content as bytes
        
    Returns:
        LayoutDocument if parsing succeeds, None otherwise
    """
    if engine not in _layout_loaders:
        logger.warning(LogModule.LAYOUT, f"No layout loader registered for engine: {engine}")
        return None
    
    try:
        loader_func = _layout_loaders[engine]
        return loader_func(zip_bytes)
    except Exception as e:
        logger.error(LogModule.LAYOUT, f"Failed to load layout from {engine} ZIP: {e}", exc_info=True)
        return None


def load_layout_from_engine_dir(engine: str, dir_path: Path) -> Optional[LayoutDocument]:
    """
    Load layout document from engine directory (for debugging/testing).
    
    Args:
        engine: Engine name (e.g., 'mineru', 'docling')
        dir_path: Path to extracted engine output directory
        
    Returns:
        LayoutDocument if parsing succeeds, None otherwise
    """
    if engine == "mineru":
        from layout.mineru_layout_model import parse_layout_json, parse_content_list_json
        
        # Scan recursively for layout files to handle nested directory structures
        # (e.g., Cloud MinerU vlm output: {filename}/vlm/layout.json or *_middle.json)
        layout_candidates = list(dir_path.rglob("layout.json"))
        if layout_candidates:
            try:
                return parse_layout_json(layout_candidates[0])
            except Exception as e:
                logger.debug(LogModule.LAYOUT, f"Failed to parse layout.json, trying middle.json: {e}")
        
        middle_candidates = list(dir_path.rglob("*_middle.json"))
        if middle_candidates:
            try:
                return parse_layout_json(middle_candidates[0])
            except Exception as e:
                logger.debug(LogModule.LAYOUT, f"Failed to parse *_middle.json, trying content_list.json: {e}")
        
        content_list_files = list(dir_path.rglob("*_content_list.json"))
        if content_list_files:
            return parse_content_list_json(content_list_files[0])
        
        logger.warning(LogModule.LAYOUT, f"No layout.json, *_middle.json, or *_content_list.json found in {dir_path}")
        return None
    else:
        logger.warning(LogModule.LAYOUT, f"Directory loading not implemented for engine: {engine}")
        return None


# Register MinerU loader
def _load_mineru_layout(zip_bytes: bytes) -> Optional[LayoutDocument]:
    """Load MinerU layout from ZIP bytes."""
    from layout.ocr_provider.mineru.layout_parser import parse_mineru_layout_from_zip_bytes
    return parse_mineru_layout_from_zip_bytes(zip_bytes, engine="mineru")


register_layout_loader("mineru", _load_mineru_layout)


def _load_paddle_layout(zip_bytes: bytes) -> Optional[LayoutDocument]:
    """Load PaddleOCR layout from ZIP bytes."""
    from layout.ocr_provider.paddle.zip_loader import parse_paddle_layout_from_zip_bytes

    return parse_paddle_layout_from_zip_bytes(zip_bytes)


register_layout_loader("paddle", _load_paddle_layout)
register_layout_loader("paddle_local", _load_paddle_layout)
