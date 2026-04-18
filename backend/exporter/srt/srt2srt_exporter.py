# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from exporter.srt.base import SrtExporter
from ir.document import Document


class Srt2SrtExporter(SrtExporter):
    def export(self, document: Document) -> Document:
        return document.copy()
