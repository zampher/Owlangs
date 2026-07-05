# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PaddleOCR local sync infer adapter and client mode detection."""

from layout.ocr_provider.paddle.api_client import PaddleOCRClient
from layout.ocr_provider.paddle.sync_infer_adapter import (
    is_sync_infer_submit_path,
    normalize_sync_infer_response,
)


def test_is_sync_infer_submit_path():
    assert is_sync_infer_submit_path("/ocr") is True
    assert is_sync_infer_submit_path("/layout-parsing") is True
    assert is_sync_infer_submit_path("/api/v2/ocr/jobs") is False


def test_normalize_sync_infer_response_from_rec_boxes():
    payload = {
        "result": {
            "dataInfo": {"pages": [{"width": 100, "height": 200}]},
            "ocrResults": [
                {
                    "prunedResult": {
                        "rec_texts": ["Hello", "World"],
                        "rec_boxes": [[1, 2, 3, 4], [5, 6, 7, 8]],
                    }
                }
            ],
        }
    }
    out = normalize_sync_infer_response(payload)
    blocks = out["layoutParsingResults"][0]["layoutParsingResults"][0]["prunedResult"]["parsing_res_list"]
    assert len(blocks) == 2
    assert blocks[0]["block_content"] == "Hello"
    assert blocks[0]["block_bbox"] == [1.0, 2.0, 3.0, 4.0]


def test_normalize_sync_infer_response_flat_layout_parsing():
    """Local /layout-parsing returns prunedResult directly on each page item."""
    payload = {
        "result": {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "width": 595,
                        "height": 842,
                        "parsing_res_list": [
                            {
                                "block_label": "doc_title",
                                "block_content": "Title",
                                "block_bbox": [10, 20, 100, 40],
                            }
                        ],
                    },
                    "markdown": {"text": "# Title"},
                }
            ]
        }
    }
    out = normalize_sync_infer_response(payload)
    page = out["layoutParsingResults"][0]
    assert page["dataInfo"]["pages"][0]["width"] == 595
    blocks = page["layoutParsingResults"][0]["prunedResult"]["parsing_res_list"]
    assert blocks[0]["block_label"] == "doc_title"


def test_paddle_client_detects_sync_infer_mode():
    client = PaddleOCRClient(
        token="",
        base_url="http://127.0.0.1:8080",
        api_endpoints={"submit": "/layout-parsing", "result": "/layout-parsing/{job_id}/result"},
    )
    assert client._sync_infer_mode is True
