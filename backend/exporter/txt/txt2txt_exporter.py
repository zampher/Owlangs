# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from exporter.txt.base import TXTExporter
from ir.document import Document


class TXT2TXTExporter(TXTExporter):
    def export(self, document: Document) -> Document:
        return document.copy()
