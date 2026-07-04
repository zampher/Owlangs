# -*- mode: python ; coding: utf-8 -*-
# Onedir (folder) portable build for Owlangs CLI + Server
# No onefile extraction overhead — files stay in a folder,启动快

import os
import sys
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.api import PYZ, EXE, COLLECT

# Ensure local source takes precedence
_project_root = Path(os.getcwd())
_project_root_str = str(_project_root)
_project_backend_str = str(_project_root / 'backend')
sys.path = [
    p for p in sys.path
    if not (isinstance(p, str) and 'owlangs' in p.lower() and 'editable' in p.lower())
]
if _project_backend_str not in sys.path:
    sys.path.insert(0, _project_backend_str)
if _project_root_str not in sys.path:
    sys.path.insert(0, _project_root_str)

# Try to get version from environment variable first (set by build script)
# Then try to import backend, then try pyproject.toml
_version = os.environ.get('OWLANGS_VERSION', None)
if not _version:
    try:
        import backend
        _version = backend.__version__
    except (ImportError, AttributeError):
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
    if not isinstance(_version, str):
        _version = str(_version)

# ── datas / binaries / hiddenimports (copied from launcher_portable.spec) ──
datas = []
binaries = []
hiddenimports = [
    'utils',  # Must be first: aliases backend.utils.* → utils.* for legacy imports
    'backend.utils', 'backend.runtime_version',
    'backend.utils.resource_utils', 'backend.utils.redis_manager',
    'backend.utils.utils', 'backend.utils.language_utils',
    'backend.utils.path_utils', 'backend.utils.font_utils',
    'backend.utils.pagination', 'backend.utils.document_rebuild',
    'backend.utils.translation_segments', 'backend.utils.markdown_splitter',
    'backend.utils.markdown_utils', 'backend.utils.json_utils',
    'backend.utils.chunk_translation_helper', 'backend.utils.translation_validator',
    'backend.utils.chunk_size_converter', 'backend.utils.token_estimator',
    'backend.utils.docx_utils', 'backend.utils.table_utils',
    'backend.utils.image_placeholder_utils', 'backend.utils.ebook_image_utils', 'backend.utils.ebook_mobi_utils',
    'utils.ebook_mobi_utils', 'backend.utils.mineru_layout_utils',
    'backend.utils.format_convert_utils',
    'backend.utils.mixed_formula_text', 'backend.utils.segment_latex_flags',
    'backend.utils.markdown_chunk_merger',
    'backend.utils.language_detection_utils', 'backend.utils.language_detector',
    'backend.utils.latex_formula_checker', 'backend.utils.latex_repair_llm',
    'backend.utils.latex_repair_payload', 'backend.utils.latex_formula_batch_repair',
    'backend.utils.math_md_normalize', 'backend.utils.docx_md_normalize',
    'backend.utils.docx_algorithm_latex_wrap', 'backend.utils.docx_math_fragment_check',
    'backend.utils.docx_math_fragment_llm_repair', 'backend.utils.llm_client',
    'backend.utils.extract_segments_debug', 'backend.utils.bilingual_export_utils',
    'backend.utils.output_suffix', 'backend.utils.batch_download_zip',
    'utils.output_suffix', 'utils.batch_download_zip',
    'backend.utils.http_content_disposition', 'utils.http_content_disposition',
    'backend.utils.epub_fix',
    'backend.utils.ebook_metadata', 'backend.utils.epub_html_segments', 'backend.utils.pdf_splitter',
    'backend.utils.layout_merger', 'backend.utils.mineru_zip_merger', 'backend.utils.mineru_image_data_map',
    'app', 'app.app_main', 'app.factory', 'app.__init__',
    'app.middleware.request_id', 'app.middleware.https_redirect',
    'app.models.anonymize', 'app.models.service', 'app.models.translation_segment',
    'backend.app.models', 'backend.app.models.anonymize',
    'backend.app.models.service', 'backend.app.models.translation_segment',
    'backend.app.services.translation.translation_execution_queue',
    'backend.app.services.translation.translation_queue_utils',
    'backend.app.services.translation.translation_result_stash',
    'app.services.task', 'app.services.task.batch_manager', 'app.services.task.queue_cleanup',
    'backend.app.services.task.queue_cleanup', 'app.services.version_service',
    'app.services.download.output_generator', 'app.services.download.download_service',
    'app.services.download.pdf_generator',
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
    'app.services.platform.platform_service',
    'app.routes.app_routes_main', 'app.routes.settings',
    'app.routes.service.app_routes_translation',
    'app.routes.service.app_routes_batches',
    'app.routes.service.app_routes_download',
    'app.routes.service.app_routes_status',
    'app.routes.service.app_routes_format_conversion',
    'app.routes.service.app_routes_glossary',
    'glossary.tbx_converter',
    'app.routes.service.app_routes_translation_segments',
    'app.routes.service.app_routes_formula_check',
    'app.routes.service.app_routes_debug',
    'app.utils.encoding_utils', 'app.utils.url_fetcher',
    'workflow.base', 'workflow.interfaces', 'workflow.docx_workflow',
    'workflow.md_based_workflow', 'workflow.txt_workflow',
    'workflow.json_workflow', 'workflow.xlsx_workflow',
    'workflow.html_workflow', 'workflow.srt_workflow',
    'workflow.epub_workflow', 'workflow.mobi_workflow',
    'workflow.qt_ts_workflow', 'workflow.pptx_workflow',
    'workflow.html_to_markdown_export', 'workflow.html_table_to_markdown',
    'html2text', 'bs4',
    'extractor.base', 'extractor.html_extractor',
    'backend.config_manager',
    'backend.mcp_server', 'backend.mcp_server.server',
    'backend.mcp_server.service_layer', 'backend.owlangs_cli',
    'backend.mcp_server.tools.config_tools',
    'backend.mcp_server.tools.translate_tools',
    'backend.mcp_server.tools.glossary_tools',
    'backend.mcp_server.tools.convert_tools',
    'backend.mcp_server.resources.providers',
    'backend.mcp_server.prompts.templates',
    'mcp', 'mcp.server', 'mcp.server.fastmcp', 'mcp.server.models',
    'mcp.server.session', 'mcp.server.lowlevel',
    'mcp.shared', 'mcp.shared.session', 'mcp.shared.request_id',
    'mcp.shared.context', 'mcp.types', 'mcp.tool', 'mcp.resource', 'mcp.prompt',
    'sse_starlette', 'sse_starlette.sse', 'httpx', 'httpx_sse', 'jwt',
    'pydantic_settings', 'anyio', 'anyio.streams.stapled',
    'markdown.extensions.tables', 'pymdownx.arithmatex',
    'pymdownx.superfences', 'pymdownx.highlight', 'pygments',
    # Ensure Python stdlib encodings are bundled for filesystem encoding init (Python 3.12+)
    'encodings',
    'latex2mathml', 'latex2mathml.converter', 'mathml2omml', 'mathml2omml_as',
    'json_repair',
    'pptx', 'pptx.util', 'pptx.dml.color', 'pptx.enum.shapes',
    'pptx.enum.text', 'pptx.shapes.base', 'pptx.shapes.group',
    'pptx.shapes.autoshape', 'pptx.table', 'pptx.shapes.freeform', 'pptx.text.text',
    'layout', 'layout.base', 'layout.block_types', 'layout.mineru_layout_model', 'layout.markdown_builder', 'layout.registry',
    # layout OCR provider - multi-engine OCR/layout parsing (MinerU + PaddleOCR)
    'layout.ocr_provider', 'layout.ocr_provider.base', 'layout.ocr_provider.types',
    'layout.ocr_provider.mineru', 'layout.ocr_provider.mineru.layout_parser', 'layout.ocr_provider.mineru.provider',
    'layout.ocr_provider.paddle', 'layout.ocr_provider.paddle.api_client',
    'layout.ocr_provider.paddle.block_labels', 'layout.ocr_provider.paddle.converter_adapter',
    'layout.ocr_provider.paddle.layout_parser', 'layout.ocr_provider.paddle.provider',
    'layout.ocr_provider.paddle.zip_loader',
    'layout.ocr_provider.paddle.paddle_det_supplements',
    # layout PDF renderer - Typst overlay (high-fidelity PDF export)
    'layout.pdf_renderer', 'layout.pdf_renderer.config',
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
    'layout.pdf_renderer.typst_overlay.visual_images',
    'layout.pdf_renderer.typst_overlay.typst_packages',
    'layout.image_overlay',
    'layout.image_overlay.pipeline',
    'layout.image_overlay.renderer',
    'layout.image_overlay.models',
    'layout.image_overlay.font_resolver',
    'layout.image_overlay.block_text_map',
    'layout.image_overlay.coordinate_space',
    'layout.image_overlay.segment_overlay',
    'layout.image_overlay.debug_output',
    'layout.renderable_block_indices',
    # PyMuPDF (required by typst overlay source_cleanup and overlay_merge)
    'fitz',
    'loguru', 'imghdr',
    # Exporter modules (used by all workflows for output generation)
    'exporter.base',
    # IR (intermediate representation) and glossary (imported by mobi/epub workflows)
    'ir.document', 'glossary.glossary',
    'extractor.epub_extractor', 'extractor.mobi_extractor',
    'translator.ai_translator.epub_translator', 'translator.ai_translator.mobi_translator',
    'translator.ai_translator.html_translator',
    # Logger modules
    'backend.logger.logger', 'backend.logger.log_messages',
    'backend.logger.module_log_manager', 'backend.logger.module_logging',
    # Config modules
    'backend.app.config.pagination_config',
    # Additional services
    'backend.app.services.status.status_service',
    'backend.app.services.format_conversion_service',
    'backend.app.services.glossary_generation_service',
]

