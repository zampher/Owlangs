# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all
import backend

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

datas = [
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),  # Add i18n directory
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    # Config templates: first run copies these to ~/Library/Application Support/Owlangs/config/
    ('./configs/system.json.template', 'config/templates/'),
    ('./configs/platforms.json.template', 'config/templates/'),
    ('./configs/ui.json.template', 'config/templates/'),
    ('./configs/secrets.json.template', 'config/templates/'),
    ('./configs/local.json.template', 'config/templates/'),
    ('./configs/translation_config.json.template', 'config/templates/'),
    ('./configs/static.json.template', 'config/templates/'),
    ('./configs/local_users.json.template', 'config/templates/'),
]
# Flutter Web frontend (built by build_macos.sh; include only if present)
if os.path.isdir('./backend/static/flutter-web'):
    # make sure flutter-web directory is included corrrectly.
    datas.append(('./backend/static/flutter-web', 'backend/static/flutter-web'))
# Application configuration file (include if present; template as fallback for default)
if os.path.isfile('./configs/app_config.json'):
    datas.append(('./configs/app_config.json', 'config/'))
elif os.path.isfile('./configs/app_config.json.template'):
    datas.append(('./configs/app_config.json.template', 'config/'))
datas += [
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),  # Default user profile template
    ('./setup_secrets.py', '.'),  # Sensitive configuration initialization script
    ('./setup_first_deploy.py', '.')  # First deployment setup script
    # Note: Redis config files are Windows-specific, not needed for macOS
]

# Collect pygments and latex2mathml data files (unimathsymbols.txt for LaTeX->OMML in DOCX)
datas += collect_data_files('pygments')
datas += collect_data_files('latex2mathml')

