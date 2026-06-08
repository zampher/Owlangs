# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for SEG-tag prompt helpers."""

import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent
_root = _backend.parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import module directly to avoid agents package __init__ side effects
import importlib.util
spec = importlib.util.spec_from_file_location(
    "seg_prompt_utils",
    _backend / "agents" / "seg_prompt_utils.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
build_seg_user_prompt = mod.build_seg_user_prompt
parse_seg_output = mod.parse_seg_output


def test_build_seg_user_prompt_includes_segment_count():
    prompt = build_seg_user_prompt({"0": "A", "2": "B", "5": "C"})
    assert "[SEG 0]:" in prompt
    assert "[SEG 2]:" in prompt
    assert "3 segment(s)" in prompt
    assert "[SEG 0] through [SEG 5]" in prompt
    print("PASS test_build_seg_user_prompt_includes_segment_count")


def test_parse_seg_output_handles_markdown_bold_header():
    raw = """Here are translations:

**[SEG 34]**
To protect Party A...

**[SEG 35]**
Price regulations
"""
    parsed = parse_seg_output(raw)
    assert 34 in parsed
    assert 35 in parsed
    assert "Party A" in parsed[34]
    print("PASS test_parse_seg_output_handles_markdown_bold_header")


if __name__ == "__main__":
    test_build_seg_user_prompt_includes_segment_count()
    test_parse_seg_output_handles_markdown_bold_header()
    print("\nAll seg_prompt_utils tests passed!")
