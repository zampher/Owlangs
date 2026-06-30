# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Helpers for flattening md_zip downloads into outer batch archives."""

from __future__ import annotations

import io
import re
import zipfile
from typing import Callable, Set

_LEGACY_OUTPUT_SUFFIXES = ("_translated", "_converted")
# Keep each ZIP entry path under common Windows archiver limits.
_MAX_ZIP_COMPONENT_BYTES = 80
_MAX_ZIP_ENTRY_BYTES = 220
_INVALID_ZIP_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


def strip_legacy_output_suffix(name: str) -> str:
    """Remove baked-in legacy suffixes before applying the current user suffix."""
    for legacy in _LEGACY_OUTPUT_SUFFIXES:
        if name.endswith(legacy):
            return name[: -len(legacy)]
    return name


def sanitize_zip_path_component(name: str) -> str:
    """Make one path segment safe for Windows ZIP tools."""
    cleaned = _INVALID_ZIP_CHARS.sub("_", (name or "").strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or "document"


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    cut = max_bytes
    while cut > 0 and (encoded[cut - 1] & 0xC0) == 0x80:
        cut -= 1
    return encoded[:cut].decode("utf-8", errors="ignore") or "document"


def make_batch_folder_name(base_name: str, task_id: str, suffix: str) -> str:
    """Build a short, Windows-friendly folder name for one batch entry."""
    clean = strip_legacy_output_suffix(base_name)
    stem = sanitize_zip_path_component(f"{clean}{suffix}")
    if len(stem.encode("utf-8")) <= _MAX_ZIP_COMPONENT_BYTES:
        return stem
    tid = sanitize_zip_path_component((task_id or "task")[:8])
    budget = max(16, _MAX_ZIP_COMPONENT_BYTES - len(tid.encode("utf-8")) - 1)
    short = _truncate_utf8(stem, budget)
    return f"{short}_{tid}"


def make_batch_md_filename(base_name: str, suffix: str) -> str:
    """Keep the original document stem in the exported Markdown file name."""
    clean = strip_legacy_output_suffix(base_name)
    stem = sanitize_zip_path_component(f"{clean}{suffix}")
    return f"{stem}.md"


def _fit_md_filename_for_folder(folder_prefix: str, md_filename: str) -> str:
    """Truncate the MD file name only when the full ZIP entry path is too long."""
    full = _normalize_zip_arcname(f"{folder_prefix}/{md_filename}")
    if len(full.encode("utf-8")) <= _MAX_ZIP_ENTRY_BYTES:
        return md_filename
    stem, _, ext = md_filename.rpartition(".")
    ext_part = f".{ext}" if ext else ".md"
    prefix_len = len(f"{folder_prefix}/".encode("utf-8"))
    budget = _MAX_ZIP_ENTRY_BYTES - prefix_len - len(ext_part.encode("utf-8"))
    if budget < 8:
        return _truncate_utf8(stem or "document", 8) + ext_part
    return _truncate_utf8(stem or "document", budget) + ext_part


def _normalize_zip_arcname(name: str) -> str:
    return name.replace("\\", "/").lstrip("./")


def _ensure_zip_parent_dirs(
    zf: zipfile.ZipFile,
    arcname: str,
    written_dirs: Set[str],
) -> None:
    """Write explicit directory records so Explorer/WinRAR can browse nested paths."""
    norm = _normalize_zip_arcname(arcname)
    if "/" not in norm:
        return
    parts = norm.split("/")[:-1]
    prefix = ""
    for part in parts:
        if not part:
            continue
        prefix = f"{prefix}/{part}" if prefix else part
        dir_name = f"{prefix}/"
        if dir_name in written_dirs:
            continue
        if dir_name not in zf.namelist():
            zf.writestr(dir_name, b"")
        written_dirs.add(dir_name)


def write_zip_entry(
    zf: zipfile.ZipFile,
    arcname: str,
    data: bytes,
    written_dirs: Set[str],
) -> str:
    """Write one file entry with parent directory stubs and path-length guard."""
    norm = _normalize_zip_arcname(arcname)
    if len(norm.encode("utf-8")) > _MAX_ZIP_ENTRY_BYTES:
        raise ValueError(f"ZIP entry path too long ({len(norm.encode('utf-8'))} bytes): {norm[:80]}...")
    _ensure_zip_parent_dirs(zf, norm, written_dirs)
    zf.writestr(norm, data)
    return norm


def _remap_inner_md_entry(inner_name: str, md_filename: str) -> str:
    norm = _normalize_zip_arcname(inner_name)
    if not norm.lower().endswith(".md"):
        return norm
    return md_filename


def add_md_zip_download_to_batch_archive(
    zf: zipfile.ZipFile,
    file_bytes: bytes,
    folder_prefix: str,
    base_name: str,
    suffix: str,
    resolve_conflict: Callable[[str], str],
    *,
    written_dirs: Set[str] | None = None,
) -> str:
    """Flatten an md_zip download into *zf*, or place a single .md when bytes are not a ZIP."""
    dirs = written_dirs if written_dirs is not None else set()
    folder_prefix = _normalize_zip_arcname(folder_prefix).rstrip("/")
    md_filename = _fit_md_filename_for_folder(
        folder_prefix,
        make_batch_md_filename(base_name, suffix),
    )
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as inner_zf:
            for inner_name in inner_zf.namelist():
                if inner_name.endswith("/"):
                    continue
                inner_bytes = inner_zf.read(inner_name)
                remapped = _remap_inner_md_entry(inner_name, md_filename)
                inner_entry = resolve_conflict(f"{folder_prefix}/{remapped}")
                write_zip_entry(zf, inner_entry, inner_bytes, dirs)
        entry_name = resolve_conflict(f"{folder_prefix}/")
        _ensure_zip_parent_dirs(zf, entry_name, dirs)
        return entry_name
    except zipfile.BadZipFile:
        md_entry = resolve_conflict(f"{folder_prefix}/{md_filename}")
        write_zip_entry(zf, md_entry, file_bytes, dirs)
        return f"{folder_prefix}/"
