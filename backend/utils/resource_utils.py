# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
import sys
from pathlib import Path

def resource_path(relative_path: str) -> Path:
    """
    Get absolute path of resources, suitable for both development environment
    and PyInstaller packaged environment.
    """
    # First handle PyInstaller runtime where files are extracted under _MEIPASS.
    if hasattr(sys, "_MEIPASS"):
        base_candidates = [
            Path(sys._MEIPASS) / "Owlangs",
            Path(sys._MEIPASS) / "backend",
            Path(sys._MEIPASS),
        ]
        for base in base_candidates:
            candidate = base / relative_path
            if candidate.exists():
                return candidate
        # Fallback to last candidate (usually _MEIPASS root) to keep path consistent
        return base_candidates[-1] / relative_path

    # Development-time fallback: project root (backend directory parent)
    return Path(__file__).resolve().parent.parent / relative_path