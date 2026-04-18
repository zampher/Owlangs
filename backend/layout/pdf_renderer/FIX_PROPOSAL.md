# PDF渲染器修复方案

## 问题1：单行bbox高度计算错误

### 问题描述
- 单行的bbox高度（如6.3pt）不包含行间距
- 当前代码在计算`available_height`时，会减去`font_metrics_space`（ascent + descent），导致可用高度变小
- 例如：bbox高度6.3pt，期望8.0pt，但实际只用了5.2pt

### 修复方案

#### 方案A：根据行数区分处理（推荐）

**原理**：
- 单行bbox：高度 = 字体高度（不包含行间距）
- 双行bbox：高度 = 字体高度 + 1个行间距
- 多行bbox：高度 = 字体高度 + (n-1)个行间距

**实现**：
```python
def calculate_available_height_for_lines(
    bbox_height: float,
    line_count: int,
    font_size: float,
    line_spacing_ratio: float = 1.2
) -> float:
    """
    根据行数计算可用高度。
    
    单行bbox不包含行间距，多行bbox包含(n-1)个行间距。
    """
    if line_count <= 0:
        return 0.0
    
    if line_count == 1:
        # 单行：bbox高度就是字体高度，直接使用（保留5%安全边距）
        return bbox_height * 0.95
    else:
        # 多行：bbox高度 = 字体高度 + (n-1)个行间距
        # 可用高度 = bbox高度 - (n-1)个行间距 = 字体高度
        # 但需要考虑第一行的ascent和最后一行的descent
        line_spacing = font_size * (line_spacing_ratio - 1.0)  # 行间距增量
        total_line_spacing = (line_count - 1) * line_spacing
        
        # bbox高度 = 字体高度 + 总行间距
        # 字体高度 = bbox高度 - 总行间距
        font_height = bbox_height - total_line_spacing
        
        # 减去第一行的ascent和最后一行的descent的额外空间
        font_ascent = font_size * 0.75
        font_descent = font_size * 0.25
        extra_space = font_ascent - font_size * 0.5  # 超出字体中心线的部分
        
        available_height = font_height - extra_space
        
        # 确保至少30%的安全边距
        return max(available_height, bbox_height * 0.3)
```

**修改位置**：
1. `render_layout_pdf_reportlab` 函数第4197行附近（主迭代循环）
2. `render_layout_pdf_reportlab` 函数第4630行附近（Final adjustment循环）

#### 方案B：简化版本（备选）

如果方案A太复杂，可以使用简化版本：

```python
def calculate_available_height_simple(
    bbox_height: float,
    line_count: int,
    font_size: float
) -> float:
    """简化版本：根据行数使用不同的计算方式"""
    if line_count == 1:
        # 单行：直接使用bbox高度（保留5%安全边距）
        return bbox_height * 0.95
    elif line_count == 2:
        # 双行：减去一个行间距
        line_spacing = font_size * 0.2  # 20%行间距
        return bbox_height - line_spacing
    else:
        # 多行：使用原有逻辑
        estimated_font_ascent = font_size * 0.75
        font_metrics_space = estimated_font_ascent + font_size * 0.25
        available_height = bbox_height - font_metrics_space
        return max(available_height, bbox_height * 0.3)
```

## 问题2：横向溢出

### 问题描述
- 文本横向超出bbox宽度
- 可能超出一个单词或半个单词

### 修复方案

#### 方案A：在换行函数中加强验证（推荐）

**修改 `_wrap_text_to_width` 函数**：
1. 在返回前，验证每行宽度
2. 如果某行超出，强制按字符拆分
3. 对于英文，如果最后一个单词超出，将其拆分

**实现**：
```python
def _wrap_text_to_width(text: str, max_width: float, font_name: str = "Helvetica", font_size: float = 12, canvas_obj=None) -> List[str]:
    """
    换行函数，确保每行严格不超过max_width。
    """
    # ... 现有换行逻辑 ...
    
    # 最终验证：确保每行严格不超过max_width
    verified_lines = []
    for line in lines:
        if canvas_obj:
            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
        else:
            line_width = len(line) * font_size * 0.6  # 近似值
        
        if line_width <= max_width:
            verified_lines.append(line)
        else:
            # 超出宽度，强制拆分
            # 对于英文：尝试在单词边界拆分
            # 对于CJK：按字符拆分
            if has_cjk:
                # CJK：按字符拆分
                temp_line = ""
                temp_width = 0
                for char in line:
                    if canvas_obj:
                        char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                    else:
                        char_width = font_size
                    
                    if temp_width + char_width <= max_width:
                        temp_line += char
                        temp_width += char_width
                    else:
                        if temp_line:
                            verified_lines.append(temp_line)
                        temp_line = char
                        temp_width = char_width
                if temp_line:
                    verified_lines.append(temp_line)
            else:
                # 英文：尝试在单词边界拆分
                words = line.split()
                temp_line = ""
                temp_width = 0
                for word in words:
                    if canvas_obj:
                        word_width = pdfmetrics.stringWidth(word + " ", font_name, font_size)
                    else:
                        word_width = len(word + " ") * font_size * 0.6
                    
                    if temp_width + word_width <= max_width:
                        temp_line += word + " "
                        temp_width += word_width
                    else:
                        if temp_line:
                            verified_lines.append(temp_line.strip())
                        # 如果单个单词就超出，强制拆分单词
                        if word_width > max_width:
                            # 按字符拆分单词
                            for char in word:
                                if canvas_obj:
                                    char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                                else:
                                    char_width = font_size * 0.6
                                if temp_width + char_width <= max_width:
                                    temp_line += char
                                    temp_width += char_width
                                else:
                                    if temp_line:
                                        verified_lines.append(temp_line)
                                    temp_line = char
                                    temp_width = char_width
                        else:
                            temp_line = word + " "
                            temp_width = word_width
                if temp_line:
                    verified_lines.append(temp_line.strip())
    
    return verified_lines
```

#### 方案B：在渲染前验证（备选）

在渲染文本前，再次验证每行宽度，如果超出则动态调整：

```python
# 在渲染前验证
for line in text_lines:
    if canvas_obj:
        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
    else:
        line_width = len(line) * font_size * 0.6
    
    if line_width > text_width_for_wrapping:
        # 超出宽度，需要进一步拆分或减小字体
        # 这里可以选择：
        # 1. 进一步拆分（推荐）
        # 2. 减小字体大小（不推荐，会影响一致性）
        logger.warning(f"Line exceeds width: {line_width:.1f}pt > {text_width_for_wrapping:.1f}pt")
        # 强制拆分...
```

## 实施建议

### 优先级
1. **高优先级**：问题1（单行bbox高度）- 影响字体大小准确性
2. **中优先级**：问题2（横向溢出）- 影响文本显示完整性

### 实施步骤
1. 先实施问题1的修复（方案A或方案B）
2. 测试单行、双行、多行的情况
3. 再实施问题2的修复
4. 全面测试各种文本情况

### 测试用例
1. 单行文本：bbox高度6.3pt，应该能使用接近6.3pt的字体
2. 双行文本：bbox高度包含1个行间距
3. 多行文本：bbox高度包含(n-1)个行间距
4. 横向溢出：英文长单词、CJK长文本

