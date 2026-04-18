from pathlib import Path


def test_pyinstaller_hiddenimports_contains_latex_check_modules() -> None:
    """
    Packaging regression guard:
    Frozen macOS build must include utils.latex_formula_checker and utils.latex_repair_llm,
    because app.routes.service.app_routes_formula_check imports them via `from utils.xxx`.
    """

    repo_root = Path(__file__).resolve().parents[1]
    lite_spec = (repo_root / "macos.spec").read_text(encoding="utf-8")
    full_spec = (repo_root / "full.spec").read_text(encoding="utf-8")

    required = [
        "backend.utils.latex_formula_checker",
        "backend.utils.latex_repair_llm",
        "backend.utils.llm_client",
    ]

    for token in required:
        assert token in lite_spec, f"Missing hidden import in macos.spec: {token}"
        assert token in full_spec, f"Missing hidden import in full.spec: {token}"

