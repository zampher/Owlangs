# PDF 导出深度重构计划

## 一、当前问题分析

### 1.1 字体大小计算流程现状

当前实现中存在以下问题：

1. **计算流程复杂且分散**：
   - `calculate_type_font_baselines()` 计算类型基线（15次迭代）
   - `_render_text_in_bbox_simple()` 有自己的字体大小计算（二进制搜索）
   - 主渲染循环中还有多次字体大小调整（10次迭代 + 5次最终调整）
   - 表格渲染有独立的字体大小计算（5次迭代）

2. **重复计算**：
   - 文本换行计算在多个地方重复
   - 字体大小调整逻辑重复
   - bbox 溢出检查逻辑重复
   - 坐标转换计算重复

3. **类型处理不一致**：
   - `text` 和 `title` 使用初始估算 + 量化
   - `ref_text` 使用全局基线（15次迭代）
   - `caption` 使用全局基线（15次迭代）
   - 表格使用独立计算
   - 缺乏统一的类型分类和处理策略

4. **字号调整规则不统一**：
   - 有些类型允许微调，有些不允许
   - 字号量化规则不一致（有些是 0.1pt，有些是 0.5pt）
   - 缺乏明确的调整策略

### 1.2 字体选择现状

- 当前有 `FontUtils.detect_and_get_font_for_text()` 方法
- 支持中文、英文等语言
- 但缺乏对 20+ 种语言的系统化支持
- 字体回退逻辑分散在多个地方

### 1.3 Bbox 溢出处理现状

- 有 `LayoutCalculator.calculate_available_height_for_lines()` 方法
- 有 `_check_and_fix_line_width()` 工具函数
- 但溢出检查逻辑分散，不够统一
- 缺乏统一的溢出容忍度策略

## 二、重构目标

### 2.1 核心目标

1. **统一字体大小计算流程**：
   - 第一阶段：计算统一字号（适用于 header, footer, caption, table_notes, table_body, ref_text）
   - 第二阶段：基于统一字号进行微调（适用于 text, title）

2. **简化计算逻辑**：
   - 减少重复计算
   - 统一溢出检查
   - 统一坐标转换

3. **提高可维护性**：
   - 清晰的类型分类
   - 明确的处理策略
   - 易于扩展的语言支持

### 2.2 类型分类

根据用户需求，将 block 类型分为以下类别：

1. **统一字号类型（0.5pt 步长，无微调）**：
   - `header` - 页眉
   - `footer` - 页脚
   - `caption` - 图片标题和表格标题（合并）
   - `table_notes` - 表格脚注（table_footnote）
   - `table_body` - 表格主体
   - `ref_text` - 参考文献

2. **统一字号类型（1.0pt 步长，需要微调）**：
   - `text` - 正文
   - `title` - 标题

**重要说明**：
- `text` 和 `title` 分别计算统一基线（text 一个，title 一个）
- 统一基线使用 1pt 步长，四舍五入取整
- **每个 block 基于统一基线进行微调**，微调步长是 1.0pt
- 如果向上微调超 bbox，则取小一档（向下调整 1pt）
- 其他统一字号类型：0.5pt 步长，四舍五入，不进行微调

3. **其他类型**（保持现有处理或使用默认策略）：
   - `image` - 图片（不包含文本，只渲染图片）
   - `table` - 表格（整体容器，包含 caption, body, notes，但分别处理）
   - `page_number` - 页码（可归入 footer 或使用统一字号）
   - `figure` - 图表（可归入 caption 或使用统一字号）
   - `formula` - 公式（可归入 text 或使用统一字号）
   - `equation` - 方程（可归入 text 或使用统一字号）
   - `list` - 列表（可归入 text 或使用统一字号）

**注意**：`page_number`, `figure`, `formula`, `equation`, `list` 这些类型如果出现频率不高，可以：
- 方案 A：归入最近的类型（如 `page_number` → `footer`, `figure` → `caption`）
- 方案 B：使用默认的统一字号计算策略

## 三、重构方案

### 3.1 阶段一：类型分类和统一字号计算

#### 3.1.1 创建类型分类器

**文件**: `backend/layout/pdf_renderer/shared/block_classifier.py`

