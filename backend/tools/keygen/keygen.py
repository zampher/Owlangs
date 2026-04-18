# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Universal keygen tool using Ed25519 private key for signing licenses/codes.

Usage:
  # Generate a license code with custom payload
  python -m backend.tools.keygen.keygen --payload '{"user_id":"12345","type":"premium"}' --expiry 2026-12-31
  
  # Generate machine-bound license
  python -m backend.tools.keygen.keygen --machine-id A1B2C3D4E5F6 --expiry 2026-12-31
  
  # Generate user license
  python -m backend.tools.keygen.keygen --user-id user123 --features premium,advanced --expiry 2026-12-31
  
  # Generate license key (no binding)
  python -m backend.tools.keygen.keygen --license-key PROD-2025 --expiry 2026-12-31
  
  # Verify a license code
  python -m backend.tools.keygen.keygen --verify CODE --machine-id A1B2C3D4E5F6
  
  # Decode and inspect a license code (without verification)
  python -m backend.tools.keygen.keygen --decode CODE

Private key: set LICENSE_PRIVATE_KEY_FILE to path to PEM file, or place at
  configs/license_private.pem (add to .gitignore).
Public key: after --generate-keys, copy configs/license_public.pem to repo
  (or deploy path) so the backend can verify codes.
"""

import argparse
import base64
import json
import os
import sys
import struct
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add project root for imports
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def _b64url_encode(data: bytes) -> str:
    """Base64 URL-safe encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64 URL-safe decoding with padding."""
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def generate_key_pair() -> Tuple[bytes, bytes]:
    """Generate Ed25519 key pair (private_pem, public_pem)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign_license(
    private_key_pem: bytes,
    payload: Dict[str, Any],
) -> str:
    """
    Sign a license payload and return base64url-encoded code.
    
    Args:
        private_key_pem: PEM-encoded Ed25519 private key.
        payload: Dictionary containing license data (e.g., machine_id, user_id, features, expiry).
    
    Returns:
        License code string (base64url-encoded signature + payload).
    """
    # Sort keys for consistent encoding
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Key must be Ed25519 private key")
    signature = key.sign(payload_bytes)
    # Code = payload_len(2 bytes) + payload + signature (64 bytes)
    packed = struct.pack(">H", len(payload_bytes)) + payload_bytes + signature
    return _b64url_encode(packed)


