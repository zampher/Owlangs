# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from backend.app.services.task import batch_manager


def test_create_and_add_task() -> None:
    batch_manager.clear_all_batches()
    batch = batch_manager.create_batch(label="Test batch", source_type="multi")
    batch_id = batch["batch_id"]
    batch_manager.add_task_to_batch(batch_id, "task_a")
    batch_manager.add_task_to_batch(batch_id, "task_b")
    loaded = batch_manager.get_batch(batch_id)
    assert loaded is not None
    assert loaded["task_ids"] == ["task_a", "task_b"]
    batch_manager.clear_all_batches()


def test_single_file_batch_label() -> None:
    batch_manager.clear_all_batches()
    batch = batch_manager.create_single_file_batch(
        "abc12345",
        "report.pdf",
        owner_username="alice",
    )
    assert batch["label"] == "report.pdf (abc12345)"
    assert batch["source_type"] == "single"
    assert batch_manager.get_batch(batch["batch_id"])["task_ids"] == ["abc12345"]
    batch_manager.clear_all_batches()