```python
class BlockClassifier:
    """Block type classification for font size calculation."""
    
    # 统一字号类型（不需要微调）
    UNIFIED_FONT_SIZE_TYPES = {
        "header",
        "footer", 
        "caption",  # image_caption + table_caption
        "table_notes",  # table_footnote
        "table_body",
        "ref_text",
    }
    
    # 可微调类型（需要根据 bbox 微调）
    ADJUSTABLE_FONT_SIZE_TYPES = {
        "text",
        "title",
    }
    
    @staticmethod
    def get_font_size_strategy(block_type: str) -> str:
        """返回字体大小计算策略：'unified' 或 'adjustable'"""
        if block_type in BlockClassifier.UNIFIED_FONT_SIZE_TYPES:
            return "unified"
        elif block_type in BlockClassifier.ADJUSTABLE_FONT_SIZE_TYPES:
            return "adjustable"
        else:
            return "default"
    
    @staticmethod
    def normalize_block_type(block: LayoutBlock) -> str:
        """标准化 block 类型，处理特殊情况"""
        block_type = getattr(block, "type", "unknown") or "unknown"
        
        # 处理 caption 类型
        if block_type in ("image_caption", "table_caption"):
            return "caption"
        
        # 处理 table_footnote
        if block_type == "table_footnote":
            return "table_notes"
        
        return block_type
```

#### 3.1.2 重构统一字号计算

**文件**: `backend/layout/pdf_renderer/shared/font_calculator.py`

**新增方法**: `calculate_unified_font_size_for_type()`

```python
@staticmethod
def calculate_unified_font_size_for_type(
    layout_doc: LayoutDocument,
    block_type: str,
    translated_text_by_block_index: Dict[int, str],
    max_iterations: int = 15,
) -> float:
    """
    计算统一字号（适用于 header, footer, caption, table_notes, table_body, ref_text）
    
    算法：
    1. 收集该类型的所有 blocks
    2. 对每个 block 估算初始字号（基于 bbox 高度和文本长度）
    3. 使用加权平均计算初始基线字号
    4. 迭代优化：
       - 对每个 block，使用基线字号计算行数和高度
       - 如果溢出，记录溢出信息
       - 如果未溢出，记录可用空间
    5. 根据溢出情况调整基线字号
    6. 重复步骤 4-5 直到收敛或达到最大迭代次数
    
    返回：统一字号（所有该类型的 blocks 使用相同字号）
    """
    # 实现细节...
```

**关键改进**：
- 统一所有"统一字号类型"的计算逻辑
- 确保不溢出 bbox
- 尽量利用 bbox 空间（字号尽可能大）
- 使用统一的溢出容忍度（5% 行高）

#### 3.1.3 Text 和 Title 的微调计算

**文件**: `backend/layout/pdf_renderer/shared/font_calculator.py`

**新增方法**: `calculate_adjustable_font_size_for_block()`

```python
@staticmethod
def calculate_adjustable_font_size_for_block(
    block: LayoutBlock,
    text: str,
    unified_baseline: float,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    adjust_step: float = 1.0,
    canvas_obj=None,
    font_name: str = "Helvetica",
) -> float:
    """
    计算可微调字号（适用于 text, title）
    
    算法：
    1. 从统一基线开始（text 类型有统一的基线，title 类型有统一的基线）
    2. 根据当前 block 的 bbox 和文本内容，计算最优字号
    3. 微调步长是 1.0pt
    4. 如果向上微调超 bbox，则取小一档（向下调整 1pt）
    5. 确保不溢出 bbox
    
    返回：微调后的字号
    """
    # 步骤 1: 从统一基线开始
    current_size = unified_baseline
    
    # 步骤 2: 计算当前 block 的最优字号（基于 bbox 和文本）
    optimal_size = calculate_optimal_font_size_for_single_block(
        block, text, canvas_obj, font_name
    )
    
    # 步骤 3: 如果最优字号大于基线，尝试向上微调
    if optimal_size > current_size:
        adjusted_size = current_size + adjust_step  # 向上微调 1.0pt
        
        # 检查是否超 bbox
        if check_would_overflow(block, text, adjusted_size, canvas_obj, font_name):
            # 超 bbox，取小一档（保持基线）
            return current_size
        else:
            # 可以向上微调
            return adjusted_size
    else:
        # 基线已经足够或更优
        return current_size
```

**关键改进**：
- 基于统一基线进行微调
- 微调步长是 **1.0pt**（不是 0.5pt）
- 向上微调时检查溢出，如果溢出则保持基线
- 确保不溢出 bbox

