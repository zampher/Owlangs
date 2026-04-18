# 现有代码复用分析

## 一、可完全复用的代码

### 1.1 基础工具方法（FontSizeCalculator）

#### ✅ `estimate_initial_font_size()`
- **位置**: `font_calculator.py:112`
- **功能**: 基于 bbox 高度、宽度、文本长度估算初始字号
- **复用方式**: 直接使用，无需修改
- **用途**: 统一字号计算的初始估算

#### ✅ `estimate_line_count_from_font_size()`
- **位置**: `font_calculator.py:40`
- **功能**: 根据字号、文本、宽度估算行数
- **复用方式**: 直接使用，无需修改
- **用途**: 计算文本行数

#### ✅ `calculate_block_height_from_font_size()`
- **位置**: `font_calculator.py:81`
- **功能**: 根据字号和行数计算块高度
- **复用方式**: 直接使用，无需修改
- **用途**: 计算块高度

#### ✅ `calculate_font_size_for_bbox()`
- **位置**: `font_calculator.py:928`
- **功能**: 使用二分搜索计算适合 bbox 的字号
- **复用方式**: 可用于 Text 和 Title 的微调计算
- **用途**: 单个 block 的最优字号计算

### 1.2 布局计算工具（LayoutCalculator）

#### ✅ `calculate_available_height_for_lines()`
- **位置**: `layout_calculator.py`
- **功能**: 根据行数计算可用高度
- **复用方式**: 直接使用，无需修改
- **用途**: 溢出检查

#### ✅ `build_page_block_bbox_index()`
- **位置**: `layout_calculator.py`
- **功能**: 构建页面 block bbox 索引
- **复用方式**: 直接使用，无需修改
- **用途**: 碰撞检测

#### ✅ `check_block_collision_with_page()`
- **位置**: `layout_calculator.py`
- **功能**: 检查 block 是否与其他 block 碰撞
- **复用方式**: 直接使用，无需修改
- **用途**: 碰撞检测

### 1.3 文本处理工具（TextUtils）

#### ✅ `wrap_text_to_width()`
- **位置**: `text_utils.py`
- **功能**: 文本换行
- **复用方式**: 直接使用，无需修改
- **用途**: 文本换行计算

#### ✅ `detect_language()`
- **位置**: `text_utils.py`
- **功能**: 语言检测
- **复用方式**: 直接使用，无需修改
- **用途**: 字体选择

### 1.4 字体工具（FontUtils）

#### ✅ `detect_and_get_font_for_text()`
- **位置**: `font_utils.py`
- **功能**: 根据文本检测语言并返回字体
- **复用方式**: 直接使用，无需修改
- **用途**: 字体选择

#### ✅ `set_font_with_fallback()`
- **位置**: `font_utils.py`
- **功能**: 设置字体，带自动回退
- **复用方式**: 直接使用，无需修改
- **用途**: 字体设置

### 1.5 块处理工具（BlockProcessor）

#### ✅ `extract_text_from_raw_layout()`
- **位置**: `block_processor.py`
- **功能**: 从 raw layout 提取文本
- **复用方式**: 直接使用，无需修改
- **用途**: 文本提取

## 二、需要修改的代码

### 2.1 `calculate_type_font_baselines()` - 需要重构

**位置**: `font_calculator.py:393`

**当前功能**:
- 收集所有类型的 blocks
- 对 ref_text, text, caption 使用 15 次迭代的全局基线搜索
- 对其他类型使用加权平均

**需要修改**:
1. **支持前端样式覆盖过滤**
   - 添加 `frontend_style_overrides` 参数
   - 在收集 blocks 时过滤掉前端覆盖的 blocks

2. **分离 text 和 title 的计算**
   - text 和 title 分别计算统一基线
   - 都使用 1pt 步长量化

3. **统一其他类型的计算**
   - header, footer, caption, table_notes, table_body, ref_text 使用统一算法
   - 都使用 0.5pt 步长量化

4. **提取为独立方法**
   - `calculate_unified_font_size_for_type()` - 统一字号计算（0.5pt 步长）
   - `calculate_unified_font_size_for_type_with_step()` - 统一字号计算（可配置步长）

