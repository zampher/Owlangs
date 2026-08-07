# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for export workdir recovery when temp_dir / original PDF go missing."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backend.utils as _backend_utils  # noqa: E402

sys.modules["utils"] = _backend_utils

from app.services.download.download_service import (  # noqa: E402
    _ensure_task_export_workdir,
    _materialize_path_into_temp,
)


def test_ensure_workdir_recreates_missing_temp_and_restores_from_sibling(tmp_path: Path) -> None:
    convert_temp = tmp_path / "owlangs_convert_x"
    convert_temp.mkdir()
    src_pdf = convert_temp / "report.pdf"
    src_pdf.write_bytes(b"%PDF-1.4 convert")
    (convert_temp / "mineru_extracted").mkdir()
    (convert_temp / "mineru_extracted" / "dummy.txt").write_text("x", encoding="utf-8")

    gone = tmp_path / "owlangs_task_gone"
    # Intentionally do not create gone/ — simulates OS/antivirus deleting temp mid-session.
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
