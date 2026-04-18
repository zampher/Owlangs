# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import TypeVar, Generic

from ir.document import Document
from logger import unified_logger


@dataclass(kw_only=True)
class TranslatorConfig:
    logger: Logger = unified_logger


T = TypeVar('T', bound=Document)


class Translator(ABC, Generic[T]):
    """
    翻译中间文本（原地替换），Translator不做格式转换
    """

    def __init__(self, config: TranslatorConfig | None = None):
        self.config = config
        self.logger = config.logger or unified_logger

    @abstractmethod
    def translate(self, document: T) -> Document:
        ...

    @abstractmethod
    async def translate_async(self, document: T) -> Document:
        ...
