# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for image placeholder replacement during export."""

import base64

from utils.image_placeholder_utils import _replace_placeholders_with_images


def _sample_image_map(path_key: str) -> dict:
    raw = b"\xff\xd8\xff"
    b64 = base64.b64encode(raw).decode("ascii")
    return {
        path_key: {
            "data": f"data:image/jpeg;base64,{b64}",
            "mime": "image/jpeg",
            "alt": "cover.jpg",
        }
    }


def test_replace_ph_placeholder_with_fuzzy_path_match():
    md = "intro\n<ph-mobi7/Images/cover.jpg>\noutro"
    image_map = _sample_image_map("Images/cover.jpg")
    out, _ = _replace_placeholders_with_images(md, image_map)
    assert "<ph-" not in out
    assert "![cover.jpg](data:image/jpeg;base64," in out


def test_replace_html_extractor_image_line():
    md = "before\n[Image: Images/cover.jpg]\nafter"
    image_map = _sample_image_map("Images/cover.jpg")
    out, _ = _replace_placeholders_with_images(md, image_map)
    assert "[Image:" not in out
    assert "![cover.jpg](data:image/jpeg;base64," in out


def test_replace_html_extractor_image_line_fuzzy_match():
    md = "[Image: mobi7/Images/cover.jpg]"
    image_map = _sample_image_map("Images/cover.jpg")
    out, _ = _replace_placeholders_with_images(md, image_map)
    assert "[Image:" not in out
    assert "data:image/jpeg;base64," in out
