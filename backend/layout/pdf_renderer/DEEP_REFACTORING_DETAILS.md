# PDF 导出深度重构 - 关键细节讨论

## 一、需要明确的细节问题

### 1.1 Text 和 Title 的统一基线计算

**问题**：`text` 和 `title` 是否分别计算统一基线？

**选项 A**：分别计算
- `text` 类型计算一个统一基线（比如 10pt）
- `title` 类型计算一个统一基线（比如 14pt）
- 然后每个 block 基于各自的统一基线进行微调

**选项 B**：合并计算后分离
- 先计算一个基础基线
- `title` 在此基础上增加 10-15%（保持当前逻辑）
- 然后分别微调

**建议**：**选项 A** - 分别计算，因为：
- `text` 和 `title` 的字号差异较大（title 通常比 text 大 20-50%）
- 分别计算可以更好地利用各自的 bbox 空间
- 逻辑更清晰，易于维护

### 1.2 微调的范围限制

**问题**：`text` 和 `title` 的微调是否需要限制范围？

**选项 A**：无限制（只要不溢出 bbox）
- 优点：最大化利用空间
- 缺点：可能导致同一类型的字号差异过大，影响视觉一致性

**选项 B**：限制在统一基线的 ±20% 范围内
- 优点：保持视觉一致性
- 缺点：可能无法充分利用某些 bbox 的空间

**选项 C**：限制在统一基线的 ±30% 范围内，但优先选择接近基线的值
- 优点：平衡一致性和空间利用
- 缺点：算法稍复杂

**建议**：**选项 C** - 限制范围但优先接近基线，因为：
- 保持视觉一致性很重要
- 但也要充分利用空间
- 可以通过权重函数实现：`score = (空间利用率 * 0.6) + (接近基线度 * 0.4)`

### 1.3 0.5pt 量化的方向

**问题**：字号量化时，向上取整还是向下取整？

**选项 A**：向下取整（floor）
- 优点：确保不溢出
- 缺点：可能浪费空间

**选项 B**：向上取整（ceil）
- 优点：充分利用空间
- 缺点：可能溢出，需要额外检查

**选项 C**：四舍五入，但溢出时向下调整
- 优点：平衡
- 缺点：需要额外的溢出检查

**建议**：**选项 C** - 四舍五入 + 溢出检查，因为：
- 四舍五入更符合直觉
- 溢出检查确保安全性
- 如果溢出，向下调整到最近的 0.5pt 倍数

**实现示例**：
```python
def quantize_font_size(font_size: float, step: float = 0.5) -> float:
    """量化字号到 step 的倍数"""
    quantized = round(font_size / step) * step
    return max(step, quantized)  # 确保不小于 step
```

### 1.4 Table Body 的统一字号计算

**问题**：`table_body` 如何计算统一字号？

**特殊性**：
- 表格有行数和列数
- 单元格内容长度差异大
- 需要考虑表格渲染方式（HTML vs Image）

**选项 A**：使用文本的统一字号计算方法
- 将表格内容视为普通文本
- 计算所有单元格的平均字号需求
- 优点：复用现有逻辑
- 缺点：可能不适合表格的特殊性

**选项 B**：独立的表格字号计算方法
- 考虑行数、列数、单元格内容
- 计算适合所有单元格的统一字号
- 优点：更精确
- 缺点：需要额外实现

**选项 C**：混合方法
- 先使用文本方法估算
- 然后根据表格特性调整（考虑行高、列宽）
- 优点：平衡精确性和复杂度
- 缺点：算法稍复杂

**建议**：**选项 C** - 混合方法，因为：
- 表格确实有特殊性，但可以复用部分逻辑
- 先估算，再根据表格特性微调
- 保持与文本字号计算的兼容性

**实现思路**：
```python
def calculate_table_body_font_size(...):
    # 1. 收集所有单元格的文本
    all_cell_texts = extract_all_cell_texts(table)
    
    # 2. 使用文本统一字号计算方法估算
    estimated_size = calculate_unified_font_size_for_type(
        block_type="table_body",
        texts=all_cell_texts,
        ...
    )
    
    # 3. 根据表格特性调整
    # - 考虑行数：行数多，字号可以稍小
    # - 考虑列数：列数多，字号需要更小
    # - 考虑单元格内容长度：内容长，字号需要更小
    
    adjusted_size = adjust_for_table_properties(
        estimated_size,
        num_rows=len(rows),
        num_cols=len(cols),
        avg_cell_length=avg_length,
    )
    
    return adjusted_size
```

### 1.5 溢出容忍度的具体数值

