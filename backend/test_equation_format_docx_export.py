# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for equation_format=image on DOCX export path."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.exporter.md.md2docx_exporter import MD2DOCXExporter, MD2DOCXExporterConfig
from utils.document_rebuild.markdown_rebuild import _recover_layout_block_indices_from_prepared_chunks


def test_recover_layout_block_indices_from_prepared_chunks():
    segments = [
        {"segment_index": 0, "target_text": "intro"},
        {"segment_index": 1, "target_text": r"$$\tag{1}$$"},
        {"segment_index": 2, "target_text": "body"},
    ]
    task_state = {
        "layout_prepared_chunks": [
            {"segment_indices": [0], "block_indices": [3]},
            {"segment_indices": [1], "block_indices": [1]},
            {"segment_indices": [2], "block_indices": [4, 5]},
        ]
    }
    recovered = _recover_layout_block_indices_from_prepared_chunks(segments, task_state)
    assert recovered == 3
    assert segments[1]["layout_block_indices"] == [1]


def test_md2docx_equation_format_image_uses_layout_image_not_omml():
    layout_doc = MagicMock()
    eq_block = MagicMock()
    eq_block.type = "interline_equation"
    eq_block.text = r"\sum x"
    eq_block.raw = {
        "lines": [
            {
                "spans": [
                    {
                        "type": "interline_equation",
                        "content": r"\sum x",
                        "image_path": "images/eq_001.jpg",
                    }
                ]
            }
        ]
    }
    eq_block.image_path = None
    layout_doc.iter_blocks.return_value = [eq_block]

    config = MD2DOCXExporterConfig(
        layout_document=layout_doc,
        equation_format="image",
        image_data_map={
            "eq_001.jpg": {"data": "data:image/png;base64,AAAA", "alt": "Equation"},
        },
    )
    exporter = MD2DOCXExporter(config)
    docx_doc = MagicMock()

    md = "$$\n\\sum x\n$$\n\nParagraph text.\n"
    with patch.object(exporter, "_add_math_formula") as mock_omml:
        with patch.object(exporter, "_add_image_from_markdown", return_value=True) as mock_img:
            exporter._markdown_to_docx_with_layout(md, docx_doc)
            mock_omml.assert_not_called()
            mock_img.assert_called_once()
            assert "eq_001.jpg" in mock_img.call_args[0][1]


def test_populate_image_data_map_from_extracted_registers_hash_filenames():
    from backend.app.services.download.download_service import _populate_image_data_map_from_extracted

    hash_name = "39f42939f5b601fe1714e383b8e008a5dfc8d09666acc210fbd5703c9d8a742e.jpg"
    images_bytes_map = {f"images/{hash_name}": b"\xff\xd8\xff fake jpeg"}
    image_data_map: dict = {}
    _populate_image_data_map_from_extracted(image_data_map, images_bytes_map)
    assert hash_name in image_data_map
    assert image_data_map[hash_name]["data"].startswith("data:image/")


def test_format_requires_md2docx_table_image():
    from backend.app.services.download.download_service import _format_requires_md2docx

    assert _format_requires_md2docx("text", "image") is True
    assert _format_requires_md2docx("image", "html") is True
    assert _format_requires_md2docx("text", "html") is False


def test_resolve_export_format_settings_from_task_state():
    from backend.app.services.download.download_service import _resolve_export_format_settings

    task_state = {"equation_format": "text", "table_body_format": "image"}
    eq, tbl = _resolve_export_format_settings(task_state)
    assert eq == "text"
    assert tbl == "image"


def test_docx_stash_download_kwargs_includes_table_image():
    from backend.app.services.download.download_service import _docx_stash_download_kwargs

    task_state = {
        "workflow_type": "markdown_based",
        "original_filename": "paper.pdf",
        "table_body_format": "image",
        "equation_format": "text",
    }
    kwargs = _docx_stash_download_kwargs(task_state)
    assert kwargs == {"equation_format": "text", "table_body_format": "image"}


def test_md2docx_table_body_format_image_inserts_table_image():
    hash_name = "f6d61e3cec4f97afa5f8dc362375b9add3f4b1835351164c110445fcc9eaf594.jpg"
    config = MD2DOCXExporterConfig(
        table_body_format="image",
        equation_format="text",
        image_data_map={
            hash_name: {"data": "data:image/jpeg;base64,AAAA", "alt": "Table"},
        },
    )
    exporter = MD2DOCXExporter(config)
    docx_doc = MagicMock()

    md = f"![Table]({hash_name})\n\nParagraph after table.\n"
    with patch.object(exporter, "_add_table") as mock_table:
        with patch.object(exporter, "_add_image_from_markdown", return_value=True) as mock_img:
            exporter._markdown_to_docx_with_layout(md, docx_doc)
            mock_table.assert_not_called()
            mock_img.assert_called_once()
            assert hash_name in mock_img.call_args[0][1]
