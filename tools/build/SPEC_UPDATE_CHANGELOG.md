# Spec文件更新日志

## 2026-07-04 — LaTeX 混排标记层 (latex_flags)

未提交改动新增 `backend/utils/segment_latex_flags.py`，并在 extract / API / PDF Typst overlay / Pandoc rebuild 路径中 lazy import。已在 `lite.spec`、`launcher_portable_onedir.spec`、`macos.spec` 补充：

- `backend.utils.segment_latex_flags` — 片段 `latex_flags: {present, mixed, needs_delimiter_wrap}` 分类与 Typst/Pandoc 导出预处理（依赖 `backend.utils.mixed_formula_text`）

**同批改动无需新增 spec 条目的模块：**

- `backend/utils/mixed_formula_text.py` — 已有 hiddenimport；仅修复 CJK 标点粘连时的 `$...$` 包裹逻辑
- `backend/test_segment_latex_flags.py` — 测试文件，不打包
- `frontend/lib/features/translation/utils/segment_type_utils.dart` — 前端，不进 PyInstaller

---

## 2026-06-27 — PDF overlay 优化 (5fbef42)

`Optimize overlay for PDF preview` 新增模块，已在 `lite.spec`、`launcher_portable_onedir.spec`、`macos.spec` 补充：

- `layout.image_overlay.coordinate_space` — image_px 坐标空间（lazy import）
- `layout.image_overlay.segment_overlay` — 单表 segment 直绘 overlay
- `layout.ocr_provider.paddle.paddle_det_supplements` — Paddle det 补全（lazy import）
- `layout.pdf_renderer.typst_overlay.visual_images` — chart/equation 视觉块判定

**无需更新 spec 的 commit：**

- `6655e0f` Bug fix - PDF preview fail with formula（仅改 `emitter.py`）
- `5c49036` Remap segement sequence in prompt（仅改现有 agents/utils，无新模块）

---

## 更新日志 (2026-06-08)

## 更新原因

对比macos.spec发现lite.spec和launcher_portable.spec缺少了一些关键模块的hiddenimports声明，虽然PyInstaller可能通过自动发现机制找到这些模块，但为了保险和一致性，我们添加了显式声明。

## 更新内容

### lite.spec
添加了以下hiddenimports：

#### 1. Exporter模块（导出功能核心）
```python
'exporter',
'exporter.base',
```
- **用途**: 所有workflow都导入exporter模块用于导出功能
- **被导入位置**: backend/workflow/*.py, backend/app/services/download/output_generator.py

#### 2. IR和Glossary模块（MOBI/EPUB工作流）
```python
'ir',
'ir.document',
'glossary',
'glossary.glossary',
```
- **用途**: MOBI/EPUB workflow使用这些模块处理文档和术语表
- **被导入位置**: backend/workflow/epub_workflow.py, backend/workflow/mobi_workflow.py

#### 3. Translator AI模块
```python
'translator',
'translator.ai_translator',
'translator.ai_translator.mobi_translator',
'translator.ai_translator.epub_translator',
```
- **用途**: MOBI/EPUB的AI翻译功能
- **被导入位置**: backend/workflow/epub_workflow.py, backend/workflow/mobi_workflow.py

#### 4. Extractor模块扩展
```python
'extractor.mobi_extractor',
'extractor.epub_extractor',
```
- **用途**: MOBI/EPUB文件解析
- **补充**: lite.spec已有extractor.base和extractor.html_extractor

#### 5. Logger模块（可选）
```python
'backend.logger',
'backend.logger.logger',
'backend.logger.log_messages',
'backend.logger.module_log_manager',
'backend.logger.module_logging',
```
- **用途**: 增强日志功能（macos.spec包含）
- **状态**: 可选，不影响核心功能

#### 6. Config模块
```python
'backend.app.config',
'backend.app.config.pagination_config',
```
- **用途**: 应用配置管理
- **被导入位置**: backend/app相关模块

#### 7. Services模块补充
```python
'backend.app.services.status',
'backend.app.services.status.status_service',
'backend.app.services.format_conversion_service',
'backend.app.services.glossary_generation_service',
```
- **用途**: 状态服务、格式转换、术语表生成
- **被导入位置**: backend/app/services相关路由

### launcher_portable.spec
同步添加了与lite.spec相同的模块，保持一致性。

## 验证结果

✅ 所有模块都能正确导入
✅ 验证脚本通过: tools/build/verify_spec_hiddenimports.py

## 测试建议

### 1. 构建测试
```bash
# Linux
tools/build/build_deb.sh --no-deb

# Windows
tools/build/build_win_pro.ps1
```

### 2. 功能测试
构建完成后，测试以下功能是否正常工作：
- ✅ 导入EPUB文件并翻译
- ✅ 导入MOBI文件并翻译
- ✅ 导出为EPUB格式
- ✅ 导出为MOBI格式
- ✅ 导出为DOCX格式（使用exporter.md模块）
- ✅ 导出为HTML格式（使用exporter模块）

### 3. 模块导入测试
```bash
# 在构建产物的环境中测试
cd dist/
./Owlangs-linux -c "from exporter.base import ExporterConfig; print('OK')"
./Owlangs-linux -c "from ir.document import Document; print('OK')"
./Owlangs-linux -c "from glossary.glossary import Glossary; print('OK')"
```

## 对比macos.spec

### macos.spec额外包含但lite.spec未添加的模块

以下模块在macos.spec中存在，但lite.spec未添加（认为是不必要或自动发现）：

1. **Exporter详细子模块**
   - macos.spec显式声明了所有exporter子模块（epub/mobi/base等）
   - lite.spec只声明exporter和exporter.base（其他自动发现）

2. **backend.app.* 路径**
   - macos.spec使用backend.app.*路径（更完整）
   - lite.spec使用app.*路径（PyInstaller路径解析不同）
   - 都能工作，保持现状

3. **Auth模块**
   - macos.spec包含backend.auth.*
   - lite.spec未添加（可能Linux版本不需要auth功能）
   - 如果需要，可后续添加

4. **其他utils模块**
   - backend.app.utils.port
   - backend.app.utils.app_utils
   - 可选添加，不影响核心功能

## 理论依据

### PyInstaller自动发现机制

PyInstaller会分析以下导入：
- ✅ 静态导入: `from exporter.base import ...`（会被自动发现）
- ⚠️ 动态导入: `import_module('exporter.base')`（可能不会被发现）
- ⚠️ Lazy导入: 在函数内部的导入（可能不会被发现）

### workflow模块的导入方式

backend/workflow/epub_workflow.py:
```python
# 静态导入（PyInstaller应该能自动发现）
from exporter.base import ExporterConfig
from exporter.epub.epub2epub_exporter import Epub2EpubExporter

# lazy导入（可能不会被自动发现）
def export_to_markdown(self, _: ExporterConfig | None = None) -> str:
    from workflow.html_to_markdown_export import html_content_to_markdown
    return html_content_to_markdown(self.export_to_html())
```

因此，显式声明exporter.base是安全的，但exporter.epub.*可能也会被自动发现。我们采用保守方案，只添加核心模块。

## 更新文件

- ✅ lite.spec (2026-06-08)
- ✅ launcher_portable.spec (2026-06-08)
- ✅ tools/build/verify_spec_hiddenimports.py (新增)

## 参考

- macOS开发者的经验教训（macos.spec显式声明）
- backend代码的实际导入分析
- PyInstaller文档关于hiddenimports的建议