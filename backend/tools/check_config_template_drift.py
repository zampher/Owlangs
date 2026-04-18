#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Check drift between configs/*.json and configs/*.json.template.

Goal:
- Ensure templates are not missing fields that exist in current json files.
  Missing template fields mean fresh install / upgrade-merge may not get new structure.

Rules:
- Compare recursively by key paths (dict keys).
- Ignore values; focus on presence/type shape (dict vs non-dict).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _iter_key_paths(obj: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            yield key
            yield from _iter_key_paths(v, key)


def _iter_dict_paths(obj: Any, prefix: str = "") -> Iterable[str]:
    """Paths whose value is a dict (so we can detect dict/non-dict mismatches)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                yield key
            yield from _iter_dict_paths(v, key)


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except Exception:
        return str(path)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    cfg_dir = repo_root / "configs"
    if not cfg_dir.exists():
        print(f"[ERROR] configs directory not found: {cfg_dir}")
        return 2

    json_files = sorted([p for p in cfg_dir.glob("*.json") if not p.name.endswith(".template")])
    any_issue = False

    for jf in json_files:
        tf = cfg_dir / f"{jf.name}.template"
        if not tf.exists():
            # Some runtime files intentionally have no template (e.g. ai_platform_status.json)
            print(f"[SKIP] No template for {_rel(jf, repo_root)}")
            continue

        try:
            j = _load_json(jf)
            t = _load_json(tf)
        except Exception as e:
            print(f"[ERROR] Failed to parse {_rel(jf, repo_root)} or its template: {e}")
            any_issue = True
            continue

        j_paths = set(_iter_key_paths(j))
        t_paths = set(_iter_key_paths(t))
        missing_in_template = sorted(j_paths - t_paths)
        extra_in_template = sorted(t_paths - j_paths)

        # dict/non-dict mismatches: if a path is dict in one but not the other
        j_dict = set(_iter_dict_paths(j))
        t_dict = set(_iter_dict_paths(t))
        dict_mismatch = sorted((j_dict ^ t_dict) & (j_paths & t_paths))

        # Special-case: local_users.json contains dynamic user keys under users.<username>.
        # Template should define the user object shape, but not enumerate all runtime users.
        if jf.name == "local_users.json":
            def _is_dynamic_user_path(p: str) -> bool:
                parts = p.split(".")
                return len(parts) >= 2 and parts[0] == "users" and parts[1] not in ("admin", "app_admin", "user1")

            missing_in_template = [p for p in missing_in_template if not _is_dynamic_user_path(p)]
            extra_in_template = [p for p in extra_in_template if not _is_dynamic_user_path(p)]

        if missing_in_template or dict_mismatch:
            any_issue = True
            print(f"\n[DRIFT] {_rel(jf, repo_root)}  vs  {_rel(tf, repo_root)}")
            if missing_in_template:
                print(f"- Missing in template ({len(missing_in_template)}):")
                for p in missing_in_template[:200]:
                    print(f"  - {p}")
                if len(missing_in_template) > 200:
                    print(f"  ... and {len(missing_in_template) - 200} more")
            if dict_mismatch:
                print(f"- Dict/non-dict mismatch ({len(dict_mismatch)}):")
                for p in dict_mismatch[:200]:
                    print(f"  - {p}")
                if len(dict_mismatch) > 200:
                    print(f"  ... and {len(dict_mismatch) - 200} more")

        # Optional: show extra keys in template (informational, usually OK)
        if extra_in_template:
            print(f"\n[INFO] {_rel(jf, repo_root)} template has extra keys: {len(extra_in_template)}")

    if any_issue:
        print("\n[RESULT] Drift detected. Please update templates to include missing fields.")
        return 1

    print("\n[RESULT] OK. No missing fields in templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

