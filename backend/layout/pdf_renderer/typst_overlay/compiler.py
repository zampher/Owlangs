# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typst compiler wrapper.

Wraps the `typst compile` CLI command, providing a Pythonic interface
for compiling .typ source files into PDF overlays.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from tempfile import mkdtemp

from layout.pdf_renderer.typst_overlay.typst_packages import bundled_packages_complete

_typst_bin_cache: Optional[str] = None
_typst_search_logged = False


def _typst_binary_name() -> str:
    return "typst.exe" if os.name == "nt" else "typst"


def _is_typst_executable(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return True
    return os.access(path, os.X_OK)


def _search_typst_in_third_party(base: Path) -> Optional[str]:
    """Search a 3rdParty root for a Typst CLI binary."""
    if not base.exists():
        return None

    bin_name = _typst_binary_name()
    direct_candidates = (
        base / bin_name,
        base / "typst" / bin_name,
        base / "bin" / bin_name,
    )
    for candidate in direct_candidates:
        if _is_typst_executable(candidate):
            return str(candidate)

    platform_base = base / "windows" if sys.platform == "win32" else base
    if platform_base.exists():
        for typst_dir in sorted(platform_base.glob("typst*")):
            candidate = typst_dir / bin_name
            if _is_typst_executable(candidate):
                return str(candidate)
        for candidate in platform_base.rglob(bin_name):
            if _is_typst_executable(candidate):
                return str(candidate)

    for candidate in base.rglob(bin_name):
        if _is_typst_executable(candidate):
            return str(candidate)
    return None


def _third_party_search_roots() -> List[Path]:
    roots: List[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            roots.append(path)

    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        exe_path = Path(sys.executable)
        _add(exe_path.parent / "3rdParty")
        _add(exe_path.parent.parent / "3rdParty")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            _add(Path(meipass) / "3rdParty")

    try:
        from utils.format_convert_utils import _get_owlangs_install_dir

        install_dir = _get_owlangs_install_dir()
        if install_dir is not None:
            _add(install_dir / "3rdParty")
    except Exception:
        pass

    try:
        _add(Path(__file__).resolve().parents[4] / "3rdParty")
    except Exception:
        pass

    _add(Path.cwd() / "3rdParty")
    return roots


def _resolve_typst_package_cache_path() -> Optional[Path]:
    """
    Resolve bundled Typst package cache for offline @preview imports.

    When complete, returns ``3rdParty/typst/packages`` (or equivalent install path).
    Honors ``TYPST_PACKAGE_CACHE_PATH`` when set and the directory exists.
    """
    explicit = os.environ.get("TYPST_PACKAGE_CACHE_PATH", "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_dir():
            return path

    for root in _third_party_search_roots():
        candidate = root / "typst" / "packages"
        if bundled_packages_complete(candidate):
            return candidate
    return None


def _get_typst_bin_path() -> Optional[str]:
    """Resolve Typst CLI path for dev, PyInstaller, and production installs."""
    global _typst_bin_cache, _typst_search_logged

    if _typst_bin_cache is not None:
        return _typst_bin_cache or None

    explicit = os.environ.get("TYPST_BIN", "").strip()
    if explicit:
        explicit_path = Path(explicit)
        if _is_typst_executable(explicit_path):
            _typst_bin_cache = str(explicit_path)
            return _typst_bin_cache

    discovered = shutil.which("typst")
    if discovered:
        _typst_bin_cache = discovered
        return discovered

    for root in _third_party_search_roots():
        resolved = _search_typst_in_third_party(root)
        if resolved:
            _typst_bin_cache = resolved
            if not _typst_search_logged:
                from logger.logger import unified_logger, LogModule as _lm

                unified_logger.info(
                    _lm.RESTOR,
                    f"[TYPST_OVERLAY] Resolved Typst CLI: {resolved}",
                )
                _typst_search_logged = True
            return resolved

    if not _typst_search_logged:
        from logger.logger import unified_logger, LogModule as _lm

        searched = ", ".join(str(p) for p in _third_party_search_roots())
        unified_logger.warning(
            _lm.RESTOR,
            "[TYPST_OVERLAY] Typst CLI not found. "
            f"Searched PATH, TYPST_BIN, and 3rdParty roots: {searched}",
        )
        _typst_search_logged = True

    _typst_bin_cache = ""
    return None


def get_typst_bin() -> str:
    """Return resolved Typst CLI path, or bare 'typst' for subprocess errors."""
    return _get_typst_bin_path() or "typst"


# Backwards-compatible module constant; resolved lazily on first use.
TYPST_BIN = get_typst_bin()


def is_typst_available() -> bool:
    """Check if Typst CLI is installed and usable."""
    bin_path = _get_typst_bin_path()
    if not bin_path:
        return False
    try:
        result = subprocess.run(
            [bin_path, "--version"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class TypstCompileError(RuntimeError):
    """Raised when typst compile fails."""

    def __init__(
        self,
        phase: str,
        stem: str,
        typ_path: Path,
        return_code: int,
        stdout: str = "",
        stderr: str = "",
    ):
        self.phase = phase
        self.stem = stem
        self.typ_path = typ_path
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        detail = (stderr or stdout).strip()
        msg = (
            f"Typst compile failed phase={phase} stem={stem} "
            f"code={return_code}\n{detail}"
        )
        super().__init__(msg)


class TypstCompiler:
    """
    Manages Typst compilation with font path resolution and error handling.

    Usage::

        compiler = TypstCompiler(font_paths=["/usr/share/fonts"])
        pdf_path = compiler.compile(typ_path, pdf_path, phase="overlay")
    """

    def __init__(self, font_paths: Optional[List[Path]] = None):
        self._font_paths: List[Path] = list(font_paths or [])
        self._resolve_font_paths()

    def _resolve_font_paths(self) -> None:
        """Collect font directories from environment and defaults."""
        font_dirs_str = os.environ.get("TYPST_FONT_PATHS", "").strip()
        if font_dirs_str:
            for item in font_dirs_str.split(os.pathsep):
                p = Path(item.strip())
                if p.exists() and p not in self._font_paths:
                    self._font_paths.append(p)

        # Add project fonts directory (NotoSansSC, NotoSansJP, NotoSansKR, etc.)
        project_fonts = (
            Path(__file__).resolve().parents[4]
            / "static"
            / "flutter-web"
            / "assets"
            / "fonts"
        )
        if project_fonts.exists():
            self._font_paths.append(project_fonts)

        # Add system font directories for the current platform
        import platform as _platform

        _system = _platform.system()
        if _system == "Windows":
            _sys_fonts = Path("C:/Windows/Fonts")
            if _sys_fonts.exists():
                self._font_paths.append(_sys_fonts)
        elif _system == "Darwin":
            for _d in [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts",
            ]:
                if _d.exists() and _d not in self._font_paths:
                    self._font_paths.append(_d)
        elif _system == "Linux":
            for _d in [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
            ]:
                if _d.exists() and _d not in self._font_paths:
                    self._font_paths.append(_d)

    def compile(
        self,
        typ_path: Path,
        pdf_path: Path,
        *,
        phase: str = "overlay",
        root: Optional[Path] = None,
    ) -> Path:
        """
        Compile a .typ source file to PDF.

        Args:
            typ_path: Path to .typ source file
            pdf_path: Desired output .pdf path
            phase: Label for error messages
            root: Optional project root directory

        Returns:
            Path to the compiled PDF

        Raises:
            TypstCompileError: If compilation fails
            FileNotFoundError: If typst binary is not found
        """
        stem = typ_path.stem
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        typst_bin = get_typst_bin()
        command = [typst_bin, "compile"]

        if root and root.exists():
            command.extend(["--root", str(root)])

        for font_path in self._font_paths:
            if font_path.exists():
                command.extend(["--font-path", str(font_path)])

        package_cache = _resolve_typst_package_cache_path()
        if package_cache is not None:
            command.extend(["--package-cache-path", str(package_cache)])

        command.extend([str(typ_path), str(pdf_path)])

        from logger.logger import unified_logger, LogModule as _lm

        if package_cache is not None:
            unified_logger.info(
                _lm.RESTOR,
                f"[TYPST_OVERLAY] Using bundled Typst package cache: {package_cache}",
            )
        unified_logger.info(
            _lm.RESTOR,
            f"[TYPST_OVERLAY] Running: {' '.join(command)}",
        )
        unified_logger.info(
            _lm.RESTOR,
            f"[TYPST_OVERLAY] source size: {typ_path.stat().st_size} bytes",
        )

        proc = subprocess.run(
            command, capture_output=True, encoding="utf-8", errors="replace"
        )
        if proc.returncode != 0:
            unified_logger.error(
                _lm.RESTOR,
                f"[TYPST_OVERLAY] Compile failed: returncode={proc.returncode}, "
                f"stdout_len={len(proc.stdout)}, stderr_len={len(proc.stderr)}",
            )
            if proc.stdout:
                unified_logger.error(_lm.RESTOR, f"[TYPST_OVERLAY] stdout:\n{proc.stdout}")
            if proc.stderr:
                unified_logger.error(_lm.RESTOR, f"[TYPST_OVERLAY] stderr:\n{proc.stderr}")
            if not proc.stdout and not proc.stderr:
                unified_logger.error(
                    _lm.RESTOR,
                    "[TYPST_OVERLAY] No stdout or stderr captured — "
                    "binary may have crashed silently or failed to start",
                )
            raise TypstCompileError(
                phase=phase,
                stem=stem,
                typ_path=typ_path,
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        return pdf_path

    def compile_source(
        self,
        source: str,
        stem: str,
        *,
        work_dir: Optional[Path] = None,
        phase: str = "overlay",
        root: Optional[Path] = None,
    ) -> Path:
        """
        Compile a Typst source string to PDF.

        Args:
            source: Typst source code as string
            stem: Base name for .typ/.pdf files
            work_dir: Directory to place .typ and .pdf (default: temp dir)
            phase: Label for error messages
            root: Optional project root

        Returns:
            Path to the compiled PDF
        """
        if work_dir is None:
            work_dir = Path(mkdtemp(prefix="typst_"))
        work_dir.mkdir(parents=True, exist_ok=True)

        typ_path = work_dir / f"{stem}.typ"
        pdf_path = work_dir / f"{stem}.pdf"

        typ_path.write_text(source, encoding="utf-8")
        return self.compile(typ_path, pdf_path, phase=phase, root=root)


# Singleton instance for convenience
_default_compiler: Optional[TypstCompiler] = None


def get_compiler() -> TypstCompiler:
    """Get or create the default TypstCompiler singleton."""
    global _default_compiler
    if _default_compiler is None:
        _default_compiler = TypstCompiler()
    return _default_compiler


def compile_overlay_pdf(
    source: str, stem: str = "overlay", work_dir: Optional[Path] = None
) -> Path:
    """Quick one-off compilation of Typst source to overlay PDF."""
    return get_compiler().compile_source(source, stem, work_dir=work_dir)
