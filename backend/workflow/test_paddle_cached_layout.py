# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Paddle markdown-cache must restore layout or force re-conversion."""

from __future__ import annotations

import io
import json
import unittest
import zipfile
from unittest.mock import MagicMock, patch

from ir.markdown_document import MarkdownDocument
from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from workflow.md_based_workflow import MarkdownBasedWorkflow, MarkdownBasedWorkflowConfig


def _minimal_paddle_layout_zip() -> bytes:
    layout_payload = {
        "engine": "paddle",
        "page_count": 1,
        "total_blocks": 1,
        "metadata": {},
        "pages": [
            {
                "page_index": 0,
                "page_width": 595.0,
                "page_height": 842.0,
                "blocks": [
                    {
                        "page_index": 0,
                        "block_index": 0,
                        "type": "text",
                        "sub_type": "",
                        "bbox": [10.0, 10.0, 100.0, 40.0],
                        "text": "hello",
                        "tags": [],
                    }
                ],
            }
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("layout.json", json.dumps(layout_payload))
        zf.writestr("full.md", "# hello\n")
    return buf.getvalue()


def _build_paddle_workflow(*, skip_cache: bool = False) -> MarkdownBasedWorkflow:
    from layout.ocr_provider.paddle.provider import PaddleOCRConfig
    from translator.ai_translator.md_translator import MDTranslatorConfig
    from exporter.md.md2html_exporter import MD2HTMLExporterConfig

    config = MarkdownBasedWorkflowConfig(
        logger=MagicMock(),
        skip_cache=skip_cache,
        convert_engine="paddle",
        converter_config=PaddleOCRConfig(),
        translator_config=MDTranslatorConfig(api_key="test", to_lang="en", skip_translate=True),
        html_exporter_config=MD2HTMLExporterConfig(),
    )
    workflow = MarkdownBasedWorkflow(config=config)
    workflow.read_bytes(content=b"%PDF-1.4 fake", stem="sample", suffix=".pdf")
    return workflow


class TestPaddleCachedLayout(unittest.TestCase):
    def test_cache_hit_without_layout_zip_returns_none(self):
        workflow = _build_paddle_workflow(skip_cache=False)
        cached_md = MarkdownDocument(content=b"# cached\n", suffix=".md", stem="sample")

        with patch(
            "workflow.md_based_workflow.md_based_convert_cacher.get_cached_result",
            return_value=cached_md,
        ):
            result = workflow._get_document_md("paddle", workflow.config.converter_config)

        self.assertIsNone(result)
        self.assertIsNone(workflow.layout_document)

    def test_cache_hit_with_layout_source_zip_loads_layout(self):
        workflow = _build_paddle_workflow(skip_cache=False)
        workflow._layout_source_zip = _minimal_paddle_layout_zip()
        cached_md = MarkdownDocument(content=b"# cached\n", suffix=".md", stem="sample")

        with patch(
            "workflow.md_based_workflow.md_based_convert_cacher.get_cached_result",
            return_value=cached_md,
        ):
            result = workflow._get_document_md("paddle", workflow.config.converter_config)

        self.assertIsNotNone(result)
        self.assertEqual(result.content, b"# cached\n")
        self.assertIsInstance(workflow.layout_document, LayoutDocument)
        self.assertEqual(workflow.layout_document.page_count, 1)

    def test_convert_without_translation_reruns_when_cache_lacks_layout(self):
        workflow = _build_paddle_workflow(skip_cache=False)
        cached_md = MarkdownDocument(content=b"# cached\n", suffix=".md", stem="sample")
        fresh_md = MarkdownDocument(content=b"# fresh\n", suffix=".md", stem="sample")
        layout_doc = LayoutDocument(
            pages=[
                LayoutPage(
                    page_index=0,
                    width=595.0,
                    height=842.0,
                    blocks=[
                        LayoutBlock(
                            page_index=0,
                            bbox=(10.0, 10.0, 100.0, 40.0),
                            type="text",
                            index=0,
                            text="fresh",
                        )
                    ],
                )
            ],
            engine="paddle",
        )

        call_count = {"n": 0}

        def _fake_get(engine, config):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: simulate cache hit without layout (returns None)
                return None
            workflow.layout_document = layout_doc
            return fresh_md

        with patch.object(workflow, "_get_document_md", side_effect=_fake_get):
            # Bypass first _get_document_md via convert path helpers
            with patch.object(
                workflow,
                "_pre_translate",
                return_value=("paddle", workflow.config.converter_config, None, None),
            ):
                # First internal call returns None → rerun path invokes _get_document_md again
                result = workflow.convert_without_translation()

        self.assertEqual(result.content, b"# fresh\n")
        self.assertIs(workflow.layout_document, layout_doc)
        self.assertGreaterEqual(call_count["n"], 2)


if __name__ == "__main__":
    unittest.main()
