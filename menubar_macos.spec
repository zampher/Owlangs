# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Owlangs macOS App.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path('.').resolve()

# Collect all dependencies
datas, binaries, hiddenimports = [], [], []
for module in ['Foundation', 'AppKit', 'objc', 'PyObjCTools']:
    try:
        m_datas, m_binaries, m_hiddenimports = collect_all(module)
        datas += m_datas
        binaries += m_binaries
        hiddenimports += m_hiddenimports
    except:
        pass

a = Analysis(
    ['tools/build/OwlangsMenuBar.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=[
        ('favicon.png', '.'),
        ('assets/Owlangs.icns', '.'),
        ('assets/owlangs_owl_solid.png', '.'),
    ] + datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'jax', 'jaxlib',
        'transformers', 'sentence_transformers',
        'spacy', 'sklearn', 'pandas', 'numpy',
        'PIL', 'matplotlib', 'flask', 'fastapi', 'uvicorn',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Owlangs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    bundle_identifier='com.owlangs.desktop',
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name='Owlangs',
)

app = BUNDLE(
    coll,
    name='Owlangs.app',
    icon='assets/Owlangs.icns',
    bundle_identifier='com.owlangs.desktop',
    info_plist={
        'CFBundleName': 'Owlangs',
        'CFBundleDisplayName': 'Owlangs',
        'CFBundleShortVersionString': '@VERSION_SHORT@',  # Replaced during build
        'CFBundleVersion': '@VERSION_FULL@',  # Replaced during build
        'NSHighResolutionCapable': True,
        'LSUIElement': True,  # Hide Dock icon, show only in menu bar
        'LSBackgroundOnly': False,
        'LSMultipleInstancesProhibited': True,
        'LSMinimumSystemVersion': '13.0',
        'CFBundleDocumentTypes': [],
    },
)
