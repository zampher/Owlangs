# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Ensure Flutter Web frontend is built and synced before packaging
_project_root = Path(os.getcwd())
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
            from pathlib import Path
            pyproject_path = Path("pyproject.toml")
            if pyproject_path.exists():
                data = tomllib.loads(pyproject_path.read_text("utf-8"))
                _version = data.get("project", {}).get("version", "0.0.0")
            else:
                _version = "0.0.0"
        except Exception:
            _version = "0.0.0"

datas = [
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),  # Add i18n directory
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    # Flutter Web frontend (built from frontend/build/web)
    ('./backend/static/flutter-web', 'backend/static/flutter-web'),
    # New config structure templates
    ('./configs/system.json.template', 'configs/'),  # System configuration template
    ('./configs/platforms.json.template', 'configs/'),  # Platforms configuration template

    ('./configs/secrets.json.template', 'configs/'),  # Secrets configuration template
    ('./configs/local.json.template', 'configs/'),  # Local configuration template
    ('./configs/translation_config.json.template', 'configs/'),  # Translation configuration template
    ('./configs/static.json.template', 'configs/'),  # Static configuration template
    # Legacy config template (for backward compatibility)
    ('./configs/app_config.json.template', 'configs/'),  # Application configuration template
    ('./configs/local_users.json.template', 'configs/'),  # Local users template file
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),  # Default user profile template
    ('./setup_secrets.py', '.'),  # Sensitive configuration initialization script
    ('./setup_first_deploy.py', '.'),  # First deployment setup script
]

# Redis executable and configuration files (Windows only)
if sys.platform.startswith('win'):
    redis_files = [
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis-server.exe', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis-server.exe'),
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows.conf', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows.conf'),
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows-service.conf', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows-service.conf'),
    ]
    for src, dst in redis_files:
        if os.path.exists(src):
            datas.append((src, dst))

datas.extend([
    # Only include necessary pygments data, exclude large files
    *collect_data_files('pygments', include_py_files=False),  # Only include data files, not Python files
    # latex2mathml: unimathsymbols.txt required for LaTeX->MathML->OMML in frozen build
    *collect_data_files('latex2mathml'),
])

# Optional: bundle Pandoc on Windows for HTML->DOCX export (document_rebuild._get_pandoc_path)
# Use os.getcwd() because PyInstaller exec() may not set __file__ in spec namespace
if sys.platform.startswith('win'):
    _pandoc_dir = os.path.join(os.getcwd(), '3rdParty', 'windows')
    if os.path.isdir(_pandoc_dir):
        for _name in os.listdir(_pandoc_dir):
            if _name.startswith('pandoc-'):
                _path = os.path.join(_pandoc_dir, _name)
                if os.path.isdir(_path) and os.path.isfile(os.path.join(_path, 'pandoc.exe')):
                    datas.append((_path, os.path.join('3rdParty', 'windows', _name)))
                    break

