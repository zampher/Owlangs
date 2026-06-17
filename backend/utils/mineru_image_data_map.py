# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Build frontend image_data_map entries from MinerU layout ZIP assets."""

from __future__ import annotations

import base64
import io
import mimetypes
import os
import zipfile
import zlib
from typing import Any, Dict, Iterable, Optional, Set


def _image_path_key_variants(path: str) -> Set[str]:
    norm_path = str(path or "").replace("\\", "/").lstrip("./")
    if not norm_path:
        return set()
    filename = norm_path.split("/")[-1]
    keys = {
        path,
        str(path).replace("\\", "/"),
        norm_path,
        f"./{norm_path}",
        filename,
        f"images/{filename}",
        f"./images/{filename}",
    }
    if norm_path.startswith("images/"):
        keys.add(norm_path[len("images/") :])
    return {key for key in keys if key}


def register_image_data_uri(
    image_data_map: Dict[str, Dict[str, str]],
    path: str,
    data_uri: str,
    *,
    alt: Optional[str] = None,
) -> None:
    """Register one image under filename/path key variants for MarkdownTextWithImages."""
    if not data_uri or not path:
        return
    norm_path = str(path).replace("\\", "/").lstrip("./")
    filename = os.path.basename(norm_path) or norm_path
    entry = {"data": data_uri, "alt": alt or filename}
    for key in _image_path_key_variants(path):
        if key not in image_data_map:
            image_data_map[key] = dict(entry)


def populate_image_data_map_from_bytes_map(
    image_data_map: Dict[str, Dict[str, str]],
    images_bytes_map: Dict[str, bytes],
) -> int:
    """Register ZIP image bytes under filename and common path key variants."""
    added = 0
    for img_path, img_bytes in (images_bytes_map or {}).items():
        if not img_bytes:
            continue
        norm_path = str(img_path).replace("\\", "/")
        mime = mimetypes.guess_type(norm_path)[0] or "image/png"
        data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
        before = len(image_data_map)
        register_image_data_uri(image_data_map, norm_path, data_uri, alt=norm_path.split("/")[-1])
        if len(image_data_map) > before:
            added += len(image_data_map) - before
    return added


def lookup_image_data_entry(
    image_data_map: Dict[str, Dict[str, str]],
    path: str,
) -> Optional[Dict[str, str]]:
    """Find image_data_map entry for a markdown image path."""
    for key in _image_path_key_variants(path):
        entry = image_data_map.get(key)
        if isinstance(entry, dict) and entry.get("data"):
            return entry
    return None


def _decompress_zip_bytes_if_needed(zip_bytes: bytes) -> bytes:
    if isinstance(zip_bytes, bytes) and len(zip_bytes) > 2 and zip_bytes[:2] in (b"\x78\x9c", b"\x78\xda"):
        return zlib.decompress(zip_bytes)
    return zip_bytes


def _collect_zip_image_bytes(
    zip_file: zipfile.ZipFile,
    layout_doc: Any = None,
) -> Dict[str, bytes]:
    from layout.pdf_renderer.shared.block_processor import BlockProcessor

    images_bytes_map: Dict[str, bytes] = {}
    if layout_doc is not None:
        images_bytes_map.update(
            BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file) or {},
        )
    if images_bytes_map:
        return images_bytes_map

    for name in zip_file.namelist():
        norm = name.replace("\\", "/")
        lower = norm.lower()
        if not lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")):
            continue
        if "/images/" not in lower and not lower.startswith("images/"):
            continue
        try:
            images_bytes_map[norm] = zip_file.read(name)
        except Exception:
            continue
    return images_bytes_map


def populate_image_data_map_from_mineru_zip(
    image_data_map: Dict[str, Dict[str, str]],
    task_state: Dict[str, Any],
    *,
    layout_doc: Any = None,
) -> int:
    """Extract MinerU ZIP images into image_data_map for Extract/source-preview UI."""
    zip_bytes = task_state.get("layout_source_zip")
    if not zip_bytes:
        return 0
    try:
        zip_bytes = _decompress_zip_bytes_if_needed(zip_bytes)
        layout_doc = layout_doc or task_state.get("layout_document")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
            images_bytes_map = _collect_zip_image_bytes(zip_file, layout_doc)
        return populate_image_data_map_from_bytes_map(image_data_map, images_bytes_map)
    except Exception:
        return 0


def populate_image_data_map_from_data_uri_map(
    image_data_map: Dict[str, Dict[str, str]],
    image_data_by_path: Dict[str, str],
) -> int:
    """Register pre-encoded data URIs (layout-extract path) under all lookup keys."""
    added = 0
    for img_path, data_uri in (image_data_by_path or {}).items():
        before = len(image_data_map)
        register_image_data_uri(image_data_map, img_path, data_uri)
        added += max(0, len(image_data_map) - before)
    return added
