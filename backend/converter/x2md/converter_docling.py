# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

import asyncio
import os
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from typing import Any

from converter.x2md.base import X2MarkdownConverter, X2MarkdownConverterConfig
from ir.attachment_manager import AttachMent
from ir.document import Document
from ir.markdown_document import MarkdownDocument

IMAGE_RESOLUTION_SCALE = 4


@dataclass(kw_only=True)
class ConverterDoclingConfig(X2MarkdownConverterConfig):
    code_ocr: bool = True
    formula_ocr: bool = True
    artifact: Path | str | None = None

    def gethash(self):
        return self.code_ocr, self.formula_ocr


class ConverterDocling(X2MarkdownConverter):
    def __init__(self, config: ConverterDoclingConfig):
        super().__init__(config=config)
        self.code = config.code_ocr
        self.formula = config.formula_ocr
        artifact = Path("./docling_artifact")
        if artifact.is_dir():
            self.logger.info(LogModule.CONVERT, "Using local model from ./docling_artifact")
            self.artifact = artifact
        else:
            self.artifact = config.artifact
        self.attachments: list[AttachMent] = []

    def convert(self, document) -> MarkdownDocument:
        assert isinstance(document.name, str)
        self.logger.info(LogModule.CONVERT, f"Converting document to markdown")
        time1 = time.time()
        # Lazy import to avoid triggering heavy third-party imports at module import time
        from docling.datamodel.document import DocumentStream
        document_stream = DocumentStream(name=document.name, stream=BytesIO(document.content))
        content = self.file2markdown_embed_images(document_stream)
        self.logger.info(LogModule.CONVERT, f"Document converted to markdown, time taken: {time.time() - time1} seconds")
        self.attachments.append(AttachMent("docling",MarkdownDocument.from_bytes(content=content.encode("utf-8"), suffix=".md", stem="docling")))
        md_document = MarkdownDocument.from_bytes(content=content.encode("utf-8"), suffix=".md", stem=document.stem)
        return md_document

    async def convert_async(self, document: Document) -> MarkdownDocument:
        return await asyncio.to_thread(
            self.convert,
            document
        )

    def support_format(self) -> list[str]:
        return [".pdf", ".docx", ".pptx", ".xlsx", ".md", "html", "xhtml", "csv", ".png", ".jpg", ".jpeg", ".tiff",
                ".bmp", ".webp"]

    def file2markdown_embed_images(self, file_path: Path | str | Any) -> str:
        # Lazy imports here to avoid early NumPy/docling initialization in frozen apps
        import numpy as _np
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.settings import settings
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import ImageRefMode
        from huggingface_hub.errors import LocalEntryNotFoundError

        try:
            self.logger.info(LogModule.CONVERT, f"NumPy runtime: version={_np.__version__}, path={getattr(_np, '__file__', 'builtin')}")
        except Exception:
            pass

        pipeline_options = PdfPipelineOptions(artifacts_path=self.artifact)
        pipeline_options.do_ocr = False
        pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
        pipeline_options.generate_picture_images = True
        # pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        pipeline_options.table_structure_options.do_cell_matching = False
        if self.formula:
            pipeline_options.do_formula_enrichment = True
        if self.code:
            pipeline_options.do_code_enrichment = True
        # pipeline_options.accelerator_options= AcceleratorOptions(
        #     num_threads=4, device=AcceleratorDevice.AUTO
        # )
        # Print timing
        settings.debug.profile_pipeline_timings = True
        converter = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)

        })
        try:
            conversion_result = converter.convert(file_path)
            result = conversion_result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
        except LocalEntryNotFoundError:
            self.logger.info(LogModule.CONVERT, f"Unable to connect to HuggingFace, trying alternative source")
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
            conversion_result = converter.convert(file_path)
            result = conversion_result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
            # translater_logger.info(f"docling conversion time: {conversion_result.timings["pipeline_total"].times}")
        return result


if __name__ == '__main__':
    pass
