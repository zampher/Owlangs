# Owlangs MCP 接口设计方案

## 1. 背景与目标

### 1.1 背景

Owlangs 是一个基于 FastAPI 的 AI 文档翻译平台，支持 27+ AI 平台、15+ 文档格式、术语表管理等功能。目前对外暴露的是 REST API（端口 8800），供 Flutter 前端调用。

随着 AI Agent（Claude Code、Cursor、Windsurf 等 IDE 内置 Agent）的普及，需要提供 **MCP（Model Context Protocol）接口**，使 AI Agent 能够直接调用 Owlangs 的翻译能力。

### 1.2 目标

- 为 Owlangs 提供标准的 MCP 接口，兼容 MCP 协议（stdio 和 HTTP 两种传输模式）
- AI Agent 可以通过 MCP 工具直接提交文档翻译任务
- 支持从 Quick Settings 中读取当前配置（选定平台、模型、参数等）作为上下文
- 术语表（Glossary）作为翻译的重要参数，支持查询和选择
- 不破坏现有 REST API 体系，MCP 作为独立的可选组件

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                   AI Agent (Claude Code/Cursor...)       │
│     MCP Client  ◄───────────────────►  MCP Server       │
└─────────────────────────────────────────────────────────┘
                    stdio 或 HTTP 传输
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 Owlangs MCP Server                       │
│              backend/mcp_server/                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ MCP Tools   │  │ MCP Resources│  │ MCP Prompts    │  │
│  │ (15 个工具)  │  │ (7 个资源)   │  │ (2 个模板)     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬─────────┘  │
│         │                 │                 │            │
│         └────────┬────────┘─────────────────┘            │
│                  ▼                                       │
│        ┌─────────────────────┐                           │
│        │  MCP Service Layer  │  ← Owlangs Service 复用   │
│        └─────────────────────┘                           │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Owlangs FastAPI Backend (端口 8800)          │
│  ┌───────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ Translation│  │  Glossary  │  │  Task Manager/Queue│  │
│  │ Service    │  │  Manager   │  │                    │  │
│  └───────────┘  └────────────┘  └────────────────────┘  │
│  ┌───────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ Config     │  │  Platform  │  │  Redis/Session     │  │
│  │ Loader    │  │  Service   │  │                    │  │
│  └───────────┘  └────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

1. **Service 层复用**：MCP Server 不重复实现业务逻辑，直接调用现有的 `backend/app/services/` 下的 Service 类和 `backend/glossary/` 下的 Manager
2. **无状态设计**：MCP Server 本身不维护状态，翻译任务的状态仍然由 Task Manager 管理
3. **认证委托**：MCP 工具调用时，通过参数传递认证信息（API Key、平台选择等），而非强制 Owlangs 用户登录
4. **独立进程**：MCP Server 作为独立进程运行，不侵入现有 FastAPI 进程

### 2.3 传输方式

支持两种 MCP 传输方式：

**方式一：stdio 模式（推荐 AI Agent 集成）**
```
# 通过 MCP Client 配置直接启动
{
  "mcpServers": {
    "owlangs": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"]
    }
  }
}
```

**方式二：HTTP 模式（支持多客户端共享）**
```
# 独立启动
python -m backend.mcp_server --http --port 8100

# MCP Client 配置
{
  "mcpServers": {
    "owlangs": {
      "url": "http://localhost:8100/mcp"
    }
  }
}
```

---

## 3. MCP 工具设计（Tools）

### 3.1 翻译工具

#### Tool 1: `owlangs_translate`

