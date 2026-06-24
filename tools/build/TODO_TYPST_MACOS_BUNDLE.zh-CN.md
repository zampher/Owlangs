# TODO: macOS Typst 内嵌二进制方案

> 状态：**暂缓** — 当前采用 Homebrew 安装，与 Redis / Pandoc / XeLaTeX 一致。  
> 创建日期：2026-06-24

## 背景

PDF 原位翻译（`typst_overlay` 渲染器）依赖 **Typst CLI**。Windows 侧可将 `typst.exe` 放入 `3rdParty/windows/typst-*/` 并随安装包分发；macOS 目前通过 `brew install typst` 解决。

后端解析逻辑见 `backend/layout/pdf_renderer/typst_overlay/compiler.py`：

1. 环境变量 `TYPST_BIN`
2. 系统 `PATH` 中的 `typst`
3. `3rdParty/` 目录（已支持，但未在 macOS 构建流程中打包）

## 当前方案（Homebrew）

- 安装脚本：`tools/setup/install_dependencies_macos.sh`（构建时同步到 `3rdParty/macos/install_dependencies.sh`）
- MenuBar「Check Dependencies」检查 `typst` 命令
- 启动 backend 时注入 Homebrew / TeX PATH，避免 GUI 进程 PATH 过短找不到 typst

手动安装：

```bash
brew install typst
typst --version
```

## 未来可选：内嵌二进制（与 Windows 对齐）

若需离线安装或避免用户安装 Homebrew，可考虑：

| 任务 | 说明 |
|------|------|
| 下载 release 二进制 | `typst-aarch64-apple-darwin.tar.xz` / `typst-x86_64-apple-darwin.tar.xz` |
| 目录布局 | `3rdParty/macos/typst-<arch>/typst` |
| `build_macos.sh` | 按 `--arm64` / `--x86_64` / `--dual-arch` 复制到 `Owlangs.app/Contents/Resources/3rdParty/` |
| MenuBar | 可选：优先使用 bundle 内 typst，再 fallback 到 PATH |
| universal2 | 两套二进制或运行时按 `uname -m` 选择 |
| Typst 包缓存 | 首次编译需联网下载 `@preview/cmarker`、`@preview/mitex`；离线需预缓存 |
| 体积 | 每个架构约 12–14 MB |

## 决策参考

| 维度 | Homebrew | 内嵌二进制 |
|------|----------|------------|
| 与现有 macOS 依赖策略 | ✅ 一致 | ❌ 需单独维护 |
| 离线 / 无 brew 用户 | ❌ | ✅ |
| GUI 启动 PATH 问题 | 需注入 PATH | bundle 路径更稳 |
| 维护成本 | 低 | 中（版本、多架构） |

## 相关文件

- `backend/layout/pdf_renderer/typst_overlay/compiler.py` — Typst 路径解析
- `tools/build/OwlangsMenuBar.py` — 依赖检查与 backend 环境
- `tools/setup/install_dependencies_macos.sh` — Homebrew 安装脚本
- `tools/build/build_macos.sh` — 同步脚本到 app bundle
