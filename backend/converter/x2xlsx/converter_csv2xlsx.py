# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import asyncio
import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Hashable

# Import chardet for encoding detection
import chardet
import openpyxl

from converter.x2xlsx.base import X2XlsxConverter, X2XlsxConverterConfig
from ir.document import Document


# Configure a basic logger (if your project hasn't configured one yet)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
@dataclass(kw_only=True)
class ConverterCsv2XlsxConfig(X2XlsxConverterConfig):

    def gethash(self) -> Hashable:
        return "1"


class ConverterCsv2Xlsx(X2XlsxConverter):
    """
    An improved and robust CSV to XLSX converter.

    Features:
    - Memory efficient: Uses streaming write mode to handle large files.
    - Automatic encoding detection: Avoids garbled text issues.
    - Automatic CSV format recognition: Supports different delimiters.
    - Comprehensive error handling and logging.
    """

    def __init__(self, config: ConverterCsv2XlsxConfig):
        super().__init__(config=config)

    def convert(self, document: Document) -> Document:
        """
        Synchronously convert CSV Document object to XLSX Document object.
        """
        self.logger.info(LogModule.CONVERT, f"Starting file conversion {document.name} (size: {len(document.content)} bytes)")

        try:
            # --- 1. Auto-detect file encoding ---
            # For better performance, only detect using file header portion
            detection_result = chardet.detect(document.content[:4096])
            encoding = detection_result['encoding'] or 'utf-8'  # Provide a default value
            confidence = detection_result['confidence']
            self.logger.info(LogModule.CONVERT, f"Detected file encoding: {encoding} (confidence: {confidence:.2%})")

            # --- 2. Decode and create text stream ---
            try:
                decoded_content = document.content.decode(encoding)
            except UnicodeDecodeError:
                self.logger.warning(LogModule.CONVERT, f"Failed to decode with detected encoding '{encoding}', trying 'utf-8'.")
                decoded_content = document.content.decode('utf-8', errors='replace')

            csv_text_stream = StringIO(decoded_content)

            # --- 3. Auto-detect CSV dialect (such as delimiter) ---
            try:
                # Sniffer needs some data to sniff, may fail if file is too small
                dialect = csv.Sniffer().sniff(csv_text_stream.read(2048))
                csv_text_stream.seek(0)  # Reset stream pointer back to file beginning
                self.logger.info(LogModule.CONVERT, f"Detected CSV delimiter: '{dialect.delimiter}'")
            except csv.Error:
                self.logger.warning(LogModule.CONVERT, "Unable to auto-detect CSV dialect, will use default comma delimiter.")
                dialect = 'excel'  # Use default dialect
                csv_text_stream.seek(0)

            csv_reader = csv.reader(csv_text_stream, dialect)

            # --- 4. Create XLSX using memory-optimized `write_only` mode ---
            wb = openpyxl.Workbook(write_only=True)
            ws = wb.create_sheet()

            # --- 5. Read CSV line by line and write to XLSX ---
            row_count = 0
            for row_data in csv_reader:
                ws.append(row_data)  # append() is efficient write method in write_only mode
                row_count += 1

            self.logger.info(LogModule.CONVERT, f"Processed {row_count} rows of data.")

            # --- 6. Save generated XLSX to in-memory byte stream ---
            output_buffer = BytesIO()
            wb.save(output_buffer)
            output_buffer.seek(0)  # Move pointer to beginning for getvalue() to read complete content

            self.logger.info(LogModule.CONVERT, f"File {document.name} successfully converted to XLSX format.")

            return Document.from_bytes(
                content=output_buffer.getvalue(),
                suffix=".xlsx",
                stem=document.stem
            )

        except Exception as e:
            self.logger.error(LogModule.CONVERT, f"Serious error occurred while converting file {document.name}: {e}", exc_info=True)
            # According to your business logic, you can throw an exception or return a specific object indicating failure
            raise

    async def convert_async(self, document: Document) -> Document:
        """
        Asynchronously execute conversion operation.
        Since core conversion logic is CPU intensive and blocking IO, using to_thread is the correct choice,
        it prevents blocking the asyncio event loop.
        """
        self.logger.info(LogModule.CONVERT, f"Creating new thread for conversion task of file {document.name}.")
        # We have optimized the `convert` method, so `to_thread` approach is very suitable
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.convert, document)

    def support_format(self) -> list[str]:
        """
        Declare source file formats supported by this converter.
        """
        return [".csv"]
