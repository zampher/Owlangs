# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from io import BytesIO, StringIO

import openpyxl
import csv
from exporter.xlsx.base import XlsxExporter
from ir.document import Document


class Xlsx2CsvExporter(XlsxExporter):

    def export(self, document: Document) -> Document:
        workbook = openpyxl.load_workbook(BytesIO(document.content))
        sheet = workbook.active

        # 2. Use StringIO as text buffer
        text_buffer = StringIO()

        # 3. Pass buffer directly to csv.writer
        writer = csv.writer(text_buffer)

        # Iterate through each row in the worksheet
        for row in sheet.rows:
            writer.writerow([cell.value for cell in row])

        # 4. Encode text buffer content as bytes
        output_bytes = text_buffer.getvalue().encode('utf-8')

        # 5. Return a Document with .csv suffix
        return Document.from_bytes(content=output_bytes, suffix=".csv", stem=document.stem)




