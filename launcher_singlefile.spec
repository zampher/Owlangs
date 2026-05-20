# -*- mode: python ; coding: utf-8 -*-
# Single-file executable spec for Owlangs Enterprise Edition
# This creates a true single-file exe that:
# 1. Extracts to temp directory on first run
# 2. Initializes user configs in C:\ProgramData\Owlangs
# 3. Starts backend server
# 4. Opens browser automatically

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Project root
_project_root = Path(os.getcwd())
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Initialize lists
datas = []
binaries = []
hiddenimports = [
    # Backend utils modules
    'backend.utils',
    'backend.runtime_version',
    # Utils alias: runtime injects sys.modules['utils'] = backend.utils; no need to duplicate
    'backend.utils.resource_utils',
    'backend.utils.redis_manager',
    'backend.utils.utils',
    'backend.utils.language_utils',
    'backend.utils.path_utils',
    'backend.utils.font_utils',
    'backend.utils.pagination',
    'backend.utils.document_rebuild',
    'backend.utils.translation_segments',
    'backend.utils.markdown_splitter',
    'backend.utils.markdown_utils',
    'backend.utils.json_utils',
    'backend.utils.chunk_translation_helper',
    'backend.utils.translation_validator',
    'backend.utils.chunk_size_converter',
    'backend.utils.token_estimator',
    'backend.utils.docx_utils',
    'backend.utils.table_utils',
    'backend.utils.image_placeholder_utils',
    'backend.utils.format_convert_utils',
    'backend.utils.mixed_formula_text',
    'backend.utils.markdown_chunk_merger',
    'backend.utils.language_detection_utils',
    'backend.utils.language_detector',
    'backend.utils.latex_formula_checker',
    'backend.utils.latex_repair_llm',
    'backend.utils.latex_repair_payload',
    'backend.utils.latex_formula_batch_repair',
    'backend.utils.math_md_normalize',
    'backend.utils.docx_md_normalize',
    'backend.utils.docx_algorithm_latex_wrap',
    'backend.utils.docx_math_fragment_check',
    'backend.utils.docx_math_fragment_llm_repair',
    'backend.utils.llm_client',
    'backend.utils.extract_segments_debug',
    'backend.utils.epub_fix',
    'backend.utils.ebook_metadata',
    # App modules
    'app',
    'app.app_main',
    'app.factory',
    'app.__init__',
    'app.middleware',
    'app.middleware.request_id',
    'app.middleware.https_redirect',
    'app.models',
    'app.models.anonymize',
    'app.models.service',
    'app.models.translation_segment',
    # Frozen runtime: backend.app.* aliases resolve to app.* via pathex; no need to duplicate
    'app.services',
    'app.services.task',
    'app.services.version_service',
    'app.services.download',
    'app.services.download.output_generator',
    'app.services.download.download_service',
    'app.services.download.pdf_generator',
    'app.services.translation',
    'app.services.translation.translation_service',
    'app.services.translation.workflow_factory',
    'app.services.translation.workflow_config_builder',
    'app.services.translation.workflow_executor',
    'app.services.translation.prompt_service',
    'app.services.translation.source_preview_service',
    'app.services.translation.translation_segment_service',
    'app.services.translation.chunk_size_service',
    'app.services.translation.translation_execution_queue',
    'app.services.translation.translation_queue_utils',
    'app.services.translation.translation_result_stash',
    'app.services.platform',
    'app.services.platform.platform_service',
    'app.routes',
    'app.routes.app_routes_main',
    'app.routes.settings',
    'app.routes.service',
    'app.routes.service.app_routes_translation',
    'app.routes.service.app_routes_download',
    'app.routes.service.app_routes_status',
    'app.routes.service.app_routes_format_conversion',
    'app.routes.service.app_routes_glossary',
    'app.routes.service.app_routes_translation_segments',
    'app.routes.service.app_routes_formula_check',
    'app.utils',
    'app.utils.encoding_utils',
    'app.utils.url_fetcher',
    'workflow',
    'workflow.base',
    'workflow.interfaces',
    'workflow.docx_workflow',
    'workflow.md_based_workflow',
    'workflow.txt_workflow',
    'workflow.json_workflow',
    'workflow.xlsx_workflow',
    'workflow.html_workflow',
    'workflow.srt_workflow',
    'workflow.epub_workflow',
    'workflow.mobi_workflow',
    'workflow.qt_ts_workflow',
    'workflow.pptx_workflow',
    'workflow.html_to_markdown_export',
    'workflow.html_table_to_markdown',
    'html2text',
    'bs4',
    # extractor (lazy-imported for HTML / Fetch URL workflows)
    'extractor',
    'extractor.base',
    'extractor.html_extractor',
    # Config manager
    'backend.config_manager',
]

