# 构建环境设置指南

本文档说明如何准备 Python 虚拟环境、Flutter、.NET 等编译与打包所需环境，以便成功执行 `build_win.ps1`、`build_win_installer.ps1` 等脚本。

---

## 1. 环境概览

| 组件 | 用途 | 必需/可选 |
|------|------|-----------|
| **Python 3.11+** | 后端、PyInstaller 打包 | 必需 |
| **Flutter SDK** | 前端 Web / Windows 桌面构建 | 必需 |
| **.NET 8 SDK** | Launcher（桌面前端启动器） | 打桌面包时必需 |
| **NuGet** | Flutter Windows 桌面前端构建时还原 C++ 依赖 | 打桌面包时需可用；未安装时 Flutter 会尝试自动下载 |
| **NSIS** | 备用安装器 | 可选 |
| **Pandoc / pdflatex** | PDF 流程导出 DOCX | 可选，仅 `-IncludePandoc` 时需事先放置 |

构建脚本会在缺少虚拟环境时自动创建并安装依赖，但建议按下面步骤预先设置，便于排查问题和重复构建。

---

## 2. Python 与虚拟环境

### 2.1 安装 Python

- **版本**：3.11 或 3.12（推荐 3.12，与当前 PyInstaller/numpy 兼容性已验证）。
- **下载**：[python.org](https://www.python.org/downloads/) 或 Windows Store。
- **安装时**：勾选 “Add Python to PATH”；如需为当前用户安装可勾选 “Install for current user only”。

验证：

```powershell
python --version
# 应显示 Python 3.11.x 或 3.12.x
```

### 2.2 创建虚拟环境

在**项目根目录**（即包含 `pyproject.toml`、`backend`、`frontend` 的目录）执行：

```powershell
# 进入项目根目录
cd D:\workspace\localrepo\Owlangs

# 创建虚拟环境（目录名为 .venv）
python -m venv .venv

# 激活虚拟环境（PowerShell）
.\.venv\Scripts\Activate.ps1
```

若执行策略禁止运行脚本，可先执行（当前用户、当前进程）：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

激活成功后，命令行前会出现 `(.venv)`。

### 2.3 升级 pip 并安装项目依赖

在虚拟环境已激活的前提下：

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

- `-e .`：以可编辑方式安装项目及 pyproject.toml 中的依赖。其中 **lxml** 为必需依赖（DOCX/公式 OMML 解析、HTML 解析等会用到），会随上述命令一并安装；若 pip 报找不到 lxml，请检查 pip 源配置（如 `%APPDATA%\pip\pip.ini`，`index-url = https://pypi.org/simple`）。

### 2.3.1 DOCX/PDF 公式导出（必选，用于公式正确显示）

为了让 **PDF 流程翻译后导出 DOCX/PDF 时，公式以 OMML 正确显示**，本项目已将原来的可选依赖 `docx_equation`（`latex2mathml`、`mathml2omml`、`mathml2omml-as`）提升为**默认必选依赖**，已直接写入 `pyproject.toml` 的 `dependencies` 中。

- 使用 `python -m pip install -e .` 或 `python -m pip install .` 安装项目时，会**自动安装**这些库。
- 若构建或运行日志中仍出现 `ModuleNotFoundError: No module named 'latex2mathml'` 等错误，通常是早期环境未更新或虚拟环境未重新安装依赖，可在已激活的 `.venv` 中执行一次：

  ```powershell
  python -m pip install latex2mathml mathml2omml mathml2omml-as
  ```

确保上述依赖存在后，PyInstaller 打包时会一并收录，导出 DOCX/PDF 时即可使用公式转换，无需再单独启用 extra。

### 2.4 Pillow（图像处理必需）

- **用途**：后端导出 DOCX、图像处理以及图标生成脚本（`backend/exporter/md/md2docx_exporter.py`、`backend/utils/document_rebuild/docx_rebuild.py`、`frontend/tools/regenerate_all_icons.py` 等）依赖 **Pillow**（`PIL`）。
- **版本要求**：项目在 `pyproject.toml` 中约束为 `pillow>=10.0.0,<12.0.0`，已与当前的 `numpy==1.26.4`、PyInstaller 组合测试通过。
- **手动安装（推荐在新机器上预拉取）**：
  ```powershell
  python -m pip install "pillow>=10.0.0,<12.0.0"
  ```
  - 若打包阶段出现 `ModuleNotFoundError: No module named 'PIL'` 或 `No module named 'Pillow'`，请先在虚拟环境中执行上述命令，再重新运行打包脚本。
  - 若出现 **`WARNING: Package(s) not found: pillow`**，说明当前 pip 源未提供 Pillow，请检查/调整 pip 源（如 `%APPDATA%\pip\pip.ini`），使之指向包含 Pillow 的 PyPI 或镜像，然后再次执行安装命令。

### 2.5 安装 PyInstaller

打包脚本（如 `build_win.ps1`）会在需要时自动执行 `pip install pyinstaller`，也可提前安装：

```powershell
python -m pip install pyinstaller
```

### 2.6 验证 Python 环境

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import backend; print(backend.__version__)"
python -c "import pyinstaller; print('PyInstaller OK')"
```

无报错即表示后端与 PyInstaller 可用。

---

## 3. Flutter 环境

### 3.1 安装 Flutter SDK

- **下载**：[Flutter 官网](https://flutter.dev/docs/get-started/install/windows) 或 [国内镜像](https://flutter.cn/docs/get-started/install/windows)。
- 解压到任意目录（如 `C:\flutter`），并将 `bin` 加入 PATH。

验证：

```powershell
flutter --version
flutter doctor
```

### 3.2 安装桌面构建依赖（仅打 Windows 桌面前端时）

若需打 `-Frontend windows` 或 `-Frontend both`，需启用 Windows 桌面支持：

```powershell
flutter config --enable-windows-desktop
flutter doctor
```

根据 `flutter doctor` 提示安装缺失项（如 Visual Studio 的 “Desktop development with C++” 工作负载）。

---

## 4. .NET SDK（Launcher 用）

打包含 **Windows 桌面前端** 的包时，需要编译 C# Launcher（`launcher/`），要求 **.NET 8.0 SDK**。

- **下载**：[.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- 安装后验证：

```powershell
dotnet --version
# 应为 8.x.x
```

若未安装或版本低于 8，打桌面包时脚本会提示并跳过 Launcher，不影响仅 Chrome/Web 的打包。

---

## 5. 可选：安装器与第三方工具

### 5.1 Inno Setup（推荐用于发布安装包）

- **下载**：[Inno Setup](https://jrsoftware.org/isinfo.php)
- 安装后脚本会自动查找 `ISCC.exe`（如 `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`）。
- 未安装时，`build_win_installer.ps1` 会回退为调用 `build_win.ps1` 做简单打包。

### 5.2 NSIS（可选）

- **下载**：[NSIS](https://nsis.sourceforge.io/Download)
- 将 `makensis` 加入 PATH 后，`build_win.ps1` 在简单打包完成后会尝试构建 NSIS 安装器。

### 5.3 Pandoc 与 pdflatex（仅 `-IncludePandoc` 时需要）

- **Pandoc**：从 [Pandoc 发布页](https://github.com/jgm/pandoc/releases) 下载 Windows 版，解压到 `3rdParty\windows\pandoc-<版本>\`（目录内需有 `pandoc.exe`）。
- **pdflatex / XeLaTeX**：运行 `3rdParty\windows\install_pdflatex.ps1` 安装 TinyTeX 到 `3rdParty\windows\pdflatex\`，或自行放置 TeX 可执行文件。

---

## 6. 一键检查清单

在项目根目录、PowerShell 下可逐条执行以自检：

```powershell
# 1. Python 与虚拟环境
python --version
if (Test-Path .venv) { .\.venv\Scripts\Activate.ps1; python -c "import backend; print('backend OK')" }

# 2. Flutter
flutter --version
flutter doctor

# Building with plugins requires symlink support.
#Please enable Developer Mode in your system settings.
start ms-settings:developers
#Win10在 设置 → 隐私和安全性 → 针对开发人员 里，打开 开发人员模式。
#Win11在 系统->高级->开发者选项->开发者模式，启用它

flutter pub get

# 3. .NET（打桌面包时需要）
dotnet --version

# 4. 可选：Inno Setup
Get-Command ISCC -ErrorAction SilentlyContinue
```

---

## 7. 构建脚本会自动执行的环境步骤

执行 `.\tools\build\build_win.ps1` 或 `.\tools\build\build_win_installer.ps1` 时，脚本会：

1. **同步版本号**：调用 `tools\setup\sync_version.ps1`（以 `backend\__init__.py` 为源）。
2. **创建/激活虚拟环境**：若无 `.venv` 则执行 `python -m venv .venv` 并激活。
3. **安装/修复依赖**：从 `pyproject.toml` 安装依赖，并按需固定 lxml、pillow、numpy、svglib 等版本以兼容 PyInstaller。
4. **安装 PyInstaller**：若未安装则 `pip install pyinstaller`。
5. **构建 Flutter Web**：`flutter clean`、`flutter pub get`、`flutter build web --release`，并复制到 `backend\static\flutter-web`。
6. **（若 -Frontend windows/both）构建 Flutter Windows**：`flutter build windows --release`。
7. **（若含桌面前端）编译 Launcher**：在 `launcher/` 下执行 `dotnet build -c Release`。

因此若已按上文创建好 `.venv` 并安装过依赖，可减少首次构建时的等待时间；若未准备，脚本也会尝试自动完成上述步骤。

---

## 8. 常见问题

### 8.1 无法激活 .venv：执行策略限制

错误类似：`无法加载文件 .\Activate.ps1，因为在此系统上禁止运行脚本`。

解决（当前用户）：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 8.2 PyInstaller 或依赖报错

- 确保在**项目根目录**、且已**激活 .venv** 再运行打包脚本。
- 可先手动执行：  
  `python -m pip install --upgrade pip`  
  `python -m pip install -e .`  
  `python -m pip install pyinstaller`  
  再重试构建。

### 8.3 Flutter 构建失败

- 执行 `flutter doctor` 按提示安装缺失项。
- 打 Windows 桌面时需：`flutter config --enable-windows-desktop` 及 Visual Studio 的 C++ 桌面开发组件。

### 8.4 Launcher 未被打包

- 检查是否已安装 .NET 8 SDK：`dotnet --version`。
- 确认 `launcher\` 目录存在且可执行 `dotnet build -c Release`。

### 8.5 清理后重新构建

- 仅清理构建产物：`.\tools\build\build_win.ps1 --clean`
- 虚拟环境不会被删除；若要完全重来，可手动删除 `.venv` 后重新执行本文档第 2 节步骤。

### 8.6 CI 上常见错误与提示

- **Build failed: WARNING: Skipping lxml as it is not installed.**  
  构建脚本在“修复 lxml 版本”时会先尝试卸载再安装。在全新 CI 环境中 lxml 未安装，`pip uninstall -y lxml` 会输出该警告并返回非零，部分环境会因此报错。当前脚本已改为：仅在已安装 lxml 时才执行 uninstall，再执行 install。若仍报错，请确认使用最新版 `tools/build/build_win.ps1`。

- **Build failed: WARNING: Package(s) not found: lxml**  
  说明构建脚本在执行 `python -m pip install "lxml<6.0.0"` 时，**pip 在当前配置的源中找不到 lxml**。这通常发生在：
  - 该电脑使用了**只包含内部包的私有 PyPI 源**，未同步 lxml；
  - 或网络受限，导致无法访问配置的外部源。

  处理步骤：

  1. 在问题机器上，进入项目根目录并激活虚拟环境：
     ```powershell
     cd D:\workspace\localrepo\Owlangs
     .\.venv\Scripts\Activate.ps1
     python -m pip install --upgrade pip
     python -m pip install "lxml>=5.4.0,<6.0.0"
     ```
  2. 若仍提示 `Package(s) not found: lxml`，请检查或修改 pip 源配置（如 `%APPDATA%\pip\pip.ini`），使其指向包含 lxml 的源，例如：`index-url = https://pypi.org/simple`。
  3. 手动安装 lxml 成功后，再次运行 `.\tools\build\build_win_basic.ps1` / `build_win_pro.ps1` / `build_win_enterprise.ps1` 即可；脚本会检测并复用已安装的 lxml。

- **CMake Deprecation Warning: Compatibility with CMake &lt; 3.10 will be removed.**  
  这是**警告**，不是错误，构建会继续。本仓库中 `frontend/windows/` 与 `frontend/linux/` 下的 CMakeLists.txt 已使用 `cmake_minimum_required(VERSION 3.14...3.30)` 等 min...max 语法；若仍出现该警告，多半来自 Flutter 引擎或某插件的 CMake。**无需处理**；若希望消除警告，可将 CI 上的 CMake 升级至 3.10+。

- **Nuget.exe not found, trying to download or use cached version.**  
  这是**提示**，不是错误。**NuGet 是 Flutter 构建 Windows 桌面前端时需要的**（用于还原 C++/Windows 依赖）。Flutter 若在 PATH 中找不到 `nuget.exe`，会自动尝试下载或使用缓存版本；若下载/缓存成功，构建会正常进行。**若后续构建成功，可忽略此提示。** 若 CI 无外网或下载失败导致构建失败，可在 CI 上预装 NuGet（例如通过 [nuget.org](https://www.nuget.org/downloads) 或 Chocolatey：`choco install nuget.commandline`），或将 Flutter 缓存目录持久化以复用已下载的 nuget.exe。

---

## 9. 相关文档

- **Windows 打包参数与示例**：`tools/build/README_Windows_Build.md`
- **版本号同步**：`tools/setup/sync_version.ps1`（`--check` 可检查各文件版本是否一致）
- **第三方依赖说明**：`docs/core/3RD_PARTY_DEPENDENCIES.md`
