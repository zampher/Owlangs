# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass

from exporter.base import Exporter, ExporterConfig
from ir.document import Document
from ir.markdown_document import MarkdownDocument


@dataclass(kw_only=True)
class MDExporterConfig(ExporterConfig):
    ...


class MDExporter(Exporter):
    def __init__(self, config: MDExporterConfig|None=None):
        super().__init__(config=config)

    def export(self, document: MarkdownDocument) -> Document:
        ...
