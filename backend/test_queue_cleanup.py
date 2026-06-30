# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _load_module(name: str, rel_path: str):
    path = _BACKEND / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


batch_manager = _load_module(
    "owlangs_batch_manager",
    "app/services/task/batch_manager.py",
)
stash = _load_module(
    "owlangs_translation_result_stash",
    "app/services/translation/translation_result_stash.py",
)


@pytest.fixture(autouse=True)
def _isolate_stash_and_batches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stash_dir = tmp_path / "stash"
    batch_dir = tmp_path / "batches"
    stash_dir.mkdir()
    batch_dir.mkdir()
    monkeypatch.setattr(stash, "stash_root", lambda: stash_dir)
    monkeypatch.setattr(
        batch_manager,
        "_index_path",
        lambda: batch_dir / "batches_index.json",
    )
    batch_manager.clear_all_batches()
    yield
    batch_manager.clear_all_batches()


def _write_shell_stash(task_id: str, *, owner: str = "alice") -> None:
    task_dir = stash.stash_root() / task_id
    task_dir.mkdir(parents=True)
    meta = {
        "task_id": task_id,
        "owner_username": owner,
        "original_filename": "",
        "files": {},
    }
    with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)


def _write_valid_stash(task_id: str, *, owner: str = "alice", filename: str = "doc.pdf") -> None:
    task_dir = stash.stash_root() / task_id
    task_dir.mkdir(parents=True)
    meta = {
        "task_id": task_id,
        "owner_username": owner,
        "original_filename": filename,
        "files": {"md": {"relative": "files/md/output.md", "saved_at": 1.0, "bytes": 10}},
    }
    with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)


def test_list_summaries_removes_empty_shell_stash() -> None:
    _write_shell_stash("shell1234")
    rows = stash.list_summaries_visible_to_user(is_guest=False, username="alice")
    assert rows == []
    assert not (stash.stash_root() / "shell1234").exists()


def test_empty_upload_batch_is_not_deleted_on_reconcile() -> None:
    batch = batch_manager.create_batch(label="awaiting upload", owner_username="alice")
    removed = batch_manager.reconcile_batches_to_task_rows(
        owner_username="alice",
        guest_view=False,
    )
    assert removed == 0
    assert batch_manager.get_batch(batch["batch_id"]) is not None


def test_reconcile_drops_stale_task_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = batch_manager.create_batch(label="mixed", owner_username="alice")
    batch_manager.add_task_to_batch(batch["batch_id"], "alive01")
    batch_manager.add_task_to_batch(batch["batch_id"], "gone001")
    _write_valid_stash("alive01")
    monkeypatch.setattr(batch_manager, "_task_has_live_resources", lambda tid: tid == "alive01")
    removed = batch_manager.reconcile_batches_to_task_rows(
        owner_username="alice",
        guest_view=False,
    )
    assert removed == 0
    loaded = batch_manager.get_batch(batch["batch_id"])
    assert loaded is not None
    assert loaded["task_ids"] == ["alive01"]


def test_reconcile_deletes_batch_when_all_tasks_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = batch_manager.create_batch(label="empty", owner_username="alice")
    batch_manager.add_task_to_batch(batch["batch_id"], "gone001")
    monkeypatch.setattr(batch_manager, "_task_has_live_resources", lambda _tid: False)
    removed = batch_manager.reconcile_batches_to_task_rows(
        owner_username="alice",
        guest_view=False,
    )
    assert removed == 1
    assert batch_manager.get_batch(batch["batch_id"]) is None


def test_remove_last_task_deletes_batch() -> None:
    batch = batch_manager.create_batch(label="solo", owner_username="alice")
    batch_manager.add_task_to_batch(batch["batch_id"], "only001")
    batch_manager.remove_task_from_all_batches("only001")
    assert batch_manager.get_batch(batch["batch_id"]) is None
