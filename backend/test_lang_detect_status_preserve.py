import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from unittest.mock import MagicMock

from app.services.status.status_service import _strip_lang_detect_status_downgrade


def test_strip_removes_detect_language_progress_when_task_completed():
    tm = MagicMock()
    tm.get_task.return_value = {"status": "completed", "progress": 100}
    upd = {
        "status": "processing",
        "progress": 0,
        "message": "Detect Language: 0/61 segments (0%)",
        "message_level": "warning",
    }
    out = _strip_lang_detect_status_downgrade(tm, "t1", upd)
    assert out == {}


def test_strip_removes_processing_when_task_completed():
    tm = MagicMock()
    tm.get_task.return_value = {"status": "completed"}
    upd = {
        "status": "processing",
        "progress": 100,
        "message": "Detect Language: 5/5 segments (100%)",
    }
    out = _strip_lang_detect_status_downgrade(tm, "t1", upd)
    assert "status" not in out
    assert "progress" not in out
    assert "message" not in out


def test_strip_keeps_non_detect_fields_when_task_completed():
    tm = MagicMock()
    tm.get_task.return_value = {"status": "completed"}
    upd = {
        "status": "processing",
        "progress": 95,
        "message": "Generating DOCX...",
    }
    out = _strip_lang_detect_status_downgrade(tm, "t1", upd)
    assert "status" not in out
    assert out["progress"] == 95
    assert out["message"] == "Generating DOCX..."


def test_strip_keeps_processing_for_non_terminal_task():
    tm = MagicMock()
    tm.get_task.return_value = {"status": "processing"}
    upd = {"status": "processing", "progress": 50}
    out = _strip_lang_detect_status_downgrade(tm, "t1", upd)
    assert out.get("status") == "processing"


def test_strip_keeps_failed_from_worker_when_task_failed():
    tm = MagicMock()
    tm.get_task.return_value = {"status": "failed"}
    upd = {"status": "processing", "progress": 100}
    out = _strip_lang_detect_status_downgrade(tm, "t1", upd)
    assert "status" not in out
