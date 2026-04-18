# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Machine ID for donor license binding.

Derives a short, stable identifier from the current machine (first disk serial
or first NIC MAC), hashed so raw hardware info is not exposed.
"""

import hashlib
import platform
import subprocess
import sys
from typing import Optional

# Salt to avoid trivial reversal; not secret, just for uniqueness
_MACHINE_ID_SALT = b"owlangs-donor-license-v1"


def _get_first_disk_serial_windows() -> Optional[str]:
    """Get serial number of first physical disk on Windows (WMI)."""
    try:
        # Prefer wmic (no extra deps; built-in on Windows)
        out = subprocess.run(
            ["wmic", "diskdrive", "get", "serialnumber"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if out.returncode != 0 or not out.stdout:
            return None
        lines = [ln.strip() for ln in out.stdout.strip().splitlines() if ln.strip()]
        # First line is header "SerialNumber", second is value
        if len(lines) >= 2:
            serial = lines[1].strip()
            if serial and serial.lower() != "serialnumber":
                return serial
        return None
    except Exception:
        return None


def _get_first_disk_serial_linux() -> Optional[str]:
    """Get serial of first block device on Linux (e.g. /sys/block/sda/device/serial)."""
    try:
        import os
        for name in sorted(os.listdir("/sys/block") if os.path.exists("/sys/block") else []):
            if name.startswith(("loop", "ram", "dm-", "sr")):
                continue
            serial_path = f"/sys/block/{name}/device/serial"
            if os.path.isfile(serial_path):
                with open(serial_path, "r", encoding="utf-8", errors="replace") as f:
                    serial = f.read().strip()
                if serial:
                    return serial
        return None
    except Exception:
        return None


def _get_first_mac() -> Optional[str]:
    """Get first NIC MAC (48-bit) as hex string. Cross-platform via uuid.getnode()."""
    try:
        import uuid
        node = uuid.getnode()
        if node == 0 or (node >> 40) == 0xFF:  # random or invalid
            return None
        return f"{node:012x}"
    except Exception:
        return None


def _normalize_and_hash(raw: str) -> str:
    """Produce a short alphanumeric machine_id from raw hardware string."""
    data = (_MACHINE_ID_SALT + raw.encode("utf-8", errors="replace"))
    h = hashlib.sha256(data).hexdigest()
    # First 12 hex chars = 6 bytes, readable and stable
    return h[:12].upper()


def get_machine_id() -> str:
    """
    Return a stable machine identifier (hashed, not raw hardware).

    Tries: first disk serial (Windows WMI / Linux sysfs), then first NIC MAC.
    Never returns raw serial or MAC; always a 12-char hex string.
    """
    raw: Optional[str] = None
    if platform.system() == "Windows":
        raw = _get_first_disk_serial_windows()
    elif platform.system() == "Linux":
        raw = _get_first_disk_serial_linux()
    if not raw:
        raw = _get_first_mac()
    if not raw:
        # Last resort: hostname + salt (unstable if hostname changes)
        raw = platform.node() or "unknown"
    return _normalize_and_hash(raw)
