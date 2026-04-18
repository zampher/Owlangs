from __future__ import annotations

"""
Small helper script to reproduce and debug Pandoc/XeLaTeX errors
for specific translated Markdown samples.

Usage (from repo root):
    python -m backend.test_pandoc_md_to_pdf

This uses the same convert_md_to_pdf() backend utility as the normal
PDF export path, so failures here should match production behavior.
"""

from pathlib import Path

from utils.format_convert_utils import convert_md_to_pdf


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_case(md_path: Path, to_lang: str = "zh") -> None:
    """Load a Markdown file and try to convert it to PDF via Pandoc."""
    print(f"\n=== Testing Markdown → PDF for: {md_path} ===")
    if not md_path.exists():
        print(f"[ERROR] File does not exist: {md_path}")
        return

    md_content = md_path.read_text(encoding="utf-8")
    print(f"[INFO ] Loaded Markdown, length={len(md_content)} chars")

    # Put outputs under a dedicated temp-like folder inside the repo
    output_dir = REPO_ROOT / "tmp_pandoc_md_pdf" / md_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{md_path.stem}.pdf"

    try:
        success = convert_md_to_pdf(
            md_content,
            str(pdf_path),
            output_dir=output_dir,
            to_lang=to_lang,
        )
        print(
            f"[RESULT] convert_md_to_pdf success={success}, "
            f"pdf_exists={pdf_path.exists()}, output_dir={output_dir}"
        )
    except Exception as exc:  # noqa: BLE001
        # Let the full exception message bubble up to the console;
        # detailed Pandoc/XeLaTeX stderr will also be in server logs
        print(f"[EXCEPTION] convert_md_to_pdf raised: {exc!r}")


def main() -> None:
    samples_dir = REPO_ROOT / "test" / "samples"
    cases = [
        samples_dir / "尿素吸附_translated.md",
        samples_dir / "聚砜 膜_translated.md",
    ]

    for case in cases:
        _run_case(case, to_lang="zh")


if __name__ == "__main__":
    main()

