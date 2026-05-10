# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
On-disk retention of generated translation **outputs** only (no workflow / segments).

Files are copied when the user successfully triggers a download while the task is still
in memory. Expired directories are removed by periodic cleanup.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule

_ENV_RETENTION_DAYS = "OWLANGS_RESULT_STASH_RETENTION_DAYS"

_META_NAME = "meta.json"
_FILES_SUBDIR = "files"


def _retention_seconds() -> float:
    raw = os.environ.get(_ENV_RETENTION_DAYS, "7").strip()
    try:
        days = float(raw)
    except ValueError:
        logger.warning(
            LogModule.SYSTEM,
            f"[RESULT-STASH] Invalid {_ENV_RETENTION_DAYS}={raw!r}, using 7 days",
        )
        days = 7.0
    days = max(0.5, min(days, 365.0))
    return days * 86400.0


def stash_root() -> Path:
    """Parent directory: ``<data_dir>/translation_result_stash``."""
    from utils.path_utils import get_system_data_dir

    return Path(get_system_data_dir()) / "translation_result_stash"


def _task_dir(task_id: str) -> Path:
    return stash_root() / task_id


def _meta_path(task_id: str) -> Path:
    return _task_dir(task_id) / _META_NAME


def load_meta(task_id: str) -> Optional[Dict[str, Any]]:
    p = _meta_path(task_id)
    if not p.is_file():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(LogModule.SYSTEM, f"[RESULT-STASH] Failed to read meta for {task_id}: {e}")
        return None


