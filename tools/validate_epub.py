#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Validate an EPUB file and print all format errors (for Apple Books / strict readers).

Uses EPUBCheck when available (recommended). Otherwise runs a minimal structural check.

Install EPUBCheck (macOS):
  brew install epubcheck
  # Requires Java; epubcheck will use it.

Usage:
  python tools/validate_epub.py path/to/book.epub
  python tools/validate_epub.py path/to/book.epub --json report.json   # EPUBCheck JSON report
  From repo root: python -m tools.validate_epub path/to/book.epub
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional, Tuple


def _run_epubcheck(epub_path: Path, json_out: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run epubcheck on the file. Returns (returncode, stdout, stderr)."""
    cmd = ["epubcheck", str(epub_path)]
    if json_out:
        cmd.extend(["--json", str(json_out)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def _minimal_structure_check(epub_path: Path) -> list[str]:
    """Perform minimal structural checks and return list of error messages."""
    errors: list[str] = []
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            names = zf.namelist()
            if not names:
                errors.append("EPUB is empty (no entries).")
                return errors
            # mimetype must be first and stored uncompressed (EPUB spec)
            if names[0] != "mimetype":
                errors.append(
                    f"EPUB structure: first entry must be 'mimetype', got '{names[0]}'. "
                    "Apple Books and strict validators require mimetype first and uncompressed."
                )
            if "mimetype" in names:
                info = zf.getinfo("mimetype")
                if info.compress_type != zipfile.ZIP_STORED:
                    errors.append(
                        "EPUB structure: 'mimetype' must be stored uncompressed (ZIP_STORED)."
                    )
                try:
                    raw = zf.read("mimetype")
                    if raw.strip() != b"application/epub+zip":
                        errors.append(
                            f"EPUB structure: mimetype content must be 'application/epub+zip', got {raw!r}."
                        )
                except Exception as e:
                    errors.append(f"EPUB structure: could not read mimetype: {e}")
            else:
                errors.append("EPUB structure: missing 'mimetype' file.")
            if "META-INF/container.xml" not in names:
                errors.append("EPUB structure: missing 'META-INF/container.xml'.")
            # Check for at least one .opf
            opfs = [n for n in names if n.endswith(".opf")]
            if not opfs:
                errors.append("EPUB structure: no .opf package file found.")
    except zipfile.BadZipFile as e:
        errors.append(f"Not a valid ZIP/EPUB: {e}")
    except Exception as e:
        errors.append(f"Error opening EPUB: {e}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate EPUB and print format errors (for Apple Books / EPUBCheck)."
    )
    parser.add_argument(
        "epub",
        type=Path,
        help="Path to the .epub file",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write EPUBCheck JSON report to FILE (only when epubcheck is used)",
    )
    parser.add_argument(
        "--no-epubcheck",
        action="store_true",
        help="Skip epubcheck and only run minimal structure check",
    )
    args = parser.parse_args()

    epub_path = args.epub.resolve()
    if not epub_path.exists():
        print(f"Error: file not found: {epub_path}", file=sys.stderr)
        return 1
    if epub_path.suffix.lower() != ".epub":
        print(f"Warning: file does not have .epub extension: {epub_path}", file=sys.stderr)

    used_epubcheck = False
    if not args.no_epubcheck and shutil.which("epubcheck"):
        used_epubcheck = True
        print("Running EPUBCheck (standard EPUB validator)...", file=sys.stderr)
        code, out, err = _run_epubcheck(epub_path, args.json)
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)
        if args.json and args.json.exists():
            print(f"JSON report written to: {args.json}", file=sys.stderr)
        if code != 0:
            print(f"\nEPUBCheck exited with code {code}. Fix the errors above.", file=sys.stderr)
        return code

    if not used_epubcheck:
        print(
            "EPUBCheck not found. Run minimal structure check only.\n"
            "For full validation (recommended): brew install epubcheck",
            file=sys.stderr,
        )
    else:
        print("\nMinimal structure check:", file=sys.stderr)

    errors = _minimal_structure_check(epub_path)
    if not errors:
        print("Minimal structure check: no issues found.", file=sys.stderr)
        return 0
    for msg in errors:
        print(msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
