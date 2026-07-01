# Typst Overlay Renderer

高保真 PDF 翻译导出渲染器。

## 设计理念

基于 RetainPDF 的 overlay 渲染思路重新设计并重写。核心理念：

1. **不重建，只覆盖** — 保留原 PDF 的一切视觉元素（背景图像、表格边框、装饰），仅在需要翻译的地方叠加译文
2. **Typst 排版** — 利用 Typst 强大的编程式排版能力处理 Markdown 和数学公式
3. **原文清理** — 用 PyMuPDF 在原 PDF 上擦除原文文字，避免新旧文字重叠
4. **自动化适配** — 根据 MinerU 的 bbox 信息自动计算字号、行距

## 与 RetainPDF 的区别

| 方面 | RetainPDF | 本实现 |
|---|---|---|
| 中间表示 IR | 自定义 `document.v1.json` | 复用 Owlangs `LayoutDocument` |
| 渲染块模型 | `RenderBlock` / `RenderPageSpec` | 重新设计 `RenderBlock` / `RenderPageSpec` |
| 原文清理 | 完整 redaction pipeline + 矢量文本剥离 | 简化版 redaction (可逐步增强) |
| 排版适配 | `layout/font_size_fit.py` + `leading_fit.py` | `font_fit.py` (重新实现) |
| Typst 源码生成 | `emitter.py` + `block_renderer.py` | `emitter.py` (重写，更简洁) |
| Overlay 合成 | pikepdf + PyMuPDF 多路径 | PyMuPDF `show_pdf_page()` (基本路径，可扩展) |
| 错误恢复 | 二分法定位 + sanitize 重试 | Typst 编译失败直接抛异常 (可逐步增强) |

## 目录结构

```
typst_overlay/
├── __init__.py          # 模块导出
├── README.md            # 本文档
├── models.py            # 数据模型 (RenderBlock, RenderPageSpec)
├── font_fit.py          # 字体/字号/行距自适应计算
├── source_cleanup.py    # 原文清理 (PyMuPDF redaction)
├── compiler.py          # Typst CLI 包装器
├── emitter.py           # Typst 源码生成器
├── overlay_merge.py     # Overlay PDF 合成
└── renderer.py          # 主渲染器 TypstOverlayRenderer
```

## 渲染流水线

```
LayoutDocument + source_pdf_path
      │
      ▼ [models.py] layout_block_to_render_block()
      │   将 Owlangs LayoutBlock 转为 RenderBlock
      ▼ [font_fit.py] FontFitCalculator.calculate_fit_params()
      │   自动计算字号、行距、是否需要自适应
      ▼ [source_cleanup.py] clean_source_pdf()
      │   PyMuPDF redaction 擦除原文文字
      ▼ [emitter.py] build_typst_overlay_source()
      │   生成 Typst .typ 源码
      ▼ [compiler.py] TypstCompiler.compile()
      │   调用 typst compile 编译 overlay PDF
      ▼ [overlay_merge.py] merge_overlay_pdf()
      │   将 overlay PDF 合成到清理后的源 PDF
      ▼
   translated.pdf
```

## 使用方式

### 1. 通过统一入口调用

```python
from layout.pdf_renderer import render_layout_pdf

pdf_bytes = render_layout_pdf(
    layout_doc,
    translated_text_by_block_index=block_text_map,
    renderer_type="typst_overlay",
    source_pdf_path="/path/to/original.pdf",
    typst_font_family="Noto Sans CJK SC",
)
```

### 2. 直接使用渲染器

```python
from layout.pdf_renderer.config import PDFRendererConfig
from layout.pdf_renderer.typst_overlay import TypstOverlayRenderer

config = PDFRendererConfig(
    translated_text_by_block_index=block_text_map,
    source_pdf_path="/path/to/original.pdf",
)
renderer = TypstOverlayRenderer(config)
pdf_bytes = renderer.render(layout_doc)
```

### 3. 仅生成 Typst 源码（调试用）

```python
from layout.pdf_renderer.typst_overlay.emitter import build_typst_overlay_source
from layout.pdf_renderer.typst_overlay.models import RenderPageSpec

source = build_typst_overlay_source(page_specs, font_family="Noto Sans CJK SC")
with open("overlay_debug.typ", "w") as f:
    f.write(source)
```

## 依赖项

- **Typst CLI**: 系统安装或 `3rdParty/windows/typst-*/typst.exe`
- **PyMuPDF**: `pip install PyMuPDF` (Owlangs 已有)
- **Typst 包**: `@preview/cmarker:0.1.8` 与 `@preview/mitex:0.2.6`；生产包应预置于 `3rdParty/typst/packages/`（运行 `tools/build/fetch_typst_packages.ps1`）
- **字体**: Noto Sans CJK SC 或其他 CJK 字体

## 后续优化方向

- [ ] 矢量文本剥离（当前仅支持文本 redaction）
- [ ] 颜色自适应采样（从原 PDF 背景色推算 overlay 填充色）
- [ ] 公式保护区域检测
- [ ] Typst 编译错误二分法定位 + 自动修复
- [ ] pikepdf overlay 合成路径（高性能）
- [ ] 分片编译支持（大文档并行处理）
- [ ] Pre-warming 缓存机制
