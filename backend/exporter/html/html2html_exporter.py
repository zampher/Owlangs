# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from exporter.base import ExporterConfig
from exporter.html.base import HtmlExporter
from ir.document import Document


class Html2HtmlExporter(HtmlExporter):
    def __init__(self, config: ExporterConfig|None = None):
        super().__init__(config=config)

    def export(self, document: Document) -> Document:
        return Document.from_bytes(content=document.content, suffix=".html", stem=document.stem)
