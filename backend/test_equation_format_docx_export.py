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


def test_resolve_export_format_settings_pdf_defaults_table_image():
    from backend.app.services.download.download_service import _resolve_export_format_settings

    task_state = {"original_filename": "paper.pdf"}
    eq, tbl = _resolve_export_format_settings(task_state)
    assert eq == "latex"
    assert tbl == "image"


def test_resolve_export_format_settings_non_pdf_defaults_table_html():
    from backend.app.services.download.download_service import _resolve_export_format_settings

    task_state = {"original_filename": "article.docx"}
    eq, tbl = _resolve_export_format_settings(task_state)
    assert eq == "text"
    assert tbl == "html"


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


def test_populate_layout_placeholder_image_map_registers_layoutimg_keys():
    import io
    import zipfile

    from layout.markdown_builder import LayoutChunk
    from backend.app.services.download.download_service import _populate_layout_placeholder_image_map

    hash_name = "abc123figure.jpg"
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"images/{hash_name}", b"\xff\xd8\xff fake jpeg")
    zip_bytes = zip_buf.getvalue()

    layout_result = MagicMock()
    layout_result.chunks = [
        LayoutChunk(
            text="<ph-layoutimg0>",
            chunk_type="image",
            block_indices=[1],
            image_path=f"images/{hash_name}",
            image_placeholder="layoutimg0",
            image_alt="Figure 1",
        ),
    ]
    task_state = {"layout_source_zip": zip_bytes, "chunk_size": 2000, "deep_split_enabled": False}
    image_data_map: dict = {}

    count = _populate_layout_placeholder_image_map(
        image_data_map,
        task_state,
        layout_doc=MagicMock(),
        layout_result=layout_result,
        equation_format="text",
        table_body_format="html",
    )

    assert count == 1
    assert "layoutimg0" in image_data_map
    assert image_data_map["layoutimg0"]["data"].startswith("data:image/")
    assert hash_name in image_data_map


def test_build_image_data_map_text_html_includes_layoutimg_for_pdf():
    import io
    import zipfile

    from layout.markdown_builder import LayoutChunk
    from backend.app.services.download.download_service import _build_image_data_map_for_format_export

    hash_name = "figure001.jpg"
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"images/{hash_name}", b"\xff\xd8\xff fake jpeg")
    zip_bytes = zip_buf.getvalue()

    layout_result = MagicMock()
    layout_result.chunks = [
        LayoutChunk(
            text="<ph-layoutimg0>",
            chunk_type="image",
            block_indices=[0],
            image_path=f"images/{hash_name}",
            image_placeholder="layoutimg0",
        ),
    ]

    with patch("layout.markdown_builder.LayoutMarkdownBuilder") as mock_builder_cls:
        mock_builder_cls.return_value.build.return_value = layout_result
        task_state = {
            "original_filename": "paper.pdf",
            "layout_document": MagicMock(),
            "layout_source_zip": zip_bytes,
            "chunk_size": 2000,
            "deep_split_enabled": False,
        }
        image_map = _build_image_data_map_for_format_export(
            task_state, md_content="", equation_format="text", table_body_format="html"
        )

    assert "layoutimg0" in image_map
    assert image_map["layoutimg0"]["data"].startswith("data:image/")


def test_populate_layout_placeholder_image_map_registers_chart_body():
    import io
    import zipfile

    from layout.markdown_builder import LayoutChunk
    from backend.app.services.download.download_service import _populate_layout_placeholder_image_map

    hash_name = "394134b7dae435eead816acd1bdff502432cdb085e50d62275c63d5233043cd5.jpg"
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"images/{hash_name}", b"\xff\xd8\xff fake jpeg")
    zip_bytes = zip_buf.getvalue()

    layout_result = MagicMock()
    layout_result.chunks = [
        LayoutChunk(
            text="![Chart](layoutimg1)",
            chunk_type="chart_body",
            block_indices=[82],
            image_path=f"images/{hash_name}",
            image_placeholder="layoutimg1",
            image_alt="Chart",
        ),
    ]
    task_state = {"layout_source_zip": zip_bytes, "chunk_size": 8000, "deep_split_enabled": False}
    image_data_map: dict = {}

    count = _populate_layout_placeholder_image_map(
        image_data_map,
        task_state,
        layout_doc=MagicMock(),
        layout_result=layout_result,
        chart_body_format="image",
    )

    assert count == 1
    assert "layoutimg1" in image_data_map
    assert image_data_map["layoutimg1"]["data"].startswith("data:image/")


def test_is_chart_body_segment_detects_layoutimg_markdown():
    from utils.document_rebuild.table_layout_utils import _is_chart_body_segment

    assert _is_chart_body_segment("![Chart](layoutimg1)", 82, [])
    assert _is_chart_body_segment("![Chart](layoutimg2)", 83, [])
    assert not _is_chart_body_segment("Figure 2: caption text only", 83, [])
    assert _is_chart_body_segment(
        None,
        82,
        [],
        segment={"chunk_type": "chart_body", "source_text": "![Chart](layoutimg1)"},
    )
