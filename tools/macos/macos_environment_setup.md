## macOS 开发环境搭建说明（Apple Silicon）

本项目在 macOS 上开发/运行主要涉及三块环境：

- **Python 3.12**：后端与工具脚本
- **Flutter 3.38.10**：前端（含 macOS 桌面）
- **Xcode + Command Line Tools**：编译 macOS 桌面应用

以下步骤以 **Apple Silicon（arm64，M1/M2/M3 系列）** 为例，默认使用 Homebrew 与官方推荐工具。

---

## 1. 基础依赖

### 1.1 安装 Homebrew

如果尚未安装 Homebrew，可以在终端执行（以官网为准）：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装完成后根据终端提示，把 Homebrew 的路径加入 `~/.zshrc`，例如：

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

然后重启终端或执行：

```bash
source ~/.zshrc
brew --version
```

确认 Homebrew 可用。

---

## 2. 安装与配置 Python 3.12

### 2.1 安装 Python 3.12（arm64）

```bash
brew install python@3.12
```

### 2.2 在 `~/.zshrc` 中配置 PATH

推荐使用 Homebrew 提供的 `libexec/bin` 包装脚本，这里同时放在 Flutter 工具路径前面：

```bash
# Python 3.12 configuration
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"
export LDFLAGS="-L/opt/homebrew/opt/python@3.12/lib"
export CPPFLAGS="-I/opt/homebrew/opt/python@3.12/include"
```

如需让 `python` 命令也使用 3.12，可添加：

```bash
alias python="python3"
```

保存后执行：

```bash
source ~/.zshrc
which python3
python3 --version
```

预期输出中版本应为 `Python 3.12.x`。

### 2.3 为本项目创建 Python 虚拟环境并运行后端

为了避免影响系统其他项目，推荐在仓库根目录下使用 Python 3.12 创建独立虚拟环境，并在其中运行后端。

> 以下示例假设仓库路径为 `/Users/xxx/Workspace/Owlangs/CollabTrans`，请根据实际路径替换。

1. 进入仓库根目录：

   ```bash
   cd /Users/xxx/Workspace/Owlangs/CollabTrans
   ```

2. 使用 Python 3.12 创建虚拟环境（命名为 `.venv`）：

   ```bash
   python3 -m venv .venv
   ```

3. 激活虚拟环境（每次新开终端、在本项目下开发时都需要先激活一次）：

   ```bash
   source .venv/bin/activate
   ```

   激活成功后，命令行提示符前面通常会出现 `(.venv)` 前缀。可以用以下命令确认当前正在使用的 Python：

   ```bash
   which python3
   python3 --version
   ```

   预期 `which python3` 指向项目的 `.venv` 目录，版本仍为 `3.12.x`。

4. 在虚拟环境中安装项目依赖（本仓库使用 `pyproject.toml` 管理依赖）：

   - 推荐在仓库根目录一次性安装（可选用可编辑模式，便于开发）：

   ```bash
   cd /Users/xxx/Workspace/Owlangs/CollabTrans
   pip install -e .
   ```

   如果不需要可编辑安装，也可以使用：

   ```bash
   pip install .
   ```

5. 启动后端服务（本项目已提供专用启动脚本）：

   ```bash
   cd /Users/xxx/Workspace/Owlangs/CollabTrans/backend
   python run_app.py
   ```

   终端中会看到类似：

   ```text
   🚀 Starting Owlangs backend server...
   📍 Backend will be available at: http://localhost:8800
   📚 API documentation at: http://localhost:8800/docs
   ```

6. 退出虚拟环境（完成开发后如需退出，可以在任何位置执行）：

   ```bash
   deactivate
   ```

### 2.4 Redis（会话管理）

后端使用 Redis 做会话与状态管理。与 Windows（内置 3rdParty Redis）、Linux 一致，macOS 上需自行安装并决定是否常驻运行。未安装或未启动时会出现 `Redis executable file not found` 或 `Connection refused`，会话功能不可用，其余功能可正常使用。

#### 安装

```bash
brew install redis
```

安装完成后 **Redis 默认不会自动运行**，因此直接执行 `redis-cli ping` 会得到 `Connection refused`，需先启动 Redis 或先启动后端（见下文）。

#### 使用方式（二选一）

- **方式 A：由后端自动拉起（适合开发）**  
  不单独启动 Redis。只要本机已安装且 `redis-server` 在 PATH 中（Homebrew 会装到 `/opt/homebrew/bin/redis-server`），**先启动后端** `python run_app.py`，程序会自动检测并启动本地 Redis，会话即可用。  
  若想单独验证 Redis，需先按方式 B 启动 Redis，再执行 `redis-cli ping`。

