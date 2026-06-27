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

build_seg_user_prompt_from_texts = mod.build_seg_user_prompt_from_texts

parse_seg_output = mod.parse_seg_output

parse_seg_output_to_global = mod.parse_seg_output_to_global

map_local_parse_to_global = mod.map_local_parse_to_global





def test_build_seg_user_prompt_uses_local_indices():

    prompt = build_seg_user_prompt({"0": "A", "2": "B", "5": "C"})

    assert "[SEG 0]:" in prompt

    assert "[SEG 1]:" in prompt

    assert "[SEG 2]:" in prompt

    assert "[SEG 5]:" not in prompt

    assert "3 segment(s)" in prompt

    assert "[SEG 0] through [SEG 2]" in prompt

    print("PASS test_build_seg_user_prompt_uses_local_indices")





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





def test_map_local_to_global_skipped_segment_indices():

    """Simulate excluded segment 10: globals [9, 11] with local prompt 0, 1."""

    global_indices = [9, 11]

    prompt = build_seg_user_prompt_from_texts(["seg nine", "seg eleven"])

    assert "[SEG 0]:" in prompt

    assert "[SEG 1]:" in prompt

    assert "[SEG 9]:" not in prompt

    assert "[SEG 11]:" not in prompt



    # Model returns correct local IDs

    llm_ok = "[SEG 0]:\ntrans nine\n[SEG 1]:\ntrans eleven"

    mapped_ok = parse_seg_output_to_global(llm_ok, global_indices)

    assert mapped_ok[9] == "trans nine"

    assert mapped_ok[11] == "trans eleven"



    # Model invents continuous global-style IDs (old failure mode)

    llm_wrong = "[SEG 9]:\ntrans nine\n[SEG 10]:\ntrans eleven"

    mapped_wrong = parse_seg_output_to_global(llm_wrong, global_indices)

    assert 11 not in mapped_wrong



    # Model returns local IDs — position mapping

    llm_local = "[SEG 0]:\ntrans nine\n[SEG 1]:\ntrans eleven"

    mapped_local = map_local_parse_to_global(parse_seg_output(llm_local), global_indices)

    assert mapped_local[9] == "trans nine"

    assert mapped_local[11] == "trans eleven"

    print("PASS test_map_local_to_global_skipped_segment_indices")





if __name__ == "__main__":

    test_build_seg_user_prompt_uses_local_indices()

    test_parse_seg_output_handles_markdown_bold_header()

    test_map_local_to_global_skipped_segment_indices()

    print("\nAll seg_prompt_utils tests passed!")


