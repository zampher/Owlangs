# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Lightweight test for result stash (loads module from path to avoid full package init)."""

import importlib.util
import json
import os
import tempfile
from pathlib import Path


def _load_stash_module():
    root = Path(__file__).resolve().parent
    path = root / "app" / "services" / "translation" / "translation_result_stash.py"
    spec = importlib.util.spec_from_file_location("translation_result_stash", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_meta_roundtrip_and_expiry_skip():
    mod = _load_stash_module()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OWLANGS_RESULT_STASH_RETENTION_DAYS"] = "0.001"
        orig_root = mod.stash_root

        def fake_root():
            return Path(tmp) / "stash"

        mod.stash_root = fake_root  # type: ignore[method-assign]

        task_id = "abc12345"
        src = Path(tmp) / "hello.md"
        src.write_text("x", encoding="utf-8")
        task_state = {
            "status": "completed",
            "owner_username": "alice",
            "original_filename": "paper.pdf",
            "task_end_time": 1000.0,
        }
        mod.record_generated_result(task_id, "md", str(src), task_state)
        mpath = fake_root() / task_id / "meta.json"
        assert mpath.is_file()
        meta = json.loads(mpath.read_text(encoding="utf-8"))
        assert meta["files"]["md"]["relative"].startswith("files/md/")
        p = mod.get_stashed_file_path(task_id, "md")
        assert p and Path(p).is_file()
        # Force expiry
        meta["expires_at"] = 1.0
        mpath.write_text(json.dumps(meta), encoding="utf-8")
        assert mod.get_stashed_file_path(task_id, "md") is None
        n = mod.cleanup_expired()
        assert n == 1
        mod.stash_root = orig_root  # type: ignore[method-assign]


if __name__ == "__main__":
    test_meta_roundtrip_and_expiry_skip()
    print("translation_result_stash tests passed")
