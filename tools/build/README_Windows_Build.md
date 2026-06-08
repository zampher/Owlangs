# Windows 安装包构建指南

本项目提供了多种 Windows 安装包构建方案，从简单的可执行文件到专业的安装器。

**环境准备**：首次构建或遇到 Python/Flutter/.NET 相关错误时，请先阅读 [tools/setup/ENV_SETUP.md](../setup/ENV_SETUP.md)（虚拟环境创建、依赖安装、Flutter/.NET 等编译所需步骤）。

## 打包参数一览与示例

### build_win.ps1 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `param1` | 字符串 | `""` |  positional：`--lite` 只打轻量版，`--full` 只打全量版，`--clean` 仅清理构建产物 |
| `-Frontend` | 枚举 | `chrome` | 前端类型：`chrome`（仅 Web）、`windows`（仅桌面前端）、`both`（两者） |
| `-IncludeAnonymize` | 开关 | 未设 | 轻量版时：加上则打包 presidio/spacy 及 spaCy 模型，否则不打包匿名化 |
| `-IncludePandoc` | 开关 | 未设 | 将 Pandoc 可执行文件与 pdflatex（XeLaTeX）一并打包，便于 PDF 流程导出 DOCX/PDF；不传则不打包，包更小 |

### build_win_installer.ps1 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `-Lite` | 开关 | - | 只构建轻量版安装器/简单包 |
| `-Full` | 开关 | - | 只构建全量版安装器/简单包 |
| `-NoSpacy` | 开关 | 未设 | 打 lite 时不打包 spaCy 模型（体积更小） |
| `-IncludeAnonymize` | 开关 | 未设 | 打 lite 时包含 presidio/spacy 及 spaCy 模型 |
| `-IncludePandoc` | 开关 | 未设 | 打包 Pandoc + pdflatex：走 Inno 时打入安装器，回退到简单打包时传参给 build_win.ps1 |
| `-Frontend` | 枚举 | `chrome` | 同 build_win.ps1（回退到简单打包时生效） |
| `-InnoSetupPath` | 字符串 | `""` | 指定 Inno Setup 的 ISCC.exe 路径 |

### 环境变量（可选）

| 变量 | 说明 |
|------|------|
| `OWLANGS_SKIP_SPACY=1` | 全量版或简单包：不复制 spaCy 模型到包内（体积更小） |
| `OWLANGS_INCLUDE_ANONYMIZE=1` | 由脚本在打 lite 且 `-IncludeAnonymize` 时自动设置，供 lite.spec 使用 |

### 打包参数组合示例（较全）