**当前实现**：5% 行高容忍度（每行 5% 行高）

**问题**：这个数值是否合适？是否需要调整？

**分析**：
- 5% 行高意味着：如果行高是 12pt，容忍度是 0.6pt
- 对于单行：容忍度较小，可能过于严格
- 对于多行：容忍度累加，可能过于宽松

**选项 A**：保持 5% 行高
- 优点：当前实现已经验证
- 缺点：可能对多行文本过于宽松

**选项 B**：固定容忍度（如 1pt）
- 优点：更可预测
- 缺点：对大字号的单行可能不够，对小字号的多行可能过多

**选项 C**：分段容忍度
- 单行：5% 行高或 0.5pt（取较大值）
- 多行：每行 3% 行高，但总容忍度不超过 2pt
- 优点：更精确
- 缺点：算法稍复杂

**建议**：**选项 C** - 分段容忍度，因为：
- 单行和多行的情况不同，需要区别对待
- 总容忍度上限防止过度溢出

**实现示例**：
```python
def calculate_overflow_tolerance(
    line_count: int,
    line_height: float,
    base_tolerance_ratio: float = 0.05,
    max_total_tolerance: float = 2.0,
) -> float:
    """计算溢出容忍度"""
    if line_count == 1:
        # 单行：5% 行高或 0.5pt，取较大值
        tolerance = max(line_height * base_tolerance_ratio, 0.5)
    else:
        # 多行：每行 3% 行高，但总容忍度不超过 max_total_tolerance
        per_line_tolerance = line_height * 0.03
        tolerance = min(per_line_tolerance * line_count, max_total_tolerance)
    
    return tolerance
```

### 1.6 字体选择的语言支持范围

**问题**：需要支持哪些语言？优先级如何？

**当前支持**：
- 中文（zh）
- 英文（en）

**需要扩展**：20+ 种语言

**建议的语言列表**（根据常见翻译需求）：
1. 中文（zh）- SimSun, SimHei, Microsoft YaHei
2. 英文（en）- Times-Roman, Helvetica
3. 日文（ja）- MS Gothic, MS Mincho
4. 韩文（ko）- Malgun Gothic, Batang
5. 法文（fr）- Times-Roman
6. 德文（de）- Times-Roman
7. 西班牙文（es）- Times-Roman
8. 意大利文（it）- Times-Roman
9. 葡萄牙文（pt）- Times-Roman
10. 俄文（ru）- Times-Roman
11. 阿拉伯文（ar）- Arial Unicode MS
12. 泰文（th）- Tahoma
13. 越南文（vi）- Times-Roman
14. 印尼文（id）- Times-Roman
15. 马来文（ms）- Times-Roman
16. 印地文（hi）- Mangal
17. 土耳其文（tr）- Times-Roman
18. 波兰文（pl）- Times-Roman
19. 荷兰文（nl）- Times-Roman
20. 希腊文（el）- Times-Roman
21. 希伯来文（he）- Arial Unicode MS
22. 捷克文（cs）- Times-Roman
23. 瑞典文（sv）- Times-Roman
24. 挪威文（no）- Times-Roman
25. 丹麦文（da）- Times-Roman

**字体选择优先级**：
1. **系统字体**（优先级 1）：检查系统字体目录
2. **项目字体**（优先级 2）：`backend/static/flutter-web/assets/fonts/`
3. **通用字体**（优先级 3）：Helvetica, Times-Roman, Arial Unicode MS

**字体下载策略**：
- **方案 A**：自动下载（需要网络，可能较慢）
- **方案 B**：引导用户下载（提供下载链接和指南）
- **方案 C**：混合（常用字体自动下载，其他引导用户）

**建议**：**方案 C** - 混合策略，因为：
- 常用字体（中、英、日、韩）可以自动下载
- 其他语言引导用户下载，避免不必要的网络请求
- 提供字体检查工具，告知用户缺少哪些字体

### 1.7 表格相关类型的处理细节

**问题**：表格的 caption, body, notes 如何协调？

**当前结构**：
- `table` - 整体容器
- `table_caption` - 表格标题（在 table.raw.blocks 中）
- `table_body` - 表格主体（在 table.raw.blocks 中）
- `table_footnote` - 表格脚注（在 table.raw.blocks 中）

**重构后的映射**：
- `table_caption` → `caption`（与其他 caption 统一）
- `table_body` → `table_body`（独立类型）
- `table_footnote` → `table_notes`（独立类型）

