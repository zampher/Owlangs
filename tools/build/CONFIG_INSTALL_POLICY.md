# 安装时配置文件处理策略 (Config Install Policy)

## 结论

- **安装/升级时，除 `secrets.json` 外，所有随安装包提供的配置文件都会在目标目录被强制覆盖（`Copy-Item -Force`）。**
- 这样可以在**配置文件版本/结构升级**时，让用户环境拿到新版本的 `system.json`、`platforms.json`、`*.template` 等，避免旧结构导致运行异常。
- `secrets.json` 不随安装包分发，由后端在运行时按模板生成或合并，用户 API Key 等不会在安装时被覆盖。

## 流程概览

### 1. 打包阶段 (build_win_desktop.ps1)

- 从仓库 `configs/` 复制到安装包目录 `config/`：
  - **排除** `secrets.json`（不打包）。
  - 其余全部复制：`system.json`、`system.json.template`、`platforms.json`、`platforms.json.template`、`local.json`、`local.json.template`、`app_config.json`、`local_users.json`、`ai_platform_status.json` 等。
- 安装包内没有 `secrets.json`，只有 `secrets.json.template`（若存在）。

### 2. 安装阶段 (installer.nsi)

- 目标目录：`C:\ProgramData\Owlangs\configs`。
- 用 PowerShell 脚本把 `$INSTDIR\config\` 下**所有文件**复制到上述目录：
  - 使用 **`Copy-Item ... -Force`**，即**强制覆盖**已存在的同名文件。
- 复制完成后删除 `$INSTDIR\config`，避免运行时误用安装目录下的 config。

### 3. 不参与覆盖的文件

- **secrets.json**：不在安装包中，安装时不会覆盖；若不存在则由后端从 `secrets.json.template` 生成，若已存在则后端启动时用模板结构做合并（保留原有 KEY，见 `SecretsManager._maybe_merge_with_template`）。

## 为何要强制覆盖

- 版本升级时，`system.json`、`platforms.json` 等可能新增字段或调整结构；若不覆盖，用户可能一直用旧版配置，导致缺字段或解析错误。
- 强制覆盖可保证**安装后使用的默认/模板配置与当前安装包版本一致**；用户若需保留本地修改，需在升级前自行备份，或依赖后续产品提供的“配置迁移/合并”逻辑（目前 secrets 已有合并逻辑）。

## 相关文件

| 文件 | 作用 |
|------|------|
| `tools/build/installer.nsi` | 生成 `copy_configs.ps1`，执行 `Copy-Item -Force` 到 `C:\ProgramData\Owlangs\configs` |
| `tools/build/build_win_desktop.ps1` | 打包时复制 `configs/*` 到 `config/`，排除 `secrets.json` |
| `backend/config/secrets_manager.py` | 启动时用模板合并已有 `secrets.json`，保留旧 KEY |
