# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from .glossary import Glossary
from .models import GlossaryFile, GlossaryItem, UserGlossarySelection
from .manager import get_glossary_manager
from .storage import get_glossary_storage
from .tbx_converter import (
    tbx_to_entries,
    entries_to_tbx,
    detect_languages,
    tbx_bytes_to_entries,
    entries_to_tbx_bytes,
)