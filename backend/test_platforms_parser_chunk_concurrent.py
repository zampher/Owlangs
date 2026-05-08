# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests: parser platforms omit chunk_size/concurrent from platforms.json semantics."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from backend.config.platforms_config import (  # noqa: E402
    AIPlatformConfig,
    PlatformsConfig,
    platform_type_uses_llm_chunk_concurrent,
)


def test_platform_type_uses_llm_chunk_concurrent():
    assert platform_type_uses_llm_chunk_concurrent("llm") is True
    assert platform_type_uses_llm_chunk_concurrent("parser") is False
    assert platform_type_uses_llm_chunk_concurrent(None) is True


def test_get_config_dict_omits_chunk_for_parser():
    cfg = PlatformsConfig()
    cfg.platforms["mineru"] = AIPlatformConfig(
        name="MinerU (Cloud)",
        url="https://example.com",
        model="vlm",
        platform_type="parser",
        parser_subtype="cloud",
        chunk_size=9999,
        concurrent=8,
    )
    d = cfg.get_config_dict()
    inner = d["platforms"]["mineru"]
    assert "chunk_size" not in inner
    assert "concurrent" not in inner
    assert inner["platform_type"] == "parser"


def test_get_config_dict_keeps_chunk_for_llm():
    cfg = PlatformsConfig()
    cfg.platforms["deepseek"] = AIPlatformConfig(
        name="DeepSeek",
        url="https://api.deepseek.com",
        model="deepseek-chat",
        platform_type="llm",
        chunk_size=4000,
        concurrent=3,
    )
    d = cfg.get_config_dict()
    inner = d["platforms"]["deepseek"]
    assert inner.get("chunk_size") == 4000
    assert inner.get("concurrent") == 3


def test_update_from_dict_strips_chunk_for_parser_json():
    cfg = PlatformsConfig()
    cfg.update_from_dict(
        {
            "_schema_version": 1,
            "default_platform": "mineru",
            "platforms": {
                "mineru": {
                    "name": "M",
                    "url": "http://x",
                    "model": "vlm",
                    "platform_type": "parser",
                    "chunk_size": 7777,
                    "concurrent": 9,
                }
            },
        }
    )
    assert cfg.platforms["mineru"].chunk_size == 3000
    assert cfg.platforms["mineru"].concurrent == 5


if __name__ == "__main__":
    test_platform_type_uses_llm_chunk_concurrent()
    test_get_config_dict_omits_chunk_for_parser()
    test_get_config_dict_keeps_chunk_for_llm()
    test_update_from_dict_strips_chunk_for_parser_json()
    print("platforms parser chunk/concurrent tests passed")
