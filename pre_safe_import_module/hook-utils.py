# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PyInstaller analysis hook: alias legacy ``utils`` package to ``backend.utils``.

Without this, modulegraph treats root ``utils/`` (shim-only) as empty and
reports ``Hidden import 'utils.*' not found``. Live imports during binary
analysis can also fail before runtime hooks run.
"""


def pre_safe_import_module(api):  # noqa: ANN001
    # real module first, alias second
    api.add_alias_module("backend.utils", "utils")
