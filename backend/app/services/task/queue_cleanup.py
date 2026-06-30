# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Release translation queue resources for one task or the current viewer."""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Set

from auth.models import User
from fastapi import HTTPException
from logger import unified_logger as logger
from logger.logger import LogModule

from backend.app.services.task import batch_manager
from backend.app.services.task.task_manager import task_manager
from backend.app.services.translation.translation_result_stash import (
    clear_stash_for_viewer,
    delete_task_stash,
    list_summaries_visible_to_user,
    stash_root,
)


async def release_task_resources(task_id: str) -> None:
    """Release one task: cancel if running, drop temp dir, stash, memory, batch refs."""
    from backend.app.routes.service.app_routes_translation import translation_service  # lazy: avoid import cycle

    task_state = task_manager.get_task(task_id)
    if task_state is None:
        delete_task_stash(task_id)
        batch_manager.remove_task_from_all_batches(task_id)
        return

    if task_state.get("is_processing") and task_state.get("current_task_ref"):
        try:
            translation_service.cancel_translation(task_id)
        except HTTPException:
            pass

    temp_dir = task_state.get("temp_dir")
    if temp_dir and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(
                LogModule.ROUTE,
                f"[QUEUE-CLEANUP] Failed to cleanup temp_dir for {task_id}: {e}",
            )

    delete_task_stash(task_id)
    task_manager.cleanup_task_resources(task_id)
    batch_manager.remove_task_from_all_batches(task_id)


def prune_orphan_batches_for_viewer(user: User) -> int:
    """Remove batch entries whose task_ids no longer refer to live queue resources."""
    guest_view = not user.is_authenticated
    owner = user.username if user.is_authenticated else None
    return batch_manager.reconcile_batches_to_task_rows(
        owner_username=owner,
        guest_view=guest_view,
    )


def _collect_viewer_task_ids(user: User) -> Set[str]:
    guest_view = not user.is_authenticated
    owner = user.username if user.is_authenticated else None
    task_ids: Set[str] = set()

    for tid, st in task_manager.get_all_tasks().items():
        if guest_view or st.get("owner_username") == owner:
            task_ids.add(str(tid))

    try:
        for row in list_summaries_visible_to_user(guest_view, owner or ""):
            tid = row.get("task_id")
            if tid:
                task_ids.add(str(tid))
    except Exception as e:
        logger.warning(LogModule.ROUTE, f"[QUEUE-CLEANUP] Failed to list stash tasks: {e}")

    batches = batch_manager.list_batches(
        owner_username=owner,
        guest_view=guest_view,
        limit=500,
    )
    for batch in batches:
        for tid in batch.get("task_ids") or []:
            task_ids.add(str(tid))

    return task_ids


async def clear_viewer_queue(user: User) -> Dict[str, Any]:
    """Remove all queue tasks, stash entries, and batches visible to the viewer."""
    guest_view = not user.is_authenticated
    owner = user.username if user.is_authenticated else None
    task_ids = _collect_viewer_task_ids(user)

    errors: List[str] = []
    released = 0
    for tid in sorted(task_ids):
        try:
            await release_task_resources(tid)
            released += 1
        except Exception as e:
            errors.append(f"{tid}:{e}")
            logger.warning(LogModule.ROUTE, f"[QUEUE-CLEANUP] release failed task_id={tid}: {e}")

    stash_removed = clear_stash_for_viewer(guest_view, owner or "")

    prune_orphan_batches_for_viewer(user)

    batches = batch_manager.list_batches(
        owner_username=owner,
        guest_view=guest_view,
        limit=500,
    )
    cleared_batches = 0
    for batch in batches:
        bid = str(batch.get("batch_id") or "")
        if not bid:
            continue
        try:
            batch_manager.delete_batch(bid)
            cleared_batches += 1
        except Exception as e:
            errors.append(f"batch:{bid}:{e}")

    logger.info(
        LogModule.ROUTE,
        f"[QUEUE-CLEANUP] viewer={owner!r} guest={guest_view} released={released} "
        f"stash_swept={stash_removed} batches={cleared_batches}",
    )
    return {
        "ok": len(errors) == 0,
        "released_count": released,
        "stash_removed": stash_removed,
        "cleared_batches": cleared_batches,
        "errors": errors[:50],
    }


def task_has_queue_resources(task_id: str) -> bool:
    """True when the task still exists in memory, stash, or batch index."""
    if task_manager.get_task(task_id) is not None:
        return True
    if (stash_root() / task_id).is_dir():
        return True
    return batch_manager.task_id_in_any_batch(task_id)
