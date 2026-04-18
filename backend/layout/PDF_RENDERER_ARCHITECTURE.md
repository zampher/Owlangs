# PDF渲染器架构设计：支持多种生成方式

## 设计目标

1. **支持多种PDF生成方式**：
   - ReportLab直接生成（当前实现，高精度）
   - HTML转PDF（未来实现，CSS样式支持）

2. **代码复用**：
   - 布局计算逻辑共享
   - 字体大小计算共享
   - 文本处理工具共享
   - 块渲染逻辑可复用

3. **易于扩展**：
   - 新增PDF生成方式只需实现接口
   - 不影响现有功能
   - 保持向后兼容

## 架构设计

### 核心抽象层

```
backend/layout/
├── pdf_renderer/
│   ├── __init__.py
│   ├── base.py              # 抽象基类和接口
│   ├── config.py            # 共享配置类
│   ├── shared/              # 共享组件（可被所有实现复用）
│   │   ├── __init__.py
│   │   ├── layout_calculator.py    # 布局计算（available_height等）
│   │   ├── font_calculator.py      # 字体大小计算
│   │   ├── text_utils.py           # 文本处理工具
│   │   ├── font_utils.py            # 字体工具
│   │   └── block_processor.py      # 块处理逻辑（文本提取、映射等）
│   ├── reportlab/           # ReportLab实现
│   │   ├── __init__.py
│   │   ├── renderer.py     # ReportLabPDFRenderer
│   │   ├── canvas_wrapper.py
│   │   └── block_renderers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── text_renderer.py
│   │       ├── table_renderer.py
│   │       └── image_renderer.py
│   └── html_to_pdf/         # HTML转PDF实现
│       ├── __init__.py
│       ├── renderer.py      # HTMLToPDFRenderer
│       ├── html_builder.py  # HTML生成（复用html_renderer.py的逻辑）
│       └── converter.py    # HTML→PDF转换（Playwright/WeasyPrint等）
└── pdf_renderer_reportlab.py  # 向后兼容的包装函数
```

### 类层次结构

```python
# base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from pathlib import Path
from layout.base import LayoutDocument

class PDFRendererConfig:
    """PDF渲染器共享配置"""
    def __init__(
        self,
        translated_text_by_block_index: Optional[Dict[int, str]] = None,
        zip_bytes: Optional[bytes] = None,
        table_body_format: str = "html",
        target_language: Optional[str] = None,
        output_path: Optional[Path] = None,
    ):
        self.translated_text_by_block_index = translated_text_by_block_index or {}
        self.zip_bytes = zip_bytes
        self.table_body_format = table_body_format
        self.target_language = target_language
        self.output_path = output_path
        self.type_font_baselines: Dict[str, float] = {}
        self.image_data_map: Dict[str, bytes] = {}


class BasePDFRenderer(ABC):
    """PDF渲染器抽象基类"""
    
    def __init__(self, config: PDFRendererConfig):
        self.config = config
        # 共享组件（所有实现都可以使用）
        from pdf_renderer.shared.layout_calculator import LayoutCalculator
        from pdf_renderer.shared.font_calculator import FontSizeCalculator
        from pdf_renderer.shared.text_utils import TextUtils
        from pdf_renderer.shared.font_utils import FontUtils
        from pdf_renderer.shared.block_processor import BlockProcessor
        
        self.layout_calc = LayoutCalculator()
        self.font_calc = FontSizeCalculator(config.type_font_baselines, config)
        self.text_utils = TextUtils()
        self.font_utils = FontUtils()
        self.block_processor = BlockProcessor(config)
    
    @abstractmethod
    def render(self, layout_doc: LayoutDocument) -> bytes:
        """
        渲染LayoutDocument为PDF字节流
        
        Args:
            layout_doc: LayoutDocument实例
            
        Returns:
            PDF文件内容（bytes）
        """
        pass
    
    def prepare(self, layout_doc: LayoutDocument) -> None:
        """
        准备阶段：计算字体基线、提取图片等（共享逻辑）
        所有实现都可以调用此方法进行预处理
        """
        # 计算类型字体基线（共享逻辑）
        from pdf_renderer.shared.font_calculator import _calculate_type_font_baselines
        self.config.type_font_baselines = _calculate_type_font_baselines(
            layout_doc,
            self.config.translated_text_by_block_index
        )
        
        # 提取图片数据（共享逻辑）
        if self.config.zip_bytes:
            from pdf_renderer.shared.block_processor import _extract_images_from_zip
            self.config.image_data_map = _extract_images_from_zip(
                self.config.zip_bytes
            )
```

### ReportLab实现

