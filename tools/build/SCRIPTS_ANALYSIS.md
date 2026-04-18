# Build Scripts Analysis - 脚本重复分析

## 脚本列表 (17个)

```
build_common.ps1           # 共享模块 (新增)
build_debug.ps1            # 调试构建
build_enterprise_clean.ps1 # 企业版完整清理构建
build_flutter_chrome.ps1   # Flutter Web 构建
build_launcher.ps1         # Launcher 单独构建
build_win.ps1              # Windows 构建主脚本 (600+ 行)
build_win_all.ps1          # 构建所有版本
build_win_desktop.ps1      # Desktop 版本构建 (600+ 行)
build_win_enterprise.ps1   # Enterprise 版本 (包装器)
build_win_installer.ps1    # Inno Setup 安装包 (400+ 行)
build_win_pro.ps1          # Pro 版本 (包装器)
build_win_standard.ps1     # Standard 版本 (包装器)
build_win_web.ps1          # Web 版本构建 (新增/重构)
fix_canvaskit_path.ps1     # CanvasKit 路径修复
sync_launcher_icon.ps1     # 图标同步
verify_build.ps1           # 构建验证
verify_canvaskit.ps1       # CanvasKit 验证 (新增)
```

---

## 重复分析

### 🔴 高度重复 (需要合并)

#### 1. Edition 包装脚本 (3个文件几乎相同)
| 脚本 | 代码行 | 差异 |
|------|-------|------|
| `build_win_pro.ps1` | 29行 | 调用参数: `-Lite -Frontend windows -IncludePandoc -Edition Pro` |
| `build_win_standard.ps1` | 29行 | 调用参数: `-Lite -Frontend windows -Edition Standard` |
| `build_win_enterprise.ps1` | 29行 | 调用参数: `-Full -Frontend both -IncludePandoc -Edition Enterprise` |

**建议**: 合并为一个 `build_win_edition.ps1`，通过参数指定版本类型

```powershell
# 替换方案
.\tools\build\build_win_edition.ps1 -Edition Pro        # 原 build_win_pro.ps1
.\tools\build\build_win_edition.ps1 -Edition Standard  # 原 build_win_standard.ps1
.\tools\build\build_win_edition.ps1 -Edition Enterprise # 原 build_win_enterprise.ps1
```

#### 2. Flutter Web 构建逻辑 (4个脚本重复)
以下脚本都有几乎相同的 Flutter Web 构建代码:
- `build_win.ps1` (第148-238行)
- `build_win_installer.ps1` (第103-159行)
- `build_win_web.ps1` (使用共享模块)
- `build_flutter_chrome.ps1` (完整重复)
- `build_enterprise_clean.ps1` (内嵌逻辑)

**重复代码包括**:
```powershell
# 重复的代码模式 (约30-50行)
flutter clean
flutter pub get
flutter build web --release --no-tree-shake-icons
Copy-Item fonts → build\web\assets\fonts
Copy-Item build\web\* → backend\static\flutter-web
# Fix CanvasKit path in index.html
```

**建议**: 所有脚本都使用 `build_common.ps1` 中的 `Build-FlutterWebUnified`

#### 3. 版本获取逻辑 (5个脚本重复)
以下脚本都有相同的 `Get-Version` 函数:
- `build_win.ps1`
- `build_win_desktop.ps1`
- `build_win_installer.ps1`
- `build_win_web.ps1`
- `build_debug.ps1`

**建议**: 使用 `build_common.ps1` 中的 `Get-BuildVersion`

#### 4. 虚拟环境设置 (4个脚本重复)
以下脚本都有虚拟环境初始化和 PyInstaller 安装:
- `build_win.ps1`
- `build_win_installer.ps1`
- `build_win_web.ps1`
- `build_debug.ps1`

**建议**: 使用 `build_common.ps1` 中的 `Ensure-BuildVenv`

---

### 🟡 部分重复 (可优化)

#### 5. CanvasKit 路径修复逻辑 (3个脚本)
- `build_win.ps1`
- `build_win_installer.ps1`
- `fix_canvaskit_path.ps1`

**建议**: 统一使用 `verify_canvaskit.ps1 -Fix`

#### 6. Launcher 构建 (2个脚本)
- `build_win_desktop.ps1` (Build-Launcher 函数)
- `build_launcher.ps1` (独立脚本)

**差异**: `build_win_desktop.ps1` 的函数会同步图标，`build_launcher.ps1` 更详细

**建议**: `build_launcher.ps1` 作为唯一入口，`build_win_desktop.ps1` 调用它

#### 7. Flutter Windows 构建 (2个脚本)
- `build_win_desktop.ps1` (Build-FlutterWindows 函数)
- `build_debug.ps1` (内嵌代码)

