# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
System Dependency Check Service

Checks availability of important third-party dependencies on macOS
and provides guidance for installation.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule


def _check_command(cmd: str) -> bool:
    """Check if a command is available in PATH."""
    if shutil.which(cmd):
        return True
    if sys.platform == "darwin":
        return _check_command_macos(cmd)
    return False


def _check_command_macos(cmd: str) -> bool:
    """
    macOS GUI/bundled processes often have a minimal PATH.
    Match OwlangsMenuBar dependency detection (login shell + common paths).
    """
    for shell_cmd in (
        ["/bin/zsh", "-l", "-c", f"command -v {cmd}"],
        ["/bin/bash", "-l", "-c", f"command -v {cmd}"],
    ):
        try:
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass

    common_dirs = (
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/Library/TeX/texbin",
    )
    for directory in common_dirs:
        candidate = Path(directory) / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def _check_calibre() -> bool:
    """Check if Calibre ebook-convert is available."""
    if _check_command("ebook-convert"):
        return True
    # macOS common install locations
    if sys.platform == "darwin":
        for path in (
            "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            "/Applications/Calibre.app/Contents/MacOS/ebook-convert",
            "/opt/homebrew/bin/ebook-convert",
            "/usr/local/bin/ebook-convert",
        ):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return True
    return False


def _check_playwright_chromium() -> bool:
    """Check if Playwright Chromium browser is installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Check if chromium executable exists
            chromium = p.chromium
            if hasattr(chromium, 'executable_path'):
                exe_path = chromium.executable_path
                if exe_path and os.path.exists(exe_path):
                    return True
        # Fallback: check common cache locations
        home = Path.home()
        cache_dirs = [
            home / "Library" / "Caches" / "ms-playwright" / "chromium",
            home / ".cache" / "ms-playwright" / "chromium",
        ]
        for d in cache_dirs:
            if d.exists() and any(d.iterdir()):
                return True
    except Exception:
        pass
    return False


def _check_xelatex() -> bool:
    """Check if XeLaTeX is available."""
    if _check_command("xelatex"):
        return True
    # macOS common install locations
    if sys.platform == "darwin":
        for path in (
            "/Library/TeX/texbin/xelatex",
            "/usr/local/texlive/current/bin/universal-darwin/xelatex",
            "/opt/homebrew/bin/xelatex",
            "/usr/local/bin/xelatex",
        ):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return True
    return False


def check_system_dependencies() -> Dict[str, any]:
    """
    Check all important third-party dependencies.
    
    Returns:
        Dictionary with dependency status and installation guidance.
    """
    platform = sys.platform
    is_macos = platform == "darwin"
    
    # Define dependencies to check
    # Each entry: (name, check_func, required_for, install_hint)
    dependencies = []
    
    # Pandoc - essential for DOCX/PDF export
    dependencies.append({
        "name": "pandoc",
        "display_name": "Pandoc",
        "installed": _check_command("pandoc"),
        "required_for": "DOCX export, PDF export, format conversion",
        "optional": False,
        "macos_install": "brew install pandoc",
        "linux_install": "sudo apt install pandoc",
    })
    
    # Typst - PDF in-place translation (typst_overlay renderer)
    dependencies.append({
        "name": "typst",
        "display_name": "Typst",
        "installed": _check_command("typst"),
        "required_for": "PDF in-place translation (typst_overlay)",
        "optional": False,
        "macos_install": "brew install typst",
        "linux_install": "See https://github.com/typst/typst/releases",
    })

    # XeLaTeX - essential for PDF math rendering
    dependencies.append({
        "name": "xelatex",
        "display_name": "XeLaTeX",
        "installed": _check_xelatex(),
        "required_for": "PDF export with math formulas",
        "optional": False,
        "macos_install": "brew install --cask mactex  (or tinytex)",
        "linux_install": "sudo apt install texlive-xetex",
    })
    
    # Redis - for caching and sessions
    dependencies.append({
        "name": "redis",
        "display_name": "Redis",
        "installed": _check_command("redis-server") or _check_command("redis-cli"),
        "required_for": "Session storage, caching, task queue",
        "optional": True,
        "macos_install": "brew install redis && brew services start redis",
        "linux_install": "sudo apt install redis-server",
    })
    
    # Calibre - for MOBI/EPUB export
    dependencies.append({
        "name": "calibre",
        "display_name": "Calibre",
        "installed": _check_calibre(),
        "required_for": "MOBI/EPUB export",
        "optional": True,
        "macos_install": "brew install --cask calibre",
        "linux_install": "sudo apt install calibre",
    })
    
    # Playwright Chromium - for HTML to PDF
    dependencies.append({
        "name": "playwright_chromium",
        "display_name": "Playwright Chromium",
        "installed": _check_playwright_chromium(),
        "required_for": "HTML to PDF conversion",
        "optional": True,
        "macos_install": "playwright install chromium  (in Python env)",
        "linux_install": "playwright install chromium  (in Python env)",
    })
    
    # Count missing dependencies
    missing = [d for d in dependencies if not d["installed"]]
    missing_required = [d for d in missing if not d["optional"]]
    missing_optional = [d for d in missing if d["optional"]]
    
    # Build macOS-specific guidance (required deps only; optional tools are on-demand)
    macos_guidance = None
    if is_macos and missing_required:
        macos_guidance = {
            "message": (
                "Some dependencies are missing. Use the menu bar installer "
                "(Check Dependencies → Install) inside Owlangs.app."
            ),
            "steps": [
                "1. Open Owlangs from Applications (menu bar icon)",
                "2. Click menu bar → Check Dependencies",
                "3. Click Install (you may be prompted for your password)",
                "4. If Install fails, click Help for manual steps",
            ],
            "latex_note": (
                "For PDF math rendering, XeLaTeX is required. "
                "If you chose not to install MacTeX, PDF export with formulas will not work."
            ) if any(d["name"] == "xelatex" and not d["installed"] for d in missing) else None,
        }
    
    return {
        "platform": platform,
        "is_macos": is_macos,
        "all_ok": len(missing) == 0,
        "all_required_ok": len(missing_required) == 0,
        "dependencies": dependencies,
        "missing_count": len(missing),
        "missing_required_count": len(missing_required),
        "missing_optional_count": len(missing_optional),
        "macos_guidance": macos_guidance,
    }