hiddenimports = [
    # macOS launch signal

    # Markdown / syntax
    'markdown.extensions.tables',
    'pymdownx.arithmatex',
    'pymdownx.superfences',
    'pymdownx.highlight',
    'pygments',
    'json_repair',
    # DOCX formula: LaTeX -> MathML -> OMML
    'latex2mathml',
    'latex2mathml.converter',
    'mathml2omml',
    'mathml2omml_as',
    # backend + logger
    'backend',
    'backend.logger',
    'backend.logger.logger',
    'backend.logger.log_messages',
    'backend.logger.module_log_manager',
    'backend.logger.module_logging',
    # backend.utils (cli injects sys.modules["utils"] = backend.utils)
    'backend.utils',
    'backend.utils.resource_utils',
    'backend.utils.redis_manager',
    'backend.utils.utils',
    'backend.utils.language_utils',
    'backend.utils.path_utils',
    'backend.utils.font_utils',
    'backend.utils.macos_launch_signal',
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
    # LaTeX integrity check service routes (utils.latex_formula_checker, utils.latex_repair_llm)
    'backend.utils.latex_formula_checker', 'backend.utils.latex_repair_llm',
    'backend.utils.latex_repair_payload', 'backend.utils.latex_formula_batch_repair',
    # Pandoc/DOCX math normalize & fragment repair (formula export pipeline)
    'backend.utils.math_md_normalize',
    'backend.utils.docx_md_normalize',
    'backend.utils.docx_algorithm_latex_wrap',
    'backend.utils.docx_math_fragment_check',
    'backend.utils.docx_math_fragment_llm_repair',
    # LLM client used by latex repair
    'backend.utils.llm_client',
    'backend.utils.extract_segments_debug',
    # backend.app (uvicorn "app.factory:app"; app = backend/app when backend_dir on path)
    'backend.app',
    'backend.app.factory',
    'backend.app.app_main',
    'backend.app.middleware',
    'backend.app.middleware.request_id',
    'backend.app.middleware.https_redirect',
    'backend.app.routes',
    'backend.app.routes.app_routes_main',
    'backend.app.routes.settings',
    'backend.app.routes.export',
    'backend.app.routes.service',
    'backend.app.routes.service.app_routes_translation',
    'backend.app.routes.service.app_routes_download',
    'backend.app.routes.service.app_routes_status',
    'backend.app.routes.service.app_routes_format_conversion',
    'backend.app.routes.service.app_routes_glossary',
    'backend.app.routes.service.app_routes_translation_segments',
    # backend.app.models, config, utils (used by routes and services)
    'backend.app.models',
    'backend.app.models.service',
    'backend.app.models.anonymize',
    'backend.app.models.translation_segment',
    'backend.app.config',
    'backend.app.config.pagination_config',
    'backend.app.utils',
    'backend.app.utils.encoding_utils',
    'backend.app.utils.port',
    'backend.app.utils.app_utils',
    # backend.app.services (task, translation, download, status, platform, etc.)
    'backend.app.services.task',
    'backend.app.services.translation',
    'backend.app.services.translation.workflow_factory',
    'backend.app.services.translation.workflow_config_builder',
    'backend.app.services.translation.workflow_executor',
    'backend.app.services.translation.prompt_service',
    'backend.app.services.translation.source_preview_service',
    'backend.app.services.translation.translation_segment_service',
    'backend.app.services.translation.chunk_size_service',
    'backend.app.services.translation.translation_execution_queue',
    'backend.app.services.translation.translation_queue_utils',
    'backend.app.services.translation.translation_result_stash',
    'backend.app.services.download',
    'backend.app.services.download.download_service',
    'backend.app.services.download.output_generator',
    'backend.app.services.download.pdf_generator',
    'backend.app.services.status',
    'backend.app.services.status.status_service',
    'backend.app.services.platform',
    'backend.app.services.platform.platform_service',
    'backend.app.services.format_conversion_service',
    'backend.app.services.glossary_generation_service',
    'backend.app.services.version_service',
    # auth (factory includes auth_router when AUTH_AVAILABLE)
    'backend.auth',
    'backend.auth.routes',
    'backend.auth.models',
    # workflow (backend/workflow; runtime path has backend so "workflow" resolves)
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
    'pptx.table',
    'pptx.shapes.freeform',
    'pptx.text.text',
    # layout module: used by layout_merger and mineru_zip_merger
    'layout',
    'layout.base',
    'layout.mineru_layout_model',
    # pdf_splitter, layout_merger, mineru_zip_merger: dynamic imports in converter_mineru.py
    'backend.utils.pdf_splitter',
    'backend.utils.layout_merger',
    'backend.utils.mineru_zip_merger',
    # MOBI/EPUB: exporter, ir, translator, extractor, agents, glossary, third-party mobi/ebooklib
    'exporter',
    'exporter.base',
    'exporter.mobi',
    'exporter.mobi.base',
    'exporter.mobi.mobi2html_exporter',
    'exporter.mobi.mobi2mobi_exporter',
    'exporter.epub',
    'exporter.epub.base',
    'exporter.epub.epub2epub_exporter',
    'exporter.epub.epub2html_exporter',
    'ir',
    'ir.document',
    'translator.ai_translator.mobi_translator',
    'translator.ai_translator.epub_translator',
    'extractor',
    'extractor.base',
    'extractor.mobi_extractor',
    'extractor.epub_extractor',
    'agents',
    'agents.segments_agent',
    'glossary',
    'glossary.glossary',
    'mobi',
    'ebooklib',
    'ebooklib.epub',
    # mobi dependencies
    'loguru',
    'imghdr',
]

# Collect mobi and ebooklib modules/data for MOBI/EPUB support in frozen build
for _pkg in ['mobi', 'ebooklib']:
    try:
        _pkg_datas, _, _pkg_hiddenimports = collect_all(_pkg)
        datas += _pkg_datas
        hiddenimports += _pkg_hiddenimports
        print(f"[PYINSTALLER] Collected {_pkg}: datas={len(_pkg_datas)}, hiddenimports={len(_pkg_hiddenimports)}")
    except Exception as e:
        print(f"Warning: Failed to collect resources for {_pkg}: {e}")

# Always exclude docling (not used on macOS)
_excludes = ["docling", "backend.converter.x2md.converter_docling"]

a = Analysis(
    ['backend/cli.py'],  # Entry point: CLI (Launcher starts server via -i)
    pathex=[os.getcwd(), os.path.join(os.getcwd(), 'backend')],  # So PyInstaller finds workflow (backend/workflow)
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.getcwd()],  # Use project hook-workflow.py (local backend/workflow), not contrib copy_metadata('workflow')
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

import os

target_arch = os.environ.get('PYI_TARGET_ARCH', None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Owlangs-{backend.__version__}-mac',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    icon='Owlangs.icns',
    target_arch=target_arch,
)