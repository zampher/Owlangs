# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Resolve TrueType font files for Pillow text rendering."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from PIL import ImageFont

_FONT_DIRS: list[Path] = []
if sys.platform == "win32":
    _FONT_DIRS.append(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts")
elif sys.platform == "darwin":
    _FONT_DIRS.extend(
        [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
        ]
    )
else:
    _FONT_DIRS.extend(
        [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
        ]
    )

_FAMILY_FILES = {
    "Microsoft YaHei": ("msyh.ttc", "msyhbd.ttc"),
    "Microsoft JhengHei": ("msjh.ttc", "msjhbd.ttc"),
    "Calibri": ("calibri.ttf", "calibrib.ttf", "calibrii.ttf"),
    "Yu Gothic": ("YuGothR.ttc", "YuGothB.ttc"),
    "Malgun Gothic": ("malgun.ttf", "malgunbd.ttf"),
    "Arial Unicode MS": ("arialuni.ttf",),
    "Times New Roman": ("times.ttf", "timesbd.ttf", "timesi.ttf"),
    "Helvetica Neue": ("HelveticaNeue.ttc",),
    "Noto Sans CJK SC": ("NotoSansCJK-Regular.ttc", "NotoSansSC-Regular.otf"),
    "Noto Sans CJK JP": ("NotoSansCJK-Regular.ttc", "NotoSansJP-Regular.otf"),
    "Noto Sans CJK KR": ("NotoSansCJK-Regular.ttc", "NotoSansKR-Regular.otf"),
}


def resolve_truetype_font_path(family_name: str, *, bold: bool = False) -> Optional[str]:
    """Return an existing font file path for the given family name."""
    candidates = _FAMILY_FILES.get(family_name or "", ())
    if bold and len(candidates) > 1:
        candidates = (candidates[1], candidates[0], *candidates[2:])
    if not candidates and family_name:
        stem = family_name.lower().replace(" ", "")
        candidates = (f"{stem}.ttf", f"{stem}.ttc", f"{stem}.otf")

    for filename in candidates:
        for font_dir in _FONT_DIRS:
            path = font_dir / filename
            if path.is_file():
                return str(path)

    for font_dir in _FONT_DIRS:
        if not font_dir.is_dir():
            continue
        try:
            for path in font_dir.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
                    continue
                if family_name and family_name.lower().replace(" ", "") in path.stem.lower():
                    return str(path)
        except OSError:
            continue
    return None


def load_overlay_font(
    family_name: str,
    size_px: int,
    *,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a Pillow font for overlay drawing."""
    path = resolve_truetype_font_path(family_name, bold=bold)
    if path:
        try:
            if path.lower().endswith(".ttc"):
                return ImageFont.truetype(path, size_px, index=0)
            return ImageFont.truetype(path, size_px)
        except OSError:
            pass

    from logger.logger import LogModule, unified_logger

    unified_logger.warning(
        LogModule.EXPORT,
        "[IMAGE_OVERLAY] Font family %r not found (bold=%s), "
        "falling back to Pillow default bitmap font. "
        "CJK characters may not render." % (family_name, bold),
    )
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def font_loader_for_family(family_name: str, *, bold: bool = False) -> Callable[[int], ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    """Return a callable that loads the same family at different pixel sizes."""

    def _load(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return load_overlay_font(family_name, max(1, int(size_px)), bold=bold)

    return _load
