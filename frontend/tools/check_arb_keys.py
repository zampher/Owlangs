#!/usr/bin/env python3
"""
Check two ARB files for missing keys (compare key sets only, not values).
Use case: ensure app_zh.arb has the same keys as app_en.arb (template).
"""

import argparse
import json
import sys
from pathlib import Path


def load_message_keys(arb_path: Path) -> set[str]:
    """Load ARB file and return set of message keys (exclude @@ metadata keys)."""
    with arb_path.open(encoding="utf-8") as f:
        data = json.load(f)
    # Only message keys: exclude keys that start with @@ (e.g. @@locale)
    return {k for k in data if not k.startswith("@@")}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two ARB files for missing keys (keys only, not values)."
    )
    parser.add_argument(
        "arb_a",
        type=Path,
        help="First ARB file (e.g. app_en.arb, used as reference).",
    )
    parser.add_argument(
        "arb_b",
        type=Path,
        help="Second ARB file (e.g. app_zh.arb).",
    )
    parser.add_argument(
        "--missing-in-b",
        action="store_true",
        help="Only list keys in A that are missing in B.",
    )
    parser.add_argument(
        "--missing-in-a",
        action="store_true",
        help="Only list keys in B that are missing in A.",
    )
    args = parser.parse_args()

    if not args.arb_a.is_file():
        print(f"Error: not a file: {args.arb_a}", file=sys.stderr)
        return 1
    if not args.arb_b.is_file():
        print(f"Error: not a file: {args.arb_b}", file=sys.stderr)
        return 1

    keys_a = load_message_keys(args.arb_a)
    keys_b = load_message_keys(args.arb_b)

    name_a = args.arb_a.name
    name_b = args.arb_b.name

    exit_code = 0

    if not args.missing_in_a:
        missing_in_b = keys_a - keys_b
        if missing_in_b:
            exit_code = 1
            if not args.missing_in_b:
                print(f"Keys in {name_a} missing in {name_b} ({len(missing_in_b)}):")
            for k in sorted(missing_in_b):
                print(k)
            if not args.missing_in_b and (keys_b - keys_a):
                print()

    if not args.missing_in_b:
        missing_in_a = keys_b - keys_a
        if missing_in_a:
            exit_code = 1
            if not args.missing_in_a:
                print(f"Keys in {name_b} missing in {name_a} ({len(missing_in_a)}):")
            for k in sorted(missing_in_a):
                print(k)

    if exit_code == 0:
        print("OK: both files have the same set of message keys.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