```powershell
# ---------- 简单打包 build_win.ps1 ----------

# 默认：轻量 + 全量，Chrome 前端，轻量版不含匿名化
.\tools\build\build_win.ps1

# 仅轻量版，Chrome 前端，不含匿名化（体积最小）
.\tools\build\build_win.ps1 --lite
.\tools\build\build_win.ps1 --lite -Frontend chrome

# 仅轻量版，含匿名化（presidio/spacy + spaCy 模型）
.\tools\build\build_win.ps1 --lite -IncludeAnonymize
.\tools\build\build_win.ps1 --lite -Frontend chrome -IncludeAnonymize

# 仅轻量版，仅 Windows 桌面前端（无 Web 包）
.\tools\build\build_win.ps1 --lite -Frontend windows
.\tools\build\build_win.ps1 --lite -Frontend windows -IncludeAnonymize

# 仅轻量版，Chrome + Windows 双前端
.\tools\build\build_win.ps1 --lite -Frontend both
.\tools\build\build_win.ps1 --lite -Frontend both -IncludeAnonymize

# 仅全量版（含匿名化与模型，除非设 OWLANGS_SKIP_SPACY）
.\tools\build\build_win.ps1 --full
.\tools\build\build_win.ps1 --full -Frontend both
$env:OWLANGS_SKIP_SPACY = "1"; .\tools\build\build_win.ps1 --full

# 打包时包含 Pandoc + pdflatex（需事先将 pandoc-* 与 pdflatex 放入 3rdParty\windows\）
.\tools\build\build_win.ps1 --lite -IncludePandoc
.\tools\build\build_win.ps1 --full -IncludePandoc

# 仅清理构建产物
.\tools\build\build_win.ps1 --clean

# ---------- 专业安装器 build_win_installer.ps1 ----------

# 默认：轻量 + 全量安装器
.\tools\build_win_installer.ps1

# 仅轻量版安装器，不含匿名化
.\tools\build_win_installer.ps1 -Lite

# 仅轻量版安装器，含匿名化
.\tools\build_win_installer.ps1 -Lite -IncludeAnonymize

# 仅轻量版安装器，不打包 spaCy 模型
.\tools\build_win_installer.ps1 -Lite -NoSpacy

# 仅全量版安装器
.\tools\build_win_installer.ps1 -Full

# 安装器包含 Pandoc + pdflatex（需事先将 pandoc-* 与 pdflatex 放入 3rdParty\windows\）
.\tools\build_win_installer.ps1 -Lite -IncludePandoc
.\tools\build_win_installer.ps1 -Full -IncludePandoc

# 指定 Inno Setup 路径（无 Inno 时会回退到简单打包并传参）
.\tools\build_win_installer.ps1 -Lite -IncludeAnonymize -Frontend both -InnoSetupPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

### 按版本快速打包（Basic / Pro / Enterprise）

与产品版本文档（`docs/PRODUCT_LICENSING_AND_EDITIONS.md`）对应，提供三条一键打包脚本，无需记忆参数组合。**每条脚本在打包结束后会自动校验产物（目录或安装器）是否存在，校验失败则退出码非 0。**

| 脚本 | 版本 | 含义 | 简单包 | 安装器 |
|------|------|------|--------|--------|
| `build_win_basic.ps1` | Basic | 仅 Windows 桌面前端，基础格式，体积最小 | `.\tools\build\build_win_basic.ps1` | `.\tools\build\build_win_basic.ps1 -Installer` |
| `build_win_pro.ps1` | Pro | 仅桌面前端，含 Pandoc+pdflatex（PDF 流程导出 DOCX） | `.\tools\build\build_win_pro.ps1` | `.\tools\build\build_win_pro.ps1 -Installer` |
| `build_win_enterprise.ps1` | Enterprise | 桌面前端 + Web，全量包，含 Pandoc+pdflatex | `.\tools\build\build_win_enterprise.ps1` | `.\tools\build\build_win_enterprise.ps1 -Installer` |
| `build_win_all.ps1` | 三版一体 | 按顺序执行 Basic → Pro → Enterprise，每步均校验 | `.\tools\build_win_all.ps1` | `.\tools\build_win_all.ps1 -Installer` |

- **Basic**：`--lite` + `-Frontend windows`，不打包匿名化与 Pandoc。
- **Pro**：`--lite` + `-Frontend windows` + `-IncludePandoc`（需事先准备 `3rdParty\windows\pandoc-*` 与 `pdflatex`）。
- **Enterprise**：`--full` + `-Frontend both` + `-IncludePandoc`。
- **build_win_all.ps1**：一行命令打完三个版本。简单包时最终得到 `build\win\Owlangs-<ver>`（Pro）与 `build\win\Owlangs-full-<ver>`（Enterprise）。带 `-Installer` 时三个版本分别生成不同安装包：`Owlangs-Basic-<ver>-x64.exe`、`Owlangs-Pro-<ver>-x64.exe`、`Owlangs-Enterprise-<ver>-x64.exe`，不会互相覆盖。

---

## 构建方案

### 1. 简单打包（推荐快速测试）

生成包含配置文件的文件夹，可直接运行：

```powershell
# 构建轻量版和全量版（默认仅 Chrome/Web 前端）
.\tools\build\build_win.ps1

