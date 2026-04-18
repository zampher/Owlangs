"""
Scan repository for ReportLab references.

This script searches for the keywords "reportlab" and "ReportLab"
in all .md / .dart / .py / .arb files under the repo root, and prints
matching lines to help inspection/cleanup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Tuple


def _get_repo_root() -> Path:
  """
  Resolve repository root based on this file location.

  Assumes this file lives under backend/tools/.
  """
  here = Path(__file__).resolve()
  # .../backend/tools/scan_pymupdf_references.py -> repo root is parent of backend
  return here.parents[2]


ROOT = _get_repo_root()

# File suffixes to inspect
TARGET_SUFFIXES = {".md", ".dart", ".py", ".arb"}

# Keywords to search (case-sensitive)
KEYWORDS = ("reportlab", "ReportLab")


def _iter_lines(path: Path) -> Iterable[Tuple[int, str]]:
  """Yield (line_number, line_text) for the given file."""
  try:
    text = path.read_text(encoding="utf-8", errors="ignore")
  except Exception as exc:  # pragma: no cover - diagnostics only
    print(f"[WARN] Cannot read {path}: {exc}")
    return

  for idx, line in enumerate(text.splitlines(), start=1):
    yield idx, line


def _scan_file(path: Path) -> None:
  """Scan a single file and print lines containing target keywords."""
  matches: list[Tuple[int, str]] = []
  for lineno, line in _iter_lines(path):
    if any(k in line for k in KEYWORDS):
      matches.append((lineno, line.rstrip("\n")))

  if not matches:
    return

  print(f"\n=== {path} ===")
  for lineno, content in matches:
    snippet = content.strip()
    if len(snippet) > 160:
      snippet = snippet[:157] + "..."
    print(f"{lineno:5d}: {snippet}")


def main() -> None:
  print(f"[INFO] Scanning for ReportLab references under: {ROOT}")
  for root, dirs, files in os.walk(ROOT):
    # Skip virtual envs, build artifacts, and 3rdParty binaries
    dirs[:] = [
      d for d in dirs
      if d not in {".venv", "venv", "build", "dist", "3rdParty", ".git", ".idea", ".vscode"}
    ]
    for fname in files:
      path = Path(root) / fname
      if path.suffix.lower() in TARGET_SUFFIXES:
        _scan_file(path)


if __name__ == "__main__":
  main()

