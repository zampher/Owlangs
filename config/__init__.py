# SPDX-FileCopyrightText: 2026 Zamphersssss
# SPDX-License-Identifier: MPL-2.0

"""
Compatibility shim for legacy imports.

The backend codebase historically imported configuration helpers via ``config.*``.
The actual implementation now lives under ``backend.config.*``.
This package re-exports ``backend.config`` to keep legacy imports working.
"""

from __future__ import annotations

import importlib
import sys

_mod = importlib.import_module("backend.config")
sys.modules.setdefault("config", _mod)
globals().update(_mod.__dict__)

# Eagerly import common backend.config submodules and alias them as config.*
_SUBMODULES = (
    "config_loader",
    "secrets_manager",
    "local_config",
    "app_config",
    "platforms_config",
    "translation_config",
    "system_config",
    "ui_config",
    "temperature_config",
    "profile_manager",
)

for _sub in _SUBMODULES:
    try:
        _m = importlib.import_module(f"backend.config.{_sub}")
    except Exception:
        # Best-effort: if a submodule cannot be imported, skip it
        continue
    sys.modules.setdefault(f"config.{_sub}", _m)

# Alias backend submodules to legacy names (config.*) to avoid duplicate module loads.
for _name, _m in list(sys.modules.items()):
    if _name == "backend.config" or _name.startswith("backend.config."):
        sys.modules.setdefault(_name.replace("backend.", "", 1), _m)