**建议**: 提取为共享函数

---

### 🟢 不重复 (保持独立)

| 脚本 | 用途 | 说明 |
|------|------|------|
| `build_win_all.ps1` | 批量构建 | 协调多个版本的构建流程 |
| `build_debug.ps1` | 快速调试 | 开发者日常使用的便捷脚本 |
| `build_enterprise_clean.ps1` | 完整清理构建 | 特殊场景使用，带验证步骤 |
| `build_flutter_chrome.ps1` | Web 调试 | 快速启动 Chrome 测试 |
| `build_launcher.ps1` | Launcher 单独构建 | 开发者便捷脚本 |
| `fix_canvaskit_path.ps1` | 部署后修复 | 现场修复工具 |
| `sync_launcher_icon.ps1` | 图标同步 | 辅助工具脚本 |
| `verify_build.ps1` | 构建验证 | 验证脚本，被其他脚本引用 |
| `verify_canvaskit.ps1` | CanvasKit 验证 | 独立的验证工具 |

---

## 重构建议

### 阶段 1: 合并 Edition 包装脚本
将 `build_win_pro.ps1`, `build_win_standard.ps1`, `build_win_enterprise.ps1` 合并:

```powershell
# build_win_edition.ps1
param(
    [Parameter(Mandatory)]
    [ValidateSet("Standard", "Pro", "Enterprise")]
    [string]$Edition,
    [switch]$Installer
)

# 根据 Edition 设置参数
switch ($Edition) {
    "Standard" { $args = @("-Lite", "-Frontend", "windows") }
    "Pro" { $args = @("-Lite", "-Frontend", "windows", "-IncludePandoc") }
    "Enterprise" { $args = @("-Full", "-Frontend", "both", "-IncludePandoc") }
}

# 调用主构建脚本
& "$ScriptDir\build_win.ps1" @args -Edition $Edition
```

### 阶段 2: 统一使用共享模块
修改以下脚本，使用 `build_common.ps1`:
- `build_win.ps1` → 使用 `Build-FlutterWebUnified`, `Get-BuildVersion`, `Ensure-BuildVenv`
- `build_win_installer.ps1` → 使用共享函数
- `build_win_desktop.ps1` → 使用共享函数

### 阶段 3: 删除冗余脚本
重构后可删除:
- `build_win_pro.ps1` → 使用 `build_win_edition.ps1 -Edition Pro`
- `build_win_standard.ps1` → 使用 `build_win_edition.ps1 -Edition Standard`
- `build_win_enterprise.ps1` → 使用 `build_win_edition.ps1 -Edition Enterprise`

---

## 优化后的脚本结构

```
tools/build/
├── build_common.ps1              # 共享模块 (增强)
│   ├── Get-BuildVersion
│   ├── Build-FlutterWebUnified
│   ├── Build-FlutterWindows
│   ├── Build-Launcher
│   ├── Build-PyInstaller
│   ├── Test-CanvasKitConfig
│   ├── Ensure-BuildVenv
│   └── Make-Package
│
├── build_win.ps1                 # 主构建脚本 (精简版)
├── build_win_edition.ps1         # 各版本统一入口 (新)
├── build_win_all.ps1             # 批量构建 (保持不变)
├── build_win_installer.ps1       # Inno Setup (精简版)
├── build_win_desktop.ps1         # Desktop 版本 (精简版)
├── build_win_web.ps1             # Web 版本 (已精简)
│
├── build_debug.ps1               # 开发调试 (保持不变)
├── build_flutter_chrome.ps1      # Web 快速测试 (保持不变)
├── build_enterprise_clean.ps1    # 完整清理构建 (保持不变)
├── build_launcher.ps1            # Launcher 单独构建 (保持不变)
│
├── fix_canvaskit_path.ps1        # CanvasKit 修复 (可选)
├── verify_canvaskit.ps1          # CanvasKit 验证 (新增)
├── verify_build.ps1              # 构建验证 (保持不变)
└── sync_launcher_icon.ps1        # 图标同步 (保持不变)
```

**脚本数量: 17 → 14 (减少 3个，简化多个)**

---

## 优先级建议

| 优先级 | 任务 | 影响 |
|-------|------|------|
| P0 | 合并 3个 Edition 包装脚本 | 减少重复，简化调用 |
| P1 | `build_win.ps1` 使用共享模块 | 减少 100+ 行代码 |
| P1 | `build_win_installer.ps1` 使用共享模块 | 减少 50+ 行代码 |
| P2 | 统一 Launcher 构建逻辑 | 保持一致性 |
| P3 | 删除 `fix_canvaskit_path.ps1` (功能被 `verify_canvaskit.ps1 -Fix` 覆盖) | 清理冗余 |
