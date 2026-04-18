# 前端样式覆盖支持

## 一、需求概述

允许前端设置片段的字号、字体、对齐、斜体、黑体、下划线、删除线、表格线条等文本常规设置。

**关键规则**：
1. 如果前端设置了，优先使用前端的设置
2. 统计字号类型基线的时候，不用纳入前端设置的片段

## 二、数据结构设计

### 2.1 前端样式覆盖数据结构

```python
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class FrontendStyleOverride:
    """前端样式覆盖配置"""
    # 字号（单位：pt）
    font_size: Optional[float] = None
    
    # 字体名称
    font_name: Optional[str] = None
    
    # 对齐方式：'left', 'center', 'right', 'justify'
    alignment: Optional[str] = None
    
    # 文本样式
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    strikethrough: Optional[bool] = None
    
    # 表格样式（仅适用于表格）
    table_border_width: Optional[float] = None
    table_border_color: Optional[str] = None
    table_cell_padding: Optional[float] = None

# 样式覆盖映射：block_index -> FrontendStyleOverride
FrontendStyleOverrides = Dict[int, FrontendStyleOverride]
```

### 2.2 在 LayoutDocument 中存储

**方案 A**：作为 LayoutDocument 的属性
```python
class LayoutDocument:
    # ... 现有属性 ...
    frontend_style_overrides: Optional[FrontendStyleOverrides] = None
```

**方案 B**：作为渲染函数的参数
```python
def render_layout_pdf_reportlab(
    layout_doc: LayoutDocument,
    ...,
    frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
) -> bytes:
```

**建议**：**方案 B** - 作为渲染函数参数，因为：
- 样式覆盖是渲染时的配置，不是文档本身的属性
- 更灵活，可以支持不同的渲染配置
- 不影响 LayoutDocument 的核心结构

## 三、实现方案

### 3.1 类型分类器更新

**文件**: `backend/layout/pdf_renderer/shared/block_classifier.py`

```python
class BlockClassifier:
    @staticmethod
    def should_include_in_baseline_calculation(
        block: LayoutBlock,
        frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
    ) -> bool:
        """
        判断 block 是否应该纳入基线计算
        
        规则：
        - 如果前端设置了字号覆盖，则不纳入
        - 如果前端设置了字体覆盖，则不纳入（因为可能影响字号计算）
        """
        if frontend_style_overrides is None:
            return True
        
        block_index = getattr(block, "index", None)
        if block_index is None:
            return True
        
        override = frontend_style_overrides.get(block_index)
        if override is None:
            return True
        
        # 如果前端设置了字号或字体，则不纳入基线计算
        if override.font_size is not None or override.font_name is not None:
            return False
        
        return True
```

### 3.2 统一字号计算更新

**文件**: `backend/layout/pdf_renderer/shared/font_calculator.py`

```python
@staticmethod
def calculate_unified_font_size_for_type(
    layout_doc: LayoutDocument,
    block_type: str,
    translated_text_by_block_index: Dict[int, str],
    frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
    max_iterations: int = 15,
) -> float:
    """
    计算统一字号，排除前端覆盖的 blocks
    """
    # 收集该类型的所有 blocks
    blocks = collect_blocks_by_type(layout_doc, block_type)
    
    # 过滤掉前端覆盖的 blocks
    filtered_blocks = [
        block for block in blocks
        if BlockClassifier.should_include_in_baseline_calculation(
            block, frontend_style_overrides
        )
    ]
    
    # 如果所有 blocks 都被覆盖，返回默认字号
    if not filtered_blocks:
        return get_default_font_size_for_type(block_type)
    
    # 使用过滤后的 blocks 计算统一字号
    # ... 后续计算逻辑 ...
```

### 3.3 渲染时应用前端覆盖

**文件**: `backend/layout/pdf_renderer_reportlab.py`

