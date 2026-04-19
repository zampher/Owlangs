# 翻译配置使用说明

## 概述

翻译配置系统 (`backend/config/translation_config.py`) 提供了集中管理翻译相关默认设置的机制，特别是 `deep_split` 参数的格式默认值。

## 快速开始

### 使用统一配置函数

所有需要获取 `deep_split` 默认值的代码都应该使用统一的配置函数：

```python
from config.translation_config import get_default_deep_split

# 根据文件名和 workflow_type 获取默认值
default_value = get_default_deep_split("document.pdf", "markdown_based")
# 返回: False (PDF 文件默认使用 False)

default_value = get_default_deep_split("document.txt", "txt")
# 返回: True (TXT 文件默认使用 True)
```

### 配置文件位置

配置文件存储在 `configs/translation_config.json`，如果不存在，系统会使用代码中的默认值。

配置文件路径优先级：
1. `{OWLANGS_CONFIG_PATH}/configs/translation_config.json` (如果设置了环境变量)
2. `{项目根目录}/configs/translation_config.json` (开发环境)
3. `C:\ProgramData\Owlangs\configs\translation_config.json` (Windows 部署环境)
4. 其他系统配置目录

### 配置文件格式

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

### 配置说明

- **`pdf`, `docx`, `txt`, `md`, `html`**: 文件扩展名对应的默认值
- **`default`**: 未知格式的默认值
- **`markdown_based`**: `markdown_based` workflow 的默认值（`null` 表示使用文件扩展名）
- **`docx_workflow`, `txt_workflow`, `html_workflow`**: 特定 workflow 的默认值（当文件扩展名无法确定时使用）

## 修改配置

### 方法1：编辑配置文件（推荐）

1. 编辑 `configs/translation_config.json`
2. 修改相应的值
3. 重启后端服务

### 方法2：修改代码默认值

编辑 `backend/config/translation_config.py` 中的 `DeepSplitDefaults` 类：

```python
@dataclass
class DeepSplitDefaults:
    pdf: bool = False  # 修改这里
    docx: bool = False
    # ...
```

## 添加新格式支持

### 在配置文件中添加

编辑 `configs/translation_config.json`：

```json
{
  "deep_split_defaults": {
    "pdf": false,
    "docx": false,
    "xlsx": false,  // 新增格式
    "srt": false,   // 新增格式
    // ...
  }
}
```

### 在代码中添加

1. 编辑 `backend/config/translation_config.py`
2. 在 `DeepSplitDefaults` 类中添加新字段
3. 在 `get_by_extension()` 方法中添加判断逻辑

## 代码示例

### 在路由中使用

```python
from config.translation_config import get_default_deep_split

# 在 _start_translation_task 中
default_deep_split = get_default_deep_split(original_filename, getattr(payload, 'workflow_type', None))
task_state["deep_split"] = default_deep_split
```

### 在服务中使用

```python
from config.translation_config import get_default_deep_split

# 在 format_conversion_service 中
default_deep_split = get_default_deep_split(request.file_name, workflow_type)
params = {
    'deep_split': getattr(request, 'deep_split', default_deep_split),
    # ...
}
```

## 优势

1. **集中管理**：所有默认值在一个地方配置
2. **易于调整**：通过配置文件即可调整，无需修改代码
3. **向后兼容**：如果配置文件不存在，使用代码默认值
4. **统一接口**：所有代码使用同一个函数获取默认值
5. **可扩展**：轻松添加新格式支持

## 相关文件

- `backend/config/translation_config.py` - 配置模块
- `configs/translation_config.json` - 配置文件（可选）
- `configs/translation_config.json.template` - 配置文件模板
- `backend/doc/DEEP_SPLIT_FORMAT_DEFAULTS_TODO.md` - 详细说明文档

