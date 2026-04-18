# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Generate donor registration codes (machine-bound).

Usage:
  # One-time: generate key pair (private key must be kept secret, not committed)
  python -m backend.tools.generate_donor_registration_code --generate-keys

  # Generate a code for a donor's machine_id (they send machine_id from the app)
  python -m backend.tools.generate_donor_registration_code A1B2C3D4E5F6
  python -m backend.tools.generate_donor_registration_code A1B2C3D4E5F6 --expiry 2026-12-31

  # Batch generate from file (one machine_id per line)
  python -m backend.tools.generate_donor_registration_code --batch machine_ids.txt --expiry 2026-12-31

  # Verify a registration code
  python -m backend.tools.generate_donor_registration_code --verify CODE --machine-id A1B2C3D4E5F6

Private key: set DONOR_LICENSE_PRIVATE_KEY_FILE to path to PEM file, or place at
  configs/donor_license_private.pem (add to .gitignore).
Public key: after --generate-keys, copy configs/donor_license_public.pem to repo
  (or deploy path) so the backend can verify codes.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add project root for imports
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.utils.donor_license import (
    generate_key_pair,
    load_private_key_from_file,
    load_public_key_from_file,
    sign_registration_code,
    verify_registration_code,
)


def _find_private_key() -> Path:
    env_path = os.environ.get("DONOR_LICENSE_PRIVATE_KEY_FILE")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Private key file from env not found: {p}")
    # Default: configs/donor_license_private.pem
    configs = _project_root / "configs"
    default = configs / "donor_license_private.pem"
    if default.exists():
        return default
    raise FileNotFoundError(
        "Private key not found. Set DONOR_LICENSE_PRIVATE_KEY_FILE or create configs/donor_license_private.pem (run with --generate-keys first)."
    )


def _find_public_key() -> Path:
    env_path = os.environ.get("DONOR_LICENSE_PUBLIC_KEY_FILE")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Public key file from env not found: {p}")
    # Default: configs/donor_license_public.pem
    configs = _project_root / "configs"
    default = configs / "donor_license_public.pem"
    if default.exists():
        return default
    raise FileNotFoundError(
        "Public key not found. Set DONOR_LICENSE_PUBLIC_KEY_FILE or create configs/donor_license_public.pem (run with --generate-keys first)."
    )


def _format_code(code: str, group_size: int = 4) -> str:
    """Format code with dashes for readability."""
    # Insert dashes every group_size characters
    formatted = ""
    for i, char in enumerate(code):
        if i > 0 and i % group_size == 0:
            formatted += "-"
        formatted += char
    return formatted


