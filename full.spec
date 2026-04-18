# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Add project root to sys.path (PyInstaller runs from repo root; __file__ is not defined in spec context)
_project_root = Path(os.getcwd())
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Ensure Flutter Web frontend is built and synced before packaging
# This is necessary because backend/static/flutter-web is in .gitignore
_frontend_build_dir = _project_root / 'frontend' / 'build' / 'web'
_backend_flutter_dir = _project_root / 'backend' / 'static' / 'flutter-web'

if _frontend_build_dir.exists():
    # Check if we need to sync (frontend build is newer than backend copy)
    _frontend_index = _frontend_build_dir / 'index.html'
    _backend_index = _backend_flutter_dir / 'index.html'
    
    _needs_sync = True
    if _backend_index.exists() and _frontend_index.exists():
        _frontend_mtime = _frontend_index.stat().st_mtime
        _backend_mtime = _backend_index.stat().st_mtime
        # Sync if frontend is more than 5 seconds newer
        if _backend_mtime >= _frontend_mtime - 5:
            _needs_sync = False
            print(f"[BUILD-SYNC] backend/static/flutter-web is up to date")
    
    if _needs_sync:
        print(f"[BUILD-SYNC] Syncing frontend/build/web to backend/static/flutter-web...")
        try:
            if _backend_flutter_dir.exists():
                shutil.rmtree(_backend_flutter_dir)
            shutil.copytree(_frontend_build_dir, _backend_flutter_dir)
            print(f"[BUILD-SYNC] Successfully synced Flutter Web build")
        except Exception as e:
            print(f"[BUILD-SYNC] Warning: Failed to sync: {e}")
else:
    print(f"[BUILD-SYNC] Warning: frontend/build/web not found. Run 'flutter build web' first.")
    if not _backend_flutter_dir.exists():
        print(f"[BUILD-SYNC] ERROR: backend/static/flutter-web also missing. Web UI will not work!")

# Try to import backend
try:
    import backend
except ImportError:
    # If backend cannot be imported, we'll handle it gracefully
    backend = None

# Initialize lists
datas = []
binaries = []
hiddenimports = ['markdown.extensions.tables', 'pymdownx.arithmatex',
                'pymdownx.superfences', 'pymdownx.highlight', 'pygments',
                # DOCX formula OMML (LaTeX -> MathML -> OMML); mathml2omml_as fallback when mathml2omml output fails to parse
                'latex2mathml', 'latex2mathml.converter', 'mathml2omml', 'mathml2omml_as',
                # JSON repair for LLM output (md_translator, segments_agent, glossary_agent)
                'json_repair',
                'backend.utils', 'backend.utils.resource_utils',
                'backend.utils.redis_manager', 'backend.utils.utils',
                'backend.utils.language_utils', 'backend.utils.path_utils',
                'backend.utils.resource_utils', 'backend.utils.font_utils',
                'backend.utils.pagination', 'backend.utils.document_rebuild',
                'backend.utils.translation_segments', 'backend.utils.markdown_splitter',
                'backend.utils.markdown_utils', 'backend.utils.json_utils',
                'backend.utils.chunk_translation_helper', 'backend.utils.translation_validator',
                'backend.utils.chunk_size_converter', 'backend.utils.token_estimator',
                'backend.utils.docx_utils', 'backend.utils.table_utils',
                'backend.utils.image_placeholder_utils', 'backend.utils.format_convert_utils',
                'backend.utils.mixed_formula_text',
                'backend.utils.markdown_chunk_merger', 'backend.utils.language_detection_utils',
                'backend.utils.language_detector',
                # LaTeX integrity check service routes (utils.latex_formula_checker, utils.latex_repair_llm)
                'backend.utils.latex_formula_checker', 'backend.utils.latex_repair_llm',
                'backend.utils.latex_repair_payload', 'backend.utils.latex_formula_batch_repair',
                # LLM client used by latex repair
                'backend.utils.llm_client',
                'backend.utils.extract_segments_debug',
                # Ensure app module is imported
                'app',
                'app.app_main',
                'app.factory',
                'app.__init__',
                'app.middleware',
                'app.middleware.request_id',
                'app.middleware.https_redirect',
                # Ensure app models and services are imported
                'app.models',
                'app.models.anonymize',
                'app.models.service',
                'app.models.translation_segment',
                # Frozen runtime: PyInstaller may resolve via backend.app.models path
                'backend.app.models',
                'backend.app.models.anonymize',
                'backend.app.models.service',
                'backend.app.models.translation_segment',
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
                # Platform service
                'app.services.platform',
                'app.services.platform.platform_service',
                # Ensure app routes are imported (required for new_service_router)
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
                # Ensure app.utils is available (alias for backend.app.utils)
                'app.utils',
                'app.utils.encoding_utils',
                # Ensure workflow module is imported (local module, not a package)
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
                # python-pptx library for PPTX processing
                'pptx',
                'pptx.util',
                'pptx.dml.color',
                'pptx.enum.shapes',
                'pptx.enum.text',
                'pptx.shapes.base',
                'pptx.shapes.group',
                'pptx.shapes.autoshape',
                'pptx.shapes.table',
                'pptx.shapes.freeform',
                'pptx.text.text',
            ]

