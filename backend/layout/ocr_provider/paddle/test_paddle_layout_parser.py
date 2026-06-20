# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PaddleOCR layout parser: JSONL -> LayoutDocument."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.ocr_provider.paddle.layout_parser import (
    parse_paddle_layout,
    extract_paddle_markdown,
    _PADDLE_IMAGE_PATH_SENTINEL,
    _resolve_paddle_render_dimensions,
)

# Fixture matching the actual PaddleOCR v2 API response structure:
#   layoutParsingResults[page_idx].dataInfo.pages[*]
#   layoutParsingResults[page_idx].layoutParsingResults[0].prunedResult.parsing_res_list
SAMPLE_PAYLOAD = {
    "layoutParsingResults": [
        {
            "dataInfo": {"pages": [{"width": 612, "height": 792}]},
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "doc_title",
                                "block_bbox": [72, 90, 540, 120],
                                "block_content": "Document Title",
                            },
                            {
                                "block_label": "text",
                                "block_bbox": [72, 140, 540, 300],
                                "block_content": "This is body text.",
                            },
                            {
                                "block_label": "image",
                                "block_bbox": [72, 320, 540, 500],
                                "block_content": "",
                            },
                            {
                                "block_label": "table",
                                "block_bbox": [72, 520, 540, 700],
                                "block_content": "<table>...</table>",
                            },
                        ]
                    }
                }
            ],
        }
    ],
    "markdown": {"text": "# Document Title\n\nThis is body text.\n\n![image](1_0.jpg)\n\n<table>...</table>"},
}

# Fixture with image dimensions different from PDF dimensions (simulates a
# high-DPI render where PaddleOCR returns pixel coordinates).
SAMPLE_PAYLOAD_SCALED = {
    "layoutParsingResults": [
        {
            "dataInfo": {"pages": [{"width": 2560, "height": 3300}]},
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "text",
                                "block_bbox": [288, 360, 2160, 1200],
                                "block_content": "Scaled text.",
                            },
                        ]
                    }
                }
            ],
        }
    ],
    "markdown": {"text": "Scaled text."},
}


def test_parse_paddle_layout_basic():
    """Parse a basic PaddleOCR result payload."""
    doc = parse_paddle_layout(SAMPLE_PAYLOAD)
    assert doc is not None
    assert doc.engine == "paddle"
    assert doc.page_count == 1

    page = doc.pages[0]
    assert page.width == 612
    assert page.height == 792
    assert len(page.blocks) == 4

    # doc_title block
    b0 = page.blocks[0]
    assert b0.type == "title"
    assert b0.sub_type == "title"
    assert "heading" in b0.tags
    assert b0.should_translate is True
    assert b0.text == "Document Title"

    # text block
    b1 = page.blocks[1]
    assert b1.type == "text"
    assert b1.sub_type == "body"
    assert b1.should_translate is True

    # image block — must have sentinel image_path so has_image() returns True
    b2 = page.blocks[2]
    assert b2.type == "image"
    assert b2.image_path == _PADDLE_IMAGE_PATH_SENTINEL
    assert b2.has_image() is True
    assert "skip_translation" in b2.tags
    assert b2.should_translate is False

    # table block
    b3 = page.blocks[3]
    assert b3.type == "table"
    assert b3.should_translate is False


def test_bbox_normalization_with_pdf_dims():
    """Bbox is scaled from image pixel space to PDF point space."""
    # PDF page is 612x792 pt, PaddleOCR image is 2560x3300 px
    pdf_dims = [(612.0, 792.0)]
    doc = parse_paddle_layout(SAMPLE_PAYLOAD_SCALED, pdf_page_dims=pdf_dims)
    assert doc is not None
    block = doc.pages[0].blocks[0]

    # Original bbox in pixels: [288, 360, 2160, 1200]
    # scale_x = 612/2560 = 0.2390625  → round after scale to 3 decimals
    # scale_y = 792/3300 = 0.24
    # Expected (rounded to 3 decimal places):
    #   288 * 0.2390625 = 68.85  → round(68.85, 3) = 68.85
    #   360 * 0.24 = 86.4        → round(86.4, 3) = 86.4
    #   2160 * 0.2390625 = 516.375 → round(516.375, 3) = 516.375
    #   1200 * 0.24 = 288.0      → round(288.0, 3) = 288.0
    assert block.bbox == (68.85, 86.4, 516.375, 288.0)

    # Page dimensions stored are PDF point dimensions
    page = doc.pages[0]
    assert page.width == 612.0
    assert page.height == 792.0


