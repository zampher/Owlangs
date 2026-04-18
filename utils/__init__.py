# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Compatibility shim for legacy imports.

Historically, backend modules imported helpers via ``utils.*``.
The actual implementation lives under ``backend.utils.*``.
This package re-exports ``backend.utils`` to keep legacy imports working in all entrypoints.
"""

from __future__ import annotations

import importlib
import sys

_mod = importlib.import_module("backend.utils")
sys.modules.setdefault("utils", _mod)
globals().update(_mod.__dict__)

# Alias backend submodules to legacy names (utils.*) to avoid duplicate module loads.
for _name, _m in list(sys.modules.items()):
    if _name == "backend.utils" or _name.startswith("backend.utils."):
        sys.modules.setdefault(_name.replace("backend.", "", 1), _m)

