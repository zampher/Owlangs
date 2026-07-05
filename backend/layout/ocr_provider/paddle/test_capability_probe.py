# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PaddleOCR capability probe."""

from layout.ocr_provider.paddle.capability_probe import (
    CAPABILITY_TEXT_OCR_ONLY,
    CAPABILITY_VL_LAYOUT,
    analyze_openapi_paths,
    analyze_probe_payload,
    build_paddle_test_user_message,
)


def test_analyze_probe_payload_text_only_rec_texts():
    payload = {
        "result": {
            "ocrResults": [
                {
                    "prunedResult": {
                        "rec_texts": ["Hello"],
                        "rec_boxes": [[0, 0, 10, 10]],
                    }
                }
            ]
        }
    }
    cap = analyze_probe_payload(payload)
    assert cap["capability_level"] == CAPABILITY_TEXT_OCR_ONLY
    assert cap["document_parsing_capable"] is False
    assert cap["warning_code"] == "paddle_text_ocr_only"


def test_analyze_probe_payload_vl_layout():
    payload = {
        "result": {
            "layoutParsingResults": [
                {
                    "layoutParsingResults": [
                        {
                            "prunedResult": {
                                "parsing_res_list": [
                                    {
                                        "block_label": "doc_title",
                                        "block_content": "Title",
                                        "block_bbox": [0, 0, 100, 20],
                                    },
                                    {
                                        "block_label": "text",
                                        "block_content": "Body",
                                        "block_bbox": [0, 30, 100, 50],
                                    },
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    }
    cap = analyze_probe_payload(payload)
    assert cap["capability_level"] == CAPABILITY_VL_LAYOUT
    assert cap["document_parsing_capable"] is True
    assert cap["warning_code"] is None


def test_analyze_probe_payload_flat_layout_parsing():
    payload = {
        "result": {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "text",
                                "block_content": "Probe",
                                "block_bbox": [0, 0, 50, 20],
                            }
                        ]
                    }
                }
            ]
        }
    }
    cap = analyze_probe_payload(payload)
    assert cap["capability_level"] == CAPABILITY_VL_LAYOUT
    assert cap["document_parsing_capable"] is True


def test_analyze_openapi_paths_cloud_vs_sync():
    cloud = analyze_openapi_paths({"/api/v2/ocr/jobs": {}, "/health": {}})
    assert cloud["has_cloud_jobs_api"] is True
    assert cloud["api_style"] == "cloud_async"

    sync = analyze_openapi_paths({"/layout-parsing": {}, "/health": {}})
    assert sync["has_sync_infer_api"] is True
    assert sync["api_style"] == "sync_infer"


def test_build_paddle_test_user_message_text_only_warning():
    msg = build_paddle_test_user_message(
        platform="paddle_local",
        base="http://127.0.0.1:8080",
        capability={
            "capability_level": CAPABILITY_TEXT_OCR_ONLY,
            "document_parsing_capable": False,
            "layout_block_labels": ["text"],
            "warning_code": "paddle_text_ocr_only",
        },
        api_style="sync_infer",
        reachable=True,
    )
    assert "basic text OCR" in msg
    assert "PaddleOCR-VL-1.6" in msg
