# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Typst @preview package names and versions used by typst_overlay."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

# (name, version) pairs required for overlay compilation.
TYPST_PREVIEW_PACKAGES: Tuple[Tuple[str, str], ...] = (
    ("cmarker", "0.1.8"),
    ("mitex", "0.2.6"),
)


def preview_package_dir(cache_root: Path, name: str, version: str) -> Path:
    """Return the on-disk path for one @preview package under a cache root."""
    return cache_root / "preview" / name / version


def bundled_packages_complete(cache_root: Path) -> bool:
    """True when every required @preview package exists under cache_root."""
    if not cache_root.is_dir():
        return False
    return all(
        preview_package_dir(cache_root, name, version).is_dir()
        for name, version in TYPST_PREVIEW_PACKAGES
    )


def typst_preview_import_lines() -> List[str]:
    """Typst #import lines for overlay preludes."""
    lines: List[str] = []
    for name, version in TYPST_PREVIEW_PACKAGES:
        if name == "mitex":
            lines.append(f'#import "@preview/{name}:{version}": mitex')
        else:
            lines.append(f'#import "@preview/{name}:{version}"')
    return lines
