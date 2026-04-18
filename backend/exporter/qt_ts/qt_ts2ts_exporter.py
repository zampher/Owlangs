# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from dataclasses import dataclass

from exporter.base import ExporterConfig
from exporter.qt_ts.base import QtTsExporter
from ir.document import Document


@dataclass
class QtTs2TsExporterConfig(ExporterConfig):
    """Configuration for Qt .ts to .ts exporter."""
    pass


class QtTs2TsExporter(QtTsExporter):
    """
    Export translated Qt .ts file.
    Simply returns the translated document as-is.
    """
    
    def __init__(self, config: QtTs2TsExporterConfig = None):
        config = config or QtTs2TsExporterConfig()
        super().__init__(config=config)
    
    def export(self, document: Document) -> Document:
        """
        Export translated .ts file.
        
        :param document: Document object containing translated .ts XML content.
        :return: Document object with translated .ts content.
        """
        # The document already contains the translated XML, just return it
        return document.copy()

