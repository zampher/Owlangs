# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""PyInstaller analysis hook: legacy ``utils.*`` maps to ``backend.utils.*``."""

from PyInstaller.utils.hooks import collect_submodules

# Ensure all backend.utils submodules are collected when analysis touches ``utils``.
hiddenimports = ["backend.utils"] + collect_submodules("backend.utils")