def record_generated_result(
    task_id: str,
    file_type: str,
    source_path: str,
    task_state: Dict[str, Any],
) -> None:
    """
    Copy a generated result file into the stash tree and update meta.json.

    Only runs for ``status == completed`` and existing regular files.
    """
    if task_state.get("status") != "completed":
        return
    if not source_path or not os.path.isfile(source_path):
        logger.debug(
            LogModule.SYSTEM,
            f"[RESULT-STASH] Skip stash task_id={task_id} file_type={file_type}: invalid path {source_path!r}",
        )
        return

    try:
        root = stash_root()
        root.mkdir(parents=True, exist_ok=True)
        tdir = _task_dir(task_id)
        files_root = tdir / _FILES_SUBDIR / file_type
        files_root.mkdir(parents=True, exist_ok=True)

        ext = Path(source_path).suffix or ""
        dest_name = f"output{ext}"
        dest_path = files_root / dest_name

        shutil.copy2(source_path, dest_path)

        now = time.time()
        retention = _retention_seconds()
        meta = load_meta(task_id) or {}
        meta.setdefault("task_id", task_id)
        meta.setdefault("owner_username", task_state.get("owner_username"))
        meta.setdefault("original_filename", task_state.get("original_filename"))
        _qa = float(task_state.get("queued_at") or 0)
        _ta = float(task_state.get("task_start_time") or 0)
        meta.setdefault("started_at", _qa if _qa > 0 else _ta)
        _ts_segs = task_state.get("translation_segments")
        if isinstance(_ts_segs, dict):
            _md = _ts_segs.get("metadata") or {}
            if isinstance(_md, dict) and _md.get("workflow_type"):
                meta.setdefault("workflow_type", _md.get("workflow_type"))
        if not meta.get("workflow_type") and task_state.get("workflow_type"):
            meta.setdefault("workflow_type", task_state.get("workflow_type"))
        meta.setdefault("completed_at", task_state.get("task_end_time") or now)
        meta["stashed_at"] = meta.get("stashed_at") or now
        if "expires_at" not in meta:
            meta["expires_at"] = now + retention
        files_map = meta.get("files")
        if not isinstance(files_map, dict):
            files_map = {}
        rel = f"{_FILES_SUBDIR}/{file_type}/{dest_name}"
        files_map[file_type] = {
            "relative": rel,
            "saved_at": now,
            "bytes": dest_path.stat().st_size,
        }
        meta["files"] = files_map

        with open(_meta_path(task_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        logger.info(
            LogModule.SYSTEM,
            f"[RESULT-STASH] Stored task_id={task_id} file_type={file_type} bytes={files_map[file_type]['bytes']}",
        )
    except Exception as e:
        logger.warning(
            LogModule.SYSTEM,
            f"[RESULT-STASH] Failed to stash task_id={task_id} file_type={file_type}: {e}",
            exc_info=True,
        )


def get_stashed_file_path(task_id: str, file_type: str) -> Optional[str]:
    """Absolute path to a stashed file, or None."""
    meta = load_meta(task_id)
    if not meta:
        return None
    exp = float(meta.get("expires_at") or 0)
    if exp and time.time() > exp:
        return None
    files_map = meta.get("files") or {}
    info = files_map.get(file_type)
    if not isinstance(info, dict):
        return None
    rel = info.get("relative")
    if not rel:
        return None
    p = _task_dir(task_id) / rel
    path_str = str(p)
    if os.path.isfile(path_str):
        return path_str
    return None


def delete_task_stash(task_id: str) -> bool:
    """Remove stash directory for a task (e.g. on explicit release)."""
    d = _task_dir(task_id)
    if not d.is_dir():
        return False
    try:
        shutil.rmtree(d)
        logger.info(LogModule.SYSTEM, f"[RESULT-STASH] Removed stash dir for task_id={task_id}")
        return True
    except Exception as e:
        logger.warning(LogModule.SYSTEM, f"[RESULT-STASH] Failed to remove stash for {task_id}: {e}")
        return False


def list_summaries_visible_to_user(is_guest: bool, username: str) -> List[Dict[str, Any]]:
    """
    Return one summary dict per stashed task (disk-only), filtered like ``GET /tasks``.

    Guest sessions see all stash records; authenticated users only their ``owner_username``.
    """
    root = stash_root()
    if not root.is_dir():
        return []

    out: List[Dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        task_id = child.name
        meta = load_meta(task_id)
        if not meta:
            continue
        exp = float(meta.get("expires_at") or 0)
        if exp and time.time() > exp:
            continue
        owner = meta.get("owner_username")
        if not is_guest:
            if owner != username:
                continue
        files_map = meta.get("files") or {}
        fts = list(files_map.keys()) if isinstance(files_map, dict) else []
        completed_at = float(meta.get("completed_at") or meta.get("stashed_at") or 0)
        started_hint = float(meta.get("started_at") or meta.get("task_start_time") or 0)
        out.append(
            {
                "task_id": task_id,
                "status": "results_stashed",
                "message": "Translated outputs cached on disk (see downloads until expiry).",
                "progress": 100,
                "original_filename": meta.get("original_filename"),
                "execution_mode": None,
                "is_processing": False,
                "download_ready": True,
                "task_start_time": completed_at,
                "queued_at": None,
                "queue_position": None,
                "owner_username": owner,
                "expires_at": exp,
                "stashed_file_types": fts,
                "in_memory": False,
                "started_at": started_hint if started_hint > 0 else 0.0,
                "completed_at": completed_at,
            }
        )
    out.sort(key=lambda x: float(x.get("task_start_time") or 0.0), reverse=True)
    return out


def cleanup_expired() -> int:
    """Delete stash directories whose ``expires_at`` is in the past. Returns removal count."""
    root = stash_root()
    if not root.is_dir():
        return 0
    now = time.time()
    removed = 0
    for child in list(root.iterdir()):
        if not child.is_dir():
            continue
        meta_path = child / _META_NAME
        if not meta_path.is_file():
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            exp = float(meta.get("expires_at") or 0)
            if exp and now > exp:
                shutil.rmtree(child)
                removed += 1
                logger.info(LogModule.SYSTEM, f"[RESULT-STASH] Expired cleanup: removed {child.name}")
        except Exception as e:
            logger.warning(LogModule.SYSTEM, f"[RESULT-STASH] Cleanup skip {child.name}: {e}")
    return removed
