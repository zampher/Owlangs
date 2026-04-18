# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
AI platform connectivity test status persistence.
Backend is the single source of truth; frontend reads status from GET /auth/ai-platform-status.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.logger import unified_logger as logger
from backend.logger.logger import LogModule

STATUS_FILENAME = "ai_platform_status.json"


def _status_path() -> Path:
    from utils.path_utils import get_config_file_path
    return get_config_file_path(STATUS_FILENAME)


def load_status() -> Dict[str, Any]:
    """Load persisted AI platform status from disk."""
    path = _status_path()
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "platforms" in data:
                    return data
                return {"platforms": {}}
        return {"platforms": {}}
    except Exception as e:
        logger.warning(LogModule.CONFIG, f"[AI_PLATFORM_STATUS] Failed to load {path}: {e}")
        return {"platforms": {}}


def save_status(data: Dict[str, Any]) -> bool:
    """Persist AI platform status to disk."""
    path = _status_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(LogModule.CONFIG, f"[AI_PLATFORM_STATUS] Failed to save {path}: {e}")
        return False


def update_platform_status(
    platform_type: str,
    is_api_available: bool,
    last_test_error: Optional[str] = None,
) -> bool:
    """Update and persist status for one platform. Called after each test (manual or scheduled)."""
    if not platform_type:
        return False
    key = (platform_type or "").strip().lower()
    data = load_status()
    if "platforms" not in data:
        data["platforms"] = {}
    data["platforms"][key] = {
        "isApiAvailable": is_api_available,
        "lastTestError": last_test_error,
        "lastTestedAt": datetime.now(tz=timezone.utc).isoformat(),
    }
    ok = save_status(data)
    if ok:
        logger.debug(
            LogModule.AUTH,
            f"[AI_PLATFORM_STATUS] Updated {key}: isApiAvailable={is_api_available}",
        )
    return ok


def get_status() -> Dict[str, Any]:
    """Return current status (platforms map). For GET /auth/ai-platform-status."""
    return load_status()
