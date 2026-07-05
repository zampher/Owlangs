# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path


def test_pyinstaller_hiddenimports_contains_latex_check_modules() -> None:
    """
    Packaging regression guard:
    Frozen builds must include LaTeX check/repair and segment latex_flags modules,
    because service routes and PDF export paths lazy-import them via `from utils.xxx`.
    """

    repo_root = Path(__file__).resolve().parents[1]
    spec_files = [
        repo_root / "lite.spec",
        repo_root / "macos.spec",
        repo_root / "launcher_portable_onedir.spec",
    ]
    optional_spec = repo_root / "full.spec"

    required = [
        "backend.utils.latex_formula_checker",
        "backend.utils.latex_repair_llm",
        "backend.utils.llm_client",
        "backend.utils.segment_latex_flags",
        "backend.utils.mixed_formula_text",
        "layout.layout_group_pair_utils",
        "layout.ocr_provider.paddle.layout_group_pairs",
    ]

    for spec_path in spec_files:
        assert spec_path.is_file(), f"Missing spec file: {spec_path.name}"
        spec_text = spec_path.read_text(encoding="utf-8")
        for token in required:
            assert token in spec_text, (
                f"Missing hidden import in {spec_path.name}: {token}"
            )

    if optional_spec.is_file():
        full_text = optional_spec.read_text(encoding="utf-8")
        for token in required:
            assert token in full_text, f"Missing hidden import in full.spec: {token}"