hiddenimports = [
    'markdown.extensions.tables',
    'pymdownx.arithmatex',
    'pymdownx.superfences',
    'pymdownx.highlight',
    'pygments',
    # DOCX formula OMML (LaTeX -> MathML -> OMML); mathml2omml_as fallback when mathml2omml output fails to parse
    'latex2mathml', 'latex2mathml.converter', 'mathml2omml', 'mathml2omml_as',
    # JSON repair for LLM output (md_translator, segments_agent, glossary_agent)
    'json_repair',
    # Code imports "from utils.xxx"; bundle has backend.utils; cli injects sys.modules["utils"] = backend.utils
    'utils',  # Must be imported first: aliases backend.utils.* → utils.* for legacy imports
    'backend.utils',
    'backend.runtime_version',
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
    'backend.utils.epub_fix',
    'backend.utils.ebook_metadata',
    'backend.utils.latex_formula_checker', 'backend.utils.latex_repair_llm',
    'backend.utils.latex_repair_payload', 'backend.utils.latex_formula_batch_repair',
    # Pandoc/DOCX math normalize & fragment repair (becc134; imported by format_convert_utils, md2docx_exporter, fragment services)
    'backend.utils.math_md_normalize',
    'backend.utils.docx_md_normalize',
    'backend.utils.docx_algorithm_latex_wrap',
    'backend.utils.docx_math_fragment_check',
    'backend.utils.docx_math_fragment_llm_repair',
    'backend.utils.llm_client',
    'backend.utils.extract_segments_debug',
    'backend.utils.bilingual_export_utils',
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
    # Frozen runtime: PyInstaller may resolve translation services via backend.app.services path
    'backend.app.services.translation.translation_execution_queue',
    'backend.app.services.translation.translation_queue_utils',
    'backend.app.services.translation.translation_result_stash',
    'app.services',
    'app.services.task',
    'app.services.task.batch_manager',
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
                # Platform service
                'app.services.platform',
                'app.services.platform.platform_service',
                # Ensure app routes are imported (required for new_service_router)
    'app.routes',
    'app.routes.app_routes_main',
    'app.routes.settings',
    'app.routes.service',
    'app.routes.service.app_routes_translation',
    'app.routes.service.app_routes_batches',
    'app.routes.service.app_routes_download',
    'app.routes.service.app_routes_status',
    'app.routes.service.app_routes_format_conversion',
    'app.routes.service.app_routes_glossary',
    # tbx_converter: all imports in auth/routes.py are lazy (inside function bodies)
    'glossary.tbx_converter',
    'app.routes.service.app_routes_translation_segments',
    'app.routes.service.app_routes_formula_check',
    # Ensure app.utils is available (alias for backend.app.utils)
    'app.utils',
    'app.utils.encoding_utils',
    'app.utils.url_fetcher',
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
    # HTML→MD (XLSX/PPTX export_md, download_service); lazy-imported from workflows
    'workflow.html_to_markdown_export',
    'workflow.html_table_to_markdown',
    'html2text',
    'bs4',
    # extractor (lazy-imported for HTML / Fetch URL workflows)
    'extractor',
    'extractor.base',
    'extractor.html_extractor',
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
    # layout module: used by layout_merger and mineru_zip_merger
    'layout',
    'layout.base',
    'layout.mineru_layout_model',
    'layout.markdown_builder',
    'layout.registry',
    # layout PDF renderer - Typst overlay (high-fidelity PDF export)
    'layout.pdf_renderer',
    'layout.pdf_renderer.config',
    'layout.pdf_renderer.typst_overlay',
    'layout.pdf_renderer.typst_overlay.renderer',
    'layout.pdf_renderer.typst_overlay.compiler',
    'layout.pdf_renderer.typst_overlay.emitter',
    'layout.pdf_renderer.typst_overlay.models',
    'layout.pdf_renderer.typst_overlay.font_fit',
    'layout.pdf_renderer.typst_overlay.formula_safety',
    'layout.pdf_renderer.typst_overlay.source_cleanup',
    'layout.pdf_renderer.typst_overlay.overlay_merge',
    'layout.pdf_renderer.typst_overlay.segment_font_metrics',
    'layout.pdf_renderer.typst_overlay.text_metrics',
    'layout.pdf_renderer.typst_overlay.affected_pages',
    'layout.pdf_renderer.typst_overlay.pdf_preview_cache',
    # PyMuPDF (required by typst overlay source_cleanup and overlay_merge)
    'fitz',
    # pdf_splitter, layout_merger, mineru_zip_merger: dynamic imports in converter_mineru.py
    'backend.utils.pdf_splitter',
    'backend.utils.layout_merger',
    'backend.utils.mineru_zip_merger',
    # mobi dependencies (ensure loguru and imghdr are included in frozen build)
    'loguru',
    'imghdr',
# Exporter modules (imported by all workflows for output generation)
    'exporter',
    'exporter.base',
    # IR (intermediate representation) and glossary (imported by mobi/epub workflows)
    'ir',
    'ir.document',
    'glossary',
    'glossary.glossary',
    # Translator AI modules (imported by mobi/epub workflows)
    'translator',
    'translator.ai_translator',
    'translator.ai_translator.mobi_translator',
    'translator.ai_translator.epub_translator',
    # Additional extractor modules for mobi/epub
    'extractor.mobi_extractor',
    'extractor.epub_extractor',
    # Logger modules (optional, for enhanced logging)
    'backend.logger',
    'backend.logger.logger',
    'backend.logger.log_messages',
    'backend.logger.module_log_manager',
    'backend.logger.module_logging',
    # Config modules
    'backend.app.config',
    'backend.app.config.pagination_config',
    # Additional services modules (imported by workflow_config_builder)
    'backend.app.services.status',
    'backend.app.services.status.status_service',
    'backend.app.services.format_conversion_service',
    'backend.app.services.glossary_generation_service',
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
    'jwt',
    'pydantic_settings',
    'anyio',
    'anyio.streams',
    'anyio.streams.stapled',
]

# mobi/ebooklib/mcp: required for MOBI/EPUB extraction, conversion, and MCP server in frozen build
for _pkg in ['mobi', 'ebooklib', 'mcp']:
    try:
        _pkg_datas, _, _pkg_hiddenimports = collect_all(_pkg)
        datas += _pkg_datas
        hiddenimports += _pkg_hiddenimports
    except Exception as e:
        print(f"Warning: Failed to collect resources for {_pkg}: {e}")

# Prefer Flutter runner ICO (generated by: python tools/generate_ico.py --frontend)
_icon_candidates = [
    os.path.join('frontend', 'windows', 'runner', 'resources', 'app_icon.ico'),
    'favicon.ico',
    os.path.join('backend', 'static', 'favicon.ico'),
]
icon_path = next((p for p in _icon_candidates if os.path.isfile(p)), None)

# Anonymize as optional: when OWLANGS_INCLUDE_ANONYMIZE=1, bundle presidio/spacy and models; otherwise exclude them
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
]
_excludes_no_anonymize = [
    "presidio_analyzer", "presidio_anonymizer", "anonymize",
    "spacy", "numpy",
]
_excludes = _excludes_always + (_excludes_no_anonymize if not _include_anonymize else [])

a = Analysis(
    ['backend/cli.py'],  # Use backend/cli.py as entry point (Launcher starts server via -i)
    pathex=[os.getcwd(), os.path.join(os.getcwd(), 'backend')],  # Add current working directory and backend to pathex
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.'],  # Add current directory to hookspath to use custom hooks
    hooksconfig={},
    runtime_hooks=['hook-numpy-fix.py'],
    excludes=_excludes,
    noarchive=False,
    optimize=2,  # Enable Python bytecode optimization
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
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)