- **方式 B：系统级常驻服务（推荐用于长期使用）**  
  启动 Redis 并设为登录时自启：

  ```bash
  brew services start redis
  ```

  之后可直接执行 `redis-cli ping`，应返回 `PONG`；再启动后端即可使用会话。  
  查看状态：`brew services list`；停止：`brew services stop redis`。

#### 仅本次会话手动启动（不常用）

不依赖 brew services，仅当前终端会话运行 Redis：

```bash
/opt/homebrew/opt/redis/bin/redis-server /opt/homebrew/etc/redis.conf
```

需保持该终端不关闭；关闭后 Redis 停止。

#### 验证

Redis 已运行时，在终端执行：

```bash
redis-cli ping
```

返回 `PONG` 表示 Redis 正常。再启动后端 `python run_app.py`，不应再出现 “Redis executable file not found” 或 “Connection refused”。

#### 临时关闭 Redis 依赖

若暂时不需要会话功能，可禁用 Redis：

- 环境变量：启动后端前执行 `export REDIS_ENABLED=false`，或在 `~/.zshrc` 中加入 `export REDIS_ENABLED=false`。
- 或修改配置文件 `configs/local.json` 中 `redis.enabled` 为 `false`。

### 2.5 可选：安装 TeX 与 Pandoc（用于 PDF 导出等）

部分功能（例如通过 Pandoc + XeLaTeX 将 HTML 转为 PDF、处理带复杂数学公式的 DOCX 等）需要系统中存在 **TeX 发行版** 和 **Pandoc**。在 Windows 下使用 `3rdParty/windows/pdflatex` 与 `3rdParty/windows/pandoc-*`，在 macOS 上通过 Homebrew 安装即可。

#### 2.5.1 安装 Pandoc

```bash
brew install pandoc
```

验证：

```bash
pandoc --version
```

能输出版本号即可。

#### 2.5.2 安装 TeX（XeLaTeX）

**方案 A：BasicTeX（推荐，体积较小，安装稳定）**

```bash
brew install --cask basictex
```

安装完成后，**必须**让当前终端识别 TeX 命令，任选其一：

- 重新打开一个终端窗口；或  
- 在当前终端执行：`eval "$(/usr/libexec/path_helper)"`

然后安装常用宏包并验证：

```bash
sudo tlmgr update --self
sudo tlmgr install collection-latexrecommended collection-fontsrecommended
xelatex --version
```

若 `xelatex --version` 能输出版本信息，说明 XeLaTeX 可用。

**方案 B：MacTeX 完整版（体积大，国内镜像可能下载失败）**

```bash
brew install --cask mactex-no-gui
```

若 CTAN 镜像下载失败，可改用方案 A（BasicTeX）。安装完成后同样需重启终端或执行 `eval "$(/usr/libexec/path_helper)"`，再执行 `xelatex --version` 验证。

> 说明：在 macOS / Linux 上，代码不会使用 `3rdParty/windows/pdflatex`，而是通过系统 PATH 中的 `xelatex` / `pdflatex` 与 `pandoc` 工作。因此只需在系统层面安装 TeX 与 Pandoc 即可，无需在 `3rdParty` 下复制一份 macOS 专用版本。

#### 2.5.3 DOCX/PDF 公式导出依赖（必选，用于公式正确显示）

当你在 macOS 上导出 **DOCX**、且原文/译文中包含 LaTeX 公式时，如果后端日志中出现类似：

- `ModuleNotFoundError: No module named 'latex2mathml'`
- `[DOCX-EQUATION] latex2mathml failed ...`

说明当前虚拟环境里**还没有安装公式转换依赖**。此时会退化为“将 LaTeX 以纯文本方式写入 DOCX”，OMML/公式效果会变差。

