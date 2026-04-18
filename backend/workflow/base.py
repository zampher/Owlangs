# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Self, Generic, TypeVar

from exporter.base import Exporter
from ir.attachment_manager import AttachMentManager
from ir.document import Document
from logger import unified_logger
from logger.logger import LogModule


@dataclass(kw_only=True)
class WorkflowConfig:
    logger: Logger = unified_logger


T_Config = TypeVar("T_Config", bound=WorkflowConfig)
T_original = TypeVar('T_original', bound=Document)
T_Translated = TypeVar('T_Translated', bound=Document)


class Workflow(ABC, Generic[T_Config, T_original, T_Translated]):
    def __init__(self, config: T_Config):
        self.config = config
        self.logger = self.config.logger
        self.document_original: T_original | None = None
        self.document_translated: T_Translated | None = None
        self.attachment = AttachMentManager()

    def read_path(self, path: Path | str) -> Self:
        document = Document.from_path(path)
        self.document_original = document
        return self

    def read_bytes(self, content: bytes, stem: str, suffix: str) -> Self:
        document = Document.from_bytes(content=content, stem=stem, suffix=suffix)
        self.document_original = document
        return self

    @abstractmethod
    def translate(self, *args, **kwargs) -> Self:
        ...

    @abstractmethod
    async def translate_async(self, *args, **kwargs) -> Self:
        ...

    def _export(self, exporter: Exporter) -> Document:
        if self.document_translated is None:
            raise RuntimeError("Document has not been translated yet. Call translate() first.")
        docu = exporter.export(self.document_translated)
        return docu

    def _save(self, exporter: Exporter, name: str = None, output_dir: Path | str = "./output"):
        docu = self._export(exporter)
        name = name or docu.name
        output_path = Path(output_dir) / Path(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(docu.content)
        self.logger.info(LogModule.WORKFLOW, f"File saved to {output_path.resolve()}")
        return self

    def get_attachment(self):
        print(f"attachment:{self.attachment.attachment_dict}")
        return self.attachment
