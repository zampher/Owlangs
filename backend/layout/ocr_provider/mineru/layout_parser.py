# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MinerU layout parser — OCR-provider entry point.

Delegates to the full MinerU parser in :mod:`layout.mineru_layout_model`.
"""

from typing import Optional

from layout.base import LayoutDocument
from layout.mineru_layout_model import parse_mineru_layout_from_zip_bytes as _parse


def parse_mineru_layout_from_zip_bytes(zip_bytes: bytes, engine: str = "mineru") -> Optional[LayoutDocument]:
    """Parse MinerU layout from ZIP bytes. Delegates to the canonical parser."""
    return _parse(zip_bytes, engine=engine)