```python
def render_layout_pdf_reportlab(
    layout_doc: LayoutDocument,
    ...,
    frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
) -> bytes:
    # ... 现有代码 ...
    
    # 计算统一字号（排除前端覆盖的 blocks）
    type_unified_font_sizes = {}
    for block_type in UNIFIED_FONT_SIZE_TYPES:
        type_unified_font_sizes[block_type] = (
            FontSizeCalculator.calculate_unified_font_size_for_type(
                layout_doc,
                block_type,
                translated_text_by_block_index,
                frontend_style_overrides,
            )
        )
    
    # 渲染 blocks
    for block in blocks:
        block_index = getattr(block, "index", None)
        override = frontend_style_overrides.get(block_index) if frontend_style_overrides else None
        
        # 应用前端覆盖
        if override:
            # 字号
            if override.font_size is not None:
                font_size = override.font_size
            else:
                font_size = get_font_size_from_type(block.type, type_unified_font_sizes)
            
            # 字体
            if override.font_name is not None:
                font_name = override.font_name
            else:
                font_name = detect_font_for_text(block.text, target_language)
            
            # 对齐
            alignment = override.alignment if override.alignment else "left"
            
            # 文本样式
            bold = override.bold if override.bold is not None else False
            italic = override.italic if override.italic is not None else False
            underline = override.underline if override.underline is not None else False
            strikethrough = override.strikethrough if override.strikethrough is not None else False
        else:
            # 使用默认计算
            font_size = get_font_size_from_type(block.type, type_unified_font_sizes)
            font_name = detect_font_for_text(block.text, target_language)
            alignment = "left"
            bold = False
            italic = False
            underline = False
            strikethrough = False
        
        # 渲染 block
        render_block_with_style(...)
```

### 3.4 文本样式渲染

**文件**: `backend/layout/pdf_renderer/shared/text_renderer.py`

```python
class TextRenderer:
    @staticmethod
    def render_text_with_style(
        canvas_obj,
        text: str,
        bbox: Tuple[float, float, float, float],
        page_height: float,
        font_size: float,
        font_name: str,
        alignment: str = "left",
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        ...
    ) -> bool:
        """
        渲染带样式的文本
        
        实现细节：
        - bold: 使用字体名称的 Bold 变体（如 Helvetica-Bold）
        - italic: 使用字体名称的 Italic 变体（如 Helvetica-Oblique）
        - underline: 使用 canvas 的 underline 功能
        - strikethrough: 使用 canvas 的 line 功能绘制删除线
        """
        # 构建字体名称（考虑 bold 和 italic）
        if bold and italic:
            style_font_name = f"{font_name}-BoldOblique"
        elif bold:
            style_font_name = f"{font_name}-Bold"
        elif italic:
            style_font_name = f"{font_name}-Oblique"
        else:
            style_font_name = font_name
        
        # 设置字体
        canvas_obj.setFont(style_font_name, font_size)
        
        # 渲染文本
        # ... 文本渲染逻辑 ...
        
        # 绘制下划线
        if underline:
            # 计算下划线位置
            underline_y = text_y - font_size * 0.1
            canvas_obj.line(text_x, underline_y, text_x + text_width, underline_y)
        
        # 绘制删除线
        if strikethrough:
            # 计算删除线位置（文本中间）
            strikethrough_y = text_y - font_size * 0.5
            canvas_obj.line(text_x, strikethrough_y, text_x + text_width, strikethrough_y)
```

### 3.5 表格样式渲染

**文件**: `backend/layout/pdf_renderer_reportlab.py`

