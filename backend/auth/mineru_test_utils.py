# SPDX-FileCopyrightText: 2026 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""Pure helpers for MinerU connectivity test responses (no HTTP dependencies)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse


def extract_version_from_health_payload(payload: Any) -> Optional[str]:
    """Parse MinerU server version from /health JSON payload."""
    if not isinstance(payload, dict):
        return None

    for key in ("version", "mineru_version", "app_version", "service_version"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = payload.get("data")
    if isinstance(data, dict):
        nested = extract_version_from_health_payload(data)
        if nested:
            return nested

    return None


def extract_version_from_payload(payload: Any) -> Optional[str]:
    """Search common API response shapes for a MinerU software version string."""
    direct = extract_version_from_health_payload(payload)
    if direct:
        return direct

    if not isinstance(payload, dict):
        return None

    for key in ("version", "mineru_version", "app_version", "service_version", "engine_version"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = payload.get("data")
    if isinstance(data, dict):
        return extract_version_from_payload(data)

    return None


def build_health_probe_urls(base_url: str) -> List[str]:
    """Build candidate /health URLs for MinerU local and self-hosted deployments."""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return []

    candidates: List[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            candidates.append(url)

    _add(f"{normalized}/health")

    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")
    if path:
        # Strip common API prefixes: /api/v4, /api/v3, etc.
        root_path = re.sub(r"/api/v\d+$", "", path, flags=re.IGNORECASE)
        root_path = re.sub(r"/api$", "", root_path, flags=re.IGNORECASE)
        if root_path != path:
            root = urlunparse(parsed._replace(path=root_path or "")).rstrip("/")
            _add(f"{root}/health")

    origin = urlunparse(parsed._replace(path="", params="", query="", fragment="")).rstrip("/")
    if origin != normalized:
        _add(f"{origin}/health")

    return candidates


def infer_cloud_api_version(base_url: str) -> Optional[str]:
    """Infer MinerU cloud API version from base URL (e.g. https://mineru.net/api/v4 -> v4)."""
    if not base_url:
        return None
    match = re.search(r"/api/(v\d+)", base_url, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    if "mineru.net" in base_url.lower():
        return "v4"
    return None


def enrich_mineru_test_result(
    result: Dict[str, Any],
    *,
    mineru_version: Optional[str] = None,
    api_version: Optional[str] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach version metadata to a successful MinerU connectivity test result."""
    if not result.get("success"):
        return result

    existing_version = result.get("mineru_version")
    if isinstance(existing_version, str) and existing_version.strip():
        mineru_version = existing_version.strip()
    elif mineru_version:
        result["mineru_version"] = mineru_version

    # api_version is supplementary metadata; do not treat it as mineru_version.
    if api_version:
        result["api_version"] = api_version
    if model_version:
        result["model_version"] = model_version

    if result.get("mineru_version") and isinstance(result.get("message"), str):
        version = result["mineru_version"]
        message = result["message"]
        if version not in message:
            result["message"] = f"{message} (version: {version})"

    return result