def test_bbox_no_normalization_when_dims_match():
    """Bbox is unchanged when image and PDF dimensions are the same."""
    pdf_dims = [(612.0, 792.0)]
    doc = parse_paddle_layout(SAMPLE_PAYLOAD, pdf_page_dims=pdf_dims)
    block = doc.pages[0].blocks[0]
    # image_w=612, pdf_w=612 → scale=1.0
    assert block.bbox == (72.0, 90.0, 540.0, 120.0)


def test_bbox_no_normalization_without_pdf_dims():
    """Bbox is unchanged when pdf_page_dims is not provided."""
    doc = parse_paddle_layout(SAMPLE_PAYLOAD_SCALED)
    block = doc.pages[0].blocks[0]
    # bbox stays in pixel space since no pdf_dims provided
    assert block.bbox == (288.0, 360.0, 2160.0, 1200.0)


def test_parse_paddle_layout_engine_param():
    """Engine parameter flows through to LayoutDocument."""
    doc = parse_paddle_layout(SAMPLE_PAYLOAD, engine="paddle-v2")
    assert doc.engine == "paddle-v2"


def test_extract_paddle_markdown():
    """Markdown text extraction from payload."""
    md = extract_paddle_markdown(SAMPLE_PAYLOAD)
    assert "Document Title" in md
    assert "body text" in md


def test_extract_paddle_markdown_string():
    """Markdown field can be a plain string."""
    md = extract_paddle_markdown({"markdown": "plain markdown text"})
    assert md == "plain markdown text"


def test_extract_paddle_markdown_empty():
    """Empty payload returns empty string."""
    md = extract_paddle_markdown({})
    assert md == ""


def test_parse_empty_payload():
    """Empty payload returns empty LayoutDocument."""
    doc = parse_paddle_layout({})
    assert doc is not None
    assert doc.page_count == 0


def test_parse_payload_no_parsing_results():
    """Payload without layoutParsingResults returns empty doc."""
    doc = parse_paddle_layout({})
    assert doc is not None
    assert doc.page_count == 0


def test_global_block_indices():
    """Block indices are globally unique across pages."""
    multi_page = {
        "layoutParsingResults": [
            {
                "dataInfo": {"pages": [{}]},
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "parsing_res_list": [
                                {"block_label": "text", "block_bbox": [0, 0, 100, 100], "block_content": "p1"},
                                {"block_label": "text", "block_bbox": [0, 100, 100, 200], "block_content": "p1b"},
                            ]
                        }
                    }
                ],
            },
            {
                "dataInfo": {"pages": [{}]},
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "parsing_res_list": [
                                {"block_label": "text", "block_bbox": [0, 0, 100, 100], "block_content": "p2"},
                            ]
                        }
                    }
                ],
            },
        ],
    }
    doc = parse_paddle_layout(multi_page)
    assert doc.page_count == 2
    indices = [b.index for b in doc.iter_blocks()]
    assert indices == [0, 1, 2]
    assert len(set(indices)) == 3


# Fixture: dataInfo.pages[*] does not include width/height.
# The parser should infer image dimensions from the max bbox extent.
SAMPLE_PAYLOAD_MISSING_DIMS = {
    "layoutParsingResults": [
        {
            "dataInfo": {"pages": [{}]},
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "text",
                                "block_bbox": [72, 90, 540, 500],
                                "block_content": "Body text.",
                            },
                            {
                                "block_label": "table",
                                "block_bbox": [72, 520, 540, 700],
                                "block_content": "<table>...</table>",
                            },
                        ]
                    }
                }
            ],
        }
    ],
    "markdown": {"text": "Body text.\n\n<table>...</table>"},
}


def test_bbox_scaling_with_missing_image_dims():
    """When dataInfo omits dims and bbox fits PDF page, treat bbox as PDF points."""
    pdf_dims = [(595.0, 842.0)]
    doc = parse_paddle_layout(SAMPLE_PAYLOAD_MISSING_DIMS, pdf_page_dims=pdf_dims)
    assert doc is not None
    assert doc.page_count == 1
    page = doc.pages[0]
    assert page.width == 595.0
    assert page.height == 842.0

    block = page.blocks[0]
    # Bbox values are already in PDF point space — no erroneous upscaling.
    assert block.bbox == (72.0, 90.0, 540.0, 500.0)


