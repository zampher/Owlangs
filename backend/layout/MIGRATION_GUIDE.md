# PDF渲染器迁移指南（简化版，无需向后兼容）

## 概述

由于软件尚未发布，**不需要向后兼容处理**，可以直接迁移到新架构。

## 重构进度

### ✅ 已完成的工作

#### 阶段1：基础函数迁移（已完成）
- ✅ 文本处理函数 → `TextUtils` (4个函数，~104行)
- ✅ 字体工具函数 → `FontUtils` (5个函数，~200行)
- ✅ 字体大小计算函数 → `FontSizeCalculator` (4个函数，~150行)
- ✅ 布局计算函数 → `LayoutCalculator` (3个函数，~70行)
- ✅ 块处理函数 → `BlockProcessor` (6个函数，~280行)

**总计**: 22个函数，~804行代码已迁移

#### 阶段2：架构基础（已完成）
- ✅ `BasePDFRenderer` 抽象基类
- ✅ `PDFRendererConfig` 配置类
- ✅ `ReportLabPDFRenderer` 实现类
- ✅ `render_layout_pdf()` 统一入口
- ✅ 调用代码更新（2处）

#### 阶段3：测试（已完成）
- ✅ 单元测试（FontSizeCalculator）
- ✅ 基础测试（BasePDFRenderer）
- ✅ 集成测试（使用真实 layout.json）

### 📋 待完成的工作

#### 阶段4：表格处理（待完成）
- ⚠️ 创建 `TableUtils` 类
- ⚠️ 迁移表格解析函数（3个函数，~342行）

#### 阶段5：文本对齐（待完成）
- ⚠️ 迁移文本对齐检测函数（2个函数，~94行）

#### 阶段6：复杂函数迁移（待完成）
- ⚠️ 分阶段迁移 `_calculate_type_font_baselines` (~511行)

详细进度请参考：`backend/layout/pdf_renderer/REFACTORING_PROGRESS.md`

## 需要更新的文件

### 1. 调用代码更新（2处）

#### 文件1: `backend/app/routes/app_routes_service.py`

**位置1**: `service_get_debug_file` 函数（原始PDF导出）
- **行号**: ~4658
- **旧代码**:
```python
from layout.pdf_renderer_reportlab import render_layout_pdf_reportlab, REPORTLAB_AVAILABLE, _reportlab_import_error

pdf_bytes = await loop.run_in_executor(
    None,
    lambda: render_layout_pdf_reportlab(
        layout_doc,
        translated_text_by_block_index=source_text_by_block_index if source_text_by_block_index else None,
        zip_bytes=zip_bytes,
        output_path=debug_pdf_path,
        table_body_format=table_body_format,
    )
)
```

- **新代码**:
```python
from layout.pdf_renderer import render_layout_pdf, REPORTLAB_AVAILABLE
from layout.pdf_renderer.reportlab import _reportlab_import_error  # 如果需要错误信息

pdf_bytes = await loop.run_in_executor(
    None,
    lambda: render_layout_pdf(
        layout_doc,
        translated_text_by_block_index=source_text_by_block_index if source_text_by_block_index else None,
        zip_bytes=zip_bytes,
        output_path=debug_pdf_path,
        table_body_format=table_body_format,
        renderer_type="reportlab",  # 明确指定使用ReportLab
    )
)
```

**位置2**: `_generate_pdf_from_html` 函数（翻译PDF导出）
- **行号**: ~5056
- **旧代码**:
```python
from layout.pdf_renderer_reportlab import render_layout_pdf_reportlab, REPORTLAB_AVAILABLE

pdf_bytes = await loop.run_in_executor(
    None,
    lambda: render_layout_pdf_reportlab(
        layout_doc,
        translated_text_by_block_index=block_text_map if block_text_map else None,
        zip_bytes=zip_bytes,
        output_path=output_dir / f"{file_stem}_reportlab_debug.pdf" if logger.level <= 10 else None,
        table_body_format=table_body_format_resolved,
        target_language=target_language,
    )
)
```

- **新代码**:
```python
from layout.pdf_renderer import render_layout_pdf, REPORTLAB_AVAILABLE

pdf_bytes = await loop.run_in_executor(
    None,
    lambda: render_layout_pdf(
        layout_doc,
        translated_text_by_block_index=block_text_map if block_text_map else None,
        zip_bytes=zip_bytes,
        output_path=output_dir / f"{file_stem}_reportlab_debug.pdf" if logger.level <= 10 else None,
        table_body_format=table_body_format_resolved,
        target_language=target_language,
        renderer_type="reportlab",  # 明确指定使用ReportLab
    )
)
```

### 2. 需要导出的常量

如果代码中使用了 `REPORTLAB_AVAILABLE` 或 `_reportlab_import_error`，需要在新架构中导出：

**文件**: `backend/layout/pdf_renderer/__init__.py`
```python
# 导出常量，保持兼容
from layout.pdf_renderer.reportlab.renderer import REPORTLAB_AVAILABLE, _reportlab_import_error

__all__ = [
    'render_layout_pdf',
    'REPORTLAB_AVAILABLE',
    '_reportlab_import_error',
]
```

## 迁移步骤

### 步骤1: 创建新架构目录结构

```bash
mkdir -p backend/layout/pdf_renderer/shared
mkdir -p backend/layout/pdf_renderer/reportlab/block_renderers
mkdir -p backend/layout/pdf_renderer/html_to_pdf
```

### 步骤2: 提取共享组件

按照 `PDF_RENDERER_REFACTORING_PLAN.md` 的阶段1，提取共享组件到 `pdf_renderer/shared/`。

### 步骤3: 创建ReportLab实现

按照 `PDF_RENDERER_REFACTORING_PLAN.md` 的阶段2-3，创建 `ReportLabPDFRenderer`。

### 步骤4: 创建统一入口

创建 `pdf_renderer/__init__.py`，实现 `render_layout_pdf` 函数。

### 步骤5: 更新调用代码

更新 `app_routes_service.py` 中的2处调用（如上所示）。

### 步骤6: 测试

运行测试，确保功能正常。

### 步骤7: 删除旧文件

```bash
rm backend/layout/pdf_renderer_reportlab.py
```

## 验证清单

- [ ] 新架构代码已创建
- [ ] `render_layout_pdf` 统一入口已实现
- [ ] `app_routes_service.py` 中的2处调用已更新
- [ ] `REPORTLAB_AVAILABLE` 和 `_reportlab_import_error` 已导出（如果需要）
- [ ] 测试通过（原始PDF导出、翻译PDF导出）
- [ ] 旧文件 `pdf_renderer_reportlab.py` 已删除

## 优势

✅ **更简洁**：不需要包装函数，直接使用统一入口  
✅ **更清晰**：调用代码明确指定 `renderer_type`  
✅ **更易维护**：只有一个入口函数，减少代码重复  
✅ **迁移成本低**：只有2处调用需要更新