### 3.2 阶段二：字体选择系统化

#### 3.2.1 扩展语言支持

**文件**: `backend/layout/pdf_renderer/shared/font_utils.py`

**新增方法**: `get_font_name_for_language_extended()`

```python
@staticmethod
def get_font_name_for_language_extended(lang: str) -> str:
    """
    根据语言代码返回最主流的字体名称。
    
    支持的语言（根据翻译支持的语言）：
    - 中文 (zh): SimSun, SimHei, Microsoft YaHei (系统字体优先)
    - 英文 (en): Times-Roman, Helvetica
    - 日文 (ja): MS Gothic, MS Mincho
    - 韩文 (ko): Malgun Gothic, Batang
    - 法文 (fr): Times-Roman
    - 德文 (de): Times-Roman
    - 西班牙文 (es): Times-Roman
    - 意大利文 (it): Times-Roman
    - 葡萄牙文 (pt): Times-Roman
    - 俄文 (ru): Times-Roman
    - 阿拉伯文 (ar): Arial Unicode MS
    - 泰文 (th): Tahoma
    - 越南文 (vi): Times-Roman
    - ... (支持 20+ 种语言)
    
    返回：字体名称（如果系统字体不可用，返回项目字体）
    """
    # 实现细节...
```

#### 3.2.2 字体下载工具

**文件**: `backend/layout/pdf_renderer/shared/font_downloader.py`

```python
class FontDownloader:
    """字体下载和管理工具"""
    
    @staticmethod
    def check_system_fonts() -> Dict[str, bool]:
        """检查系统字体是否可用"""
        # 实现细节...
    
    @staticmethod
    def download_font_if_needed(lang: str) -> bool:
        """如果需要，下载字体到项目目录"""
        # 实现细节...
    
    @staticmethod
    def generate_font_download_guide() -> str:
        """生成字体下载指南（引导用户下载需要的字体）"""
        # 实现细节...
```

### 3.3 阶段三：统一溢出检查和文本渲染

#### 3.3.1 统一溢出检查

**文件**: `backend/layout/pdf_renderer/shared/layout_calculator.py`

**新增方法**: `check_text_fits_in_bbox()`

```python
@staticmethod
def check_text_fits_in_bbox(
    text_lines: List[str],
    font_size: float,
    bbox_width: float,
    bbox_height: float,
    line_height_ratio: float = 1.2,
    overflow_tolerance: float = 0.05,  # 5% 行高容忍度
    canvas_obj=None,
    font_name: str = "Helvetica",
) -> Tuple[bool, float, float]:
    """
    检查文本是否适合 bbox，返回 (fits, actual_width, actual_height)
    
    Args:
        text_lines: 文本行列表
        font_size: 字体大小
        bbox_width: bbox 宽度
        bbox_height: bbox 高度
        line_height_ratio: 行高比例
        overflow_tolerance: 溢出容忍度（相对于行高的百分比）
        canvas_obj: Canvas 对象（用于测量文本宽度）
        font_name: 字体名称
    
    Returns:
        (fits: bool, actual_width: float, actual_height: float)
    """
    # 实现细节...
```

#### 3.3.2 统一文本渲染

**文件**: `backend/layout/pdf_renderer/shared/text_renderer.py`

```python
class TextRenderer:
    """统一的文本渲染器"""
    
    @staticmethod
    def render_text_in_bbox(
        canvas_obj,
        text: str,
        bbox: Tuple[float, float, float, float],
        page_height: float,
        font_size: float,
        font_name: str,
        alignment: str = "left",  # left, center, right
        line_height_ratio: float = 1.2,
        strict_bbox_limit: bool = True,  # 严格限制在 bbox 内
    ) -> bool:
        """
        在 bbox 内渲染文本
        
        要求：
        1. 左对齐（默认，可通过 alignment 参数调整）
        2. 文本严格限制在 bbox 内
        3. 使用指定的字体和字号
        """
        # 实现细节...
```

### 3.4 阶段四：重构主渲染流程

#### 3.4.1 新的渲染流程

**文件**: `backend/layout/pdf_renderer_reportlab.py`