```python
# pdf_renderer/reportlab/renderer.py
from pdf_renderer.base import BasePDFRenderer, PDFRendererConfig
from layout.base import LayoutDocument
import io
from reportlab.pdfgen import canvas

class ReportLabPDFRenderer(BasePDFRenderer):
    """使用ReportLab直接生成PDF"""
    
    def render(self, layout_doc: LayoutDocument) -> bytes:
        """使用ReportLab渲染PDF"""
        # 1. 预处理（共享逻辑）
        self.prepare(layout_doc)
        
        # 2. 创建PDF缓冲区
        pdf_buffer = io.BytesIO()
        
        # 3. 渲染每一页
        for page_idx, page in enumerate(layout_doc.pages):
            canvas_obj = self._create_canvas(pdf_buffer, page, page_idx)
            
            # 渲染页面中的所有块
            for block_idx, block in enumerate(page.blocks):
                self._render_block(canvas_obj, block, page, page_idx, block_idx)
            
            canvas_obj.showPage()
        
        # 4. 保存PDF
        canvas_obj.save()
        pdf_bytes = pdf_buffer.getvalue()
        
        # 5. 保存调试文件（如果指定）
        if self.config.output_path:
            self.config.output_path.write_bytes(pdf_bytes)
        
        return pdf_bytes
    
    def _create_canvas(self, buffer, page, page_idx):
        """创建ReportLab Canvas"""
        # ... (ReportLab特定的Canvas创建逻辑)
        pass
    
    def _render_block(self, canvas_obj, block, page, page_idx, block_idx):
        """渲染单个块（使用ReportLab特定的渲染器）"""
        from pdf_renderer.reportlab.block_renderers import get_block_renderer
        
        renderer = get_block_renderer(block.type)
        if renderer:
            renderer.render(
                canvas_obj, block, page, page_idx, block_idx,
                self.config, self.layout_calc, self.font_calc
            )
```

### HTML转PDF实现

```python
# pdf_renderer/html_to_pdf/renderer.py
from pdf_renderer.base import BasePDFRenderer, PDFRendererConfig
from layout.base import LayoutDocument
from typing import Optional

class HTMLToPDFRenderer(BasePDFRenderer):
    """使用HTML转PDF方式生成PDF"""
    
    def __init__(
        self,
        config: PDFRendererConfig,
        converter_type: str = "playwright"  # "playwright" or "weasyprint"
    ):
        super().__init__(config)
        self.converter_type = converter_type
        self.html_builder = HTMLBuilder(config)
        self.converter = self._create_converter(converter_type)
    
    def render(self, layout_doc: LayoutDocument) -> bytes:
        """通过HTML转PDF渲染"""
        # 1. 预处理（共享逻辑）
        self.prepare(layout_doc)
        
        # 2. 生成HTML（复用html_renderer.py的逻辑，但可以增强）
        html_content = self.html_builder.build(layout_doc)
        
        # 3. 转换HTML为PDF
        pdf_bytes = self.converter.convert(html_content)
        
        # 4. 保存调试文件（如果指定）
        if self.config.output_path:
            self.config.output_path.write_bytes(pdf_bytes)
        
        return pdf_bytes
    
    def _create_converter(self, converter_type: str):
        """创建HTML→PDF转换器"""
        if converter_type == "playwright":
            from pdf_renderer.html_to_pdf.converter import PlaywrightConverter
            return PlaywrightConverter()
        elif converter_type == "weasyprint":
            from pdf_renderer.html_to_pdf.converter import WeasyPrintConverter
            return WeasyPrintConverter()
        else:
            raise ValueError(f"Unknown converter type: {converter_type}")
```

### HTML构建器（复用现有逻辑）

```python
# pdf_renderer/html_to_pdf/html_builder.py
from pdf_renderer.base import PDFRendererConfig
from layout.base import LayoutDocument
from layout.html_renderer import render_layout_html  # 复用现有实现

class HTMLBuilder:
    """HTML构建器（增强版，可以复用现有html_renderer.py）"""
    
    def __init__(self, config: PDFRendererConfig):
        self.config = config
    
    def build(self, layout_doc: LayoutDocument) -> str:
        """
        构建HTML内容
        
        可以：
        1. 直接复用 render_layout_html（最简单）
        2. 或者增强它，添加更多CSS样式支持
        """
        # 方案1：直接复用（推荐，保持一致性）
        html = render_layout_html(
            layout_doc,
            translated_text_by_block_index=self.config.translated_text_by_block_index,
            zip_bytes=self.config.zip_bytes
        )
        
        # 方案2：增强HTML（如果需要更多CSS支持）
        # html = self._enhance_html(html, layout_doc)
        
        return html
    
    def _enhance_html(self, base_html: str, layout_doc: LayoutDocument) -> str:
        """增强HTML（添加更多CSS样式、字体支持等）"""
        # 可以在这里添加：
        # - 更精确的字体回退
        # - 更好的表格样式
        # - 图片优化
        # 等等
        pass
```