def verify_license(
    public_key_pem: bytes,
    code: str,
    expected_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Verify a license code and optionally check against expected data.
    
    Args:
        public_key_pem: PEM-encoded Ed25519 public key.
        code: License code string from user.
        expected_data: Optional dict with expected values (e.g., {"machine_id": "..."}).
    
    Returns:
        (is_valid, error_message, decoded_payload) tuple.
    """
    try:
        packed = _b64url_decode(code.strip())
    except Exception as e:
        return False, f"Invalid code format: {e}", None

    if len(packed) < 2 + 64:
        return False, "Code too short", None

    (plen,) = struct.unpack(">H", packed[:2])
    if 2 + plen + 64 > len(packed):
        return False, "Code payload length invalid", None
    payload_bytes = packed[2 : 2 + plen]
    signature = packed[2 + plen : 2 + plen + 64]

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        return False, f"Invalid payload: {e}", None

    # Verify signature
    key = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        return False, "Invalid public key type", payload
    try:
        key.verify(signature, payload_bytes)
    except InvalidSignature:
        return False, "Invalid signature", payload

    # Check expiry if present
    expiry = payload.get("expiry")
    if expiry:
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            if datetime.now().date() > exp_date:
                return False, "License has expired", payload
        except ValueError:
            return False, "Invalid expiry in license", payload

    # Check expected data if provided
    if expected_data:
        for key, expected_value in expected_data.items():
            actual_value = payload.get(key)
            if actual_value != expected_value:
                return False, f"License {key} mismatch: expected {expected_value}, got {actual_value}", payload

    return True, None, payload


def decode_license(code: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Decode a license code without verification (for inspection only).
    
    Returns:
        (payload_dict, error_message) tuple.
    """
    try:
        packed = _b64url_decode(code.strip())
    except Exception as e:
        return None, f"Invalid code format: {e}"

    if len(packed) < 2 + 64:
        return None, "Code too short"

    (plen,) = struct.unpack(">H", packed[:2])
    if 2 + plen + 64 > len(packed):
        return None, "Code payload length invalid"
    payload_bytes = packed[2 : 2 + plen]

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        return payload, None
    except Exception as e:
        return None, f"Invalid payload: {e}"


def _find_private_key() -> Path:
    """Find private key file from env or default location."""
    env_path = os.environ.get("LICENSE_PRIVATE_KEY_FILE")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Private key file from env not found: {p}")
    # Default: configs/license_private.pem
    configs = _project_root / "configs"
    default = configs / "license_private.pem"
    if default.exists():
        return default
    # Fallback to donor license private key
    donor_default = configs / "donor_license_private.pem"
    if donor_default.exists():
        return donor_default
    raise FileNotFoundError(
        "Private key not found. Set LICENSE_PRIVATE_KEY_FILE or create configs/license_private.pem"
    )


def _find_public_key() -> Path:
    """Find public key file from env or default location."""
    env_path = os.environ.get("LICENSE_PUBLIC_KEY_FILE")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Public key file from env not found: {p}")
    # Default: configs/license_public.pem
    configs = _project_root / "configs"
    default = configs / "license_public.pem"
    if default.exists():
        return default
    # Fallback to donor license public key
    donor_default = configs / "donor_license_public.pem"
    if donor_default.exists():
        return donor_default
    raise FileNotFoundError(
        "Public key not found. Set LICENSE_PUBLIC_KEY_FILE or create configs/license_public.pem"
    )


def _load_private_key(path: Path) -> bytes:
    """Load PEM private key from file."""
    with open(path, "rb") as f:
        return f.read()


def _load_public_key(path: Path) -> bytes:
    """Load PEM public key from file."""
    with open(path, "rb") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Universal keygen tool using Ed25519 private key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate key pair (one-time setup)
  %(prog)s --generate-keys

  # Generate license with custom JSON payload
  %(prog)s --payload '{"user_id":"12345","type":"premium","features":["feature1","feature2"]}'

  # Generate machine-bound license
  %(prog)s --machine-id A1B2C3D4E5F6 --expiry 2026-12-31

  # Generate user license with features
  %(prog)s --user-id user123 --features premium,advanced --expiry 2026-12-31

  # Generate license with product edition (PRO desktop / PRO-WEB web)
  %(prog)s --machine-id A1B2C3D4E5F6 --license-key PRO --expiry 2026-12-31
  %(prog)s --machine-id WEB_INSTANCE_ID --license-key PRO-WEB

  # Verify a license code
  %(prog)s --verify CODE --machine-id A1B2C3D4E5F6

  # Decode and inspect a license code
  %(prog)s --decode CODE
        """,
    )
    
    parser.add_argument("--generate-keys", action="store_true", help="Generate Ed25519 key pair and exit")
    parser.add_argument("--payload", type=str, help="Custom JSON payload (overrides other options)")
    parser.add_argument("--machine-id", type=str, help="Machine ID for machine-bound license")
    parser.add_argument("--user-id", type=str, help="User ID for user-bound license")
    parser.add_argument(
        "--license-key",
        type=str,
        choices=["PRO", "PRO-WEB"],
        help="Product edition: PRO (desktop) or PRO-WEB (web); omit for legacy (no license_key in payload)",
    )
    parser.add_argument("--features", type=str, help="Comma-separated list of features")
    parser.add_argument("--expiry", type=str, metavar="YYYY-MM-DD", help="Expiry date (format: YYYY-MM-DD)")
    parser.add_argument("--verify", type=str, metavar="CODE", help="Verify a license code")
    parser.add_argument("--decode", type=str, metavar="CODE", help="Decode and inspect a license code (no verification)")
    parser.add_argument("--format", action="store_true", help="Format output code with dashes for readability")
    
    args = parser.parse_args()

    # Generate keys
    if args.generate_keys:
        configs = _project_root / "configs"
        configs.mkdir(parents=True, exist_ok=True)
        private_path = configs / "license_private.pem"
        public_path = configs / "license_public.pem"
        
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

    # Decode license (no verification)
    if args.decode:
        payload, error = decode_license(args.decode)
        if error:
            print(f"✗ Error: {error}", file=sys.stderr)
            return 1
        print("✓ License decoded successfully:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    # Verify license
    if args.verify:
        try:
            key_path = _find_public_key()
            public_pem = _load_public_key(key_path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        expected_data = {}
        if args.machine_id:
            expected_data["machine_id"] = args.machine_id.strip().upper()
        if args.user_id:
            expected_data["user_id"] = args.user_id.strip()
        if args.license_key:
            expected_data["license_key"] = args.license_key.strip()
        
        is_valid, error_msg, payload = verify_license(public_pem, args.verify, expected_data if expected_data else None)
        if is_valid:
            print("✓ License code is VALID")
            print(f"  Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            return 0
        else:
            print(f"✗ License code is INVALID: {error_msg}", file=sys.stderr)
            if payload:
                print(f"  Decoded payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            return 1

    # Generate license
    try:
        key_path = _find_private_key()
        private_pem = _load_private_key(key_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Build payload
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON payload: {e}", file=sys.stderr)
            return 1
    else:
        payload = {}
        if args.machine_id:
            payload["machine_id"] = args.machine_id.strip().upper()
        if args.user_id:
            payload["user_id"] = args.user_id.strip()
        if args.license_key:
            payload["license_key"] = args.license_key.strip()
        if args.features:
            features_list = [f.strip() for f in args.features.split(",") if f.strip()]
            if features_list:
                payload["features"] = features_list
        if args.expiry:
            payload["expiry"] = args.expiry.strip()
        
        if not payload:
            parser.error("Must provide at least one of: --payload, --machine-id, --user-id, --license-key")

    try:
        code = sign_license(private_pem, payload)
        
        if args.format:
            # Format with dashes every 4 characters
            formatted = ""
            for i, char in enumerate(code):
                if i > 0 and i % 4 == 0:
                    formatted += "-"
                formatted += char
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            print(f"Code:    {code}")
            print(f"Formatted: {formatted}")
        else:
            print(code)
        
        return 0
    except Exception as e:
        print(f"Error generating license: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