本项目已将原来的可选 `docx_equation` extra（一次性安装 `latex2mathml`、`mathml2omml`、`mathml2omml-as` 等依赖）提升为**默认必选依赖**，直接写入 `pyproject.toml` 的 `dependencies` 中。正常情况下，只要按前文在虚拟环境中执行：

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans
source .venv/bin/activate
pip install -e .
```

就会自动安装这些库，无需单独启用 extra。

如果你是从早期版本升级，或虚拟环境较旧，导出 DOCX 时仍在日志中看到：

- `ModuleNotFoundError: No module named 'latex2mathml'`
- `[DOCX-EQUATION] latex2mathml failed ...`

可以在已激活的虚拟环境中手动补齐依赖：

```bash
pip install latex2mathml mathml2omml mathml2omml-as
```

安装完成后，重新启动后端，再次导出带公式的 DOCX/PDF，日志中不应再出现 `ModuleNotFoundError: No module named 'latex2mathml'`，公式会尽可能转换为 OMML（或在 PDF 中以更合理的形式呈现）。

---

## 3. 安装与配置 Flutter 3.38.10

推荐使用 FVM（Flutter Version Manager）管理 Flutter 版本。

### 3.1 安装 FVM

```bash
brew tap leoafarias/fvm
brew install fvm
fvm --version
```

### 3.2 使用 FVM 安装 Flutter 3.38.10

```bash
fvm install 3.38.10
fvm global 3.38.10
```

可以查看当前已安装版本：

```bash
fvm list
```

### 3.3 配置 Flutter 命令 PATH

FVM 的全局可执行脚本通常安装在 `~/.pub-cache/bin`，为了让 `flutter` 命令指向通过 FVM 管理的版本，在 `~/.zshrc` 追加：

```bash
export PATH="$HOME/.pub-cache/bin:$PATH"
```

如果你使用的是从官网解压的 Flutter SDK 放在仓库外部（例如 `/Users/xxx/Workspace/tools/flutter`），则需将其 `bin` 目录加入 PATH，例如：

```bash
export PATH="/Users/xxx/Workspace/tools/flutter/bin:$PATH"
```

保存后执行：

```bash
source ~/.zshrc
which flutter
flutter --version
```

预期 `flutter --version` 中的 Flutter 版本为 `3.38.10`。

---

## 4. 中国大陆网络环境下的 Flutter 镜像配置

在中国大陆使用 Flutter，建议配置国内镜像以加速下载。可以在 `~/.zshrc` 中添加以下任意一组环境变量。

### 4.1 CFUG 官方中国镜像（推荐）

```bash
export PUB_HOSTED_URL="https://pub.flutter-io.cn"
export FLUTTER_STORAGE_BASE_URL="https://storage.flutter-io.cn"
```

### 4.2 清华 TUNA 镜像

```bash
export PUB_HOSTED_URL="https://mirrors.tuna.tsinghua.edu.cn/dart-pub"
export FLUTTER_STORAGE_BASE_URL="https://mirrors.tuna.tsinghua.edu.cn/flutter"
```

### 4.3 上交大 SJTUG 镜像

```bash
export PUB_HOSTED_URL="https://mirror.sjtu.edu.cn/dart-pub"
export FLUTTER_STORAGE_BASE_URL="https://mirror.sjtu.edu.cn"
```

保存后执行：

```bash
source ~/.zshrc
flutter pub get
```

确认依赖下载速度明显提升。

> 说明：上述镜像配置主要作用于 Flutter 组件与 Dart 包下载；FVM 在安装 Flutter SDK 时仍需要访问 Git 仓库，如果 GitHub 访问不稳定，建议为 git 单独配置 HTTP/HTTPS 代理。

---

## 5. 安装 Xcode 与 Command Line Tools

Flutter 构建 macOS 桌面应用需要完整 Xcode（不仅仅是 Command Line Tools）。

### 5.1 安装 Xcode

1. 打开 App Store，搜索并安装 **Xcode**。
2. 安装完成后，首次启动 Xcode，同意所有协议，并等待其完成第一次组件安装。

### 5.2 安装/确认 Command Line Tools

在终端执行：

```bash
xcode-select --install
```

如果提示已安装，可忽略。

### 5.3 将 `xcode-select` 指向 Xcode

安装 Xcode 后，执行：

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

验证：

```bash
xcodebuild -version
```

预期输出类似：

```text
Xcode 16.x
Build version ...
```

如果未按上述路径安装（例如 `Xcode-beta.app`），请根据实际 `.app` 路径调整命令。

### 5.4 安装 CocoaPods

Flutter 在 iOS / macOS 上使用大量依赖原生代码的插件，需要通过 CocoaPods 管理这些原生依赖。

#### 5.4.1 使用 RubyGems 安装（推荐）

```bash
sudo gem install cocoapods
```

如果系统 Ruby 有权限问题，再使用 Homebrew 方式：

```bash
brew install cocoapods
```

安装完成后，验证：

```bash
pod --version
```

能正常输出版本号即可。

---

## 6. 验证 Flutter macOS 环境

### 6.1 使用 `flutter doctor` 检查

在仓库根目录或任意位置执行：

```bash
flutter doctor
```

确认输出中：

- `Flutter` 为 3.38.10（或预期版本）
- `Xcode` 与 `macOS` 模块显示为已配置

### 6.2 在本项目中运行 macOS 应用

进入前端目录：

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans/frontend
flutter clean
flutter pub get
cd macos
pod install
cd ..
flutter run -d macos
```

