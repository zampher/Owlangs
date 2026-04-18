# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from exporter.txt.base import TXTExporter
from exporter.xlsx.base import XlsxExporter
from ir.document import Document


class Epub2EpubExporter(XlsxExporter):
    def export(self, document: Document) -> Document:
        # CRITICAL: Ensure content is bytes and create a proper copy
        content = document.content
        if not isinstance(content, bytes):
            if isinstance(content, str):
                content = content.encode('utf-8')
            else:
                content = bytes(content)
        
        # Create a new Document with the content to ensure proper copying
        from ir.document import Document as DocClass
        return DocClass(
            suffix=document.suffix,
            content=content,
            stem=document.stem,
            path=document.path
        )
