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
from pathlib import Path
from typing import List, Optional
from tempfile import mkdtemp


def _resolve_typst_bin() -> str:
    """Find the typst binary, preferring environment override."""
    explicit = os.environ.get("TYPST_BIN", "").strip()
    if explicit:
        return explicit
    discovered = shutil.which("typst")
    if discovered:
        return discovered

    # Search bundled Typst in project 3rdParty directory
    try:
        project_root = Path(__file__).resolve().parents[4]
        third_party = project_root / "3rdParty"
        if third_party.exists():
            bin_name = "typst.exe" if os.name == "nt" else "typst"
            for candidate in third_party.rglob(bin_name):
                if candidate.is_file():
                    return str(candidate)
    except Exception:
        pass

    return "typst"  # let subprocess raise FileNotFoundError


TYPST_BIN = _resolve_typst_bin()


def is_typst_available() -> bool:
    """Check if Typst CLI is installed and usable."""
    try:
        result = subprocess.run(
            [TYPST_BIN, "--version"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class TypstCompileError(RuntimeError):
    """Raised when typst compile fails."""
    def __init__(self, phase: str, stem: str, typ_path: Path, return_code: int,
                 stdout: str = "", stderr: str = ""):
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
            / "static" / "flutter-web" / "assets" / "fonts"
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

    def compile(self, typ_path: Path, pdf_path: Path, *,
                phase: str = "overlay",
                root: Optional[Path] = None) -> Path:
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

        command = [TYPST_BIN, "compile"]

        if root and root.exists():
            command.extend(["--root", str(root)])

        for font_path in self._font_paths:
            if font_path.exists():
                command.extend(["--font-path", str(font_path)])

        command.extend([str(typ_path), str(pdf_path)])

        from logger.logger import unified_logger, LogModule as _lm

        unified_logger.info(
            _lm.RESTOR,
            f"[TYPST_OVERLAY] Running: {' '.join(command)}"
        )
        unified_logger.info(
            _lm.RESTOR,
            f"[TYPST_OVERLAY] source size: {typ_path.stat().st_size} bytes"
        )

        proc = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            unified_logger.error(
                _lm.RESTOR,
                f"[TYPST_OVERLAY] Compile failed: returncode={proc.returncode}, "
                f"stdout_len={len(proc.stdout)}, stderr_len={len(proc.stderr)}"
            )
            if proc.stdout:
                unified_logger.error(_lm.RESTOR, f"[TYPST_OVERLAY] stdout:\n{proc.stdout}")
            if proc.stderr:
                unified_logger.error(_lm.RESTOR, f"[TYPST_OVERLAY] stderr:\n{proc.stderr}")
            if not proc.stdout and not proc.stderr:
                unified_logger.error(
                    _lm.RESTOR,
                    f"[TYPST_OVERLAY] No stdout or stderr captured — "
                    f"binary may have crashed silently or failed to start"
                )
            raise TypstCompileError(
                phase=phase, stem=stem, typ_path=typ_path,
                return_code=proc.returncode,
                stdout=proc.stdout, stderr=proc.stderr,
            )
        return pdf_path

    def compile_source(self, source: str, stem: str, *,
                       work_dir: Optional[Path] = None,
                       phase: str = "overlay",
                       root: Optional[Path] = None) -> Path:
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


def compile_overlay_pdf(source: str, stem: str = "overlay",
                        work_dir: Optional[Path] = None) -> Path:
    """Quick one-off compilation of Typst source to overlay PDF."""
    return get_compiler().compile_source(source, stem, work_dir=work_dir)
