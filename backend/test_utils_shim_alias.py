# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Ensure legacy ``utils.*`` imports resolve to ``backend.utils.*``."""

from __future__ import annotations

import importlib
import sys


def test_utils_package_is_backend_utils() -> None:
    """Root utils/ shim must force-replace sys.modules['utils']."""
    for key in list(sys.modules):
        if key == "utils" or key.startswith("utils.") or key.startswith("backend.utils"):
            del sys.modules[key]

    # Loading the shim package triggers the force-replace.
    importlib.import_module("utils")
    assert "utils" in sys.modules
    assert sys.modules["utils"].__name__ == "backend.utils"

    mod = importlib.import_module("utils.http_content_disposition")
    assert hasattr(mod, "file_download_response")
    backend_mod = importlib.import_module("backend.utils.http_content_disposition")
    assert mod is backend_mod
    assert "utils.http_content_disposition" in sys.modules


def test_auth_routes_import_via_utils_alias() -> None:
    """Auth routes must import cleanly (uses backend.utils, not legacy utils.*)."""
    for key in list(sys.modules):
        if key == "utils" or key.startswith("utils.") or key.startswith("backend"):
            del sys.modules[key]

    auth = importlib.import_module("backend.auth")
    assert getattr(auth, "auth_router", None) is not None