for _pkg in ['mobi', 'ebooklib', 'mcp']:
    try:
        _pkg_datas, _, _pkg_hiddenimports = collect_all(_pkg)
        datas += _pkg_datas
        hiddenimports += _pkg_hiddenimports
    except Exception as e:
        print(f"Warning: Failed to collect resources for {_pkg}: {e}")

datas.extend([
    *collect_data_files('pygments', include_py_files=False),
    *collect_data_files('latex2mathml'),
])

custom_datas = [
    ('./backend/static', 'backend/static'),
    ('./backend/template', 'backend/template'),
    ('./backend/i18n', 'backend/i18n'),
    ('./backend/static/favicon.ico', 'backend/favicon.ico'),
    ('./backend/static/flutter-web', 'backend/static/flutter-web'),
    ('./configs/system.json.template', 'configs/'),
    ('./configs/platforms.json.template', 'configs/'),

    ('./configs/secrets.json.template', 'configs/'),
    ('./configs/local.json.template', 'configs/'),
    ('./configs/translation_config.json.template', 'configs/'),
    ('./configs/static.json.template', 'configs/'),
    ('./configs/app_config.json.template', 'configs/'),
    ('./configs/local_users.json.template', 'configs/'),
    ('./configs/launcher_config.json.template', 'configs/'),
    ('./backend/config/templates/default_profile.json', 'backend/config/templates/'),
    ('./setup_secrets.py', '.'),
    ('./setup_first_deploy.py', '.'),
]

