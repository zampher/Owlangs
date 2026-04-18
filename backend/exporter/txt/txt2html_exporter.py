# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass

import jinja2

from exporter.base import ExporterConfig
from exporter.txt.base import TXTExporter
from ir.document import Document
from utils.resource_utils import resource_path


def _decode_with_detection(data: bytes) -> str:
    """
    Decode bytes to str with robust fallback:
    1) Try UTF-8 (strict), then UTF-8 with BOM
    2) Try charset detection (charset_normalizer) if available
    3) Fallback through common encodings
    4) Final fallback: UTF-8 with replacement to avoid crash
    """
    if data is None:
        return ""

    # 1) UTF-8 strict
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 1b) UTF-8 with BOM
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # 2) charset_normalizer (optional dependency)
    try:
        import charset_normalizer  # type: ignore

        result = charset_normalizer.from_bytes(data).best()
        if result is not None:
            return str(result)
    except Exception:
        # Either not installed or detection failed; continue with fallbacks
        pass

    # 3) Try common encodings explicitly
    for enc in ("gb18030", "gbk", "cp936", "big5", "shift_jis", "euc-jp", "euc-kr", "iso-8859-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue

    # 4) Final fallback: avoid crash and preserve as much as possible
    return data.decode("utf-8", errors="replace")


@dataclass
class TXT2HTMLExporterConfig(ExporterConfig):
    cdn: bool = True


class TXT2HTMLExporter(TXTExporter):
    def __init__(self, config: TXT2HTMLExporterConfig = None):
        config = config or TXT2HTMLExporterConfig()
        super().__init__(config=config)
        self.cdn = config.cdn

    def export(self, document: Document) -> Document:
        cdn = self.cdn
        html_template = resource_path("template/txt.html").read_text(encoding="utf-8")

        # language=html
        pico = f'<style>{resource_path("static/pico.css").read_text(encoding="utf-8")}</style>' if not cdn else r'<link rel="stylesheet" href="https://s4.zstatic.net/ajax/libs/picocss/2.1.1/pico.min.css" integrity="sha512-+4kjFgVD0n6H3xt19Ox84B56MoS7srFn60tgdWFuO4hemtjhySKyW4LnftYZn46k3THUEiTTsbVjrHai+0MOFw==" crossorigin="anonymous" referrerpolicy="no-referrer" />'

        # Robust decoding with detection, then render as UTF-8 HTML
        decoded_text = _decode_with_detection(document.content)
        body = '\n'.join([r'<p>' + para + '</p>' for para in decoded_text.split("\n")])
        render = jinja2.Template(html_template).render(
            title=document.stem,
            pico=pico,
            body=body,
        )
        return Document.from_bytes(content=render.encode("utf-8"), suffix=".html", stem=document.stem)
