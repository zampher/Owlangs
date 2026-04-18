"""
Small MinerU layout inspection tool.

Usage (from repo root, in venv):

    python -m backend.tools.mineru_layout_inspector --dir "temp/510c33b3-50f9-4f56-86a3-48ce5a36fbd2"

It will:
  - Load `layout.json` in the given directory (if present)
  - Load `*_content_list.json` and `*_model.json` (if present)
  - Print a concise summary of:
      * Top-level keys
      * List lengths (e.g. pages, blocks)
      * Sample entries containing positions (x/y/bbox/page) and text

This is only for schema / capability investigation. It does NOT integrate
with the main translation workflow.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


POSITION_KEYS = {"x", "y", "w", "h", "width", "height", "bbox", "left", "top", "right", "bottom"}
PAGE_KEYS = {"page", "page_index", "page_no", "page_number"}
TEXT_KEYS = {"text", "content", "value", "raw_text"}


@dataclass
class SampleEntry:
    source: str  # which file
    path: str    # JSON path, e.g. pages[0].blocks[3]
    data: Dict[str, Any]


def _shorten(s: str, max_len: int = 120) -> str:
    s = s.replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _iter_objects(obj: Any, path: str = "") -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Recursively iterate over dict objects in a JSON structure.
    Yields (json_path, dict_obj).
    """
    if isinstance(obj, dict):
        yield path or "$", obj
        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else k
            yield from _iter_objects(v, child_path)
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            child_path = f"{path}[{idx}]" if path else f"[{idx}]"
            yield from _iter_objects(v, child_path)


def _has_any_key(d: Dict[str, Any], keys: Iterable[str]) -> bool:
    return any(k in d for k in keys)


def _load_json_files(base_dir: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}

    layout_path = base_dir / "layout.json"
    if layout_path.exists():
        data["layout.json"] = json.loads(layout_path.read_text(encoding="utf-8"))

    # Find *content_list.json and *model.json
    for p in base_dir.glob("*_content_list.json"):
        data[p.name] = json.loads(p.read_text(encoding="utf-8"))
    for p in base_dir.glob("*_model.json"):
        data[p.name] = json.loads(p.read_text(encoding="utf-8"))

    return data


def _summarize_top_level(name: str, obj: Any) -> None:
    print(f"\n=== File: {name} ===")
    if isinstance(obj, dict):
        keys = list(obj.keys())
        print(f"- Top-level type: dict, keys ({len(keys)}): {keys}")
        for k in keys:
            v = obj[k]
            if isinstance(v, list):
                print(f"  - {k}: list (len={len(v)})")
            else:
                print(f"  - {k}: {type(v).__name__}")
    elif isinstance(obj, list):
        print(f"- Top-level type: list (len={len(obj)})")
        if obj and isinstance(obj[0], dict):
            sample_keys = list(obj[0].keys())
            print(f"  - First item keys: {sample_keys}")
    else:
        print(f"- Top-level type: {type(obj).__name__}")


def _collect_samples(name: str, obj: Any, max_samples: int = 10) -> List[SampleEntry]:
    samples: List[SampleEntry] = []
    for json_path, d in _iter_objects(obj):
        if not isinstance(d, dict):
            continue
        if not _has_any_key(d, POSITION_KEYS | PAGE_KEYS | TEXT_KEYS):
            continue

        entry: Dict[str, Any] = {}
        for k in sorted(d.keys()):
            v = d[k]
            if isinstance(v, (str, int, float, bool)) or v is None:
                entry[k] = v
            elif isinstance(v, list):
                entry[k] = f"<list len={len(v)}>"
            elif isinstance(v, dict):
                entry[k] = f"<dict keys={list(v.keys())[:5]}>"
            else:
                entry[k] = f"<{type(v).__name__}>"

        samples.append(SampleEntry(source=name, path=json_path, data=entry))
        if len(samples) >= max_samples:
            break
    return samples


def inspect_mineru_layout(base_dir: Path) -> None:
    if not base_dir.exists():
        raise SystemExit(f"Directory not found: {base_dir}")

    json_data = _load_json_files(base_dir)
    if not json_data:
        print(f"No layout/content_list/model JSON files found in: {base_dir}")
        return

    print(f"Inspecting MinerU layout directory: {base_dir}")
    print(f"Found JSON files: {list(json_data.keys())}")

    for name, obj in json_data.items():
        _summarize_top_level(name, obj)
        samples = _collect_samples(name, obj)
        if not samples:
            print("  (No objects with obvious page/position/text keys found.)")
            continue

        print("  Sample entries with page/position/text-like fields:")
        for s in samples:
            print(f"  - Path: {s.path}")
            for k, v in s.data.items():
                if isinstance(v, str):
                    v = _shorten(v)
                print(f"      {k}: {v}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect MinerU layout.json / content_list / model JSON for page/layout/text structure."
    )
    parser.add_argument(
        "--dir",
        type=str,
        required=True,
        help="Path to extracted MinerU ZIP directory (containing layout.json, *_content_list.json, *_model.json).",
    )
    args = parser.parse_args()
    base_dir = Path(args.dir)
    inspect_mineru_layout(base_dir)


if __name__ == "__main__":
    main()


