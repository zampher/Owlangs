# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Helpers for MinerU layout-driven workflows (PDF and OCR image inputs)."""

MINERU_LAYOUT_IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tiff",
    ".tif",
    ".bmp",
    ".gif",
)


def is_mineru_layout_image(filename: str) -> bool:
    """Return True when the file is an image parsed via MinerU OCR/layout."""
    return (filename or "").lower().endswith(MINERU_LAYOUT_IMAGE_EXTENSIONS)


def is_mineru_layout_source(filename: str) -> bool:
    """Return True for PDF or image inputs that use MinerU layout extraction."""
    name = (filename or "").lower()
    return name.endswith(".pdf") or is_mineru_layout_image(name)


def needs_mineru_zip_restore(filename: str) -> bool:
    """Return True when MinerU ZIP attachment should be restored before translate/export."""
    return is_mineru_layout_source(filename)


def original_image_download_extension(filename: str) -> str | None:
    """Return lowercase extension for original-format image download, if applicable."""
    if not is_mineru_layout_image(filename):
        return None
    if "." not in (filename or ""):
        return None
    return filename.rsplit(".", 1)[-1].lower()


def is_original_image_format_request(file_type: str, original_filename: str) -> bool:
    """Return True when the client requests the source image extension export."""
    orig_ext = original_image_download_extension(original_filename)
    if not orig_ext:
        return False
    requested = (file_type or "").lower()
    if requested == orig_ext:
        return True
    if {requested, orig_ext} <= {"jpg", "jpeg"}:
        return True
    return False