提交文档翻译任务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是* | 文档本地路径（与 file_content 二选一） |
| `file_content` | string | 是* | Base64 编码的文件内容（与 file_path 二选一） |
| `file_name` | string | 是 | 文件名（含扩展名，用于自动识别格式） |
| `to_lang` | string | 是 | 目标语言，如 "Chinese", "English", "Japanese" |
| `base_url` | string | 是 | LLM API 地址，如 "https://api.openai.com/v1" |
| `api_key` | string | 是 | LLM API 密钥 |
| `model_id` | string | 是 | 模型 ID，如 "gpt-4o", "deepseek-chat" |
| `glossary` | dict | 否 | 术语表字典，格式 `{"原文": "译文"}` |
| `glossary_ids` | string[] | 否 | 要使用的现有术语表 ID 列表 |
| `glossary_generate` | boolean | 否 | 是否自动生成术语表（默认 false） |
| `convert_engine` | string | 否 | 文档解析引擎：`identity`/`mineru`/`docling` |
| `chunk_size` | int | 否 | 分块大小（字符数，0=使用平台默认） |
| `concurrent` | int | 否 | 并发数（默认 3） |
| `temperature` | float | 否 | LLM 温度参数（默认 0.3） |
| `custom_prompt` | string | 否 | 自定义翻译提示词 |
| `prompt_mode` | string | 否 | 提示词模式：`off`/`simple`/`advanced` |
| `prompt_style` | string | 否 | 翻译风格：`literal`/`fluent`/`academic`/`business`/`technical` |
| `deep_split` | boolean | 否 | 是否启用精细切分 |
| `execution_mode` | string | 否 | 执行模式：`immediate`/`queued`（默认 immediate） |
| `skip_translate` | boolean | 否 | 是否仅转换不翻译（默认 false） |

返回示例：
```json
{
  "task_started": true,
  "task_id": "a1b2c3d4",
  "message": "Translation task started successfully"
}
```

#### Tool 2: `owlangs_translate_status`

查询翻译任务状态。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |

返回：
```json
{
  "task_id": "a1b2c3d4",
  "status": "processing",
  "progress": 45,
  "message": "Translating: 45/100 chunks",
  "is_processing": true,
  "download_ready": false
}
```

可能的状态值：`queued`、`extracting`、`translating`、`exporting`、`completed`、`failed`、`cancelled`

#### Tool 3: `owlangs_translate_download`

下载翻译结果。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `file_type` | string | 否 | 文件类型：`target`（译文）/ `compare`（对照）/ `source`（原文）（默认 target） |

返回：Base64 编码的文件内容 + 文件名

#### Tool 4: `owlangs_translate_cancel`

取消进行中的翻译任务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |

#### Tool 5: `owlangs_translate_batch_zip`

上传 ZIP 压缩包，自动提取其中所有支持格式的文档并逐一提交翻译任务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `zip_content` | string | 是 | Base64 编码的 ZIP 文件内容 |
| `zip_file_name` | string | 否 | ZIP 文件名（默认 "documents.zip"） |
| `to_lang` | string | 是 | 目标语言 |
| `base_url` | string | 是 | LLM API 地址 |
| `api_key` | string | 是 | LLM API 密钥 |
| `model_id` | string | 是 | 模型 ID |
| `glossary` | dict | 否 | 术语表字典 |
| `glossary_ids` | string[] | 否 | 现有术语表 ID 列表 |
| `glossary_generate` | boolean | 否 | 是否自动生成术语表 |
| `convert_engine` | string | 否 | 文档解析引擎 |
| `chunk_size` | int | 否 | 分块大小 |
| `concurrent` | int | 否 | 并发数（默认 3） |
| `temperature` | float | 否 | LLM 温度参数（默认 0.3） |
| `custom_prompt` | string | 否 | 自定义翻译提示词 |
| `prompt_mode` | string | 否 | 提示词模式 |
| `prompt_style` | string | 否 | 翻译风格 |
| `deep_split` | boolean | 否 | 是否启用精细切分 |
| `execution_mode` | string | 否 | 执行模式（默认 queued） |
| `skip_translate` | boolean | 否 | 是否仅转换不翻译 |

ZIP 内支持的文件格式：`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.txt`, `.md`, `.html`, `.json`, `.srt`, `.epub`, `.mobi`, `.ts`, `.csv` 及图片。不支持的格式会被跳过。

返回示例：
```json
{
  "success": true,
  "total": 5,
  "submitted": 4,
  "failed": 1,
  "tasks": [
    {"task_id": "a1b2c3d4", "file_name": "doc1.pdf"},
    {"task_id": "e5f6g7h8", "file_name": "doc2.docx"}
  ],
  "errors": [
    {"file": "notes.txt", "reason": "Unsupported extension"}
  ]
}
```

#### Tool 6: `owlangs_translate_batch_download`

