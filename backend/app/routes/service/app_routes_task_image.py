# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""On-demand task image serving (URL refs instead of base64 in JSON)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path as FastApiPath, Query as FastApiQuery
from fastapi.responses import Response

from backend.app.services.task import task_manager
from backend.utils.task_image_refs import resolve_task_image_bytes

router = APIRouter()


@router.get(
    "/task-image/{task_id}",
    summary="Get one task image by key",
    description=(
        "Serve a single image from the task's image_data_map by key. "
        "Used so preview APIs can return lightweight `{url, alt}` refs "
        "instead of embedding base64 data URIs in JSON."
    ),
    responses={
        200: {
            "description": "Image bytes",
            "content": {
                "image/png": {},
                "image/jpeg": {},
                "image/gif": {},
                "image/webp": {},
                "application/octet-stream": {},
            },
        },
        404: {"description": "Task or image key not found"},
    },
)
async def service_task_image_route(
    task_id: str = FastApiPath(..., description="Task ID", examples=["a1b2c3d4"]),
    key: str = FastApiQuery(..., description="Image key / placeholder id / path"),
):
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

    resolved = resolve_task_image_bytes(task_state, key)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail=f"Image key not found for task '{task_id}'.",
        )
    raw, mime = resolved
    return Response(
        content=raw,
        media_type=mime or "application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=300",
        },
    )
