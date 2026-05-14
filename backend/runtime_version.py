# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Spawn-safe reads of ``backend.__version__`` / ``backend.__version_type__``.

Windows multiprocessing ``spawn`` may resolve ``backend`` to a namespace package without
those attributes; ``from backend import __version__`` then raises ImportError during
worker bootstrap (e.g. language detection). Use ``importlib`` + ``getattr`` instead.
"""

from __future__ import annotations

import importlib
from typing import Tuple


def get_backend_version_tuple() -> Tuple[str, str]:
    try:
        pkg = importlib.import_module("backend")
    except ImportError:
        return "unknown", ""
    ver = getattr(pkg, "__version__", None)
    vtype = getattr(pkg, "__version_type__", None)
    if not isinstance(ver, str) or not ver.strip():
        return "unknown", ""
    vtype_s = vtype.strip() if isinstance(vtype, str) else ""
    return ver.strip(), vtype_s
