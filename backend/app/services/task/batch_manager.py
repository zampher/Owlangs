# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Upload batch grouping for translation tasks.

Each batch groups one or more task_ids submitted together (or a single file).
Persisted on disk so batch metadata survives server restarts.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule

_INDEX_NAME = "batches_index.json"
_lock = threading.Lock()


def _index_path() -> Path:
    from utils.path_utils import get_system_data_dir

    root = Path(get_system_data_dir()) / "translation_batches"
    root.mkdir(parents=True, exist_ok=True)
    return root / _INDEX_NAME


def _load_index() -> Dict[str, Any]:
    path = _index_path()
    if not path.is_file():
        return {"batches": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("batches"), dict):
            return data
    except Exception as e:
        logger.warning(LogModule.SYSTEM, f"[BATCH] Failed to read index: {e}")
    return {"batches": {}}


def _save_index(data: Dict[str, Any]) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def create_batch(
    *,
    label: str,
    source_type: str = "single",
    owner_username: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an empty batch and return its record."""
    batch_id = uuid.uuid4().hex[:8]
    now = time.time()
    record: Dict[str, Any] = {
        "batch_id": batch_id,
        "label": (label or "").strip() or batch_id,
        "source_type": source_type or "single",
        "owner_username": owner_username,
        "created_at": now,
        "task_ids": [],
    }
    with _lock:
        index = _load_index()
        index["batches"][batch_id] = record
        _save_index(index)
    logger.info(
        LogModule.SYSTEM,
        f"[BATCH] Created batch_id={batch_id} label={record['label']!r} "
        f"source_type={source_type} owner={owner_username!r}",
    )
    return dict(record)


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        batch = _load_index()["batches"].get(batch_id)
    return dict(batch) if batch else None


def add_task_to_batch(batch_id: str, task_id: str) -> None:
    with _lock:
        index = _load_index()
        batch = index["batches"].get(batch_id)
        if batch is None:
            raise KeyError(f"Batch '{batch_id}' not found")
        task_ids: List[str] = list(batch.get("task_ids") or [])
        if task_id not in task_ids:
            task_ids.append(task_id)
        batch["task_ids"] = task_ids
        index["batches"][batch_id] = batch
        _save_index(index)


def remove_task_from_all_batches(task_id: str) -> None:
    with _lock:
        index = _load_index()
        changed = False
        empty_batch_ids: List[str] = []
        for batch_id, batch in list(index["batches"].items()):
            task_ids = list(batch.get("task_ids") or [])
            if task_id not in task_ids:
                continue
            remaining = [t for t in task_ids if t != task_id]
            if remaining:
                batch["task_ids"] = remaining
                index["batches"][batch_id] = batch
            else:
                empty_batch_ids.append(batch_id)
            changed = True
        for batch_id in empty_batch_ids:
            index["batches"].pop(batch_id, None)
        if changed:
            _save_index(index)


def set_batch_task_ids(batch_id: str, task_ids: List[str]) -> None:
    with _lock:
        index = _load_index()
        batch = index["batches"].get(batch_id)
        if batch is None:
            return
        batch["task_ids"] = list(task_ids)
        index["batches"][batch_id] = batch
        _save_index(index)


def task_id_in_any_batch(task_id: str) -> bool:
    with _lock:
        for batch in _load_index()["batches"].values():
            if task_id in (batch.get("task_ids") or []):
                return True
    return False


def _task_has_live_resources(task_id: str) -> bool:
    """True when task data exists in memory or on-disk stash (not batch index alone)."""
    from backend.app.services.task.task_manager import task_manager
    from backend.app.services.translation.translation_result_stash import (
        load_meta,
        stash_root,
    )

    if task_manager.get_task(task_id) is not None:
        return True
    stash_dir = stash_root() / task_id
    if not stash_dir.is_dir():
        return False
    meta = load_meta(task_id)
    if meta is None:
        return True
    from backend.app.services.translation.translation_result_stash import _has_stash_content

    return _has_stash_content(meta)


def reconcile_batches_to_task_rows(
    *,
    owner_username: Optional[str] = None,
    guest_view: bool = False,
) -> int:
    """Drop stale task_ids from batches and delete batches whose tasks are all gone.

    Never deletes a batch that was created with ``task_ids=[]`` and is still awaiting uploads.
    """
    removed_batches = 0
    with _lock:
        index = _load_index()
        changed = False
        to_delete: List[str] = []
        for batch_id, batch in list(index["batches"].items()):
            if not guest_view and owner_username is not None:
                if batch.get("owner_username") != owner_username:
                    continue
            task_ids = [str(t) for t in (batch.get("task_ids") or [])]
            if not task_ids:
                continue
            live = [t for t in task_ids if _task_has_live_resources(t)]
            if not live:
                to_delete.append(batch_id)
                continue
            if live != task_ids:
                batch["task_ids"] = live
                index["batches"][batch_id] = batch
                changed = True
        for batch_id in to_delete:
            index["batches"].pop(batch_id, None)
            removed_batches += 1
            changed = True
        if changed:
            _save_index(index)
    return removed_batches


def delete_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        index = _load_index()
        batch = index["batches"].pop(batch_id, None)
        if batch is not None:
            _save_index(index)
    return dict(batch) if batch else None


def list_batches(
    *,
    owner_username: Optional[str] = None,
    guest_view: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    with _lock:
        batches = list(_load_index()["batches"].values())
    if not guest_view and owner_username is not None:
        batches = [
            b
            for b in batches
            if b.get("owner_username") == owner_username
        ]
    batches.sort(key=lambda b: float(b.get("created_at") or 0), reverse=True)
    return [dict(b) for b in batches[: max(1, limit)]]


def create_single_file_batch(
    task_id: str,
    original_filename: str,
    owner_username: Optional[str] = None,
) -> Dict[str, Any]:
    """One file = one batch; label is ``filename (task_id)``."""
    label = f"{original_filename} ({task_id})"
    batch = create_batch(
        label=label,
        source_type="single",
        owner_username=owner_username,
    )
    add_task_to_batch(batch["batch_id"], task_id)
    return batch


def clear_all_batches() -> int:
    with _lock:
        index = _load_index()
        count = len(index.get("batches") or {})
        index["batches"] = {}
        _save_index(index)
    return count
