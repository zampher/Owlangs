# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Compatibility shim for legacy imports.

Historically, backend modules imported helpers via ``utils.*``.
The actual implementation lives under ``backend.utils.*``.
This package re-exports ``backend.utils`` to keep legacy imports working in all entrypoints.

Important: ``sys.modules['utils']`` must be the real ``backend.utils`` module object
(not this shim), otherwise ``from utils.foo import ...`` resolves against the empty
``utils/`` directory and fails under PyInstaller analysis.

Submodule imports are routed through a meta_path finder so ``utils.foo`` and
``backend.utils.foo`` share one module object (avoids double-exec of the same file).
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType


class _UtilsAliasFinder(importlib.abc.MetaPathFinder):
    """Map ``utils.*`` submodule names onto ``backend.utils.*`` singletons."""

    def find_spec(self, fullname, path, target=None):  # noqa: ANN001
        if not fullname.startswith("utils."):
            return None
        real_name = "backend." + fullname
        if real_name in sys.modules:
            module = sys.modules[real_name]
            sys.modules[fullname] = module

            class _ExistingLoader(importlib.abc.Loader):
                def create_module(self, spec):  # noqa: ANN001
                    return module

                def exec_module(self, module_: ModuleType) -> None:  # noqa: ARG002
                    return None

            return importlib.util.spec_from_loader(fullname, _ExistingLoader())

        try:
            module = importlib.import_module(real_name)
        except ModuleNotFoundError:
            return None

        sys.modules[fullname] = module

        class _AliasLoader(importlib.abc.Loader):
            def create_module(self, spec):  # noqa: ANN001
                return module

            def exec_module(self, module_: ModuleType) -> None:  # noqa: ARG002
                return None

        return importlib.util.spec_from_loader(fullname, _AliasLoader())


_mod = importlib.import_module("backend.utils")
# Force-replace: setdefault is a no-op because this shim is already registered as
# ``utils`` while its __init__ is running.
sys.modules["utils"] = _mod

# Alias already-imported backend.utils.* submodules to utils.*
for _name, _m in list(sys.modules.items()):
    if _name == "backend.utils" or _name.startswith("backend.utils."):
        sys.modules.setdefault(_name.replace("backend.", "", 1), _m)

if not any(isinstance(_f, _UtilsAliasFinder) for _f in sys.meta_path):
    sys.meta_path.insert(0, _UtilsAliasFinder())