if sys.platform.startswith('win'):
    _redis_files = [
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis-server.exe', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/'),
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows.conf', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/'),
        ('./3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/redis.windows-service.conf', '3rdParty/windows/Redis-8.8.0-Windows-x64-msys2-with-Service/'),
    ]
    for _src, _dst in _redis_files:
        if os.path.exists(_src):
            datas.append((_src, _dst))
# Pandoc/Typst are staged externally by the build script (build_win_portable_onedir.ps1 copies
# 3rdParty/ to the package root). _get_pandoc_path() and typst compiler resolution use that copy first,
# so bundling inside _internal/ is redundant for onedir builds.

for data in custom_datas:
    if data not in datas:
        datas.append(data)

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
    f'{_np_core_prefix}.multiarray', f'{_np_core_prefix}.umath',
    f'{_np_core_prefix}._multiarray_umath', f'{_np_core_prefix}.overrides',
]
hiddenimports = list(set(hiddenimports + numpy_essential))

_excludes = [
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
    "tensorflow", "keras", "xgboost", "lightgbm",
    'numpy.tests', 'numpy.testing', 'numpy._pyinstaller', 'numpy.f2py.tests',
    'numpy.ma.tests', 'numpy.lib.tests', 'numpy.core.tests', 'numpy.random.tests',
    'numpy.linalg.tests', 'numpy.fft.tests', 'numpy.polynomial.tests',
    'numpy.matrixlib.tests', 'numpy.typing.tests', 'numpy.compat.tests',
    'numpy._core.tests', 'numpy._typing.tests',
    'numpy.core._add_newdocs', 'numpy.core.machar', 'numpy.core.umath_tests',
    'numpy._core._add_newdocs', 'numpy.core._multiarray_tests',
    "presidio_analyzer", "presidio_anonymizer", "anonymize",
    "spacy", "numpy",
]

# ── Analysis ──
a = Analysis(
    ['backend/config_manager.py'],
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Owlangs-win',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=next(
        (
            p for p in (
                os.path.join('frontend', 'windows', 'runner', 'resources', 'app_icon.ico'),
                'Owlangs.ico', 'favicon.ico',
                os.path.join('backend', 'static', 'favicon.ico'),
            )
            if os.path.isfile(p)
        ),
        None,
    ),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=f'Owlangs-{_version}',
)