```python
def render_layout_pdf_reportlab(...):
    """
    新的渲染流程：
    
    1. 类型分类和准备
       - 使用 BlockClassifier 分类所有 blocks
       - 提取翻译文本
    
    2. 第一阶段：计算统一字号
       - 对每个"统一字号类型"，调用 calculate_unified_font_size_for_type()
       - 结果存储在 type_unified_font_sizes: Dict[str, float]
    
    3. 第二阶段：计算可微调字号
       - 对每个 text/title block，调用 calculate_adjustable_font_size_for_block()
       - 基于统一基线进行微调
    
    4. 第三阶段：渲染
       - 使用统一的 TextRenderer.render_text_in_bbox() 渲染所有文本
       - 使用统一的字体选择逻辑
       - 使用统一的溢出检查
    """
    # 实现细节...
```

## 四、实施步骤

### 步骤 1: 创建类型分类器（1-2 天）

- [ ] 创建 `BlockClassifier` 类
- [ ] 实现类型标准化逻辑
- [ ] 添加单元测试

### 步骤 2: 重构统一字号计算（3-5 天）

- [ ] 重构 `calculate_unified_font_size_for_type()` 方法
- [ ] 统一所有"统一字号类型"的计算逻辑
- [ ] 确保不溢出 bbox
- [ ] 优化算法，尽量利用 bbox 空间
- [ ] 添加单元测试

### 步骤 3: 实现可微调字号计算（2-3 天）

- [ ] 实现 `calculate_adjustable_font_size_for_block()` 方法
- [ ] 实现 0.5pt 量化逻辑
- [ ] 针对 text 和 title 的特殊处理
- [ ] 添加单元测试

### 步骤 4: 扩展字体支持（2-3 天）

- [ ] 扩展 `get_font_name_for_language_extended()` 支持 20+ 种语言
- [ ] 创建字体下载工具
- [ ] 添加字体检查逻辑
- [ ] 生成字体下载指南

### 步骤 5: 统一溢出检查和文本渲染（2-3 天）

- [ ] 实现 `check_text_fits_in_bbox()` 方法
- [ ] 创建 `TextRenderer` 类
- [ ] 实现统一的文本渲染逻辑
- [ ] 确保严格限制在 bbox 内
- [ ] 添加单元测试

### 步骤 6: 重构主渲染流程（3-5 天）

- [ ] 重构 `render_layout_pdf_reportlab()` 主函数
- [ ] 集成新的计算流程
- [ ] 移除旧的重复计算逻辑
- [ ] 更新表格渲染使用新流程
- [ ] 添加集成测试

### 步骤 7: 测试和优化（2-3 天）

- [ ] 运行完整测试套件
- [ ] 性能测试和优化
- [ ] 修复发现的 bug
- [ ] 代码审查

## 五、关键技术细节

### 5.1 统一字号计算算法

```python
def calculate_unified_font_size_for_type(...):
    # 步骤 1: 收集该类型的所有 blocks
    blocks = collect_blocks_by_type(layout_doc, block_type)
    
    # 步骤 2: 初始估算
    initial_sizes = []
    for block in blocks:
        estimated_size = estimate_initial_font_size(block)
        initial_sizes.append((block, estimated_size))
    
    # 步骤 3: 计算加权平均基线
    baseline = calculate_weighted_average(initial_sizes)
    
    # 步骤 4: 迭代优化（最多 15 次）
    for iteration in range(max_iterations):
        overflow_count = 0
        total_overflow = 0.0
        total_available_space = 0.0
        
        for block, _ in initial_sizes:
            # 使用当前基线计算
            lines = wrap_text(block.text, block.bbox_width, baseline)
            total_height = calculate_total_height(lines, baseline)
            available_height = calculate_available_height(block.bbox_height, len(lines))
            
            if total_height > available_height * 1.05:  # 5% 容忍度
                overflow_count += 1
                total_overflow += (total_height - available_height)
            else:
                total_available_space += (available_height - total_height)
        
        # 调整基线
        if overflow_count > 0:
            # 有溢出，减小字号
            adjustment = total_overflow / (len(blocks) * baseline * 0.1)
            baseline = baseline * (1 - adjustment * 0.1)
        elif total_available_space > 0:
            # 有可用空间，尝试增大字号（但要保守）
            adjustment = min(total_available_space / (len(blocks) * baseline * 0.1), 0.05)
            baseline = baseline * (1 + adjustment)
        
        # 收敛检查
        if abs(adjustment) < 0.01:
            break
    
    return baseline
```

### 5.2 可微调字号计算算法

