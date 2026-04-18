# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from exporter.base import ExporterConfig
from exporter.qt_ts.base import QtTsExporter
from ir.document import Document


@dataclass
class QtTs2HTMLExporterConfig(ExporterConfig):
    """Configuration for Qt .ts to HTML exporter."""
    cdn: bool = False  # Whether to use CDN for resources


class QtTs2HTMLExporter(QtTsExporter):
    """
    Convert Qt .ts file to HTML for preview.
    """
    
    def __init__(self, config: QtTs2HTMLExporterConfig = None):
        config = config or QtTs2HTMLExporterConfig()
        super().__init__(config=config)
        self.cdn = config.cdn
    
    def export(self, document: Document) -> Document:
        """
        Convert Qt .ts file to HTML.
        
        :param document: Document object containing .ts XML content.
        :return: Document object containing HTML content.
        """
        try:
            root = ET.fromstring(document.content)
            
            html_parts = []
            
            # Process all contexts
            for context in root.findall('.//context'):
                context_name_elem = context.find('name')
                context_name = context_name_elem.text if context_name_elem is not None else 'Unknown'
                
                html_parts.append(f'<h2>Context: {self._escape_html(context_name)}</h2>')
                html_parts.append('<table border="1" cellpadding="5" style="width: 100%; border-collapse: collapse;">')
                html_parts.append('<tr><th>Source</th><th>Translation</th></tr>')
                
                # Process all messages in this context
                for message in context.findall('message'):
                    source = message.find('source')
                    translation = message.find('translation')
                    
                    source_text = source.text if source is not None and source.text else ''
                    translation_text = translation.text if translation is not None and translation.text else ''
                    translation_type = translation.get('type') if translation is not None else None
                    
                    # Style based on translation status
                    if translation_type == 'unfinished':
                        style = 'background-color: #fff3cd;'
                    elif translation_type in ('vanished', 'obsolete'):
                        style = 'background-color: #f8d7da;'
                    elif translation_text:
                        style = 'background-color: #d4edda;'
                    else:
                        style = 'background-color: #f8f9fa;'
                    
                    html_parts.append(f'<tr style="{style}">')
                    html_parts.append(f'<td>{self._escape_html(source_text)}</td>')
                    html_parts.append(f'<td>{self._escape_html(translation_text)}</td>')
                    html_parts.append('</tr>')
                
                html_parts.append('</table>')
                html_parts.append('<br>')
            
            # Generate HTML
            html_content = self._generate_html(html_parts)
            return Document(suffix='.html', content=html_content.encode('utf-8'))
            
        except Exception as e:
            error_html = self._generate_error_html(str(e))
            return Document(suffix='.html', content=error_html.encode('utf-8'))
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ''
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def _generate_html(self, content_parts: list) -> str:
        """Generate complete HTML document."""
        combined_content = "\n".join(content_parts)
        
        pico_css = (
            '<link rel="stylesheet" href="https://s4.zstatic.net/ajax/libs/picocss/2.1.1/pico.min.css" integrity="sha512-+4kjFgVD0n6H3xt19Ox84B56MoS7srFn60tgdWFuO4hemtjhySKyW4LnftYZn46k3THUEiTTsbVjrHai+0MOFw==" crossorigin="anonymous" referrerpolicy="no-referrer" />'
            if self.cdn else
            '<style>/* Pico CSS would be embedded here */</style>'
        )
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qt .ts Translation Preview</title>
    {pico_css}
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 10px;
            text-align: left;
        }}
        td {{
            padding: 8px;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <h1>Qt .ts Translation Preview</h1>
    {combined_content}
</body>
</html>"""
        return html_template
    
    def _generate_error_html(self, error_msg: str) -> str:
        """Generate error HTML page."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <h1>Error: Unable to convert Qt .ts file to HTML</h1>
    <p>Error details: {self._escape_html(error_msg)}</p>
</body>
</html>"""

