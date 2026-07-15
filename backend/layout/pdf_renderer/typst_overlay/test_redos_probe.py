# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Probe script for math delimiter regex performance (run manually)."""

import re
import time

INLINE_MATH_RE = re.compile(
    r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
    re.DOTALL,
)


def bench(label: str, text: str, timeout: float = 2.0) -> None:
    t0 = time.perf_counter()
    INLINE_MATH_RE.sub(lambda m: m.group(0), text)
    elapsed = time.perf_counter() - t0
    print(f"{label}: len={len(text)} elapsed={elapsed:.4f}s")
    assert elapsed < timeout, f"{label} too slow: {elapsed:.2f}s"


if __name__ == "__main__":
    bench("paired", "$x$ " * 50)
    bench("unpaired_tail", "$" + "a" * 200 + "$" * 30, timeout=5.0)
