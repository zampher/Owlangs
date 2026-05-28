# -*- mode: python ; coding: utf-8 -*-
# Portable executable spec for Owlangs Enterprise Edition
# This creates a standalone exe that:
# 1. Extracts to temp directory on first run
# 2. Initializes user configs in C:\ProgramData\Owlangs
# 3. Starts backend server
# 4. Opens browser automatically

import os
import sys
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Ensure local source takes precedence over editable installs in the active venv
_project_root = Path(os.getcwd())
_project_root_str = str(_project_root)
_project_backend_str = str(_project_root / 'backend')
# Remove old editable-install path hooks that shadow local backend
sys.path = [
    p for p in sys.path
    if not (isinstance(p, str) and 'owlangs' in p.lower() and 'editable' in p.lower())
]
if _project_backend_str not in sys.path:
    sys.path.insert(0, _project_backend_str)
if _project_root_str not in sys.path:
    sys.path.insert(0, _project_root_str)

# Ensure Flutter Web frontend is built and synced before packaging
_frontend_build_dir = _project_root / 'frontend' / 'build' / 'web'
_backend_flutter_dir = _project_root / 'backend' / 'static' / 'flutter-web'

if _frontend_build_dir.exists():
    _frontend_index = _frontend_build_dir / 'index.html'
    _backend_index = _backend_flutter_dir / 'index.html'
    _needs_sync = True
    if _backend_index.exists() and _frontend_index.exists():
        if _backend_index.stat().st_mtime >= _frontend_index.stat().st_mtime - 5:
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
    print(f"[BUILD-SYNC] Warning: frontend/build/web not found.")

# Try to get version from environment variable first (set by build script)
# Then try to import backend, then try pyproject.toml
_version = os.environ.get('OWLANGS_VERSION', None)
if not _version:
    try:
        import backend
        _version = backend.__version__
    except (ImportError, AttributeError):
        # Try to read from pyproject.toml
        try:
            import tomllib
            pyproject_path = _project_root / "pyproject.toml"
            if pyproject_path.exists():
                data = tomllib.loads(pyproject_path.read_text("utf-8"))
                _version = data.get("project", {}).get("version", "0.0.0")
            else:
                _version = "0.0.0"
        except Exception:
            _version = "0.0.0"
else:
    # Ensure _version is a plain string, not a list
    if not isinstance(_version, str):
        _version = str(_version)

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
    'backend.app.models',
    'backend.app.models.anonymize',
    'backend.app.models.service',
    'backend.app.models.translation_segment',
    # Frozen runtime: backend.app.services path
    'backend.app.services.translation.translation_execution_queue',
    'backend.app.services.translation.translation_queue_utils',
    'backend.app.services.translation.translation_result_stash',
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
    # tbx_converter: all imports in auth/routes.py are lazy (inside function bodies)
    'glossary.tbx_converter',
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
    # MCP server modules
    'backend.mcp_server',
    'backend.mcp_server.server',
    'backend.mcp_server.service_layer',
    'backend.owlangs_cli',
    'backend.mcp_server.tools',
    'backend.mcp_server.tools.config_tools',
    'backend.mcp_server.tools.translate_tools',
    'backend.mcp_server.tools.glossary_tools',
    'backend.mcp_server.tools.convert_tools',
    'backend.mcp_server.resources',
    'backend.mcp_server.resources.providers',
    'backend.mcp_server.prompts',
    'backend.mcp_server.prompts.templates',
    # MCP protocol package
    'mcp',
    'mcp.server',
    'mcp.server.fastmcp',
    'mcp.server.models',
    'mcp.server.session',
    'mcp.server.lowlevel',
    'mcp.shared',
    'mcp.shared.session',
    'mcp.shared.request_id',
    'mcp.shared.context',
    'mcp.types',
    'mcp.tool',
    'mcp.resource',
    'mcp.prompt',
    # MCP transport dependencies
    'sse_starlette',
    'sse_starlette.sse',
    'httpx_sse',
    'pyjwt',
    'pydantic_settings',
    'anyio',
    'anyio.streams',
    'anyio.streams.stapled',
    # Markdown extensions (imported by md_translator/md_splitter)
    'markdown.extensions.tables',
    'pymdownx.arithmatex',
    'pymdownx.superfences',
    'pymdownx.highlight',
    'pygments',
    # DOCX formula OMML (LaTeX -> MathML -> OMML)
    'latex2mathml', 'latex2mathml.converter', 'mathml2omml', 'mathml2omml_as',
    # JSON repair for LLM output
    'json_repair',
    # python-pptx library for PPTX processing
    'pptx',
    'pptx.util',
    'pptx.dml.color',
    'pptx.enum.shapes',
    'pptx.enum.text',
    'pptx.shapes.base',
    'pptx.shapes.group',
    'pptx.shapes.autoshape',
    'pptx.table',
    'pptx.shapes.freeform',
    'pptx.text.text',
    # layout module
    'layout',
    'layout.base',
    'layout.mineru_layout_model',
    # pdf_splitter, layout_merger, mineru_zip_merger
    'backend.utils.pdf_splitter',
    'backend.utils.layout_merger',
    'backend.utils.mineru_zip_merger',
    # mobi dependencies
    'loguru',
    'imghdr',
]

