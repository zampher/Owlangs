# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF splitting utilities for large-file processing.

Splits a PDF into multiple byte chunks by page count,
so that each chunk can be processed independently by MinerU.
"""

import io
from typing import List


def split_pdf_by_pages(file_bytes: bytes, max_pages_per_split: int = 100) -> List[bytes]:
    """
    Split a PDF into multiple byte chunks, each containing at most ``max_pages_per_split`` pages.

    Args:
        file_bytes: The original PDF file content as bytes.
        max_pages_per_split: Maximum number of pages per chunk (default 100).

    Returns:
        A list of PDF byte chunks. If the original PDF has <= max_pages_per_split pages,
        returns a single-element list containing the original bytes (no copy).
    """
    if not file_bytes or len(file_bytes) < 100:
        return [file_bytes]

    try:
        import PyPDF2
    except ImportError:
        # If PyPDF2 is missing, return the original bytes unchanged
        return [file_bytes]

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)

    if total_pages <= max_pages_per_split:
        return [file_bytes]

    parts: List[bytes] = []
    for start in range(0, total_pages, max_pages_per_split):
        end = min(start + max_pages_per_split, total_pages)
        writer = PyPDF2.PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        parts.append(output.getvalue())

    return parts
