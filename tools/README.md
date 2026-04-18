# Tools

Scripts and docs are grouped into:

- **[build/](build/)** — 打包：Windows 安装包/简单包、Flutter Web/Windows、Launcher、Linux .deb 等。入口文档：[build/README_Windows_Build.md](build/README_Windows_Build.md)。
- **[setup/](setup/)** — 准备工作：版本号同步、pdfium/字体预下载、环境说明等。入口文档：[setup/ENV_SETUP.md](setup/ENV_SETUP.md)。

其他脚本（调试启动、i18n、图标生成等）保留在 `tools` 根目录。

## 常用命令（仓库根目录执行）

| 目的 | 命令 |
|------|------|
| 同步版本号 | `.\tools\setup\sync_version.ps1` |
| 检查版本一致 | `.\tools\setup\sync_version.ps1 --check` |
| Windows 轻量包 | `.\tools\build\build_win.ps1 --lite` |
| Windows 安装器 | `.\tools\build\build_win_installer.ps1 -Lite` |
| Pro/Enterprise 一键包 | `.\tools\build\build_win_pro.ps1`、`.\tools\build\build_win_enterprise.ps1` |

详见 [build/README_Windows_Build.md](build/README_Windows_Build.md) 与 [setup/ENV_SETUP.md](setup/ENV_SETUP.md)。
