# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Hashable

from ir.document import Document
from logger import unified_logger


@dataclass(kw_only=True)
class ConverterConfig(ABC):
    logger: Logger = unified_logger

    @abstractmethod
    def gethash(self) -> Hashable:
        ...


class Converter(ABC):
    def __init__(self, config: ConverterConfig | None = None):
        self.config = config
        if config:
            self.logger = config.logger

    @abstractmethod
    def convert(self, document: Document) -> Document:
        ...

    async def convert_async(self, document: Document) -> Document:
        ...
