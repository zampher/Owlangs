# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Donor registration code: sign (generator) and verify (backend).

Uses Ed25519: private key only in generator, public key in backend.
Payload: machine_id (str) + optional expiry_iso (str YYYY-MM-DD) + optional license_key (str).
- license_key: "PRO" = desktop, "PRO-WEB" = web; absent = legacy (desktop only).
Code = base64url(signature) for compact typing; payload is in signature context.
"""

import base64
import json
import struct
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def sign_registration_code(
    private_key_pem: bytes,
    machine_id: str,
    expiry_iso: Optional[str] = None,
) -> str:
    """
    Produce a registration code for the given machine_id and optional expiry.

    Args:
        private_key_pem: PEM-encoded Ed25519 private key.
        machine_id: From get_machine_id() on the target machine.
        expiry_iso: Optional "YYYY-MM-DD" or None for no expiry.

    Returns:
        Registration code string (base64url-encoded signature + payload).
    """
    payload = {"machine_id": machine_id, "expiry": expiry_iso}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Key must be Ed25519 private key")
    signature = key.sign(payload_bytes)
    # Code = payload_len(2 bytes) + payload + signature (64 bytes)
    packed = struct.pack(">H", len(payload_bytes)) + payload_bytes + signature
    return _b64url_encode(packed)


def sign_year_only_code(
    private_key_pem: bytes,
    code: str,
    expiry_iso: str,
) -> str:
    """
    Produce a year-only registration code (no machine binding). Used for special code 1037+year.
    Valid on any machine until expiry_iso (e.g. end of registration year).

    Args:
        private_key_pem: PEM-encoded Ed25519 private key.
        code: Code with year appended (e.g. "10372026").
        expiry_iso: Expiry date "YYYY-MM-DD" (e.g. "2026-12-31").

    Returns:
        Registration code string (base64url-encoded signature + payload).
    """
    payload = {"code": code, "expiry": expiry_iso}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Key must be Ed25519 private key")
    signature = key.sign(payload_bytes)
    packed = struct.pack(">H", len(payload_bytes)) + payload_bytes + signature
    return _b64url_encode(packed)


def decode_license_payload(code: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Decode a registration code and return the payload dict without verifying signature.
    Used to show current license info (edition, expiry) in the UI.

    Args:
        code: Registration code string (e.g. stored license_token).

    Returns:
        (payload_dict, None) on success; (None, error_message) on failure.
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
    except Exception as e:
        return None, f"Invalid payload: {e}"

    if not isinstance(payload, dict):
        return None, "Payload is not a dict"
    return payload, None


def verify_registration_code(
    public_key_pem: bytes,
    code: str,
    current_machine_id: str,
    current_edition: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Verify a registration code against the current machine_id and optional edition.

    Args:
        public_key_pem: PEM-encoded Ed25519 public key.
        code: Registration code string from user.
        current_machine_id: From get_machine_id() on this machine.
        current_edition: "PRO" (desktop) or "PRO-WEB" (web). If None, no edition check (backward compatible).

    Returns:
        (True, None) if valid; (False, error_message) if invalid.
    """
    try:
        packed = _b64url_decode(code.strip())
    except Exception as e:
        return False, f"Invalid code format: {e}"

    if len(packed) < 2 + 64:
        return False, "Code too short"

    (plen,) = struct.unpack(">H", packed[:2])
    if 2 + plen + 64 > len(packed):
        return False, "Code payload length invalid"
    payload_bytes = packed[2 : 2 + plen]
    signature = packed[2 + plen : 2 + plen + 64]

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        return False, f"Invalid payload: {e}"

    expiry = payload.get("expiry")
    if expiry:
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            if datetime.now().date() > exp_date:
                return False, "Code has expired"
        except ValueError:
            return False, "Invalid expiry in code"

    # Year-only code (e.g. 1037+year): no machine binding, only signature + expiry
    if "code" in payload and "expiry" in payload:
        key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(key, Ed25519PublicKey):
            return False, "Invalid public key type"
        try:
            key.verify(signature, payload_bytes)
        except InvalidSignature:
            return False, "Invalid signature"
        return True, None

    # Machine-bound code
    machine_id = payload.get("machine_id")
    if not machine_id or machine_id != current_machine_id:
        return False, "Code is not valid for this machine"

    # Edition check: when current_edition is set, enforce PRO vs PRO-WEB
    if current_edition in ("PRO", "PRO-WEB"):
        payload_license_key = (payload.get("license_key") or "").strip()
        if not payload_license_key:
            # Legacy code (no license_key): valid only on desktop (PRO)
            if current_edition != "PRO":
                return False, "This registration code is for desktop only. Use a PRO-WEB code for web deployment."
        else:
            # Code has license_key: must match current deployment
            if payload_license_key != current_edition:
                if current_edition == "PRO":
                    return False, "This registration code is for web only. Use a desktop (PRO) code."
                return False, "This registration code is for desktop only. Use a PRO-WEB code for web deployment."

    key = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        return False, "Invalid public key type"
    try:
        key.verify(signature, payload_bytes)
    except InvalidSignature:
        return False, "Invalid signature"
    return True, None


def load_private_key_from_file(path: Path) -> bytes:
    """Load PEM private key from file."""
    with open(path, "rb") as f:
        return f.read()


def load_public_key_from_file(path: Path) -> bytes:
    """Load PEM public key from file."""
    with open(path, "rb") as f:
        return f.read()


def generate_key_pair() -> Tuple[bytes, bytes]:
    """Generate Ed25519 key pair (private_pem, public_pem). For one-time setup."""
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