# First collect third-party package resources (collect if exists)
# latex2mathml: unimathsymbols.txt required for LaTeX->MathML->OMML in frozen build
for package in ['pygments', 'latex2mathml', 'mobi', 'ebooklib']:
    try:
        tmp_ret = collect_all(package)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Failed to collect resources for {package}: {e}")

# Then add your custom resources (avoid duplicates)
# Note: Use 'backend' directory name as that's the actual source directory
# PyInstaller will map it to 'backend' in the package
custom_datas = [
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),  # Add i18n directory
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    # Flutter Web frontend (built from frontend/build/web)
    ('./backend/static/flutter-web', 'backend/static/flutter-web'),
    # New config structure templates
    ('./configs/system.json.template', 'configs/'),  # System configuration template
    ('./configs/platforms.json.template', 'configs/'),  # Platforms configuration template
    ('./configs/ui.json.template', 'configs/'),  # UI configuration template
    ('./configs/secrets.json.template', 'configs/'),  # Secrets configuration template
    ('./configs/local.json.template', 'configs/'),  # Local configuration template
    # Legacy config files (for backward compatibility)
    ('./configs/app_config.json', 'configs/'),  # Application configuration file
    ('./configs/local_users.json.template', 'configs/'),  # Local users template file
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),  # Default user profile template
    ('./setup_secrets.py', '.'),  # Sensitive configuration initialization script
    ('./setup_first_deploy.py', '.'),  # First deployment setup script
    # Redis executable and configuration files
    ('./3rdParty/windows/Redis-x64-3.0.504/redis-server.exe', '3rdParty/windows/Redis-x64-3.0.504/redis-server.exe'),
    ('./3rdParty/windows/Redis-x64-3.0.504/redis.windows.conf', '3rdParty/windows/Redis-x64-3.0.504/redis.windows.conf'),
    ('./3rdParty/windows/Redis-x64-3.0.504/redis.windows-service.conf', '3rdParty/windows/Redis-x64-3.0.504/redis.windows-service.conf')
]

# Avoid adding duplicate data
for data in custom_datas:
    if data not in datas:
        datas.append(data)

# Optional: bundle Pandoc on Windows for HTML->DOCX export (document_rebuild._get_pandoc_path)
if sys.platform.startswith('win'):
    _pandoc_dir = _project_root / '3rdParty' / 'windows'
    if _pandoc_dir.is_dir():
        for _p in _pandoc_dir.iterdir():
            if _p.is_dir() and _p.name.startswith('pandoc-') and (_p / 'pandoc.exe').exists():
                datas.append((str(_p), '3rdParty/windows/' + _p.name))
                break

# —— Sync balance version NumPy compatibility handling ——
try:
    # Detect NumPy version to choose correct module paths
    import numpy
    _np_version = tuple(int(x) for x in numpy.__version__.split('.')[:2])
    _np_has_core = hasattr(numpy, '_core')
except Exception:
    _np_version = (1, 0)
    _np_has_core = False

# For NumPy 2.x, use numpy._core.*; for NumPy 1.x, use numpy.core.*
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

a = Analysis(
    ['backend/cli.py'],  # Entry point: CLI (Launcher starts server via -i)
    pathex=[os.getcwd(), os.path.join(os.getcwd(), 'backend')],  # Add current working directory and backend to pathex
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),  # Remove duplicates
    hookspath=[str(_project_root.resolve())],  # Must be first: use project hook-workflow.py (local backend/workflow), not contrib copy_metadata('workflow')
    hooksconfig={},
    runtime_hooks=['hook-numpy-fix.py'],
    # Sync balance numpy exclusion strategy, avoid known crash points
    excludes=[
        # numpy testing/packaging assistance
        'numpy.tests','numpy.testing','numpy._pyinstaller','numpy.f2py.tests',
        'numpy.ma.tests','numpy.lib.tests','numpy.core.tests','numpy.random.tests',
        'numpy.linalg.tests','numpy.fft.tests','numpy.polynomial.tests',
        'numpy.matrixlib.tests','numpy.typing.tests','numpy.compat.tests',
        'numpy._core.tests','numpy._typing.tests',
        # Problematic numpy core modules
        'numpy.core._add_newdocs','numpy.core.machar','numpy.core.umath_tests',
        'numpy._core._add_newdocs','numpy.core._multiarray_umath','numpy.core._multiarray_tests',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

platform_suffix = 'win' if sys.platform.startswith('win') else ('mac' if sys.platform == 'darwin' else 'linux')

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Owlangs-{platform_suffix}',  # No version in filename for simpler version updates
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
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