# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

from layout.pdf_renderer.typst_overlay import compiler as typst_compiler


def test_search_typst_in_third_party_finds_windows_bundle(tmp_path: Path) -> None:
    typst_dir = tmp_path / "windows" / "typst-x86_64-pc-windows-msvc"
    typst_dir.mkdir(parents=True)
    typst_exe = typst_dir / "typst.exe"
    typst_exe.write_bytes(b"stub")

    resolved = typst_compiler._search_typst_in_third_party(tmp_path)
    assert resolved == str(typst_exe)


def test_get_typst_bin_path_honors_explicit_env(
    tmp_path: Path, monkeypatch,
) -> None:
    typst_exe = tmp_path / "typst.exe"
    typst_exe.write_bytes(b"stub")
    monkeypatch.setenv("TYPST_BIN", str(typst_exe))
    typst_compiler._typst_bin_cache = None
    typst_compiler._typst_search_logged = False

    assert typst_compiler._get_typst_bin_path() == str(typst_exe)