def test_bbox_scaling_when_datainfo_reports_pdf_dims_but_bbox_is_pixels():
    """dataInfo may report PDF pt while block_bbox stays in render pixels."""
    payload = {
        "layoutParsingResults": [
            {
                # Wrong: reports PDF dimensions instead of render pixel size.
                "dataInfo": {"pages": [{"width": 612, "height": 792}]},
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "parsing_res_list": [
                                {
                                    "block_label": "text",
                                    "block_bbox": [288, 360, 2160, 1200],
                                    "block_content": "Scaled text.",
                                },
                            ]
                        }
                    }
                ],
            }
        ],
    }
    pdf_dims = [(612.0, 792.0)]
    doc = parse_paddle_layout(payload, pdf_page_dims=pdf_dims)
    block = doc.pages[0].blocks[0]
    # render_w=2160 from bbox; height synced to PDF aspect → 2160/(612/792)=2796.19
    assert block.bbox == (81.6, 102.0, 612.0, 340.0)


def test_bbox_height_when_datainfo_pixel_aspect_differs_from_pdf():
    """Pixel dataInfo height inflated vs PDF aspect — Y scale was too small."""
    payload = {
        "layoutParsingResults": [
            {
                "dataInfo": {"pages": [{"width": 2480, "height": 3300}]},
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "parsing_res_list": [
                                {
                                    "block_label": "table",
                                    "block_bbox": [120, 180, 2300, 420],
                                    "block_content": "<table>...</table>",
                                },
                                {
                                    "block_label": "text",
                                    "block_bbox": [120, 2800, 2300, 3100],
                                    "block_content": "Footer text",
                                },
                            ]
                        }
                    }
                ],
            }
        ],
    }
    pdf_dims = [(612.0, 792.0)]
    doc = parse_paddle_layout(payload, pdf_page_dims=pdf_dims)
    table = doc.pages[0].blocks[0]
    uniform_scale = 612.0 / 2480.0
    expected_h = round((420.0 - 180.0) * uniform_scale, 3)
    actual_h = round(table.bbox[3] - table.bbox[1], 3)
    assert actual_h == expected_h


def test_sync_render_canvas_aspect_ratio_width_authoritative():
    from layout.ocr_provider.paddle.layout_parser import _sync_render_canvas_aspect_ratio

    w, h = _sync_render_canvas_aspect_ratio(
        2160.0,
        792.0,
        612.0,
        792.0,
        max_x1=2160.0,
        max_y1=680.0,
    )
    assert w == 2160.0
    assert abs(h - (2160.0 * 792.0 / 612.0)) < 0.1


def test_resolve_paddle_render_dimensions_datainfo_pdf_bbox_pixels():
    render_w, render_h, already_pt = _resolve_paddle_render_dimensions(
        612,
        792,
        max_x1=2160.0,
        max_y1=1200.0,
        pdf_w_pt=612.0,
        pdf_h_pt=792.0,
    )
    assert already_pt is False
    assert render_w == 2160.0
    assert abs(render_h - (2160.0 * 792.0 / 612.0)) < 0.2


def test_resolve_paddle_render_dimensions_bbox_already_pdf_pt():
    render_w, render_h, already_pt = _resolve_paddle_render_dimensions(
        None,
        None,
        max_x1=540.0,
        max_y1=700.0,
        pdf_w_pt=595.0,
        pdf_h_pt=842.0,
    )
    assert already_pt is True
    assert render_w == 595.0
    assert render_h == 842.0


def test_bbox_no_scaling_without_pdf_dims_missing_image_dims():
    """Without pdf_page_dims, bbox is unchanged even when image dims are missing."""
    doc = parse_paddle_layout(SAMPLE_PAYLOAD_MISSING_DIMS)
    block = doc.pages[0].blocks[0]
    assert block.bbox == (72.0, 90.0, 540.0, 500.0)


if __name__ == "__main__":
    test_parse_paddle_layout_basic()
    test_bbox_normalization_with_pdf_dims()
    test_bbox_no_normalization_when_dims_match()
    test_bbox_no_normalization_without_pdf_dims()
    test_parse_paddle_layout_engine_param()
    test_extract_paddle_markdown()
    test_extract_paddle_markdown_string()
    test_extract_paddle_markdown_empty()
    test_parse_empty_payload()
    test_parse_payload_no_parsing_results()
    test_global_block_indices()
    test_bbox_scaling_with_missing_image_dims()
    test_bbox_scaling_when_datainfo_reports_pdf_dims_but_bbox_is_pixels()
    test_bbox_height_when_datainfo_pixel_aspect_differs_from_pdf()
    test_sync_render_canvas_aspect_ratio_width_authoritative()
    test_resolve_paddle_render_dimensions_datainfo_pdf_bbox_pixels()
    test_resolve_paddle_render_dimensions_bbox_already_pdf_pt()
    test_bbox_no_scaling_without_pdf_dims_missing_image_dims()
    print("Paddle layout parser tests passed")
