# -*- coding: utf-8 -*-
"""
PyInstaller hook for pandas: do not bundle pandas binaries/datas in lite build.
Pandas is excluded in lite.spec; this hook ensures no pandas DLLs or data files
are collected when another dependency pulls it in (e.g. docling_core, tqdm).
"""
# Do not collect any pandas binaries or data files to reduce package size
binaries = []
datas = []
