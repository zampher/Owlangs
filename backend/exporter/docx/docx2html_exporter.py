# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from dataclasses import dataclass
from io import BytesIO

try:
    import mammoth
except ImportError as e:
    raise ImportError(
        "The 'mammoth' package is required for DOCX to HTML conversion. "
        "Please install it by running: pip install mammoth>=1.10.0 "
        "or: uv sync (if using uv). "
        f"Original error: {e}"
    ) from e

from exporter.base import ExporterConfig
from exporter.docx.base import DocxExporter
from ir.document import Document


@dataclass
class Docx2HTMLExporterConfig(ExporterConfig):
    cdn: bool = True


class Docx2HTMLExporter(DocxExporter):
    def __init__(self, config: Docx2HTMLExporterConfig = None):
        config = config or Docx2HTMLExporterConfig()
        super().__init__(config=config)
        self.cdn = config.cdn

    def export(self, document: Document) -> Document:
        html_content = mammoth.convert_to_html(BytesIO(document.content)).value

        return Document.from_bytes(content=html_content.encode("utf-8"), suffix=".html", stem=document.stem)