### HTML→PDF转换器接口

```python
# pdf_renderer/html_to_pdf/converter.py
from abc import ABC, abstractmethod

class HTMLConverter(ABC):
    """HTML→PDF转换器抽象接口"""
    
    @abstractmethod
    def convert(self, html_content: str) -> bytes:
        """将HTML内容转换为PDF字节流"""
        pass


class PlaywrightConverter(HTMLConverter):
    """使用Playwright转换HTML为PDF"""
    
    async def convert_async(self, html_content: str) -> bytes:
        """异步转换"""
        from playwright.async_api import async_playwright
        import tempfile
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # 写入临时HTML文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_html_path = f.name
            
            # 加载HTML并转换为PDF
            await page.goto(f"file://{temp_html_path}")
            pdf_bytes = await page.pdf(format='A4')
            
            await browser.close()
            return pdf_bytes
    
    def convert(self, html_content: str) -> bytes:
        """同步转换（内部调用异步）"""
        import asyncio
        return asyncio.run(self.convert_async(html_content))


class WeasyPrintConverter(HTMLConverter):
    """使用WeasyPrint转换HTML为PDF"""
    
    def convert(self, html_content: str) -> bytes:
        """使用WeasyPrint转换"""
        try:
            from weasyprint import HTML
            from io import BytesIO
            
            html_obj = HTML(string=html_content)
            pdf_bytes = html_obj.write_pdf()
            return pdf_bytes
        except ImportError:
            raise ImportError("WeasyPrint is required. Install with: pip install weasyprint")
```

### 统一入口函数

```python
# pdf_renderer/__init__.py
from pdf_renderer.base import PDFRendererConfig
from pdf_renderer.reportlab.renderer import ReportLabPDFRenderer
from pdf_renderer.html_to_pdf.renderer import HTMLToPDFRenderer
from layout.base import LayoutDocument
from typing import Optional, Dict
from pathlib import Path

def render_layout_pdf(
    layout_doc: LayoutDocument,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    zip_bytes: Optional[bytes] = None,
    output_path: Optional[Path] = None,
    table_body_format: str = "html",
    target_language: Optional[str] = None,
    renderer_type: str = "reportlab",  # "reportlab" or "html_to_pdf"
    html_converter: str = "playwright",  # "playwright" or "weasyprint" (仅当renderer_type="html_to_pdf"时有效)
) -> bytes:
    """
    统一的PDF渲染入口函数
    
    Args:
        layout_doc: LayoutDocument实例
        translated_text_by_block_index: 翻译文本映射
        zip_bytes: ZIP字节流（包含图片）
        output_path: 输出路径（可选，用于调试）
        table_body_format: 表格格式（"html" 或 "image"）
        target_language: 目标语言
        renderer_type: 渲染器类型
            - "reportlab": 使用ReportLab直接生成（高精度，推荐）
            - "html_to_pdf": 使用HTML转PDF（CSS样式支持）
        html_converter: HTML→PDF转换器类型（仅当renderer_type="html_to_pdf"时有效）
            - "playwright": 使用Playwright（需要浏览器）
            - "weasyprint": 使用WeasyPrint（纯Python，推荐）
    
    Returns:
        PDF文件内容（bytes）
    """
    # 创建配置
    config = PDFRendererConfig(
        translated_text_by_block_index=translated_text_by_block_index,
        zip_bytes=zip_bytes,
        table_body_format=table_body_format,
        target_language=target_language,
        output_path=output_path,
    )
    
    # 选择渲染器
    if renderer_type == "reportlab":
        renderer = ReportLabPDFRenderer(config)
    elif renderer_type == "html_to_pdf":
        renderer = HTMLToPDFRenderer(config, converter_type=html_converter)
    else:
        raise ValueError(f"Unknown renderer_type: {renderer_type}")
    
    # 渲染PDF
    return renderer.render(layout_doc)
```

### 简化方案（无需向后兼容）

由于软件尚未发布，**不需要向后兼容处理**，可以直接：

1. **删除旧的 `pdf_renderer_reportlab.py` 文件**
2. **直接使用新的 `render_layout_pdf` 统一入口**
3. **更新调用代码**（只有2处调用，很容易更新）

#### 调用代码更新示例

**旧代码**（`app_routes_service.py`）:
```python
from layout.pdf_renderer_reportlab import render_layout_pdf_reportlab

pdf_bytes = render_layout_pdf_reportlab(
    layout_doc,
    translated_text_by_block_index=block_text_map,
    zip_bytes=zip_bytes,
    table_body_format=table_body_format,
    target_language=target_language,
)
```

**新代码**:
```python
from layout.pdf_renderer import render_layout_pdf

pdf_bytes = render_layout_pdf(
    layout_doc,
    translated_text_by_block_index=block_text_map,
    zip_bytes=zip_bytes,
    table_body_format=table_body_format,
    target_language=target_language,
    renderer_type="reportlab",  # 明确指定使用ReportLab
)
```