**字号关系**：
- `caption` 和 `table_notes` 使用各自的统一字号
- `table_body` 使用独立的统一字号
- 三者之间没有强制的大小关系，但通常：`caption >= table_body >= table_notes`

**建议**：
- 不强制字号关系，让算法自然优化
- 如果用户需要，可以通过配置调整（未来功能）

### 1.8 其他类型的处理策略

**问题**：`page_number`, `figure`, `formula`, `equation`, `list` 如何处理？

**选项 A**：归入最近的类型
- `page_number` → `footer`
- `figure` → `caption`
- `formula`, `equation`, `list` → `text`

**选项 B**：使用默认的统一字号计算策略
- 所有类型都参与统一字号计算
- 如果数量少，可能计算结果不准确

**选项 C**：混合策略
- 常见类型归入最近的类型
- 罕见类型使用默认策略

**建议**：**选项 C** - 混合策略，因为：
- `page_number` 确实应该和 `footer` 一致
- `figure` 确实应该和 `caption` 一致
- `formula`, `equation`, `list` 可以归入 `text`，但如果数量足够，也可以独立计算

**实现**：
```python
TYPE_MAPPING = {
    "page_number": "footer",
    "figure": "caption",
    "formula": "text",  # 如果数量少，可以独立
    "equation": "text",  # 如果数量少，可以独立
    "list": "text",  # 如果数量少，可以独立
}
```

### 1.9 性能优化考虑

**问题**：是否需要缓存和并行计算？

**缓存策略**：
- **字体大小计算结果**：可以缓存，因为相同类型的 blocks 使用相同字号
- **文本换行结果**：不建议缓存，因为每个 block 的文本不同
- **字体选择结果**：可以缓存，因为相同语言的文本使用相同字体

**并行计算**：
- **不同类型的基础字号计算**：可以并行（header, footer, caption 等互不依赖）
- **同一类型的 blocks 处理**：可以并行（但需要合并结果）

**建议**：
- 第一阶段：不实现缓存和并行，先保证正确性
- 第二阶段：如果性能成为瓶颈，再优化

### 1.10 向后兼容性

**问题**：如何确保重构后的输出与现有系统兼容？

**策略**：
1. **保留旧代码**：在完全验证前，保留旧代码作为回退选项
2. **功能开关**：添加配置选项，可以选择使用新算法或旧算法
3. **充分测试**：使用相同的测试用例，对比新旧算法的输出
4. **渐进式迁移**：先迁移部分类型，验证后再迁移其他类型

**建议**：
- 使用功能开关，方便回退
- 保留旧代码至少一个版本周期
- 充分测试后再移除旧代码

## 二、需要确认的决策

### 2.1 关键决策清单

1. ✅ **Text 和 Title 分别计算统一基线**（选项 A）
2. ✅ **微调范围限制在统一基线的 ±30%**（选项 C）
3. ✅ **0.5pt 量化使用四舍五入 + 溢出检查**（选项 C）
4. ✅ **Table Body 使用混合方法计算字号**（选项 C）
5. ✅ **溢出容忍度使用分段策略**（选项 C）
6. ✅ **字体选择支持 25 种语言，使用混合下载策略**（方案 C）
7. ✅ **其他类型使用混合策略处理**（选项 C）
8. ⏸️ **性能优化：第一阶段不实现，第二阶段再优化**
9. ✅ **向后兼容：使用功能开关，保留旧代码**

### 2.2 待确认的问题

1. **语言支持列表**：是否同意上述 25 种语言的列表？是否需要增减？
2. **字体下载策略**：是否同意混合策略（常用自动，其他引导）？
3. **微调范围**：±30% 是否合适？是否需要调整？
4. **溢出容忍度**：分段策略的参数（单行 5% 或 0.5pt，多行 3% 但总上限 2pt）是否合适？
5. **Table Body 计算**：混合方法的具体实现细节是否需要进一步讨论？

## 三、实施建议

### 3.1 优先级排序

1. **高优先级**（必须明确）：
   - Text 和 Title 的统一基线计算方式
   - 0.5pt 量化的方向
   - 溢出容忍度的具体数值

2. **中优先级**（建议明确）：
   - 微调的范围限制
   - Table Body 的计算方法
   - 其他类型的处理策略

3. **低优先级**（可以后续调整）：
   - 字体支持的语言列表（可以先实现核心语言，后续扩展）
   - 性能优化（可以先实现基础版本，后续优化）
   - 向后兼容策略（可以先实现，后续移除旧代码）

### 3.2 建议的讨论顺序

1. 先确认高优先级问题
2. 然后讨论中优先级问题
3. 低优先级问题可以在实施过程中逐步明确

