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
    build_platform_config_from_dict,
    infer_parser_engine,
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
        model="hybrid-auto-engine",
        platform_type="parser",
        parser_subtype="cloud",
        chunk_size=9999,
        concurrent=8,
    )
    d = cfg.get_config_dict()
    inner = d["platforms"]["mineru"]
    assert "chunk_size" not in inner
    # concurrent is now valid for parser platforms (controls PDF fragment concurrency)
    assert inner["concurrent"] == 8
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
    # concurrent is now preserved for parser platforms
    assert cfg.platforms["mineru"].concurrent == 9
    assert cfg.platforms["mineru"].parser_engine == "mineru"


def test_get_config_dict_omits_parser_fields_for_llm():
    cfg = PlatformsConfig()
    cfg.platforms["deepseek"] = AIPlatformConfig(
        name="DeepSeek",
        url="https://api.deepseek.com",
        model="deepseek-chat",
        platform_type="llm",
        parser_engine="mineru",
        parser_subtype="cloud",
        use_doc_orientation_classify=True,
        api_endpoints={"submit": "/ocr"},
    )
    inner = cfg.get_config_dict()["platforms"]["deepseek"]
    assert "parser_engine" not in inner
    assert "parser_subtype" not in inner
    assert "use_doc_orientation_classify" not in inner
    assert "restructure_pages" not in inner
    assert "api_endpoints" not in inner


def test_build_platform_config_preserves_parser_engine():
    cfg = build_platform_config_from_dict(
        "paddle_local",
        {
            "name": "PaddleOCR (Local)",
            "url": "http://localhost:8099",
            "platform_type": "parser",
            "parser_subtype": "local",
        },
    )
    assert cfg.parser_engine == "paddle"
    assert cfg.parser_subtype == "local"


def test_build_platform_config_strips_parser_fields_for_llm():
    cfg = build_platform_config_from_dict(
        "deepseek",
        {
            "name": "DeepSeek",
            "url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "platform_type": "llm",
            "parser_engine": "mineru",
            "parser_subtype": "cloud",
            "api_endpoints": {"x": "y"},
        },
    )
    assert cfg.parser_engine is None
    assert cfg.parser_subtype is None
    assert cfg.api_endpoints == {}


def test_infer_parser_engine():
    assert infer_parser_engine("mineru", None, "parser") == "mineru"
    assert infer_parser_engine("paddle_local", None, "parser") == "paddle"
    assert infer_parser_engine("deepseek", None, "llm") is None


def test_sanitize_platforms_json_root_strips_parser_fields_for_llm():
    from backend.config.platforms_config import sanitize_platforms_json_root

    data = {
        "_schema_version": 1,
        "default_platform": "deepseek",
        "platforms": {
            "deepseek": {
                "name": "DeepSeek",
                "url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "platform_type": "llm",
                "parser_subtype": None,
                "api_endpoints": {},
            },
            "mineru": {
                "name": "MinerU",
                "url": "https://mineru.net",
                "platform_type": "parser",
                "parser_subtype": "cloud",
                "api_endpoints": {"submit": "/ocr"},
            },
        },
    }
    sanitized = sanitize_platforms_json_root(data)
    llm = sanitized["platforms"]["deepseek"]
    parser = sanitized["platforms"]["mineru"]
    assert "parser_subtype" not in llm
    assert "api_endpoints" not in llm
    assert parser["parser_subtype"] == "cloud"
    assert parser["api_endpoints"] == {"submit": "/ocr"}


def test_ai_platforms_api_omits_parser_fields_for_llm():
    from backend.config.config_loader import UnifiedConfig
    from backend.config.platforms_config import AIPlatformConfig, PlatformsConfig

    platforms = PlatformsConfig()
    platforms.platforms["deepseek"] = AIPlatformConfig(
        name="DeepSeek",
        url="https://api.deepseek.com",
        model="deepseek-chat",
        platform_type="llm",
        parser_subtype="cloud",
        api_endpoints={"submit": "/ocr"},
    )
    cfg = UnifiedConfig.__new__(UnifiedConfig)
    cfg.platforms = platforms
    cfg.secrets = None
    payload = cfg.ai_platforms["deepseek"]
    assert "parser_subtype" not in payload
    assert "api_endpoints" not in payload


if __name__ == "__main__":
    test_platform_type_uses_llm_chunk_concurrent()
    test_get_config_dict_omits_chunk_for_parser()
    test_get_config_dict_keeps_chunk_for_llm()
    test_update_from_dict_strips_chunk_for_parser_json()
    test_get_config_dict_omits_parser_fields_for_llm()
    test_build_platform_config_preserves_parser_engine()
    test_build_platform_config_strips_parser_fields_for_llm()
    test_infer_parser_engine()
    print("platforms parser chunk/concurrent tests passed")
