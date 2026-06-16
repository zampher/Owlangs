# SPDX-FileCopyrightText: 2026 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for MinerU version extraction helpers."""

from backend.auth.mineru_test_utils import (
    build_health_probe_urls,
    enrich_mineru_test_result,
    extract_version_from_health_payload,
    extract_version_from_payload,
    infer_cloud_api_version,
)


def test_extract_version_from_health_payload() -> None:
    assert extract_version_from_health_payload({"version": "2.1.0"}) == "2.1.0"
    assert extract_version_from_health_payload({"mineru_version": "2.1.0"}) == "2.1.0"
    assert extract_version_from_health_payload({"status": "healthy"}) is None
    assert extract_version_from_health_payload("invalid") is None


def test_extract_version_from_payload_nested() -> None:
    payload = {"code": 0, "data": {"version": "3.2.1"}}
    assert extract_version_from_payload(payload) == "3.2.1"


def test_build_health_probe_urls() -> None:
    urls = build_health_probe_urls("http://127.0.0.1:8000/api/v4")
    assert "http://127.0.0.1:8000/api/v4/health" in urls
    assert "http://127.0.0.1:8000/health" in urls


def test_infer_cloud_api_version() -> None:
    assert infer_cloud_api_version("https://mineru.net/api/v4") == "v4"
    assert infer_cloud_api_version("https://mineru.net") == "v4"
    assert infer_cloud_api_version("http://127.0.0.1:8000") is None


def test_enrich_mineru_test_result_success_only() -> None:
    base = {"success": True, "message": "ok"}
    enriched = enrich_mineru_test_result(
        base,
        mineru_version="2.1.0",
        api_version="v4",
        model_version="hybrid-auto-engine",
    )
    assert enriched["mineru_version"] == "2.1.0"
    assert enriched["api_version"] == "v4"
    assert enriched["model_version"] == "hybrid-auto-engine"
    assert "version: 2.1.0" in enriched["message"]

    failed = enrich_mineru_test_result({"success": False, "message": "fail"}, mineru_version="1.0")
    assert "mineru_version" not in failed