批量下载多个翻译任务的结果文件，打包为一个 ZIP 压缩包。不支持指定格式的任务会被跳过，并在 `_manifest.json` 中记录。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_ids` | string[] | 是 | 任务 ID 列表 |
| `file_type` | string | 否 | 格式：`target` / `html` / `md` / `docx` / `pdf` / `txt` 等（默认 target） |

返回 Base64 编码的 ZIP：
```json
{
  "success": true,
  "file_content": "<base64-zip>",
  "file_name": "batch_results.zip",
  "manifest": {
    "a1b2c3d4": {"status": "success", "file": "doc1_a1b2c3d4.html"},
    "e5f6g7h8": {"status": "skipped", "reason": "Task not found"}
  }
}
```

### 3.2 平台/配置工具

#### Tool 7: `owlangs_list_platforms`

列出所有可用的 AI 翻译平台及默认配置。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lang` | string | 否 | 按语言区域过滤（zh/en/ja/ko） |

返回：平台列表（id, name, model, url, api_protocol, chunk_size, concurrent, requires_api_key）

#### Tool 8: `owlangs_get_platform`

获取指定平台的详细配置。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform_id` | string | 是 | 平台 ID（如 openai, deepseek, anthropic） |

返回：平台完整配置（含 url, model, temperature, chunk_size, concurrent 等）

#### Tool 9: `owlangs_list_supported_formats`

列出支持的文档格式。

返回：格式列表及对应的 workflow_type

#### Tool 10: `owlangs_get_system_config`

获取系统配置（Quick Settings 中的关键参数）。

返回：translation_config（deep_split 默认值、语言检测模式）、系统默认值

### 3.3 术语表工具

#### Tool 11: `owlangs_list_glossaries`

列出可用术语表。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scope` | string | 否 | 范围：`global`/`personal`/`all`（默认 all） |

返回：术语表列表（id, name, owner, is_global, item_count, description）

#### Tool 12: `owlangs_search_glossary`

搜索术语表中的词条。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索关键词 |
| `glossary_id` | string | 否 | 限定术语表（不传则搜索全部） |
| `limit` | int | 否 | 返回数量限制（默认 20） |

返回：匹配的术语条目（src, dst, category, glossary_name）

#### Tool 13: `owlangs_add_glossary_terms`

向术语表添加词条。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `glossary_id` | string | 是 | 术语表 ID |
| `terms` | dict | 是 | 术语字典，格式 `{"原文": "译文"}` |

#### Tool 14: `owlangs_generate_glossary`

从文档自动生成术语表。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是* | 文档路径（与 file_content 二选一） |
| `file_content` | string | 是* | Base64 文件内容（与 file_path 二选一） |
| `file_name` | string | 是 | 文件名 |
| `to_lang` | string | 是 | 目标语言 |
| `base_url` | string | 是 | LLM API 地址 |
| `api_key` | string | 是 | API 密钥 |
| `model_id` | string | 是 | 模型 ID |
| `detection_mode` | string | 否 | 检测模式：`uncertain`/`deep`（默认 uncertain） |
| `save_to_personal` | boolean | 否 | 是否保存到个人术语表 |

### 3.4 文档转换工具

#### Tool 15: `owlangs_convert_document`

文档格式转换（不翻译，仅解析转换格式）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是* | 文档路径（与 file_content 二选一） |
| `file_content` | string | 是* | Base64 文件内容（与 file_path 二选一） |
| `file_name` | string | 是 | 文件名 |
| `convert_engine` | string | 否 | 解析引擎 |
| `formula_ocr` | boolean | 否 | 是否启用公式 OCR |
| `table_ocr` | boolean | 否 | 是否启用表格 OCR |

---

## 4. MCP 资源设计（Resources）

MCP Resources 提供只读的数据访问能力，通过 URI 模式暴露：

| Resource URI | 说明 | 返回格式 |
|-------------|------|---------|
| `owlangs://platforms` | 平台列表和配置 | JSON |
| `owlangs://platforms/{id}` | 特定平台详情 | JSON |
| `owlangs://glossaries` | 术语表概览列表 | JSON |
| `owlangs://glossaries/{id}` | 特定术语表所有词条 | JSON（src/dst 数组） |
| `owlangs://formats` | 支持的文档格式 | JSON |
| `owlangs://task/{task_id}/status` | 任务状态 | JSON |
| `owlangs://task/{task_id}/logs` | 任务日志 | JSON |

