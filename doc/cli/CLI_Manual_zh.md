# Owlangs CLI 使用说明

Owlangs CLI 是 Owlangs 翻译平台的命令行工具，支持单文件翻译、批量翻译、文档格式转换、任务管理等操作。

## 运行方式

根据你的安装方式，选择以下任一命令：

| 安装方式 | 命令 |
|---------|------|
| 源码运行 | `python backend/cli.py <子命令>` 或 `python backend/owlangs_cli.py <子命令>` |
| pip 安装 | `owlangs <子命令>` |
| 打包版 exe | `Owlangs.exe <子命令>` |

示例：

```bash
# 源码
python backend/cli.py translate report.pdf --to Chinese

# pip 安装
owlangs translate report.pdf --to Chinese

# 打包版 exe
Owlangs.exe translate report.pdf --to Chinese
```

## 全局选项

以下选项可在任意子命令前或后使用：

| 选项 | 说明 |
|------|------|
| `--json` | 以 JSON 格式输出（机器可读），放在子命令**前或后**均可 |
| `-v`, `--verbose` | 输出详细日志 |
| `--version` | 显示版本号 |

示例：

```bash
# JSON 输出
Owlangs.exe --json translate file.pdf --to Chinese
Owlangs.exe platform list --json

# 详细日志
Owlangs.exe translate file.pdf --to Chinese -v
```

## 命令列表

| 命令 | 功能 |
|------|------|
| `translate` | 翻译单个文件 |
| `convert` | 转换文档格式（不翻译） |
| `batch` | 批量翻译 ZIP 中的文件 |
| `status` | 查询任务状态 |
| `download` | 下载任务结果 |
| `cancel` | 取消运行中的任务 |
| `platform list` | 列出可用的 LLM 平台 |
| `formats` | 列出支持的文件格式 |
| `glossary list` | 列出术语表 |
| `glossary search` | 搜索术语表条目 |
| `config init` | 创建默认配置文件 |
| `config show` | 查看配置文件路径 |

---

## translate —— 翻译单个文件

```bash
Owlangs.exe translate <文件路径> --to <目标语言> [选项]
```

### 必填参数

| 参数 | 说明 |
|------|------|
| `file` | 文件路径，支持 PDF / DOCX / MD / HTML / TXT / XLSX / PPTX / SRT / EPUB / MOBI / 图片 等。使用 `-` 从标准输入读取 |

### 常用选项

| 选项 | 说明 |
|------|------|
| `--to <语言>` | 目标语言（如 Chinese、Japanese、English）。默认从配置文件读取 |
| `-o, --output <目录>` | 输出目录（默认：`<文件名>_translated/`） |
| `--formats <格式列表>` | 下载格式，可指定多个（如 `target docx md html`）。默认从配置文件读取 |
| `--no-wait` | 只提交任务不等待完成 |
| `--platform <平台ID>` | 指定 LLM 平台（如 `openai`、`deepseek`）。默认从配置文件读取 |
| `--glossary <术语表ID列表>` | 指定术语表（可指定多个，如 `g1 g2`） |

### 高级选项

| 选项 | 说明 |
|------|------|
| `--temperature <数值>` | LLM 温度参数（0~1），默认 0.3 |
| `--chunk-size <数值>` | 分块大小（tokens），0 = 自动 |
| `--concurrent <数值>` | 并发处理数，默认 3 |
| `--prompt-mode <模式>` | 提示词模式（如 standard、academic） |
| `--prompt-style <风格>` | 提示词风格（如 concise、detailed） |
| `--file-name <文件名>` | 从 stdin 读取时指定原始文件名 |

### 示例

```bash
# 基本翻译
Owlangs.exe translate report.pdf --to Chinese

# 指定输出格式和目录
Owlangs.exe translate report.docx --to Japanese -o ./output --formats target docx md

# 提交后不等待（后台运行）
Owlangs.exe translate big-file.pdf --to English --no-wait

# 指定平台和术语表
Owlangs.exe translate contract.docx --to Chinese --platform deepseek --glossary legal

# 从标准输入读取
cat document.md | Owlangs.exe translate - --to Chinese --file-name document.md

# JSON 输出
Owlangs.exe --json translate file.pdf --to Chinese
```

---

## convert —— 转换文档格式

```bash
Owlangs.exe convert <文件路径> [选项]
```

| 选项 | 说明 |
|------|------|
| `-o, --output <目录>` | 输出目录（默认：`<文件名>_converted/`） |
| `--engine <引擎>` | 转换引擎（如 `docling`） |
| `--no-wait` | 只提交任务不等待完成 |

### 示例

```bash
Owlangs.exe convert invoice.xlsx
Owlangs.exe convert report.pdf --engine docling
Owlangs.exe convert document.docx -o ./output/
```

---

## batch —— 批量翻译

```bash
Owlangs.exe batch <ZIP文件> --to <目标语言> [选项]
```

将多个文件打包为 ZIP，批量提交翻译。

