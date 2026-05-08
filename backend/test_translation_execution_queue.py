# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for translation queue position helper (loads module without heavy app imports)."""

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _load_queue_utils():
    path = _ROOT / "app" / "services" / "translation" / "translation_queue_utils.py"
    spec = importlib.util.spec_from_file_location("translation_queue_utils", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_queue_position_orders_by_queued_at():
    mod = _load_queue_utils()
    tasks = {
        "a": {"status": "queued", "queued_at": 100.0},
        "b": {"status": "queued", "queued_at": 50.0},
        "c": {"status": "processing"},
    }
    assert mod.queue_position_for_task(tasks, "b") == 1
    assert mod.queue_position_for_task(tasks, "a") == 2
    assert mod.queue_position_for_task(tasks, "c") is None


def test_queue_position_not_queued():
    mod = _load_queue_utils()
    tasks = {"x": {"status": "completed", "queued_at": 1.0}}
    assert mod.queue_position_for_task(tasks, "x") is None


if __name__ == "__main__":
    test_queue_position_orders_by_queued_at()
    test_queue_position_not_queued()
    print("translation_queue_utils tests passed")