# Collect third-party resources
for package in ['pygments', 'latex2mathml', 'mobi', 'ebooklib']:
    try:
        tmp_ret = collect_all(package)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Failed to collect resources for {package}: {e}")

# Custom data files
custom_datas = [
    # Static files (Flutter Web frontend)
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    # Configuration templates
    ('./configs/system.json.template', 'configs/'),
    ('./configs/platforms.json.template', 'configs/'),
    ('./configs/ui.json.template', 'configs/'),
    ('./configs/secrets.json.template', 'configs/'),
    ('./configs/local.json.template', 'configs/'),
    ('./configs/translation_config.json.template', 'configs/'),  # Translation configuration template
    ('./configs/static.json.template', 'configs/'),  # Static configuration template
    ('./configs/app_config.json.template', 'configs/'),
    ('./configs/local_users.json.template', 'configs/'),
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),
    ('./setup_secrets.py', '.'),  # Sensitive configuration initialization script
    ('./setup_first_deploy.py', '.'),  # First deployment setup script
]

# Add pandoc if available
if sys.platform.startswith('win'):
    _pandoc_dir = _project_root / '3rdParty' / 'windows'
    if _pandoc_dir.is_dir():
        for _p in _pandoc_dir.iterdir():
            if _p.is_dir() and _p.name.startswith('pandoc-') and (_p / 'pandoc.exe').exists():
                datas.append((str(_p), '3rdParty/windows/' + _p.name))
                break

for data in custom_datas:
    if data not in datas:
        datas.append(data)

# NumPy compatibility
try:
    import numpy
    _np_version = tuple(int(x) for x in numpy.__version__.split('.')[:2])
    _np_has_core = hasattr(numpy, '_core')
except Exception:
    _np_version = (1, 0)
    _np_has_core = False

if _np_has_core or _np_version >= (2, 0):
    _np_core_prefix = 'numpy._core'
else:
    _np_core_prefix = 'numpy.core'

numpy_essential = [
    f'{_np_core_prefix}.multiarray',
    f'{_np_core_prefix}.umath',
    f'{_np_core_prefix}._multiarray_umath',
    f'{_np_core_prefix}.overrides',
]
hiddenimports = list(set(hiddenimports + numpy_essential))

# Analysis
a = Analysis(
    ['backend/config_manager.py'],  # Entry point: single-file launcher
    pathex=[os.getcwd(), os.path.join(os.getcwd(), 'backend')],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[str(_project_root.resolve())],
    hooksconfig={},
    runtime_hooks=['hook-numpy-fix.py'],
    excludes=[
        'numpy.tests', 'numpy.testing', 'numpy._pyinstaller', 'numpy.f2py.tests',
        'numpy.ma.tests', 'numpy.lib.tests', 'numpy.core.tests', 'numpy.random.tests',
        'numpy.linalg.tests', 'numpy.fft.tests', 'numpy.polynomial.tests',
        'numpy.matrixlib.tests', 'numpy.typing.tests', 'numpy.compat.tests',
        'numpy._core.tests', 'numpy._typing.tests',
        'numpy.core._add_newdocs', 'numpy.core.machar', 'numpy.core.umath_tests',
        'numpy._core._add_newdocs', 'numpy.core._multiarray_tests',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Single-file executable configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Owlangs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,  # Use system temp directory
    console=True,  # Show console for interactive mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=next(
        (
            p
            for p in (
                os.path.join('frontend', 'windows', 'runner', 'resources', 'app_icon.ico'),
                'Owlangs.ico',
                'favicon.ico',
                os.path.join('backend', 'static', 'favicon.ico'),
            )
            if os.path.isfile(p)
        ),
        None,
    ),
)
