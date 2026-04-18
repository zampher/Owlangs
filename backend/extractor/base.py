# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class ExtractResult:
    segments: List[str]
    separators_after: Optional[List[Optional[str]]] = None
    segment_info: Optional[List[dict]] = None  # Per-segment metadata (format-specific)

    @property
    def total_segments(self) -> int:
        return len(self.segments)


class Extractor(Protocol):
    def extract(self) -> ExtractResult:
        ...


