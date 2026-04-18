from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

import httpx

from backend import __version__ as CURRENT_VERSION, __version_type__ as CURRENT_VERSION_TYPE
from logger import unified_logger as logger
from logger.logger import LogModule
from utils.utils import get_httpx_proxies


LATEST_RELEASE_API = "https://api.github.com/repos/zampher/Owlangs/releases/latest"
RELEASE_NOTE_ZH_URL = "https://raw.githubusercontent.com/zampher/Owlangs/main/release_note_zh.md"
RELEASE_NOTE_EN_URL = "https://raw.githubusercontent.com/zampher/Owlangs/main/release_note_en.md"
CACHE_TTL_SECONDS = 86400  # Cache GitHub latest version for 24 hours (1 day)

# Match four-part version like 1.2.3.4 anywhere in the string
_VERSION_REGEX = re.compile(r"(\d+\.\d+\.\d+\.\d+)")

_latest_version_cache: Optional[str] = None
_latest_release_url_cache: Optional[str] = None
_latest_cache_timestamp: float = 0.0


def _parse_version_from_text(text: str) -> Optional[str]:
    """Extract first 4-part version (MAJOR.MINOR.PATCH.RELEASE) from text."""
    if not text:
        return None
    match = _VERSION_REGEX.search(text)
    if match:
        return match.group(1)
    return None


def _parse_version_tuple(version: str) -> tuple[int, int, int, int]:
    """Parse version string like '1.2.3.4' into a comparable tuple."""
    parts = version.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid version format (expected 4 parts): {version}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _is_newer_version(latest: str, current: str) -> bool:
    """Return True if latest > current in semantic order."""
    try:
        return _parse_version_tuple(latest) > _parse_version_tuple(current)
    except Exception as e:
        logger.error(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] Failed to compare versions latest={latest!r}, current={current!r}: {e}",
        )
        return False


async def _fetch_latest_release_from_github() -> Optional[Dict[str, str]]:
    """
    Fetch latest release info from GitHub Releases API.

    Returns a dict with keys:
        - version: latest version string (e.g. '1.0.0.0')
        - release_url: URL to the latest release page
    """
    global _latest_version_cache, _latest_release_url_cache, _latest_cache_timestamp

    now = time.time()
    if (
        _latest_version_cache is not None
        and (now - _latest_cache_timestamp) < CACHE_TTL_SECONDS
    ):
        return {
            "version": _latest_version_cache,
            "release_url": _latest_release_url_cache
            or "https://github.com/zampher/Owlangs/releases",
        }

    proxies = get_httpx_proxies()
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Owlangs-UpdateChecker",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, proxies=proxies) as client:
            response = await client.get(LATEST_RELEASE_API, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        logger.warning(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] Timeout when fetching latest version from GitHub: {e}",
        )
        return None
    except httpx.HTTPError as e:
        logger.error(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] HTTP error when fetching latest version from GitHub: {e}",
        )
        return None
    except Exception as e:
        logger.error(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] Unexpected error when fetching latest version from GitHub: {e}",
            exc_info=True,
        )
        return None

    tag_name = str(data.get("tag_name") or "")
    name = str(data.get("name") or "")
    html_url = str(data.get("html_url") or "").strip() or "https://github.com/zampher/Owlangs/releases"

    version = _parse_version_from_text(tag_name) or _parse_version_from_text(name)
    if not version:
        logger.warning(
            LogModule.SYSTEM,
            f"[UPDATE-CHECK] Could not parse version from GitHub release: "
            f"tag_name={tag_name!r}, name={name!r}",
        )
        return None

    _latest_version_cache = version
    _latest_release_url_cache = html_url
    _latest_cache_timestamp = now

    logger.info(
        LogModule.SYSTEM,
        f"[UPDATE-CHECK] Latest GitHub release version detected: {version} ({html_url})",
    )

    return {"version": version, "release_url": html_url}


async def _fetch_release_notes() -> Dict[str, Optional[str]]:
    """
    Fetch release note markdown from Owlangs repo (zh and en).
    Returns dict with keys release_notes_zh, release_notes_en (value None on fetch failure).
    """
    result: Dict[str, Optional[str]] = {"release_notes_zh": None, "release_notes_en": None}
    proxies = get_httpx_proxies()
    timeout = httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)
    headers = {"User-Agent": "Owlangs-UpdateChecker"}

    async def get_text(url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=timeout, proxies=proxies) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and resp.text:
                    return resp.text.strip()
        except Exception as e:
            logger.debug(
                LogModule.SYSTEM,
                f"[UPDATE-CHECK] Failed to fetch release notes from {url}: {e}",
            )
        return None

    result["release_notes_zh"] = await get_text(RELEASE_NOTE_ZH_URL)
    result["release_notes_en"] = await get_text(RELEASE_NOTE_EN_URL)
    return result


async def check_update() -> Dict[str, Any]:
    """
    Check whether a newer version is available on GitHub Releases.

    Returns a JSON-serializable dict:
        {
            "ok": true/false,
            "current_version": "...",
            "current_version_type": "...",    # optional, may be empty string
            "latest_version": "...",         # only when ok=True
            "update_available": true/false,  # only when ok=True
            "release_url": "..."             # only when ok=True
            "error": "..."                   # only when ok=False
        }
    """
    current = CURRENT_VERSION

    latest_info = await _fetch_latest_release_from_github()
    if not latest_info:
        return {
            "ok": False,
            "current_version": current,
            "current_version_type": CURRENT_VERSION_TYPE,
            "update_available": False,
            "error": "failed_to_fetch_latest_version",
        }

    latest = latest_info["version"]
    release_url = latest_info["release_url"]
    update_available = _is_newer_version(latest, current)

    out: Dict[str, Any] = {
        "ok": True,
        "current_version": current,
        "current_version_type": CURRENT_VERSION_TYPE,
        "latest_version": latest,
        "update_available": update_available,
        "release_url": release_url,
    }
    if update_available:
        notes = await _fetch_release_notes()
        out["release_notes_zh"] = notes.get("release_notes_zh")
        out["release_notes_en"] = notes.get("release_notes_en")
    return out


# Service instance
version_service = type('VersionService', (), {
    'check_update': check_update
})()


async def run_daily_version_check() -> None:
    """
    Daily version check loop.
    Runs once every 24 hours to refresh the version cache.
    Intended to be run as asyncio.create_task() from app lifespan.
    """
    while True:
        try:
            await asyncio.sleep(86400)  # 24 hours
            logger.info(LogModule.SYSTEM, "[UPDATE-CHECK] Running daily version check...")
            result = await check_update()
            if result.get("ok"):
                current = result.get("current_version")
                latest = result.get("latest_version")
                update_available = result.get("update_available")
                if update_available:
                    logger.info(
                        LogModule.SYSTEM,
                        f"[UPDATE-CHECK] Daily check: New version available: {latest} (current: {current})"
                    )
                else:
                    logger.info(
                        LogModule.SYSTEM,
                        f"[UPDATE-CHECK] Daily check: Running latest version: {current}"
                    )
            else:
                logger.warning(
                    LogModule.SYSTEM,
                    f"[UPDATE-CHECK] Daily check failed: {result.get('error')}"
                )
        except asyncio.CancelledError:
            logger.info(LogModule.SYSTEM, "[UPDATE-CHECK] Daily version check cancelled")
            return
        except Exception as e:
            logger.error(LogModule.SYSTEM, f"[UPDATE-CHECK] Daily check error: {e}", exc_info=True)

