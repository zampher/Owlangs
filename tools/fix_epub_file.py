#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Fix an existing EPUB file for Apple Books / EPUBCheck and write a new file.

Applies: dc:title, nav document, remove toc=ncx, sanitize XHTML (font, mbp:pagebreak,
deprecated attributes, 一mages -> Images). Use this on an EPUB that was exported
before these fixes were applied in the app.

Usage:
  python tools/fix_epub_file.py input.epub [output.epub]
  python tools/fix_epub_file.py input.epub --inplace   # overwrite input with fixed copy

  From repo root: python -m tools.fix_epub_file /path/to/book.epub
"""

import argparse
import sys
from pathlib import Path

# Add backend to path so we can import utils.epub_fix
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if _BACKEND.exists() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix EPUB for EPUBCheck/Apple Books and write to a new file."
    )
    parser.add_argument("input", type=Path, help="Input .epub file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Output .epub file (default: input_fixed.epub)",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite input file with fixed content",
    )
    args = parser.parse_args()

    inp = args.input.resolve()
    if not inp.exists():
        print(f"Error: file not found: {inp}", file=sys.stderr)
        return 1
    if inp.suffix.lower() != ".epub":
        print(f"Warning: file does not have .epub extension: {inp}", file=sys.stderr)

    if args.inplace:
        out_path = inp.parent / (inp.stem + "_fixed_temp.epub")
        overwrite = True
    else:
        out_path = args.output
        if out_path is None:
            # Default: same dir as input, suffix _fixed.epub
            out_path = inp.parent / (inp.stem + "_fixed.epub")
        else:
            out_path = Path(args.output).resolve()
        overwrite = False

    try:
        from utils.epub_fix import fix_epub_for_epubcheck
    except ImportError:
        try:
            from backend.utils.epub_fix import fix_epub_for_epubcheck
        except ImportError:
            print("Error: could not import epub_fix. Run from repo root with backend on PYTHONPATH.", file=sys.stderr)
            return 1

    epub_bytes = inp.read_bytes()
    fixed = fix_epub_for_epubcheck(epub_bytes)
    if not fixed or len(fixed) < 100:
        print("Error: fix produced no or invalid output.", file=sys.stderr)
        return 1

    out_path.write_bytes(fixed)
    print(f"Wrote: {out_path} ({len(fixed)} bytes)", file=sys.stderr)

    if overwrite:
        out_path.rename(inp)
        print(f"Replaced original with fixed file: {inp}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
