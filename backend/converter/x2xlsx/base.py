# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from abc import abstractmethod
from dataclasses import dataclass
from typing import Hashable

from converter.base import Converter, ConverterConfig
from ir.document import Document

@dataclass(kw_only=True)
class X2XlsxConverterConfig(ConverterConfig):
    ...
    @abstractmethod
    def gethash(self) ->Hashable:
        ...

class X2XlsxConverter(Converter):
    """
    Responsible for converting files from other formats to xlsx
    """

    @abstractmethod
    def convert(self, document: Document) -> Document:
        ...

    @abstractmethod
    async def convert_async(self, document: Document) -> Document:
        ...

    @abstractmethod
    def support_format(self)->list[str]:
        ...