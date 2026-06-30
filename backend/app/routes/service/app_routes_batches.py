# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Upload batch routes: list, create, delete, and batch-scoped download.
"""

from __future__ import annotations

from typing import Any, Dict, List

from auth.models import User
from auth.routes import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.routes.service.app_routes_download import (
    BatchDownloadRequest,
    service_batch_download_route,
)
from backend.app.services.task import batch_manager
from backend.app.services.task.queue_cleanup import release_task_resources
from backend.app.services.task.task_manager import task_manager
from backend.app.services.translation.translation_result_stash import (
    list_summaries_visible_to_user,
)
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()


class CreateBatchRequest(BaseModel):
    label: str = Field(..., description="User-visible batch label / remark")
    source_type: str = Field(
        default="multi",
        description="single | folder | zip | multi",
    )


def _task_row_from_state(
    tid: str,
    st: Dict[str, Any],
    *,
    in_memory: bool = True,
) -> Dict[str, Any]:
    qa = float(st.get("queued_at") or 0)
    ta = float(st.get("task_start_time") or 0)
    te = float(st.get("task_end_time") or 0)
    row: Dict[str, Any] = {
        "task_id": tid,
        "status": st.get("status"),
        "message": st.get("message"),
        "message_level": st.get("message_level", 0),
        "progress": st.get("progress"),
        "error": st.get("error"),
        "original_filename": st.get("original_filename"),
        "original_relative_path": st.get("original_relative_path"),
        "execution_mode": st.get("execution_mode"),
        "is_processing": st.get("is_processing"),
        "download_ready": st.get("download_ready"),
        "task_start_time": st.get("task_start_time"),
        "queued_at": st.get("queued_at"),
        "owner_username": st.get("owner_username"),
        "in_memory": in_memory,
        "convert_only": st.get("convert_only", False),
        "is_format_conversion": st.get("convert_only", False)
        or st.get("is_format_conversion", False),
        "started_at": qa if qa > 0 else ta,
        "completed_at": te,
        "batch_id": st.get("batch_id"),
    }
    downloads = st.get("downloads")
    if isinstance(downloads, dict) and downloads:
        row["downloads"] = downloads
    return row


def _task_row_from_stash(meta: Dict[str, Any]) -> Dict[str, Any]:
    tid = str(meta.get("task_id") or "")
    stashed_types = meta.get("stashed_file_types") or []
    downloads: Dict[str, str] = {}
    if isinstance(stashed_types, list):
        for ft in stashed_types:
            if isinstance(ft, str) and ft:
                downloads[ft] = f"/service/download/{tid}/{ft}"
    return {
        "task_id": tid,
        "status": meta.get("status") or "completed",
        "message": meta.get("message"),
        "progress": 100 if meta.get("status") == "completed" else meta.get("progress"),
        "error": meta.get("error"),
        "original_filename": meta.get("original_filename"),
        "original_relative_path": meta.get("original_relative_path"),
        "execution_mode": meta.get("execution_mode"),
        "owner_username": meta.get("owner_username"),
        "in_memory": False,
        "convert_only": bool(meta.get("is_format_conversion")),
        "is_format_conversion": bool(meta.get("is_format_conversion")),
        "started_at": meta.get("started_at"),
        "completed_at": meta.get("completed_at"),
        "stashed_file_types": stashed_types,
        "downloads": downloads,
        "batch_id": meta.get("batch_id"),
    }


def _collect_visible_task_rows(
    user: User,
    *,
    limit: int = 500,
) -> Dict[str, Dict[str, Any]]:
    guest_view = not user.is_authenticated
    rows: Dict[str, Dict[str, Any]] = {}
    for tid, st in task_manager.get_all_tasks().items():
        if not guest_view and st.get("owner_username") != user.username:
            continue
        rows[tid] = _task_row_from_state(tid, st, in_memory=True)
    memory_ids = set(rows.keys())
    try:
        for meta in list_summaries_visible_to_user(guest_view, user.username):
            tid = meta.get("task_id")
            if tid and tid not in memory_ids:
                rows[str(tid)] = _task_row_from_stash(meta)
    except Exception as e:
        logger.warning(LogModule.ROUTE, f"[BATCH] Failed to merge stash tasks: {e}")
    if len(rows) > limit:
        sorted_rows = sorted(
            rows.values(),
            key=lambda r: float(r.get("started_at") or r.get("task_start_time") or 0),
            reverse=True,
        )[:limit]
        rows = {str(r["task_id"]): r for r in sorted_rows if r.get("task_id")}
    return rows


def _batch_summary(
    batch: Dict[str, Any],
    task_rows: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    task_ids = list(batch.get("task_ids") or [])
    tasks: List[Dict[str, Any]] = []
    completed = 0
    failed = 0
    for tid in task_ids:
        row = task_rows.get(str(tid))
        if row is None:
            continue
        tasks.append(row)
        status = str(row.get("status") or "").lower()
        if status == "completed":
            completed += 1
        elif status in ("failed", "cancelled"):
            failed += 1
    return {
        "batch_id": batch.get("batch_id"),
        "label": batch.get("label"),
        "source_type": batch.get("source_type"),
        "created_at": batch.get("created_at"),
        "owner_username": batch.get("owner_username"),
        "task_count": len(tasks),
        "completed_count": completed,
        "failed_count": failed,
        "task_ids": task_ids,
        "tasks": tasks,
    }


@router.post(
    "/batches",
    summary="Create an upload batch",
)
async def create_upload_batch(
    body: CreateBatchRequest,
    user: User = Depends(get_current_user),
):
    owner = user.username if user.is_authenticated else None
    batch = batch_manager.create_batch(
        label=body.label.strip(),
        source_type=body.source_type,
        owner_username=owner,
    )
    return JSONResponse(content={"success": True, "batch": batch})


@router.get(
    "/batches",
    summary="List upload batches with nested tasks and ungrouped legacy tasks",
)
async def list_upload_batches(
    limit: int = 100,
    user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 500))
    guest_view = not user.is_authenticated
    owner = user.username if user.is_authenticated else None
    task_rows = _collect_visible_task_rows(user, limit=limit * 20)
    batches_raw = batch_manager.list_batches(
        owner_username=owner,
        guest_view=guest_view,
        limit=limit,
    )
    batched_task_ids: set[str] = set()
    batches: List[Dict[str, Any]] = []
    for batch in batches_raw:
        summary = _batch_summary(batch, task_rows)
        batches.append(summary)
        for tid in batch.get("task_ids") or []:
            batched_task_ids.add(str(tid))
    ungrouped: List[Dict[str, Any]] = []
    for tid, row in task_rows.items():
        if tid in batched_task_ids:
            continue
        if row.get("batch_id"):
            continue
        ungrouped.append(row)
    ungrouped.sort(
        key=lambda r: float(r.get("started_at") or 0),
        reverse=True,
    )
    return JSONResponse(
        content={
            "batches": batches,
            "ungrouped_tasks": ungrouped,
            "limit": limit,
        }
    )


@router.delete(
    "/batches/{batch_id}",
    summary="Delete batch and release all associated tasks",
)
async def delete_upload_batch(
    batch_id: str,
    user: User = Depends(get_current_user),
):
    batch = batch_manager.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    if user.is_authenticated and batch.get("owner_username") not in (
        None,
        user.username,
    ):
        raise HTTPException(status_code=403, detail="Not allowed to delete this batch.")

    task_ids = list(batch.get("task_ids") or [])
    released: List[str] = []
    errors: List[str] = []
    for tid in task_ids:
        try:
            await release_task_resources(str(tid))
            released.append(str(tid))
        except Exception as e:
            errors.append(f"{tid}: {e}")

    batch_manager.delete_batch(batch_id)
    return JSONResponse(
        content={
            "success": len(errors) == 0,
            "batch_id": batch_id,
            "released_task_ids": released,
            "errors": errors,
        }
    )


@router.post(
    "/batches/{batch_id}/download",
    summary="Download completed tasks in a batch as ZIP (skips failed/incomplete)",
)
async def download_upload_batch(
    batch_id: str,
    body: BatchDownloadRequest,
    user: User = Depends(get_current_user),
):
    batch = batch_manager.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    if user.is_authenticated and batch.get("owner_username") not in (
        None,
        user.username,
    ):
        raise HTTPException(status_code=403, detail="Not allowed to download this batch.")

    task_rows = _collect_visible_task_rows(user)
    downloadable: List[str] = []
    for tid in batch.get("task_ids") or []:
        row = task_rows.get(str(tid))
        if row is None:
            continue
        status = str(row.get("status") or "").lower()
        if status != "completed":
            continue
        downloadable.append(str(tid))

    if not downloadable:
        raise HTTPException(
            status_code=400,
            detail="No completed downloadable tasks in this batch.",
        )

    download_body = BatchDownloadRequest(
        task_ids=downloadable,
        file_type=body.file_type,
    )
    return await service_batch_download_route(download_body)
