# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""HTTP Content-Disposition helpers (RFC 5987 for non-ASCII filenames)."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional
from urllib.parse import quote

from fastapi.responses import FileResponse, Response, StreamingResponse


def build_content_disposition_header(
    filename: str,
    disposition: str = "attachment",
) -> str:
    """Build a Content-Disposition header value safe for latin-1 HTTP headers.

    Starlette/FastAPI encode header values as latin-1. Non-ASCII filenames must
    use ``filename*`` (RFC 5987) with an ASCII ``filename`` fallback.
    """
    safe_name = (filename or "download").replace("\\", "_").replace('"', "'")
    try:
        safe_name.encode("ascii")
        return f'{disposition}; filename="{safe_name}"'
    except UnicodeEncodeError:
        ascii_fallback = "".join(
            ch if ord(ch) < 128 else "_"
            for ch in safe_name
        )
        encoded = quote(safe_name, safe="")
        return (
            f'{disposition}; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{encoded}"
        )


def apply_content_disposition_header(
    response: FileResponse | Response,
    filename: str,
    *,
    disposition: str = "attachment",
) -> None:
    """Set RFC 5987 Content-Disposition on an existing response."""
    response.headers["Content-Disposition"] = build_content_disposition_header(
        filename,
        disposition=disposition,
    )


def file_download_response(
    path: str | os.PathLike[str],
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    media_type: str | None = None,
    background: Any = None,
    filename: str | None = None,
    stat_result: os.stat_result | None = None,
    content_disposition_type: str = "attachment",
) -> FileResponse:
    """FileResponse with unified RFC 5987 Content-Disposition when filename is set."""
    merged = dict(headers or {})
    if filename is not None:
        merged["Content-Disposition"] = build_content_disposition_header(
            filename,
            disposition=content_disposition_type,
        )
    return FileResponse(
        path=path,
        status_code=status_code,
        headers=merged or None,
        media_type=media_type,
        background=background,
        filename=filename,
        stat_result=stat_result,
        content_disposition_type=content_disposition_type,
    )


def bytes_download_response(
    content: bytes,
    *,
    filename: str,
    media_type: str = "application/octet-stream",
    disposition: str = "attachment",
    headers: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    """In-memory Response with unified RFC 5987 Content-Disposition."""
    merged = dict(headers or {})
    merged["Content-Disposition"] = build_content_disposition_header(
        filename,
        disposition=disposition,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers=merged,
        status_code=status_code,
    )


def streaming_download_response(
    content: Any,
    *,
    filename: str,
    media_type: str = "application/octet-stream",
    disposition: str = "attachment",
    headers: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> StreamingResponse:
    """StreamingResponse with unified RFC 5987 Content-Disposition."""
    merged = dict(headers or {})
    merged["Content-Disposition"] = build_content_disposition_header(
        filename,
        disposition=disposition,
    )
    return StreamingResponse(
        content,
        media_type=media_type,
        headers=merged,
        status_code=status_code,
    )
