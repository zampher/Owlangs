# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import json
from dataclasses import dataclass

import jinja2

from exporter.base import ExporterConfig
from exporter.js.base import JsonExporter
from ir.document import Document
from utils.resource_utils import resource_path


@dataclass
class Json2HTMLExporterConfig(ExporterConfig):
    cdn: bool = True


class Json2HTMLExporter(JsonExporter):
    def __init__(self, config: Json2HTMLExporterConfig = None):
        config = config or Json2HTMLExporterConfig()
        super().__init__(config=config)
        self.cdn = config.cdn

    def export(self, document: Document) -> Document:
        cdn = self.cdn
        html_template = resource_path("template/json.html").read_text(encoding="utf-8")

        # language=html
        pico = f'<style>{resource_path("static/pico.css").read_text(encoding="utf-8")}</style>' if not cdn else r'<link rel="stylesheet" href="https://s4.zstatic.net/ajax/libs/picocss/2.1.1/pico.min.css" integrity="sha512-+4kjFgVD0n6H3xt19Ox84B56MoS7srFn60tgdWFuO4hemtjhySKyW4LnftYZn46k3THUEiTTsbVjrHai+0MOFw==" crossorigin="anonymous" referrerpolicy="no-referrer" />'
        # language=html
        renderjson=f'<script><{resource_path("static/renderjson.min.js").read_text(encoding="utf-8")}/script>'
        json_data= document.content.decode()
        render = jinja2.Template(html_template).render(
            title=document.stem,
            pico=pico,
            renderjson=renderjson,
            jsonData=json_data,
        )
        return Document.from_bytes(content=render.encode("utf-8"), suffix=".html", stem=document.stem)
