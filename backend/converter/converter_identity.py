# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from converter.base import Converter
from ir.document import Document


class ConverterIdentity(Converter):

    def convert(self, document: Document) -> Document:
        return Document.from_bytes(content=document.content, suffix=document.suffix, stem=document.stem)

    async def convert_async(self, document: Document) -> Document:
        return Document.from_bytes(content=document.content, suffix=document.suffix, stem=document.stem)
