# -*- coding: utf-8 -*-
"""
PyInstaller hook for numpy (lite build): do not bundle numpy binaries/datas.
Numpy is excluded in lite.spec; this hook ensures no numpy .libs or data files
are collected when another dependency pulls it in (e.g. openpyxl optional).
Runtime hook hook-numpy-fix.py provides stubs for frozen app compatibility
when numpy is not bundled.
"""
# Do not collect numpy binaries or data files in lite build to reduce package size
binaries = []
datas = []
