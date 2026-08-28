# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for export workdir recovery when temp_dir / original PDF go missing."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backend.utils as _backend_utils  # noqa: E402

sys.modules["utils"] = _backend_utils

from app.services.download.download_service import (  # noqa: E402
    TASK_STATE_DURABLE_ORIGINAL_KEY,
    _ensure_task_export_workdir,
    _materialize_path_into_temp,
    persist_original_pdf_durable,
)


def test_ensure_workdir_recreates_missing_temp_and_restores_from_sibling(
    tmp_path: Path,
) -> None:
    convert_temp = tmp_path / "owlangs_convert_x"
    convert_temp.mkdir()
    src_pdf = convert_temp / "report.pdf"
    src_pdf.write_bytes(b"%PDF-1.4 convert")
    (convert_temp / "mineru_extracted").mkdir()
    (convert_temp / "mineru_extracted" / "dummy.txt").write_text(
        "x", encoding="utf-8"
    )

    gone = tmp_path / "owlangs_task_gone"
    # Intentionally do not create gone/ — simulates OS deleting temp mid-session.
    task_state = {
        "temp_dir": str(gone),
        "original_filename": "report.pdf",
        "original_file_path": str(gone / "report.pdf"),
        "mineru_extract_dir": str(convert_temp / "mineru_extracted"),
    }

    workdir = _ensure_task_export_workdir(task_state, "abcd1234")
    assert workdir.is_dir()
    assert (workdir / "output").is_dir()
    restored = Path(task_state["original_file_path"])
    assert restored.is_file()
    assert restored.read_bytes() == b"%PDF-1.4 convert"


def test_ensure_workdir_restores_from_durable_when_all_temps_gone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Customer case: both translate and convert TEMP dirs wiped; durable survives."""
    durable_root = tmp_path / "programdata_cache"
    durable_root.mkdir()

    def _fake_cache_dir(task_id: str) -> Path:
        d = durable_root / str(task_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(
        "backend.config_manager.ConfigManager.get_task_cache_dir",
        staticmethod(_fake_cache_dir),
    )

    gone_task = tmp_path / "owlangs_362f4a29_gone"

    durable_pdf = _fake_cache_dir("362f4a29") / "TestPDF001.pdf"
    durable_pdf.write_bytes(b"%PDF-1.4 durable")

    task_state = {
        "temp_dir": str(gone_task),
        "original_filename": "TestPDF001.pdf",
        "original_file_path": str(gone_task / "TestPDF001.pdf"),
        "_convert_original_file_backup": str(
            gone_task / "_convert_source_TestPDF001.pdf"
        ),
        "convert_task_id": "f61106cb",
        TASK_STATE_DURABLE_ORIGINAL_KEY: str(durable_pdf),
        "mineru_zip_path": None,
        "mineru_extract_dir": None,
        "paddle_zip_path": None,
    }

    workdir = _ensure_task_export_workdir(task_state, "362f4a29")
    assert workdir.is_dir()
    restored = Path(task_state["original_file_path"])
    assert restored.is_file()
    assert restored.read_bytes() == b"%PDF-1.4 durable"
    assert restored.parent == workdir


def test_persist_original_pdf_durable_writes_outside_temp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    durable_root = tmp_path / "cache"
    durable_root.mkdir()

    def _fake_cache_dir(task_id: str) -> Path:
        d = durable_root / str(task_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(
        "backend.config_manager.ConfigManager.get_task_cache_dir",
        staticmethod(_fake_cache_dir),
    )

    temp = tmp_path / "temp"
    temp.mkdir()
    src = temp / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 src")
    task_state: dict = {}
    dest = persist_original_pdf_durable(task_state, "tid1", src)
    assert dest is not None and dest.is_file()
    assert dest.read_bytes() == b"%PDF-1.4 src"
    assert task_state[TASK_STATE_DURABLE_ORIGINAL_KEY] == str(dest)


def test_materialize_copies_external_dir_into_temp(tmp_path: Path) -> None:
    external = tmp_path / "external_mineru"
    external.mkdir()
    (external / "a.bin").write_bytes(b"zip")
    own_temp = tmp_path / "owlangs_own"
    own_temp.mkdir()
    task_state = {"mineru_extract_dir": str(external)}
    _materialize_path_into_temp(task_state, "t1", "mineru_extract_dir", str(own_temp))
    new_path = Path(task_state["mineru_extract_dir"])
    assert new_path.is_dir()
    assert new_path.parent == own_temp
    assert (new_path / "a.bin").read_bytes() == b"zip"