**复用策略**:
- 保留现有的 block 收集逻辑（lines 418-540）
- 保留现有的初始估算逻辑（lines 557-586）
- 保留现有的 15 次迭代搜索逻辑（lines 588-750），但需要：
  - 支持可配置的步长（1pt 或 0.5pt）
  - 支持前端样式覆盖过滤
  - 分离 text 和 title

### 2.2 `quantize_font_size()` - 需要扩展

**位置**: `font_calculator.py:173`

**当前功能**:
- 量化到 0.1pt 精度

**需要修改**:
- 支持可配置步长（0.5pt 或 1.0pt）
- 重命名为 `quantize_font_size_with_step()`

**复用策略**:
- 保留核心量化逻辑
- 添加 `step` 参数
- 保持四舍五入逻辑

### 2.3 类型分类逻辑 - 需要提取

**当前位置**: `calculate_type_font_baselines()` 内部（lines 426-540）

**需要提取**:
- 创建独立的 `BlockClassifier` 类
- 提取类型标准化逻辑（image_caption → caption, table_footnote → table_notes）
- 提取前端样式覆盖检查逻辑

**复用策略**:
- 将现有的类型处理逻辑提取到 `BlockClassifier.normalize_block_type()`
- 将 caption 提取逻辑提取到独立方法

## 三、需要新增的代码

### 3.1 `BlockClassifier` 类

**新文件**: `backend/layout/pdf_renderer/shared/block_classifier.py`

**功能**:
- 类型分类
- 类型标准化
- 前端样式覆盖检查

**可复用部分**:
- 从 `calculate_type_font_baselines()` 提取类型标准化逻辑
- 从现有代码提取 caption 处理逻辑

### 3.2 `calculate_adjustable_font_size_for_block()` 方法

**新位置**: `font_calculator.py`

**功能**:
- Text 和 Title 的微调计算
- 基于统一基线，1.0pt 步长微调

**可复用部分**:
- 使用 `calculate_font_size_for_bbox()` 计算最优字号
- 使用现有的溢出检查逻辑

### 3.3 `calculate_unified_font_size_for_type()` 方法

**新位置**: `font_calculator.py`

**功能**:
- 统一字号计算（0.5pt 步长类型）
- 统一字号计算（1.0pt 步长类型，用于 text/title 基线）

**可复用部分**:
- 从 `calculate_type_font_baselines()` 提取核心算法
- 复用现有的 15 次迭代搜索逻辑

### 3.4 前端样式覆盖支持

**新文件**: `backend/layout/pdf_renderer/shared/frontend_override.py`

**功能**:
- 定义 `FrontendStyleOverride` 数据类
- 样式覆盖检查逻辑

**可复用部分**:
- 无（全新功能）

## 四、重构策略

### 4.1 第一阶段：提取和重构

1. **创建 `BlockClassifier`**
   - 从 `calculate_type_font_baselines()` 提取类型处理逻辑
   - 添加前端样式覆盖检查

2. **重构 `quantize_font_size()`**
   - 重命名为 `quantize_font_size_with_step()`
   - 添加 `step` 参数

3. **提取统一字号计算方法**
   - 从 `calculate_type_font_baselines()` 提取核心算法
   - 创建 `calculate_unified_font_size_for_type()` 方法
   - 支持可配置步长

### 4.2 第二阶段：实现新功能

1. **实现 Text 和 Title 的微调**
   - 创建 `calculate_adjustable_font_size_for_block()` 方法
   - 复用 `calculate_font_size_for_bbox()` 计算最优字号

2. **更新 `calculate_type_font_baselines()`**
   - 调用新的统一字号计算方法
   - 分离 text 和 title 的计算
   - 添加前端样式覆盖支持

### 4.3 第三阶段：集成和测试

1. **更新渲染流程**
   - 使用新的计算方法
   - 应用前端样式覆盖

2. **测试和验证**
   - 单元测试
   - 集成测试
   - 对比新旧输出

## 五、代码复用统计

