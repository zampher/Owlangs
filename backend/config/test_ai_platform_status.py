# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for AI platform status helpers."""

from backend.config.ai_platform_status import (
    platform_test_is_api_available,
    platform_test_status_error,
)


def test_platform_test_is_api_available_paddle_text_only():
    result = {
        "success": True,
        "document_parsing_capable": False,
        "message": "text OCR only",
    }
    assert platform_test_is_api_available(result) is False
    assert platform_test_status_error(result) == "text OCR only"


def test_platform_test_is_api_available_paddle_vl():
    result = {
        "success": True,
        "document_parsing_capable": True,
    }
    assert platform_test_is_api_available(result) is True
    assert platform_test_status_error(result) is None


def test_platform_test_is_api_available_llm_success():
    result = {"success": True, "message": "ok"}
    assert platform_test_is_api_available(result) is True
