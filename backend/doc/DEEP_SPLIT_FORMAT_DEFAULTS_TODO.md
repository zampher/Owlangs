# Deep Split Format Defaults - TODO

## 概述

根据文件格式设置 `deep_split` 参数的默认值，以优化不同文档类型的翻译体验。

## 当前实现

### 默认值规则

- **PDF/Docx**: `deep_split = False`
  - 原因：这些格式使用布局提取（layout-based extraction），已经按照文档结构进行了分块。过度细分可能导致片段过小，影响翻译质量和上下文连贯性。

- **TXT/MD/HTML**: `deep_split = True`
  - 原因：这些格式是纯文本或标记文本，按段落细分有助于：
    - 更精确的校对和编辑
    - 更好的上下文控制
    - 更细粒度的翻译质量控制

- **其他格式**: `deep_split = True`（默认）
  - 原因：对于未明确测试的格式，默认启用 deep split 以提供更细粒度的控制。

## 需要调试的格式

以下格式目前使用默认值 `True`，需要根据实际使用情况调整：

1. **JSON** (`.json`)
   - 当前默认：`True`
   - 建议：根据 JSON 结构决定
     - 如果 JSON 包含长文本字段，可能需要 `True`
     - 如果 JSON 是结构化数据（如配置、数据表），可能需要 `False`

2. **XLSX** (`.xlsx`)
   - 当前默认：`True`
   - 建议：`False`（表格数据通常按行/列分块，不需要进一步细分）

3. **SRT** (`.srt`)
   - 当前默认：`True`
   - 建议：`False`（字幕文件已经按时间戳分块）

4. **EPUB** (`.epub`)
   - 当前默认：`True`
   - 建议：根据内容类型决定
     - 如果包含长文本章节，可能需要 `True`
     - 如果主要是结构化内容，可能需要 `False`

5. **MOBI** (`.mobi`)
   - 当前默认：`True`
   - 建议：类似 EPUB，根据内容类型决定

6. **QT_TS** (`.ts`)
   - 当前默认：`True`
   - 建议：`False`（Qt 翻译文件已经按条目分块）

## 实现位置

### 后端

1. **`backend/config/translation_config.py`** ⭐ **统一配置模块**
   - `TranslationConfig`: 翻译配置类，管理所有翻译相关的默认设置
   - `DeepSplitDefaults`: `deep_split` 默认值配置
   - `get_default_deep_split()`: 统一的入口函数，根据文件格式返回默认值
   - 配置文件：`configs/translation_config.json`（如果不存在，使用代码中的默认值）

2. **`backend/app/routes/app_routes_service.py`**
   - `_start_translation_task()`: 使用 `get_default_deep_split()` 设置 `task_state["deep_split"]`

3. **`backend/app/models/service.py`**
   - `BaseWorkflowParams.deep_split`: 默认值改为 `None`（使用格式默认值）
   - `ConvertFormatRequest.deep_split`: 默认值改为 `None`（使用格式默认值）

4. **`backend/app/services/format_conversion_service.py`**
   - `_create_translation_payload()`: 使用 `get_default_deep_split()` 获取默认值

### 前端

前端不需要修改，因为默认值由后端根据文件格式自动设置。

## 测试建议

对于每个需要调试的格式，建议：

1. **导入测试文件**：使用典型的该格式文件进行导入测试
2. **检查片段数量**：观察生成的片段数量是否合理
3. **检查片段大小**：确认片段大小是否适合翻译和校对
4. **翻译测试**：实际翻译并检查质量
5. **用户体验**：确认前端显示和编辑体验是否良好

## 调整方法

### 方法1：通过配置文件（推荐）⭐

编辑 `configs/translation_config.json` 文件（如果不存在，从 `configs/translation_config.json.template` 复制）：

```json
{
  "deep_split_defaults": {
    "pdf": false,
    "docx": false,
    "txt": true,
    "md": true,
    "html": true,
    "default": true,
    "markdown_based": null,
    "docx_workflow": false,
    "txt_workflow": true,
    "html_workflow": true
  }
}
```

修改后，重启后端服务即可生效。

### 方法2：修改代码默认值

如果需要修改代码中的默认值，编辑 `backend/config/translation_config.py` 中的 `DeepSplitDefaults` 类：

```python
@dataclass
class DeepSplitDefaults:
    """Default deep_split values for different file formats."""
    pdf: bool = False  # 修改这里
    docx: bool = False
    txt: bool = True
    # ... 其他格式
    default: bool = True  # 未知格式的默认值
```

### 添加新格式支持

1. **在配置文件中添加**（推荐）：
   - 编辑 `configs/translation_config.json`
   - 在 `deep_split_defaults` 中添加新格式，例如：`"xlsx": false`

2. **在代码中添加**：
   - 编辑 `backend/config/translation_config.py`
   - 在 `DeepSplitDefaults` 类中添加新字段
   - 在 `get_by_extension()` 方法中添加对应的判断逻辑

## 注意事项

1. **用户覆盖**：用户仍然可以通过前端或 API 参数显式设置 `deep_split`，这会覆盖默认值。
2. **向后兼容**：如果用户之前设置了 `deep_split`，应该保持其设置不变。
3. **日志记录**：在设置 `deep_split` 时记录日志，便于调试和追踪。

## 相关文件

- `backend/config/translation_config.py` ⭐ **统一配置模块**
- `configs/translation_config.json` ⭐ **配置文件**（可选，如果不存在则使用代码默认值）
- `configs/translation_config.json.template` ⭐ **配置文件模板**
- `backend/app/routes/app_routes_service.py`
- `backend/app/models/service.py`
- `backend/app/services/format_conversion_service.py`
- `backend/utils/markdown_splitter.py`
- `backend/layout/markdown_builder.py`

## 配置系统优势

1. **集中管理**：所有 `deep_split` 默认值在一个地方配置
2. **易于调整**：通过修改配置文件即可调整，无需修改代码
3. **向后兼容**：如果配置文件不存在，使用代码中的默认值
4. **可扩展**：轻松添加新格式的支持
5. **统一接口**：所有代码都通过 `get_default_deep_split()` 函数获取默认值

