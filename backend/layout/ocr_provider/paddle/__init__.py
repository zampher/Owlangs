# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""PaddleOCR provider package.

Core modules (block_labels, layout_parser) have no external dependencies.
Optional modules (api_client, provider, converter_adapter) require ``httpx``.
"""

from .block_labels import PADDLE_LABEL_MAP, map_paddle_label
from .layout_parser import parse_paddle_layout, extract_paddle_markdown

__all__ = [
    "PADDLE_LABEL_MAP",
    "map_paddle_label",
    "parse_paddle_layout",
    "extract_paddle_markdown",
]

# Optional: require httpx
try:
    from .api_client import PaddleOCRClient
    from .provider import PaddleOCRConfig, PaddleOCRProvider
    from .converter_adapter import PaddleToConverterAdapter
    __all__ += ["PaddleOCRClient", "PaddleOCRConfig", "PaddleOCRProvider", "PaddleToConverterAdapter"]
except ImportError:
    pass
