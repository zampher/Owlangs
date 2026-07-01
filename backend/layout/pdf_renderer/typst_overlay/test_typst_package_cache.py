# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

from layout.pdf_renderer.typst_overlay import compiler as typst_compiler
from layout.pdf_renderer.typst_overlay.typst_packages import (
    TYPST_PREVIEW_PACKAGES,
    bundled_packages_complete,
    preview_package_dir,
)


def test_bundled_packages_complete_requires_all_preview_packages(tmp_path: Path) -> None:
    cache = tmp_path / "packages"
    name, version = TYPST_PREVIEW_PACKAGES[0]
    preview_package_dir(cache, name, version).mkdir(parents=True)
    assert bundled_packages_complete(cache) is False

    for pkg_name, pkg_version in TYPST_PREVIEW_PACKAGES[1:]:
        preview_package_dir(cache, pkg_name, pkg_version).mkdir(parents=True)
    assert bundled_packages_complete(cache) is True


def test_resolve_typst_package_cache_path_uses_complete_bundle(
    tmp_path: Path, monkeypatch,
) -> None:
    third_party = tmp_path / "3rdParty"
    cache = third_party / "typst" / "packages"
    for name, version in TYPST_PREVIEW_PACKAGES:
        preview_package_dir(cache, name, version).mkdir(parents=True)

    monkeypatch.setattr(
        typst_compiler,
        "_third_party_search_roots",
        lambda: [third_party],
    )
    monkeypatch.delenv("TYPST_PACKAGE_CACHE_PATH", raising=False)

    resolved = typst_compiler._resolve_typst_package_cache_path()
    assert resolved == cache


def test_resolve_typst_package_cache_path_honors_env(
    tmp_path: Path, monkeypatch,
) -> None:
    cache = tmp_path / "custom-cache"
    cache.mkdir()
    monkeypatch.setenv("TYPST_PACKAGE_CACHE_PATH", str(cache))
    monkeypatch.setattr(typst_compiler, "_third_party_search_roots", lambda: [])

    assert typst_compiler._resolve_typst_package_cache_path() == cache