#### 需要更新的文件

只需要更新 **2处调用**：
- `backend/app/routes/app_routes_service.py:5056` - `_generate_pdf_from_html` 函数中
- `backend/app/routes/app_routes_service.py:4658` - `service_get_debug_file` 函数中（原始PDF导出）

#### 删除的文件

- `backend/layout/pdf_renderer_reportlab.py` - 整个文件可以删除，功能迁移到新架构

## 代码复用策略

### 1. 共享组件（shared/）

所有PDF渲染实现都可以使用：

- **LayoutCalculator**: 计算 `available_height`、行高等
- **FontSizeCalculator**: 计算字体大小、基线等
- **TextUtils**: 文本换行、语言检测等
- **FontUtils**: 字体注册、回退等
- **BlockProcessor**: 块文本提取、映射等

### 2. 复用现有HTML渲染器

HTML转PDF实现可以直接复用 `layout/html_renderer.py` 中的 `render_layout_html` 函数，或者在此基础上增强。

### 3. 配置共享

`PDFRendererConfig` 类包含所有渲染器需要的配置，避免重复传递参数。

## 使用示例

### 使用ReportLab（当前方式）

```python
from layout.pdf_renderer import render_layout_pdf

pdf_bytes = render_layout_pdf(
    layout_doc,
    translated_text_by_block_index=translated_text,
    zip_bytes=zip_bytes,
    renderer_type="reportlab",  # 使用ReportLab
)
```

### 使用HTML转PDF（新方式）

```python
from layout.pdf_renderer import render_layout_pdf

pdf_bytes = render_layout_pdf(
    layout_doc,
    translated_text_by_block_index=translated_text,
    zip_bytes=zip_bytes,
    renderer_type="html_to_pdf",  # 使用HTML转PDF
    html_converter="weasyprint",   # 使用WeasyPrint转换器
)
```

### 默认使用ReportLab（简化调用）

```python
from layout.pdf_renderer import render_layout_pdf

# renderer_type 默认为 "reportlab"，可以省略
pdf_bytes = render_layout_pdf(
    layout_doc,
    translated_text_by_block_index=translated_text,
    zip_bytes=zip_bytes,
)
```

## 迁移计划（简化版，无需向后兼容）

### 阶段1：提取共享组件

1. 创建 `pdf_renderer/shared/` 目录
2. 提取 `LayoutCalculator`、`FontSizeCalculator` 等共享组件
3. 从 `pdf_renderer_reportlab.py` 中提取这些组件到新文件

### 阶段2：创建抽象接口和ReportLab实现

1. 创建 `BasePDFRenderer` 抽象基类
2. 创建 `ReportLabPDFRenderer` 继承基类
3. 将 `pdf_renderer_reportlab.py` 中的 `render_layout_pdf_reportlab` 函数逻辑迁移到 `ReportLabPDFRenderer.render()`

### 阶段3：创建统一入口

1. 创建 `pdf_renderer/__init__.py`，实现 `render_layout_pdf` 统一入口
2. **更新调用代码**（只有2处，直接更新）：
   - `app_routes_service.py:5056` - `_generate_pdf_from_html`
   - `app_routes_service.py:4658` - `service_get_debug_file`
3. **删除旧文件** `pdf_renderer_reportlab.py`

### 阶段4：实现HTML转PDF（未来）

1. 创建 `HTMLToPDFRenderer`
2. 实现 `HTMLBuilder`（复用 `html_renderer.py`）
3. 实现 `PlaywrightConverter` 和 `WeasyPrintConverter`

### 优势

- ✅ **更简洁**：不需要包装函数，直接使用统一入口
- ✅ **更清晰**：调用代码明确指定 `renderer_type`
- ✅ **更易维护**：只有一个入口函数，减少代码重复
- ✅ **迁移成本低**：只有2处调用需要更新

## 优势总结

1. **代码复用**：布局计算、字体计算等逻辑只写一次
2. **易于扩展**：新增PDF生成方式只需实现 `BasePDFRenderer`
3. **向后兼容**：现有代码无需修改
4. **灵活选择**：可以根据需求选择不同的渲染方式
5. **统一接口**：所有渲染方式使用相同的配置和接口

## 文件大小优化

按照此架构拆分后：

- **主入口**: `pdf_renderer/__init__.py` (~100行)
- **抽象基类**: `pdf_renderer/base.py` (~150行)
- **共享组件**: 每个文件 ~200-400行
- **ReportLab实现**: `pdf_renderer/reportlab/renderer.py` (~300行)
- **HTML转PDF实现**: `pdf_renderer/html_to_pdf/renderer.py` (~200行)

每个文件都 < 500行，Cursor交互效率最优！

