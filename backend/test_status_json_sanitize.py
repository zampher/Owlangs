# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Status JSON must not crash when task_state holds internal caches with tuple keys."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Prefer backend.utils over app.utils (app/__init__ inserts backend/app ahead of backend).
import backend.utils as _backend_utils  # noqa: E402

sys.modules["utils"] = _backend_utils

from app.services.status.status_service import StatusService  # noqa: E402


def _make_service() -> StatusService:
    return StatusService(task_manager_instance=MagicMock())


def test_sanitize_strips_image_layout_grouping_cache_with_tuple_keys():
    svc = _make_service()
    task_state = {
        "status": "completed",
        "progress": 100,
        "message": "done",
        "_image_layout_grouping_cache": {
            ("text", "html", "image", 12345, 10): ([1, 2], {"a.png": 1}, object()),
        },
        "layout_block_bbox": {0: (1.0, 2.0, 3.0, 4.0)},
    }
    svc._sanitize_task_state_for_json(task_state, "ca5ea7de")
    payload = svc._build_slim_status_response(task_state, "ca5ea7de")
    assert "_image_layout_grouping_cache" not in payload
    # Must be encodable by the same path Starlette JSONResponse uses.
    json.dumps(payload)
    assert payload["layout_block_bbox"][0] == [1.0, 2.0, 3.0, 4.0]


def test_convert_rewrites_nested_tuple_dict_keys():
    svc = _make_service()
    nested = {
        "ok": 1,
        "inner": {
            ("a", "b"): {"x": 2.0},
        },
    }
    svc._convert_to_native_json_types(nested)
    assert ("a", "b") not in nested["inner"]
    assert nested["inner"][str(("a", "b"))]["x"] == 2.0
    json.dumps(nested)


def test_slim_status_skips_strip_keys_even_if_still_present():
    svc = _make_service()
    task_state = {
        "status": "processing",
        "_image_layout_grouping_cache": {("x",): "y"},
        "layout_document": object(),
    }
    payload = svc._build_slim_status_response(task_state, "t1")
    assert "_image_layout_grouping_cache" not in payload
    assert "layout_document" not in payload
    assert payload["status"] == "processing"


if __name__ == "__main__":
    test_sanitize_strips_image_layout_grouping_cache_with_tuple_keys()
    test_convert_rewrites_nested_tuple_dict_keys()
    test_slim_status_skips_strip_keys_even_if_still_present()
    print("ok")
