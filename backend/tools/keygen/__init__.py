# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Keygen package for license code generation and verification.

This package provides:
- CLI tool: keygen.py
- GUI tool: keygen_gui.py
- Core functions: sign_license, verify_license, decode_license

Usage:
  # CLI
  python -m backend.tools.keygen.keygen --generate-keys
  python -m backend.tools.keygen.keygen --machine-id A1B2C3D4E5F6 --expiry 2026-12-31
  
  # GUI
  python -m backend.tools.keygen.keygen_gui
"""

# Export core functions for easy import
from backend.tools.keygen.keygen import (  # noqa: F401
    decode_license,
    generate_key_pair,
    sign_license,
    verify_license,
)
