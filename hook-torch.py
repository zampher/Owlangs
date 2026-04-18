# -*- coding: utf-8 -*-
"""
PyInstaller hook for torch: do not bundle torch binaries/datas in lite build.
Torch is excluded in lite.spec; this hook ensures no torch DLLs or data files
are collected when another dependency (e.g. safetensors, huggingface_hub) pulls it in.
"""
# Do not collect any torch binaries or data files to reduce package size
binaries = []
datas = []
