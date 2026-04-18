# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from .glossary import Glossary
from .models import GlossaryFile, GlossaryItem, UserGlossarySelection
from .manager import get_glossary_manager
from .storage import get_glossary_storage