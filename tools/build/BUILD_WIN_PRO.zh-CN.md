# 使用 `build_win_pro.ps1` 编译与打包 Owlangs Pro 版（Windows）

> 英文版见 [BUILD_WIN_PRO.en.md](BUILD_WIN_PRO.en.md)

本文说明如何通过 `tools/build/build_win_pro.ps1` 在 Windows 上构建 **Pro** 发行包：桌面端（Windows）、**精简（lite）** 体积、捆绑 **Pandoc + pdflatex**（用于 PDF / DOCX 相关工作流），且 **不包含匿名化（anonymize）** 相关组件（与脚本内注释一致）。

---

## 脚本做什么

| 步骤 | 说明 |
|------|------|
| 切换目录 | 自动切换到仓库根目录（脚本位于 `tools/build`，向上两级为项目根）。 |
| 版本同步 | 调用 `tools/setup/sync_version.ps1` 同步版本号（失败时通常仅警告并继续）。 |
| 构建 | 委托 `build_win.ps1` 或 `build_win_installer.ps1`，参数固定为 **Lite + Windows 桌面前端 + IncludePandoc + Edition Pro**。 |
| 校验 | 引用 `verify_build.ps1`，检查输出目录或安装包是否存在关键产物。 |

---

## 运行环境建议

在运行脚本前请确认：

- **PowerShell**（建议以普通权限即可；若策略限制，按需调整执行策略）。
- **Flutter SDK**：用于构建 Windows 桌面前端。
- **Python** 与仓库内 **虚拟环境**（`.venv`）：后端打包依赖常见于此。
- **Inno Setup**：仅在需要生成 **安装程序（`-Installer`）** 时使用；脚本会尝试在常见安装路径查找 `ISCC.exe`。

具体依赖与完整构建流水线以 `build_win.ps1`、`build_win_installer.ps1` 为准。

---

## 用法

在 **仓库根目录** 下执行（推荐）：

```powershell
cd <你的Owlangs仓库根目录>
.\tools\build\build_win_pro.ps1
```

### 模式一：目录包（默认）

不附带 `-Installer` 时，脚本调用：

`build_win.ps1 --lite -Frontend windows -IncludePandoc -Edition Pro`

成功后，校验逻辑期望在：

`build\win\Owlangs-<版本号>\`

中存在关键文件之一，例如：

- `bin\Owlangs-win.exe`，或  
- `launcher\OwlangsLauncher.exe`

（版本号通常来自后端 `backend.__version__` 或 `backend/__init__.py`。）

### 模式二：安装程序

生成 Inno Setup 安装包：

```powershell
.\tools\build\build_win_pro.ps1 -Installer
```

此时会调用 `build_win_installer.ps1`，校验期望在 `build\installer\` 下能找到例如：

- `Owlangs-Installer-<版本>.exe`，或  
- `Owlangs-Standard-<版本>-x64.exe`（Pro 版的备选命名，见 `verify_build.ps1`）

---

## 输出与失败排查

| 现象 | 可检查项 |
|------|-----------|
| 脚本立即报错退出 | 查看控制台最前面的 Flutter / Python / Inno 报错；确认在**仓库根**执行，路径为 `.\tools\build\build_win_pro.ps1`。 |
| `Verify: Package dir not found` | 确认 `build_win.ps1` 是否完整执行成功，`build\win` 下是否生成 `Owlangs-<版本>`。 |
| `Verify: Installer not found` | 确认已安装 Inno Setup，且 `build_win_installer.ps1` 阶段无错误；查看 `build\installer` 目录。 |
| 版本同步警告 | `sync_version.ps1` 失败时多为路径或权限问题，可按日志修复后重试。 |

---

## 与其他脚本的关系

- **`build_win_pro.ps1`**：仅 **Pro + lite + Windows 桌面 + Pandoc** 的快捷入口，不带额外参数扩展。
- 需要 **Enterprise**、**Web + 桌面双前端**、单独 **full** 包等，请直接使用 **`build_win.ps1`** 或 **`build_win_enterprise.ps1`** 等脚本并阅读其注释。

---

## Verify（自检清单）

1. 在仓库根目录执行：`.\tools\build\build_win_pro.ps1`，确认结束时提示 **Pro edition build finished and verified**。  
2. 检查 `build\win\Owlangs-<版本>\` 下是否存在 `bin\Owlangs-win.exe` 或 `launcher\OwlangsLauncher.exe`。  
3. 若使用 `-Installer`，检查 `build\installer\` 下是否生成预期的 `.exe`。  
4. 若失败，从日志中向上追溯第一个非零退出步骤（Flutter 构建、PyInstaller、Inno 等）并针对性修复。