def _read_machine_ids_from_file(file_path: Path) -> List[str]:
    """Read machine IDs from file (one per line, skip empty lines and comments)."""
    machine_ids = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Remove any whitespace and convert to uppercase
            machine_id = line.upper().replace(" ", "").replace("\t", "")
            if machine_id:
                machine_ids.append(machine_id)
    return machine_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate donor registration codes (machine-bound)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate key pair (one-time setup)
  %(prog)s --generate-keys

  # Generate a single code
  %(prog)s A1B2C3D4E5F6
  %(prog)s A1B2C3D4E5F6 --expiry 2026-12-31

  # Batch generate from file
  %(prog)s --batch machine_ids.txt --expiry 2026-12-31 --output codes.txt

  # Verify a code
  %(prog)s --verify CODE --machine-id A1B2C3D4E5F6
        """,
    )
    parser.add_argument("--generate-keys", action="store_true", help="Generate Ed25519 key pair and exit")
    parser.add_argument("machine_id", nargs="?", help="Machine ID from donor's app (e.g. from Donate screen)")
    parser.add_argument("--expiry", type=str, metavar="YYYY-MM-DD", help="Optional expiry date (format: YYYY-MM-DD)")
    parser.add_argument("--batch", type=str, metavar="FILE", help="Batch generate codes from file (one machine_id per line)")
    parser.add_argument("--output", type=str, metavar="FILE", help="Output file for batch generation (default: stdout)")
    parser.add_argument("--verify", type=str, metavar="CODE", help="Verify a registration code")
    parser.add_argument("--machine-id", type=str, help="Machine ID for verification (required with --verify)")
    parser.add_argument("--format", action="store_true", help="Format output code with dashes for readability")
    args = parser.parse_args()

    # Generate keys
    if args.generate_keys:
        configs = _project_root / "configs"
        configs.mkdir(parents=True, exist_ok=True)
        private_path = configs / "donor_license_private.pem"
        public_path = configs / "donor_license_public.pem"
        
        if private_path.exists() or public_path.exists():
            response = input(f"Keys already exist at {configs}. Overwrite? (y/N): ")
            if response.lower() != "y":
                print("Cancelled.", file=sys.stderr)
                return 1
        
        priv_pem, pub_pem = generate_key_pair()
        with open(private_path, "wb") as f:
            f.write(priv_pem)
        with open(public_path, "wb") as f:
            f.write(pub_pem)
        print("✓ Keys generated successfully:")
        print(f"  Private: {private_path}  (keep secret, add to .gitignore)")
        print(f"  Public:  {public_path}   (commit or deploy for backend verification)")
        return 0

    # Verify code
    if args.verify:
        if not args.machine_id:
            parser.error("--machine-id is required when using --verify")
            return 1
        
        try:
            key_path = _find_public_key()
            public_pem = load_public_key_from_file(key_path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        machine_id = args.machine_id.strip().upper()
        code = args.verify.strip()
        
        is_valid, error_msg = verify_registration_code(public_pem, code, machine_id)
        if is_valid:
            print("✓ Registration code is VALID")
            print(f"  Machine ID: {machine_id}")
            return 0
        else:
            print(f"✗ Registration code is INVALID: {error_msg}", file=sys.stderr)
            return 1

    # Batch generation
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            print(f"Error: Batch file not found: {batch_file}", file=sys.stderr)
            return 1
        
        try:
            machine_ids = _read_machine_ids_from_file(batch_file)
            if not machine_ids:
                print("Error: No valid machine IDs found in file", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error reading batch file: {e}", file=sys.stderr)
            return 1
        
        try:
            key_path = _find_private_key()
            private_pem = load_private_key_from_file(key_path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        output_file = None
        if args.output:
            output_file = Path(args.output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
        
        results = []
        for machine_id in machine_ids:
            if len(machine_id) != 12:
                print(f"Warning: machine_id '{machine_id}' is not 12 chars, skipping", file=sys.stderr)
                continue
            
            try:
                code = sign_registration_code(
                    private_pem,
                    machine_id,
                    expiry_iso=args.expiry,
                )
                results.append((machine_id, code))
            except Exception as e:
                print(f"Error generating code for {machine_id}: {e}", file=sys.stderr)
                continue
        
        # Output results
        output_lines = []
        for machine_id, code in results:
            if args.format:
                formatted_code = _format_code(code)
                output_lines.append(f"{machine_id}\t{code}\t{formatted_code}")
            else:
                output_lines.append(f"{machine_id}\t{code}")
        
        output_text = "\n".join(output_lines)
        
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"✓ Generated {len(results)} codes, saved to {output_file}")
        else:
            print(output_text)
        
        return 0

    # Single generation
    if not args.machine_id:
        parser.error("machine_id is required (or use --generate-keys, --batch, or --verify)")
        return 1

    machine_id = args.machine_id.strip().upper()
    if len(machine_id) != 12:
        print("Warning: machine_id is usually 12 hex chars from the app.", file=sys.stderr)

    try:
        key_path = _find_private_key()
        private_pem = load_private_key_from_file(key_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        code = sign_registration_code(
            private_pem,
            machine_id,
            expiry_iso=args.expiry,
        )
        
        if args.format:
            formatted = _format_code(code)
            print(f"Machine ID: {machine_id}")
            print(f"Code:       {code}")
            print(f"Formatted:  {formatted}")
            if args.expiry:
                print(f"Expiry:     {args.expiry}")
        else:
            print(code)
        
        return 0
    except Exception as e:
        print(f"Error generating code: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