| 选项 | 说明 |
|------|------|
| `--to <语言>` | 目标语言。默认从配置文件读取 |
| `-o, --output <目录>` | 输出目录（默认：`<ZIP名>_results/`） |
| `--no-wait` | 只提交任务不等待完成 |

### 示例

```bash
Owlangs.exe batch docs.zip --to Chinese
Owlangs.exe batch articles.zip --to Japanese --no-wait --json
```

---

## status —— 查询任务状态

```bash
Owlangs.exe status <任务ID>
```

### 示例

```bash
Owlangs.exe status abc-123
Owlangs.exe --json status abc-123
```

---

## download —— 下载任务结果

```bash
Owlangs.exe download <任务ID> --type <格式> --output <路径>
```

| 选项 | 说明 |
|------|------|
| `--type <格式>` | 文件类型：`target`、`docx`、`md`、`html`、`pdf`、`txt` |
| `-o, --output <路径>` | 输出文件或目录路径 |

### 示例

```bash
# 下载到指定文件
Owlangs.exe download abc-123 --type docx -o result.docx

# 下载到目录（自动生成文件名）
Owlangs.exe download abc-123 --type md -o ./output/
```

---

## cancel —— 取消任务

```bash
Owlangs.exe cancel <任务ID>
```

### 示例

```bash
Owlangs.exe cancel abc-123
```

---

## platform list —— 列出 LLM 平台

```bash
Owlangs.exe platform list [选项]
```

### 示例

```bash
Owlangs.exe platform list
Owlangs.exe --json platform list
```

---

## formats —— 列出支持的文件格式

```bash
Owlangs.exe formats [选项]
```

### 示例

```bash
Owlangs.exe formats
Owlangs.exe --json formats
```

---

## glossary —— 术语表管理

### 列出术语表

```bash
Owlangs.exe glossary list [选项]
```

| 选项 | 说明 |
|------|------|
| `--scope <范围>` | 范围：`all`（全部）或 `global`（全局），默认 `all` |

### 搜索术语

```bash
Owlangs.exe glossary search <查询词> [选项]
```

| 选项 | 说明 |
|------|------|
| `--glossary <术语表ID>` | 在指定术语表中搜索 |
| `--limit <数量>` | 最大返回条数，默认 20 |

### 示例

```bash
Owlangs.exe glossary list
Owlangs.exe --json glossary list --scope global
Owlangs.exe glossary search hello --glossary g1 --limit 10
```

---

## config —— 配置管理

### 初始化配置文件

```bash
Owlangs.exe config init [选项]
```

| 选项 | 说明 |
|------|------|
| `--force` | 覆盖已有的配置文件 |

### 查看配置路径

```bash
Owlangs.exe config show [选项]
```

### 示例

```bash
Owlangs.exe config init
Owlangs.exe config init --force
Owlangs.exe --json config show
```

### 配置文件格式

配置文件为 TOML 格式，位于：

| 系统 | 路径 |
|------|------|
| Windows | `%LOCALAPPDATA%\Owlangs\config.toml` |
| macOS | `~/Library/Application Support/Owlangs/config.toml` |
| Linux | `~/.config/Owlangs/config.toml` |

```toml
# Owlangs CLI 配置文件

[translate]
default_lang = "Chinese"
# default_platform = "deepseek"
# default_formats = ["target", "docx", "md"]

[translate.advanced]
# temperature = 0.3
# chunk_size = 8000
# concurrent = 3
# prompt_mode = "standard"
# prompt_style = "detailed"

[glossary]
# default_glossaries = ["medical", "legal"]
```

无需手动编辑——执行 `config init` 即生成默认配置文件，取消注释即可启用对应项。

---

## 退出码

| 退出码 | 含义 |
|-------|------|
| 0 | 成功 |
| 1 | 参数错误（文件不存在、参数无效等） |
| 2 | 任务失败（翻译失败、部分失败等） |
| 3 | 轮询超时（超过 60 分钟） |
| 4 | 内部错误 |

配合 `--json` 可在脚本中可靠判断执行结果：

```bash
Owlangs.exe --json translate file.pdf --to Chinese
if [ $? -eq 0 ]; then
    echo "翻译成功"
else
    echo "翻译失败"
fi
```

## 典型工作流

### 单文件翻译

```bash
# 1. 翻译
Owlangs.exe translate report.pdf --to Japanese

# 2. 产物默认输出到 report_translated/ 目录
ls report_translated/
```

### 提交 + 后台轮询

```bash
# 1. 提交任务，获取任务 ID
TASK_ID=$(Owlangs.exe --json translate big.docx --to Chinese --no-wait | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# 2. 自行轮询
sleep 30
Owlangs.exe status $TASK_ID

# 3. 下载结果
Owlangs.exe download $TASK_ID --type docx -o result.docx
```

### 批量翻译

```bash
# 1. 将所有待翻译文件打包
zip docs.zip report.pdf contract.docx manual.md

# 2. 批量提交翻译
Owlangs.exe batch docs.zip --to Chinese

# 3. 结果输出到 docs_results/batch_results.zip
```