# 只构建轻量版（推荐用 -Lite 单横线，避免 PowerShell 解析问题）
.\tools\build\build_win.ps1 --lite

# 轻量版并包含匿名化（presidio/spacy 及 spaCy 模型，体积更大）
.\tools\build\build_win.ps1 --lite -IncludeAnonymize

# 只构建全量版
.\tools\build\build_win.ps1 --full

# 全量版不打包 spaCy 模型（包更小）
$env:OWLANGS_SKIP_SPACY = "1"; .\tools\build\build_win.ps1 --full
```

**可选匿名化**（`-IncludeAnonymize`，仅影响轻量版）：
- **不传**（默认）：轻量版不打包 presidio/spacy 及 spaCy 模型，体积更小；应用内匿名化功能不可用。
- **传 `-IncludeAnonymize`**：轻量版打包 presidio/spacy 并复制 spaCy 模型，匿名化可用，体积更大。

**可选前端**（`-Frontend`，默认 `chrome`）：

| 取值 | 说明 |
|------|------|
| `chrome` | 仅 Chrome/Web 前端（后端提供 Web UI，用户用浏览器访问 localhost:8800） |
| `windows` | 仅 Windows 桌面前端（打包 Flutter Windows + Launcher，无 Web 包） |
| `both` | Windows + Chrome（同时打包桌面前端与 Web，Launcher 启动桌面，也可用浏览器访问） |

```powershell
# 仅 Chrome/Web 前端（默认，包最小）
.\tools\build\build_win.ps1 -Frontend chrome
.\tools\build\build_win.ps1 -Lite -Frontend chrome

# 仅 Windows 桌面前端（含 Launcher）
.\tools\build\build_win.ps1 -Frontend windows

# Windows + Chrome（两种前端都包含）
.\tools\build\build_win.ps1 -Frontend both
```

**输出位置**: 轻量版 `build\win\Owlangs-<version>\`，全量版 `build\win\Owlangs-full-<version>\`

**包含内容**（随 `-Frontend`、`-IncludeAnonymize`、`-IncludePandoc` 变化）:
- 可执行文件 (`bin\` 目录)、配置文件模板 (`config\` 目录)
- **轻量版**：默认不含匿名化（presidio/spacy）与 spaCy 模型；加 `-IncludeAnonymize` 则包含 presidio/spacy 并复制 spaCy 模型
- **全量版**：可含匿名化与模型；可用 `OWLANGS_SKIP_SPACY=1` 跳过复制 spaCy 模型。Redis 始终包含
- **Pandoc/pdflatex**：不加 `-IncludePandoc` 时不打包，安装包更小；加 `-IncludePandoc` 时从 `3rdParty\windows\pandoc-*` 与 `3rdParty\windows\pdflatex` 复制到包内 `3rdParty\windows\`，便于 PDF 流程导出 DOCX/PDF（需事先放置 Pandoc 与 TinyTeX/pdflatex，见下方「Pandoc 与 pdflatex 打包」）
- **chrome**：启动脚本 `owlangs.bat`（启动后端，提示用浏览器打开 localhost:8800）
- **windows** / **both**：Flutter Windows 前端 (`frontend\`)、Launcher、`owlangs.bat`（启动 Launcher）
- 安装/卸载脚本 (`install.bat`, `uninstall.bat`)、说明文档 (`README.txt`)

**Pandoc 与 pdflatex 打包**（`-IncludePandoc`）:
- 用于在安装包内自带 Pandoc 与 XeLaTeX，使 PDF 流程导出 DOCX/PDF 时无需用户另行安装。不传 `-IncludePandoc` 则不打包，体积更小。
- **前置**：构建前需在仓库中准备好：
  - **Pandoc**：将 [Pandoc Windows 版](https://github.com/jgm/pandoc/releases) 解压到 `3rdParty\windows\pandoc-<版本>\`（目录内需包含 `pandoc.exe`）。
  - **pdflatex（XeLaTeX）**：使用 `3rdParty\windows\install_pdflatex.ps1` 安装 TinyTeX 到 `3rdParty\windows\pdflatex\`，或自行将 TinyTeX/TeX Live 的 `bin\windows\xelatex.exe` 等放入该目录。
- 打包后安装目录中为 `3rdParty\windows\pandoc-*` 与 `3rdParty\windows\pdflatex`，后端会自动检测并用于 DOCX/PDF 导出。

### 2. 专业安装器（推荐发布）

生成 Windows 安装包 (.exe)，支持安装向导、快捷方式、卸载程序：

```powershell
# 构建安装器（需要先安装 Inno Setup）
.\tools\build_win_installer.ps1

