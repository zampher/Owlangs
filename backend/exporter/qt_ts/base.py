# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from exporter.base import ExporterConfig
from exporter.base import Exporter
from ir.document import Document


class QtTsExporter(Exporter[Document]):
    """Base exporter for Qt .ts files."""
    pass

