# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from exporter.base import Exporter
from ir.document import Document

# TODO: Consider if a separate document type is needed for MOBI files
class MobiExporter(Exporter[Document]):

    def export(self, document: Document) -> Document:
        ...

