# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Tests for URL-based task image refs (no base64 in API JSON)."""

from __future__ import annotations

import base64

from backend.utils.task_image_refs import (
    build_frontend_image_data_map,
    decode_data_uri,
    resolve_task_image_bytes,
    strip_segment_inline_image_data,
    task_image_url,
)


def test_task_image_url_encodes_key():
    url = task_image_url("abc123", "mobi7/Images/foo bar.jpg")
    assert url.startswith("/service/task-image/abc123?key=")
    assert " " not in url
    assert "Images" in url or "Images" in url.replace("%2F", "/")


def test_build_frontend_image_data_map_strips_data_uri():
    raw = {
        "images/a.png": {
            "data": "data:image/png;base64,aaaa",
            "mime": "image/png",
        },
        "empty": {"data": ""},
    }
    out = build_frontend_image_data_map("tid1", raw)
    assert "images/a.png" in out
    assert "data" not in out["images/a.png"]
    assert out["images/a.png"]["url"].startswith("/service/task-image/tid1?key=")
    assert out["images/a.png"]["alt"] == "a.png"
    assert "empty" not in out


def test_decode_and_resolve_roundtrip():
    payload = b"\x89PNG\r\n\x1a\nfake"
    data_uri = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    raw, mime = decode_data_uri(data_uri)
    assert raw == payload
    assert mime == "image/png"

    task_state = {
        "image_data_map": {
            "images/x.png": {"data": data_uri, "mime": "image/png"},
        }
    }
    resolved = resolve_task_image_bytes(task_state, "x.png")
    assert resolved is not None
    assert resolved[0] == payload
    assert resolved[1] == "image/png"


def test_strip_segment_inline_image_data():
    segs = [
        {"segment_index": 0, "image_data": "data:image/png;base64,xx", "placeholder_id": "p1"},
        {"segment_index": 1, "text": "hi"},
    ]
    strip_segment_inline_image_data(segs)
    assert "image_data" not in segs[0]
    assert segs[0]["placeholder_id"] == "p1"
    assert segs[1]["text"] == "hi"
