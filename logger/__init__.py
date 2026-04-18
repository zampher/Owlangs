# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""
Compatibility shim for legacy imports.

The backend codebase historically imported logging helpers via ``logger.*``.
The actual implementation lives under ``backend.logger.*``.
This package re-exports ``backend.logger`` to keep legacy imports working.
"""

from __future__ import annotations

import importlib
import sys

_mod = importlib.import_module("backend.logger")
sys.modules.setdefault("logger", _mod)
globals().update(_mod.__dict__)

# Alias backend submodules to legacy names (logger.*).
# This prevents duplicate module loads like backend.logger.logger vs logger.logger,
# which would otherwise create distinct Enum classes (e.g., LogModule) and break isinstance checks.
for _name, _m in list(sys.modules.items()):
    if _name == "backend.logger" or _name.startswith("backend.logger."):
        sys.modules.setdefault(_name.replace("backend.", "", 1), _m)