```python
def calculate_adjustable_font_size_for_block(...):
    # 步骤 1: 从统一基线开始
    current_size = unified_baseline
    
    # 步骤 2: 计算当前 block 的最优字号
    optimal_size = calculate_optimal_font_size_for_single_block(block, text)
    
    # 步骤 3: 量化到 0.5pt 的倍数
    quantized_size = round(optimal_size / quantize_step) * quantize_step
    
    # 步骤 4: 确保不溢出
    while quantized_size > 0:
        if check_fits_in_bbox(text, quantized_size, block.bbox):
            return quantized_size
        quantized_size -= quantize_step
    
    return quantize_step  # 最小字号
```

### 5.3 字体选择优先级

1. **系统字体**（优先级 1）：
   - Windows: `C:/Windows/Fonts/`
   - macOS: `/System/Library/Fonts/`
   - Linux: `/usr/share/fonts/`

2. **项目字体**（优先级 2）：
   - `backend/static/flutter-web/assets/fonts/`

3. **回退字体**（优先级 3）：
   - 通用字体（Helvetica, Times-Roman 等）

### 5.4 Bbox 溢出检查策略

- **宽度检查**：严格限制，不允许任何溢出
- **高度检查**：允许 5% 的行高容忍度（每行 5% 行高）
- **计算方式**：`max_allowed_height = available_height + line_count * (line_height * 0.05)`

## 六、预期效果

### 6.1 代码质量提升

- **代码行数**：预计减少 200-300 行重复代码
- **函数复杂度**：降低，每个函数职责更单一
- **可维护性**：显著提升，逻辑更清晰

### 6.2 性能提升

- **计算次数**：减少重复计算，预计提升 10-20% 性能
- **内存使用**：优化数据结构，减少内存占用

### 6.3 功能改进

- **字体支持**：从当前几种语言扩展到 20+ 种语言
- **字号一致性**：统一字号类型使用完全一致的字号
- **溢出控制**：更严格的溢出检查，确保文本不超出 bbox

## 七、风险评估

### 7.1 潜在风险

1. **兼容性风险**：
   - 新算法可能产生不同的字号结果
   - 需要充分测试确保输出质量不下降

2. **性能风险**：
   - 新的计算流程可能影响性能
   - 需要性能测试和优化

3. **功能风险**：
   - 重构可能引入 bug
   - 需要完整的测试覆盖

### 7.2 缓解措施

1. **分阶段实施**：每个阶段完成后进行测试
2. **保留旧代码**：在完全验证前保留旧代码作为回退
3. **充分测试**：单元测试 + 集成测试 + 手动测试
4. **代码审查**：每个阶段完成后进行代码审查

## 八、时间估算

- **总时间**：15-25 个工作日
- **阶段 1-3**：6-10 天（核心计算逻辑）
- **阶段 4**：2-3 天（字体支持）
- **阶段 5-6**：5-8 天（渲染流程）
- **阶段 7**：2-3 天（测试和优化）

## 九、后续优化方向

1. **缓存机制**：缓存字体大小计算结果
2. **并行计算**：并行计算不同类型的基础字号
3. **增量更新**：支持增量更新（只重新计算变化的 blocks）
4. **配置化**：将字号调整策略配置化，支持用户自定义
5. **前端样式覆盖**：支持前端设置片段的字号、字体、对齐、样式等（详见 `FRONTEND_OVERRIDE_SUPPORT.md`）

## 十、重要更新（根据用户确认）

### 10.1 字号量化规则更新

1. **Text 和 Title**：
   - 使用 **1pt 步长**，四舍五入取整
   - 如果向上取整超 bbox，则取小一档
   - **不进行微调**，使用统一字号

2. **其他统一字号类型**：
   - 使用 **0.5pt 步长**，四舍五入

3. **溢出容忍度**：
   - 单行：5% 行高或 0.5pt（取较大值）
   - 多行：每行 3% 行高，总容忍度不超过 2pt

### 10.2 前端样式覆盖支持

**新增功能**：允许前端设置片段的字号、字体、对齐、斜体、黑体、下划线、删除线、表格线条等。

**关键规则**：
- 如果前端设置了，优先使用前端的设置
- 统计字号类型基线的时候，不用纳入前端设置的片段

**详细设计**：参见 `FRONTEND_OVERRIDE_SUPPORT.md`

