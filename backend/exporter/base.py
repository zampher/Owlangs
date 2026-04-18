# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from abc import ABC,abstractmethod
from typing import Generic,TypeVar, Any

from dataclasses import dataclass

from ir.document import Document

D_in = TypeVar('D_in', bound=Document)

@dataclass(kw_only=True)
class ExporterConfig:
    ...

class Exporter(ABC,Generic[D_in]):
    def __init__(self,config:ExporterConfig|None=None):
        self.config=config

    @abstractmethod
    def export(self, document: D_in) -> Any:
        ...