### 5.1 可完全复用（无需修改）
- ✅ `estimate_initial_font_size()` - 初始字号估算
- ✅ `estimate_line_count_from_font_size()` - 行数估算
- ✅ `calculate_block_height_from_font_size()` - 高度计算
- ✅ `calculate_font_size_for_bbox()` - bbox 字号计算
- ✅ `calculate_available_height_for_lines()` - 可用高度计算
- ✅ `build_page_block_bbox_index()` - bbox 索引构建
- ✅ `check_block_collision_with_page()` - 碰撞检测
- ✅ `wrap_text_to_width()` - 文本换行
- ✅ `detect_language()` - 语言检测
- ✅ `detect_and_get_font_for_text()` - 字体选择
- ✅ `set_font_with_fallback()` - 字体设置
- ✅ `extract_text_from_raw_layout()` - 文本提取

**总计**: 12 个方法可完全复用

### 5.2 需要修改后复用
- 🔧 `calculate_type_font_baselines()` - 需要重构，但可复用核心算法
- 🔧 `quantize_font_size()` - 需要扩展支持不同步长

**总计**: 2 个方法需要修改

### 5.3 需要新增
- ➕ `BlockClassifier` 类
- ➕ `calculate_adjustable_font_size_for_block()` 方法
- ➕ `calculate_unified_font_size_for_type()` 方法
- ➕ 前端样式覆盖支持

**总计**: 4 个新组件

## 六、实施建议

### 6.1 优先级排序

1. **高优先级**（核心功能）：
   - 创建 `BlockClassifier`（复用现有类型处理逻辑）
   - 重构 `quantize_font_size()`（简单扩展）
   - 提取统一字号计算方法（从现有代码提取）

2. **中优先级**（新功能）：
   - 实现 Text 和 Title 的微调（复用 `calculate_font_size_for_bbox()`）
   - 更新 `calculate_type_font_baselines()`（调用新方法）

3. **低优先级**（扩展功能）：
   - 前端样式覆盖支持（全新功能）

### 6.2 实施步骤

1. **步骤 1**: 创建 `BlockClassifier`（1 天）
   - 从现有代码提取类型处理逻辑
   - 添加前端样式覆盖检查

2. **步骤 2**: 重构 `quantize_font_size()`（0.5 天）
   - 添加 `step` 参数
   - 更新调用处

3. **步骤 3**: 提取统一字号计算方法（2 天）
   - 从 `calculate_type_font_baselines()` 提取核心算法
   - 支持可配置步长
   - 添加前端样式覆盖过滤

4. **步骤 4**: 实现 Text 和 Title 的微调（1.5 天）
   - 创建 `calculate_adjustable_font_size_for_block()` 方法
   - 复用 `calculate_font_size_for_bbox()` 计算最优字号

5. **步骤 5**: 更新 `calculate_type_font_baselines()`（1 天）
   - 调用新的统一字号计算方法
   - 分离 text 和 title 的计算

6. **步骤 6**: 前端样式覆盖支持（2 天）
   - 定义数据结构
   - 实现样式应用逻辑

**总时间**: 约 8 天

## 七、风险分析

### 7.1 低风险（可完全复用）
- 基础工具方法：风险低，已充分测试
- 布局计算工具：风险低，逻辑简单
- 文本处理工具：风险低，功能独立

### 7.2 中风险（需要修改）
- `calculate_type_font_baselines()` 重构：需要仔细测试，确保输出一致
- `quantize_font_size()` 扩展：简单修改，风险较低

### 7.3 高风险（全新功能）
- Text 和 Title 的微调：新算法，需要充分测试
- 前端样式覆盖：新功能，需要完整测试

## 八、测试策略

### 8.1 单元测试
- 测试所有可复用的方法（确保没有破坏现有功能）
- 测试新方法（BlockClassifier, 微调计算等）
- 测试修改后的方法（quantize_font_size_with_step）

### 8.2 集成测试
- 对比新旧算法的输出
- 测试前端样式覆盖功能
- 测试不同类型的分组和计算

### 8.3 回归测试
- 使用现有的测试用例
- 确保输出质量不下降
- 性能测试

