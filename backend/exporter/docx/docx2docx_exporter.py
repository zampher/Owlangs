# SPDX-FileCopyrightText: 2026 Zamphers
# SPDX-License-Identifier: MPL-2.0

from exporter.docx.base import DocxExporter
from ir.document import Document


class Docx2DocxExporter(DocxExporter):
    def export(self, document: Document) -> Document:
        return document.copy()
