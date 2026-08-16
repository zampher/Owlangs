# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Runtime hook: register utils alias for backend.utils in frozen builds."""

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


try:
    if "backend.utils" not in sys.modules:
        importlib.import_module("backend.utils")
    sys.modules["utils"] = sys.modules["backend.utils"]
    for name, module in list(sys.modules.items()):
        if name.startswith("backend.utils."):
            sys.modules.setdefault(name.replace("backend.", "", 1), module)
    if not any(isinstance(f, _UtilsAliasFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _UtilsAliasFinder())
except Exception:
    # Keep boot resilient; missing alias surfaces as a clear import error later.
    pass