---

## 5. MCP 提示词模板（Prompts）

MCP Prompts 提供可复用的提示词模板，帮助 AI Agent 理解如何使用这些工具：

### Prompt 1: `translate_document`

用于文档翻译的完整工作流提示。引导 AI Agent 完成：分析文档 → 选择平台 → 选择术语表 → 提交翻译 → 监控进度 → 下载结果。

### Prompt 2: `manage_glossary`

术语表管理提示。引导 AI Agent 完成：查看现有术语表 → 搜索术语 → 添加/更新术语 → 从文档生成术语表。

---

## 6. 关键数据流

### 6.1 翻译流程

```
AI Agent 用户
    │
    ▼
1. owlangs_list_platforms       ← 了解可用平台和模型
    │
    ▼
2. owlangs_list_glossaries      ← 查看可选术语表
    │
    ▼ (可选)
3. owlangs_search_glossary      ← 搜索特定术语确认
    │
    ▼
4. owlangs_translate            ← 提交翻译任务
   ├─ file_path / file_content
   ├─ base_url / api_key / model_id
   ├─ to_lang
   └─ glossary / glossary_ids (可选)
    │
    ▼
5. owlangs_translate_status     ← 轮询进度
    │ (循环直到 completed / failed)
    ▼
6. owlangs_translate_download   ← 下载结果
```

### 6.2 批量翻译流程

```
AI Agent 用户
    │
    ▼
1. owlangs_translate_batch_zip   ← 上传 ZIP 压缩包
   ├─ zip_content (base64 编码的 ZIP)
   ├─ to_lang / base_url / api_key / model_id
   └─ glossary / glossary_ids (可选)
    │
    ▼
2. owlangs_translate_status     ← 轮询每个 task_id 的进度
    │ (循环直到全部完成)
    ▼
3. owlangs_translate_batch_download ← 批量下载同一格式结果
   ├─ task_ids: [全部任务 ID]
   └─ file_type: "html" (统一格式)
    │
    ▼
   返回 ZIP 压缩包（含 _manifest.json）
```

### 6.3 AI Agent 使用术语表的两种方式

**方式一：直接传入术语字典**
```
glossary = {
    "Machine Learning": "机器学习",
    "Deep Learning": "深度学习",
    "Natural Language Processing": "自然语言处理"
}
```

**方式二：引用现有术语表**
```
glossary_ids = ["glossary-uuid-1", "glossary-uuid-2"]
```

两种方式可以同时使用，在翻译时合并。

---

## 7. 与沉浸式翻译（Immersive Translate）的类比

沉浸式翻译（immersive-translate）的 MCP 接口设计思路是：

1. **读取配置**：AI Agent 先读取当前翻译配置（目标语言、服务商、模型等）
2. **传入原文**：AI Agent 将选中的原文文本传给翻译工具
3. **输出译文**：翻译工具返回译文，AI Agent 将译文替换原文

Owlangs 与之对标的差异化能力：

| 能力 | 沉浸式翻译 | Owlangs MCP |
|------|-----------|-------------|
| 翻译范围 | 网页/选中文本 | **完整文档（PDF/DOCX/PPTX/EPUB...）** |
| 格式保留 | 纯文本替换 | **保留原文排版、样式、布局** |
| 术语表 | 通过 glossary 参数传入 | **支持术语表管理（查询/选择/自动生成）** |
| 平台支持 | 单 LLM | **27+ 平台，灵活选择** |
| 文档解析 | 无 | **MinerU/Docling 专业解析引擎** |
| 并发翻译 | 单段 | **智能分块 + 并发翻译** |

因此 Owlangs 的 MCP 接口更适合 **文档级翻译场景**，AI Agent 将完整的文档路径或内容传递给 Owlangs，由 Owlangs 完成解析、翻译、排版的全流程。

---

## 8. 配置集成示例