# Collect third-party resources for mobi/ebooklib/mcp
for _pkg in ['mobi', 'ebooklib', 'mcp']:
    try:
        _pkg_datas, _, _pkg_hiddenimports = collect_all(_pkg)
        datas += _pkg_datas
        hiddenimports += _pkg_hiddenimports
    except Exception as e:
        print(f"Warning: Failed to collect resources for {_pkg}: {e}")

# Only include necessary pygments/latex2mathml data files
datas.extend([
    *collect_data_files('pygments', include_py_files=False),
    *collect_data_files('latex2mathml'),
])

# Custom data files
custom_datas = [
    # Static files (Flutter Web frontend)
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    # Flutter Web frontend (explicit)
    ('./backend/static/flutter-web', 'backend/static/flutter-web'),
    # Configuration templates
    ('./configs/system.json.template', 'configs/'),
    ('./configs/platforms.json.template', 'configs/'),
    ('./configs/ui.json.template', 'configs/'),
    ('./configs/secrets.json.template', 'configs/'),
    ('./configs/local.json.template', 'configs/'),
    ('./configs/translation_config.json.template', 'configs/'),
    ('./configs/static.json.template', 'configs/'),
    ('./configs/app_config.json.template', 'configs/'),
    ('./configs/local_users.json.template', 'configs/'),
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),
    ('./setup_secrets.py', '.'),
    ('./setup_first_deploy.py', '.'),
]

# Redis executable and configuration files (Windows only)
if sys.platform.startswith('win'):
    _redis_files = [
        ('./3rdParty/windows/Redis-x64-3.0.504/redis-server.exe', '3rdParty/windows/Redis-x64-3.0.504/redis-server.exe'),
        ('./3rdParty/windows/Redis-x64-3.0.504/redis.windows.conf', '3rdParty/windows/Redis-x64-3.0.504/redis.windows.conf'),
        ('./3rdParty/windows/Redis-x64-3.0.504/redis.windows-service.conf', '3rdParty/windows/Redis-x64-3.0.504/redis.windows-service.conf'),
    ]
    for _src, _dst in _redis_files:
        if os.path.exists(_src):
            datas.append((_src, _dst))

# Add pandoc if available
if sys.platform.startswith('win'):
    _pandoc_dir = os.path.join(os.getcwd(), '3rdParty', 'windows')
    if os.path.isdir(_pandoc_dir):
        for _name in os.listdir(_pandoc_dir):
            if _name.startswith('pandoc-'):
                _path = os.path.join(_pandoc_dir, _name)
                if os.path.isdir(_path) and os.path.isfile(os.path.join(_path, 'pandoc.exe')):
                    datas.append((_path, os.path.join('3rdParty', 'windows', _name)))
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

# Excludes: large ML/AI frameworks not needed in this build
_include_anonymize = os.environ.get('OWLANGS_INCLUDE_ANONYMIZE') == '1'
_excludes_always = [
    "docling", "backend.converter.x2md.converter_docling",
    "torch", "torchvision", "torchaudio",
    "transformers", "tokenizers", "sentencepiece",
    "easyocr", "cv2", "opencv-python",
    "scipy", "pandas", "matplotlib", "seaborn",
    "sklearn", "scikit-learn",
    "nltk", "gensim", "jieba",
    "celery", "sqlalchemy",
    "safetensors", "huggingface_hub",
    "pytest", "pytest-asyncio", "pytest-cov",
    "black", "flake8", "mypy",
    "jupyter", "ipython", "notebook",
    "tensorflow", "keras",
    "xgboost", "lightgbm",
    # numpy test excludes
    'numpy.tests', 'numpy.testing', 'numpy._pyinstaller', 'numpy.f2py.tests',
    'numpy.ma.tests', 'numpy.lib.tests', 'numpy.core.tests', 'numpy.random.tests',
    'numpy.linalg.tests', 'numpy.fft.tests', 'numpy.polynomial.tests',
    'numpy.matrixlib.tests', 'numpy.typing.tests', 'numpy.compat.tests',
    'numpy._core.tests', 'numpy._typing.tests',
    'numpy.core._add_newdocs', 'numpy.core.machar', 'numpy.core.umath_tests',
    'numpy._core._add_newdocs', 'numpy.core._multiarray_tests',
]
_excludes_no_anonymize = [
    "presidio_analyzer", "presidio_anonymizer", "anonymize",
    "spacy", "numpy",
]
_excludes = _excludes_always + (_excludes_no_anonymize if not _include_anonymize else [])

# Analysis
a = Analysis(
    ['backend/config_manager.py'],  # Entry point: single-file launcher
    pathex=[os.getcwd(), os.path.join(os.getcwd(), 'backend')],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=['hook-numpy-fix.py'],
    excludes=_excludes,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

# Single-file executable configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Owlangs-{_version}',
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
