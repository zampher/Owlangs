# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from exporter.xlsx.base import XlsxExporter
from ir.document import Document


class Xlsx2XlsxExporter(XlsxExporter):
    def export(self, document: Document) -> Document:
        return document.copy()