# 只构建轻量版安装器
.\tools\build_win_installer.ps1 -Lite

# 只构建轻量版且不打包 spaCy 模型（包更小，运行时再下载模型）
.\tools\build_win_installer.ps1 -Lite -NoSpacy

# 只构建全量版安装器
.\tools\build_win_installer.ps1 -Full

# 可选前端（与 build_win.ps1 一致；仅在回退到简单打包时生效）
.\tools\build_win_installer.ps1 -Lite -Frontend chrome
.\tools\build_win_installer.ps1 -Lite -Frontend both
```

**前置要求**: 安装 [Inno Setup](https://jrsoftware.org/isinfo.php)

**-IncludeAnonymize**：打 lite 时加 `-IncludeAnonymize` 会打包 presidio/spacy 及 spaCy 模型，匿名化可用，体积更大；不加则 lite 不含匿名化。

**-NoSpacy**：打 lite 时加 `-NoSpacy` 可不把 spaCy 模型打进包，体积更小；首次运行需通过应用内或 `download_models` 下载模型。

**输出位置与命名**：`build\installer\` 下按版本区分，格式为 **Owlangs-{Edition}-{Version}-x64.exe**（如 `Owlangs-Standard-1.0.0.0-x64.exe`、`Owlangs-Pro-1.0.0.0-x64.exe`、`Owlangs-Enterprise-1.0.0.0-x64.exe`）。Edition 由各打包脚本传入（Standard/Pro/Enterprise），Version 取自 `backend/__init__.py`。

### 3. Flutter Chrome / Web 单独构建

仅编译前端 Web（供 Chrome 等浏览器使用），不打包后端；适合前端调试或仅更新静态资源：

```powershell
# 构建并复制到 backend/static/flutter-web
.\tools\build\build_flutter_chrome.ps1

# 仅构建，不复制到 backend
.\tools\build\build_flutter_chrome.ps1 -NoCopy

# 构建后在本机用 Chrome 打开（会启动临时 HTTP 服务）
.\tools\build\build_flutter_chrome.ps1 -OpenChrome

