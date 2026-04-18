# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from ir.markdown_document import MarkdownDocument
from utils.markdown_utils import MaskDict, uris2placeholder, placeholder2uris


class MDMaskUrisContext:
    def __init__(self, document: MarkdownDocument):
        self.document = document
        self.mask_dict = MaskDict()

    def __enter__(self):
        content_str = self.document.content.decode('utf-8') if isinstance(self.document.content, bytes) else self.document.content
        self.document.content = uris2placeholder(content_str, self.mask_dict).encode('utf-8')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        content_str = self.document.content.decode('utf-8') if isinstance(self.document.content, bytes) else self.document.content
        self.document.content = placeholder2uris(content_str, self.mask_dict).encode('utf-8')