首次运行会自动：

- 升级项目的 macOS 部署目标（如从 10.13 升级到 10.15）
- 生成或更新 Xcode 项目配置

如果遇到 `xcrun: error: unable to find utility "xcodebuild"` 类错误，请回到上文 **5.3** 步骤检查 `xcode-select`。

---

## 7. 运行 Web 前端

如果您想在浏览器中运行前端，而不需要安装 Chrome 浏览器，可以使用 Web Server 模式：

### 7.1 启用 Web 支持

首先确保 Flutter Web 支持已启用：

```bash
flutter config --enable-web
```

### 7.2 启动 Web 服务器

在前端目录执行：

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans/frontend
flutter clean
flutter pub get
flutter run -d web-server --web-port=8080
```

### 7.3 访问 Web 应用

启动成功后，在任何浏览器中访问：

```
http://localhost:8080
```

### 7.4 与后端配合使用

Web 前端需要后端服务支持。请先启动后端：

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans
source .venv/bin/activate
python backend/run_app.py
```

然后再启动 Web 前端，这样前端会自动连接到后端 API。

---

## 8. 打包 macOS 应用

本项目提供了统一的打包脚本 `tools/build/build_macos.sh`，支持构建两种不同版本的 macOS 应用：

### 8.1 版本类型

1. **Web 版（默认）**：
   - 后端 + Web 前端
   - 用户通过浏览器访问 `http://localhost:8800` 使用应用
   - 后端服务自动启动并托管 Web 前端

2. **桌面版**：
   - 独立的 Flutter macOS 桌面应用
   - 应用启动时自动启动后端服务
   - 关闭应用时自动停止后端服务
   - 提供更原生的桌面体验

### 8.2 使用方法

#### 构建 Web 版（默认）

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans
tools/build/build_macos.sh
```

构建产物：
- 可执行文件：`dist/Owlangs-{version}-mac`
- 应用包：`dist/Owlangs.app`
- 安装包：`dist/Owlangs-{version}-mac.dmg`

#### 构建桌面版

```bash
cd /Users/xxx/Workspace/Owlangs/CollabTrans
tools/build/build_macos.sh --frontend desktop
```

构建产物：
- 桌面应用：`dist/Owlangs.app`
- 安装包：`dist/Owlangs-{version}-mac-desktop.dmg`

#### 其他选项

```bash
# 构建 lite 版本（默认）
tools/build/build_macos.sh lite

# 构建 full 版本
tools/build/build_macos.sh full

# 跳过 DMG 生成
tools/build/build_macos.sh --no-dmg

# 组合使用
tools/build/build_macos.sh --frontend desktop --no-dmg
```

### 8.3 运行构建产物

构建完成后，可以直接运行应用：

```bash
# 运行应用
open dist/Owlangs.app
```

或者双击 DMG 文件进行安装。

### 8.4 注意事项

1. **图标文件**：打包前需要确保 `assets/Owlangs.icns` 文件存在。可以通过以下命令生成：
   ```bash
   python tools/build/macos_create_icns_from_icon_composer.py
   ```

2. **虚拟环境**：打包脚本会自动创建和激活虚拟环境，无需手动激活。

3. **构建时间**：首次构建可能需要较长时间，请耐心等待。

4. **磁盘空间**：构建过程会生成大量临时文件，确保磁盘空间充足。

---

## 9. 快速排查清单

如果 macOS 构建失败，可以按以下顺序排查：

1. **Python 版本**
   - `python3 --version` 应为 `3.12.x`。
2. **Flutter 版本**
   - `flutter --version` 应为 `3.38.10`（或预期版本）。
3. **Xcode 与 Command Line Tools**
   - `xcodebuild -version` 能正常输出版本。
   - `xcode-select -p` 指向 `Xcode.app/Contents/Developer`。
4. **镜像配置（中国大陆）**
   - `PUB_HOSTED_URL` 与 `FLUTTER_STORAGE_BASE_URL` 已设置为国内镜像。
5. **项目依赖**
   - 在 `frontend` 中执行 `flutter pub get` 无严重报错。
6. **Redis（后端会话，可选）**
   - 需要会话管理时：`brew install redis`，`redis-cli ping` 返回 `PONG`；或设置 `REDIS_ENABLED=false` / 配置 `redis.enabled=false` 临时关闭。
7. **CocoaPods 安装状态**
   - `pod --version` 能正常输出版本号。
   - `flutter run -d macos` 不再出现 “CocoaPods not installed or not in valid state” 报错。

上述检查项均通过后，一般即可正常在 macOS 上编译和运行本项目的桌面应用和 Web 应用。