```python
def _render_table_block(
    ...,
    frontend_style_overrides: Optional[FrontendStyleOverrides] = None,
) -> bool:
    # ... 现有代码 ...
    
    # 应用表格样式覆盖
    table_override = None
    if frontend_style_overrides and block.index is not None:
        table_override = frontend_style_overrides.get(block.index)
    
    # 表格边框宽度
    border_width = 0.5  # 默认
    if table_override and table_override.table_border_width is not None:
        border_width = table_override.table_border_width
    
    # 表格边框颜色
    border_color = black  # 默认
    if table_override and table_override.table_border_color is not None:
        border_color = parse_color(table_override.table_border_color)
    
    # 单元格内边距
    cell_padding = 2.0  # 默认
    if table_override and table_override.table_cell_padding is not None:
        cell_padding = table_override.table_cell_padding
    
    # 构建表格样式
    style_commands = [
        ("GRID", (0, 0), (-1, -1), border_width, border_color),
        # ... 其他样式命令 ...
        ("TOPPADDING", (0, 0), (-1, -1), cell_padding),
        # ... 其他内边距命令 ...
    ]
```

## 四、API 接口设计

### 4.1 前端传递样式覆盖

```json
{
  "frontend_style_overrides": {
    "123": {
      "font_size": 14.0,
      "font_name": "Times-Roman",
      "alignment": "center",
      "bold": true,
      "italic": false,
      "underline": false,
      "strikethrough": false
    },
    "456": {
      "font_size": 12.0,
      "alignment": "right",
      "bold": true
    },
    "789": {
      "table_border_width": 1.0,
      "table_border_color": "#000000",
      "table_cell_padding": 3.0
    }
  }
}
```

### 4.2 后端接收和处理

```python
# 在 app_routes_service.py 中
def export_pdf(...):
    # 解析前端样式覆盖
    frontend_style_overrides = None
    if request_data.get("frontend_style_overrides"):
        frontend_style_overrides = parse_frontend_style_overrides(
            request_data["frontend_style_overrides"]
        )
    
    # 传递给渲染函数
    pdf_bytes = render_layout_pdf_reportlab(
        layout_doc,
        ...,
        frontend_style_overrides=frontend_style_overrides,
    )
```

## 五、实施步骤

### 步骤 1: 定义数据结构（1 天）

- [ ] 创建 `FrontendStyleOverride` 数据类
- [ ] 定义样式覆盖映射类型
- [ ] 添加单元测试

### 步骤 2: 更新类型分类器（1 天）

- [ ] 添加 `should_include_in_baseline_calculation()` 方法
- [ ] 更新基线计算逻辑，排除前端覆盖的 blocks
- [ ] 添加单元测试

### 步骤 3: 更新渲染逻辑（2-3 天）

- [ ] 更新 `render_layout_pdf_reportlab()` 接收样式覆盖参数
- [ ] 实现样式应用逻辑
- [ ] 实现文本样式渲染（bold, italic, underline, strikethrough）
- [ ] 实现表格样式渲染（边框、内边距）
- [ ] 添加单元测试

### 步骤 4: 更新 API 接口（1 天）

- [ ] 更新导出 API 接收样式覆盖参数
- [ ] 添加参数验证
- [ ] 添加集成测试

### 步骤 5: 测试和文档（1-2 天）

- [ ] 完整测试覆盖
- [ ] 更新 API 文档
- [ ] 添加使用示例

## 六、注意事项

### 6.1 样式覆盖的优先级

1. **前端样式覆盖**（最高优先级）
2. **类型统一字号**（如果没有前端覆盖）
3. **默认字号**（如果类型没有 blocks）

### 6.2 样式覆盖的验证

- 字号范围：6pt - 72pt
- 字体名称：必须是已注册的字体
- 对齐方式：必须是 'left', 'center', 'right', 'justify' 之一
- 颜色格式：支持 '#RRGGBB' 或颜色名称

### 6.3 性能考虑

- 样式覆盖只影响被覆盖的 blocks，不影响其他 blocks
- 基线计算时排除覆盖的 blocks，计算量不会显著增加
- 样式应用是 O(1) 操作，性能影响可忽略

## 七、未来扩展

1. **段落级样式**：支持段落级别的样式设置
2. **字符级样式**：支持字符级别的样式设置（富文本）
3. **样式模板**：支持样式模板，方便批量应用
4. **样式继承**：支持样式继承机制

