# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""URL-based image refs for frontend APIs (avoid embedding base64 in JSON)."""

from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, unquote

from logger import unified_logger as logger
from logger.logger import LogModule

_IMAGE_MAP_KEYS = (
    "translation_image_data_map",
    "image_data_map",
    "mobi_image_data_map",
)


def task_image_url(task_id: str, key: str) -> str:
    """Relative API path for one task image (key is URL-encoded)."""
    return f"/service/task-image/{task_id}?key={quote(str(key), safe='')}"


def build_frontend_image_data_map(
    task_id: str,
    raw_map: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    """
    Convert backend image_data_map entries to frontend URL refs.

    Backend entries typically look like:
      {path: {"data": "data:image/...;base64,...", "mime": "...", "alt"?: "..."}}

    Frontend receives:
      {path: {"url": "/service/task-image/...?key=...", "alt": "..."}}
    """
    out: Dict[str, Dict[str, str]] = {}
    if not isinstance(raw_map, dict) or not raw_map:
        return out

    for key, info in raw_map.items():
        key_str = str(key)
        if isinstance(info, dict):
            data = info.get("data") or ""
            existing_url = (info.get("url") or "").strip()
            # Skip empty shells with neither payload nor URL.
            if not data and not existing_url:
                continue
            alt = (
                info.get("alt")
                or os.path.basename(key_str.replace("\\", "/"))
                or key_str
            )
            out[key_str] = {
                "url": existing_url or task_image_url(task_id, key_str),
                "alt": str(alt),
            }
        elif isinstance(info, str) and info.startswith("data:image/"):
            # Legacy: value is a bare data URI.
            out[key_str] = {
                "url": task_image_url(task_id, key_str),
                "alt": os.path.basename(key_str.replace("\\", "/")) or key_str,
            }
    return out


def decode_data_uri(data_uri: str) -> Tuple[bytes, str]:
    """Decode a data URI into (bytes, mime_type). Raises ValueError on failure."""
    if not data_uri or not isinstance(data_uri, str):
        raise ValueError("empty data URI")
    if not data_uri.startswith("data:"):
        raise ValueError("not a data URI")
    header, _, payload = data_uri.partition(",")
    if not payload:
        raise ValueError("data URI missing payload")
    mime = "application/octet-stream"
    meta = header[5:]  # strip "data:"
    if meta:
        mime = meta.split(";")[0].strip() or mime
    if ";base64" in header.lower():
        return base64.b64decode(payload), mime
    from urllib.parse import unquote_to_bytes

    return unquote_to_bytes(payload), mime


def _path_variants(path: str) -> set[str]:
    norm = str(path or "").replace("\\", "/").lstrip("./")
    if not norm:
        return set()
    filename = norm.split("/")[-1]
    keys = {
        path,
        str(path).replace("\\", "/"),
        norm,
        f"./{norm}",
        filename,
        f"images/{filename}",
        f"./images/{filename}",
    }
    if norm.startswith("images/"):
        keys.add(norm[len("images/") :])
    return {k for k in keys if k}


def _lookup_entry(
    image_map: Dict[str, Any],
    key: str,
) -> Optional[Dict[str, Any]]:
    if not image_map or not key:
        return None
    direct = image_map.get(key)
    if isinstance(direct, dict):
        return direct
    if isinstance(direct, str) and direct.startswith("data:"):
        return {"data": direct}
    # Try unquoted / common variants
    candidates = _path_variants(key)
    candidates.add(unquote(key))
    for cand in candidates:
        hit = image_map.get(cand)
        if isinstance(hit, dict):
            return hit
        if isinstance(hit, str) and hit.startswith("data:"):
            return {"data": hit}
    # Fuzzy basename / containment match
    key_norm = key.replace("\\", "/").lstrip("./")
    key_base = key_norm.split("/")[-1]
    for map_key, value in image_map.items():
        mk = str(map_key).replace("\\", "/").lstrip("./")
        if mk == key_norm or mk.endswith(key_norm) or key_norm.endswith(mk):
            if isinstance(value, dict):
                return value
            if isinstance(value, str) and value.startswith("data:"):
                return {"data": value}
        if key_base and mk.split("/")[-1] == key_base:
            if isinstance(value, dict):
                return value
            if isinstance(value, str) and value.startswith("data:"):
                return {"data": value}
    return None


def resolve_task_image_bytes(
    task_state: Dict[str, Any],
    key: str,
) -> Optional[Tuple[bytes, str]]:
    """
    Resolve image bytes + mime for a task_state image key.

    Searches translation_image_data_map, image_data_map, mobi_image_data_map.
    """
    if not task_state or not key:
        return None
    key = unquote(key)
    for map_name in _IMAGE_MAP_KEYS:
        image_map = task_state.get(map_name)
        if not isinstance(image_map, dict) or not image_map:
            continue
        entry = _lookup_entry(image_map, key)
        if not entry:
            continue
        data = entry.get("data")
        if isinstance(data, str) and data.startswith("data:"):
            try:
                return decode_data_uri(data)
            except Exception as exc:
                logger.warning(
                    LogModule.SYSTEM,
                    f"[TASK-IMAGE] Failed to decode data URI for key={key!r}: {exc}",
                )
                return None
        # Raw bytes stored under uncommon keys (defensive)
        raw = entry.get("bytes") or entry.get("content")
        if isinstance(raw, (bytes, bytearray)):
            mime = entry.get("mime") or mimetypes.guess_type(key)[0] or "application/octet-stream"
            return bytes(raw), str(mime)
    return None


def strip_segment_inline_image_data(segments: Any) -> None:
    """Remove per-segment base64 image_data fields in-place (keep placeholder_id)."""
    if not isinstance(segments, list):
        return
    for seg in segments:
        if isinstance(seg, dict) and "image_data" in seg:
            seg.pop("image_data", None)
