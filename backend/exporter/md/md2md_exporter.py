# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from exporter.md.base import MDExporter
from ir.markdown_document import MarkdownDocument, Document


class MD2MDExporter(MDExporter):

    def export(self, document: MarkdownDocument) -> Document:
        return Document.from_bytes(suffix=".md", content=document.content, stem=document.stem)
