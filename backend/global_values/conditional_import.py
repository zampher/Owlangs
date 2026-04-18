# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import importlib

available_packages={}

def conditional_import(packagename,alias=None):
    try:
        imported= importlib.import_module(packagename)
        if alias:
            globals()[alias]=imported
        else:
            globals()[packagename]=imported
        available_packages[packagename]=True
        return True
    except ImportError:
        available_packages[packagename]=False
        return False

# In PyInstaller environment, if docling is excluded, set to False directly
try:
    DOCLING_EXIST=conditional_import("docling")
except Exception:
    # If import fails (e.g., in lite version), set to False
    DOCLING_EXIST=False