### 8.1 Claude Code 配置

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "owlangs": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "env": {
        "OWLANGS_ROOT": "D:/workspace/localrepo/Owlangs_test/Owlangs"
      }
    }
  }
}
```

### 8.2 Cursor 配置

在 `~/.cursor/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "owlangs": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "env": {
        "OWLANGS_ROOT": "D:/workspace/localrepo/Owlangs_test/Owlangs"
      }
    }
  }
}
```

### 8.3 HTTP 模式（多客户端共享）

```bash
# 在 Owlangs 项目根目录启动 MCP HTTP 服务
python -m backend.mcp_server --http --port 8100

# 客户端配置
{
  "mcpServers": {
    "owlangs": {
      "url": "http://localhost:8100/mcp"
    }
  }
}
```

---

## 9. 项目结构与实现计划

### 9.1 新增文件结构

```
Owlangs/
├── backend/
│   └── mcp_server/                 # MCP 服务器包
│       ├── __init__.py             # 包定义
│       ├── __main__.py             # CLI 入口（python -m backend.mcp_server）
│       ├── server.py               # MCP 服务器主类（FastMCP 初始化、生命周期）
│       ├── tools/                  # MCP 工具实现
│       │   ├── __init__.py
│       │   ├── translate_tools.py  # 翻译相关工具
│       │   ├── config_tools.py     # 配置/平台工具
│       │   ├── glossary_tools.py   # 术语表工具
│       │   └── convert_tools.py    # 文档转换工具
│       ├── resources/              # MCP 资源实现
│       │   ├── __init__.py
│       │   └── providers.py        # 资源提供者
│       ├── prompts/                # MCP 提示词模板
│       │   ├── __init__.py
│       │   └── templates.py        # 提示词模板定义
│       └── service_layer.py        # Service 层适配（调用现有 Service）
```

### 9.2 依赖项

在 `pyproject.toml` 中添加：

```toml
mcp>=1.0.0    # MCP Python SDK
```

MCP Python SDK 提供了 `FastMCP`、`Tool`、`Resource`、`Prompt` 等装饰器和基类，可以快速构建 MCP 服务器。

### 9.3 实现要点

1. **路径解析**：MCP Server 需要知道 Owlangs 项目根目录，通过环境变量 `OWLANGS_ROOT` 获取或自动推断
2. **配置加载**：复用 `backend/config/config_loader.py` 中的 `get_unified_config()` 加载系统配置
3. **翻译任务**：直接调用 `backend/app/services/translation/` 中的 `TranslationService`
4. **术语表**：直接调用 `backend/glossary/manager.py` 中的 `GlossaryManager`
5. **任务管理**：直接引入 `backend/app/services/task.py` 中的 `task_manager`
6. **文件处理**：MCP 接收文件时，保存到临时目录后调用 Owlangs 的处理流程

### 9.4 实施阶段

| 阶段 | 内容 | 涉及文件 |
|------|------|---------|
| **Phase 1** | 项目骨架、MCP Server 初始化、依赖配置 | `__init__.py`, `__main__.py`, `server.py`, pyproject.toml |
| **Phase 2** | 基础工具：列出平台、列出格式、获取配置 | `config_tools.py`, `service_layer.py` |
| **Phase 3** | 翻译工具：提交翻译、查询状态、下载结果、取消 | `translate_tools.py`, `service_layer.py` |
| **Phase 3b** | 批量工具：ZIP 上传批量翻译、批量下载结果 | `translate_tools.py`, `service_layer.py` |
| **Phase 4** | 术语表工具：列出、搜索、添加、生成 | `glossary_tools.py`, `service_layer.py` |
| **Phase 5** | 文档转换工具 | `convert_tools.py`, `service_layer.py` |
| **Phase 6** | Resources 和 Prompts 实现 | `resources/providers.py`, `prompts/templates.py` |
| **Phase 7** | 测试与集成文档完善 | 测试用例、README |

---

## 10. 安全与注意事项

1. **API 密钥安全**：MCP 工具接收 `api_key` 参数，但传输过程中请确保 MCP 连接使用安全通道（stdio 模式在本地进程间通信是安全的，HTTP 模式建议绑定 localhost 或使用 TLS）
2. **文件权限**：MCP 处理文件时应确保在安全临时目录中操作，处理完毕后清理
3. **任务隔离**：不同的 MCP 客户端提交的任务在 Task Manager 中独立管理
4. **资源限制**：建议对并发任务数做出限制，防止资源耗尽