# 跳过 flutter clean，加快二次构建
.\tools\build\build_flutter_chrome.ps1 -NoClean
```

**输出**: `frontend\build\web\`；若未加 `-NoCopy`，会同步到 `backend\static\flutter-web\`。

### 4. Flutter Windows 桌面前端

前端已通过条件导入与 stub（`dart:html` / `dart:ui_web` 在非 Web 平台使用 stub）支持 Windows 桌面构建；CMake 已使用 `VERSION 3.14...3.30` 消除弃用告警。

- **本地运行**（调试）：在项目根目录执行 `flutter run -d windows`（需先启动后端，或由 Launcher 启动）。
- **打包含桌面前端的安装包**：使用 `.\tools\build\build_win_desktop.ps1`（会构建 Flutter Windows 并打包进 Launcher 安装包）。

日常使用以 Chrome 访问后端提供的 Web UI 即可；需要原生窗口时可使用上述桌面前端。

## Windows 配置路径适配

### 配置文件位置

- **Linux**: `/etc/Owlangs/`
- **Windows**: `C:\ProgramData\Owlangs\`

### 自动配置生成

安装包会自动：

1. **创建配置目录**: `C:\ProgramData\Owlangs\`
2. **复制模板文件**:
   - `system.json.template` → `system.json` (系统配置)
   - `platforms.json.template` → `platforms.json` (平台配置)
   - `secrets.json.template` → `secrets.json` (API 密钥)
   - `local.json.template` → `local.json` (本地配置)
   - `app_config.json.template` → `app_config.json` (应用配置)
3. **设置环境变量**:
   - `OWLANGS_CONFIG_PATH` = `C:\ProgramData\Owlangs`
   - `DOCUTRANSLATE_PORT` = `8800`

### 启动脚本功能

Windows 启动脚本 (`owlangs.bat`, `owlangs-full.bat`) 会：

1. 检查配置目录是否存在，不存在则创建
2. 检查配置文件是否存在，不存在则从模板复制
3. 设置环境变量
4. 启动应用程序

## 使用说明

### 简单打包使用

1. 运行 `install.bat` (需要管理员权限)
2. 应用程序安装到 `C:\Program Files\Owlangs\Document Agent`
3. 配置文件创建到 `C:\ProgramData\Owlangs`
4. 桌面和开始菜单快捷方式自动创建

### 专业安装器使用

1. 运行生成的 `.exe` 安装器
2. 跟随安装向导，可选择配置目录位置
3. 安装完成后可通过开始菜单或桌面快捷方式启动

## 开发说明

### 命令行参数速查

| 脚本 | 参数 | 说明 |
|------|------|------|
| `build_win.ps1` | `--lite` | 只打 lite 简单包 |
| `build_win.ps1` | `--full` | 只打 full 简单包 |
| `build_win.ps1` | `--clean` | 仅清理构建产物 |
| `build_win.ps1` | `-Frontend` | 取值：`chrome`、`windows`、`both`，默认 chrome |
| `build_win.ps1` | `-IncludeAnonymize` | 轻量版时包含 presidio/spacy 及 spaCy 模型 |
| `build_win_installer.ps1` | `-Lite` | 只打 lite 安装器/简单包 |
| `build_win_installer.ps1` | `-Full` | 只打 full 安装器/简单包 |
| `build_win_installer.ps1` | `-NoSpacy` | 打 lite 时不打包 spaCy 模型 |
| `build_win_installer.ps1` | `-IncludeAnonymize` | 打 lite 时包含 presidio/spacy 及 spaCy 模型 |
| `build_win_installer.ps1` | `-IncludePandoc` | 打安装器时一并打包 Pandoc + pdflatex（走 Inno 或回退简单包均生效） |
| `build_win_installer.ps1` | `-Frontend` | 取值同 build_win.ps1，回退到简单打包时生效 |
| `build_win_installer.ps1` | `-InnoSetupPath "路径"` | 指定 Inno Setup 的 ISCC.exe 路径 |
| `build_flutter_chrome.ps1` | `-NoCopy` | 只构建 Web，不复制到 backend |
| `build_flutter_chrome.ps1` | `-OpenChrome` | 构建后启动临时 HTTP 并用 Chrome 打开 |
| `build_flutter_chrome.ps1` | `-NoClean` | 跳过 flutter clean，加快二次构建 |
| `build_win_standard.ps1` | （无） | 打 Standard 版简单包（完成后校验） |
| `build_win_standard.ps1` | `-Installer` | 打 Standard 版 Inno 安装器（完成后校验） |
| `build_win_pro.ps1` | （无） | 打 Pro 版简单包（完成后校验） |
| `build_win_pro.ps1` | `-Installer` | 打 Pro 版 Inno 安装器（完成后校验） |
| `build_win_enterprise.ps1` | （无） | 打 Enterprise 版简单包（完成后校验） |
| `build_win_enterprise.ps1` | `-Installer` | 打 Enterprise 版 Inno 安装器（完成后校验） |
| `build_win_all.ps1` | （无） | 依次打 Standard、Pro、Enterprise 简单包，每步校验 |
| `build_win_all.ps1` | `-Installer` | 依次打三版 Inno 安装器，每步校验 |

环境变量：`$env:OWLANGS_SKIP_SPACY = "1"` 时全量版/简单包不复制 spaCy 模型。

### 文件结构

```
tools/
├── build/                     # 打包相关
│   ├── build_win.ps1, build_win_installer.ps1, build_win_standard.ps1, build_win_pro.ps1, build_win_enterprise.ps1, build_win_all.ps1
│   ├── verify_build.ps1, build_flutter_chrome.ps1, build_win_web.ps1, build_win_desktop.ps1, build_launcher.ps1, build_deb.sh
│   ├── owlangs_installer.iss, installer.nsi, README_Windows_Build.md
│   └── windows/ (Owlangs.bat, Owlangs-full.bat)
├── setup/                     # 准备工作
│   ├── sync_version.ps1, search_version_refs.ps1
│   ├── download_pdfium.ps1, patch_pdfx_for_local_pdfium.ps1
│   ├── download_fonts.ps1 / .sh, ENV_SETUP.md, README_Font_Download.md
└── (其他脚本见 tools 根目录)
```

### 自定义配置

如需修改配置路径或添加其他功能，可编辑：

- **启动脚本**: `tools\build\windows\*.bat`
- **安装器脚本**: `tools\build\owlangs_installer.iss`
- **构建脚本**: `tools\build\build_win*.ps1`

## 故障排除

### 常见问题

1. **PyInstaller 构建失败**
   - 确保关闭所有 Python 进程: `taskkill /F /IM python.exe`
   - 检查虚拟环境是否正确激活

2. **图标文件缺失或安装包图标不对**
   - 先在仓库根执行：`python tools/generate_ico.py --frontend`（需 Pillow、cairosvg），生成 `frontend/windows/runner/resources/app_icon.ico` 等；详见 `docs/workflow/WINDOWS_PACKAGE_ICONS.md`
   - 构建时会通过 `tools/build/sync_launcher_icon.ps1` 同步 Launcher / NSIS 用图标；若仍缺失会打印 WARNING

3. **Inno Setup 未找到**
   - 安装 Inno Setup 或使用简单打包方案
   - 或指定路径: `.\tools\build_win_installer.ps1 -InnoSetupPath "C:\Path\To\ISCC.exe"`

4. **配置文件未生成**
   - 确保启动脚本有写入权限
   - 检查 `C:\ProgramData\Owlangs` 目录权限

5. **Flutter Windows 构建失败：pdfium 下载（Build step for pdfium failed / Connection was reset）**
   - 原因：构建时需从 GitHub 下载 pdfium 预编译包（pdfx 插件），网络不稳定、代理或防火墙会导致连接重置（如 `CURLE_RECV_ERROR`）。
   - 建议：**先直接重试一次**（CMake 已对诊断下载做最多 3 次重试）；若仍失败，检查网络/代理/VPN/防火墙，或换时段/换网络后再执行同一构建命令。
   - **离线方案**：可预先将 pdfium 下载到 3rdParty，构建时不再联网下载。步骤：
     1. 在仓库根目录执行 `.\tools\setup\download_pdfium.ps1`，将 `pdfium-win-x64-7651.tgz` 下载到 `3rdParty\windows\`。
     2. 执行一次 `.\tools\setup\patch_pdfx_for_local_pdfium.ps1`（需先执行 `flutter pub get`），使 pdfx 插件在检测到父级已设置 `PDFIUM_URL`（本地 file://）时不覆盖。
     此后 Flutter Windows 构建会使用本地 tarball，无需再访问 GitHub。

### 调试模式

在启动脚本中添加 `pause` 命令可查看详细输出：

```batch
echo Debug information...
pause
```

## 下一步计划

1. **代码路径适配**: 修改应用程序代码，支持 Windows 配置路径
2. **服务安装**: 添加 Windows 服务安装选项
3. **自动更新**: 集成自动更新机制
4. **多语言支持**: 完善安装器多语言界面
