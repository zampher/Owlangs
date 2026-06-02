# 配置管理系统

## 概述

Owlangs 使用分层配置：仓库或安装目录下的 **`configs/`** 存放系统与服务配置；认证与用户档案分层管理，便于本地部署与私有化运维。

## 部署后默认登录（重要）

在 **`configs/local_users.json` 中尚未写入任何用户**（首次启动、用户存储为空）时，后端会在启动阶段自动创建默认超级管理员：

| 项目 | 默认值 | 说明 |
|------|--------|------|
| **用户名** | `admin` | 可通过环境变量 `DEFAULT_USERNAME`，或 `configs/local.json` 中的认证相关配置覆盖 |
| **密码** | `Changeme` | 由 `UnifiedUserStore.ensure_default_admin_if_empty` 在首次安装时使用 |

**请注意：**

- 若安装包或脚本已生成 **预置的 `configs/local_users.json`**（内含用户与密码哈希），则**不会**自动创建上述账户，请使用发行说明或安装向导提供的账号；登录后请尽快修改密码。
- **首次登录后务必修改默认密码**，并在生产环境中妥善保管 `secrets.json`、`local_users.json`。
- 若在 `local.json` 中启用密码恢复相关选项，恢复逻辑会将默认管理员密码重置为 **`Changeme`**（与 `backend/auth/password_recovery.py` 一致）。

默认 Web 入口（本地）：**http://127.0.0.1:8800**（端口以实际启动参数为准）。

## 本地部署与云平台

- **支持完全本地部署**：后端可直接在本机运行（如 `python -m backend.cli -i`）；AI 侧可使用 **Ollama**、兼容 OpenAI 的本地网关（`local`）、可选的自托管解析（如 **MinerU** 本地等）。
- **`configs/platforms.json`** 中预置多条平台条目，涵盖云端 API 与本地/自托管场景；其中面向本地或离线场景的示例包括：`local`（OpenAI 兼容）、`ollama`、`anthropic_local`、`mineru`、`mineru_local` 等，按需填写 URL、模型名与密钥即可。
- **预置 LLM/解析类平台条目数量**：以仓库内 `configs/platforms.json` 的 `"platforms"` 对象为准（当前版本一般为 **约 27** 个独立平台 key；新增或删减平台时以此文件为准，README 不逐一罗列）。

## 配置架构

### 1. 系统配置目录（`configs/`）

与打包、路径解析相关的文件通常位于：

| 文件 | 用途 |
|------|------|
| `system.json` | 系统级行为、解析引擎、日志等 |
| `platforms.json` | AI 平台、模型、并发、分块等 |
| `secrets.json` | 敏感信息（API Key 等），勿提交版本库 |
| `local.json` | 本机/部署环境：Redis、会话、LDAP、认证默认值等 |
| `local_users.json` | 本地用户与角色（与统一用户存储配合） |
| `app_config.json` | 应用级补充配置（若使用） |
| `*.json.template` | 各配置模板，首次部署可从模板复制 |

实际路径由 `utils.path_utils` 按是否安装到系统目录、环境变量等解析，开发时多为项目根下 **`configs/`**。

### 2. 用户配置模板

- **目录**：`backend/config/templates/`
- **统一用户档案模板**：`default_profile.json`（新用户初始化时参考；具体以产品逻辑为准）
- 模板中的 UI 语言、翻译工作流、分块、并发等均有默认值，可在应用内由用户或管理员调整。

### 3. 用户实际配置

- **目录**：`user_profiles/`
- **文件格式**：`{username}_profile.json`（若当前版本仍启用该目录）
- 权限上，各用户通常仅能修改自己的档案；敏感凭据仍应放在 `secrets.json` 或平台配置中，而非用户档案内。

## 配置管理工具

项目内提供 **`backend/config/profile_manager.py`** 用于用户配置管理（请从项目根或 `backend` 在 `PYTHONPATH` 下执行）：

```bash
# 示例：在仓库根目录
python backend/config/profile_manager.py list
python backend/config/profile_manager.py create --username <username>
python backend/config/profile_manager.py delete --username <username>
python backend/config/profile_manager.py backup --username <username>
python backend/config/profile_manager.py restore --username <username>
python backend/config/profile_manager.py info --username <username>
python backend/config/profile_manager.py validate --username <username>
```

### system.json `features`（节选）

- **`auto_docx_math_fragment_llm_repair`**（默认 `false`）：在翻译结束后的后处理阶段，对 **`markdown_based`** 任务（如 PDF/MD 等）若已配置有效的 **`llm_config_for_repair`**，是否**自动**执行 Pandoc 片段级 DOCX 检测并用 LLM 修复。关闭时仍可在客户端使用「AI 修复 DOCX 公式」**手动**触发（接口：`POST /service/translation-segments/{task_id}/repair-docx-math-fragments`）。

## 配置更新流程（简要）

1. 修改 **`configs/`** 下对应 JSON 或模板后，按部署方式重启服务或等待热加载策略生效。
2. 新增用户时，系统可按模板初始化用户档案；升级模板后，已有用户可能需要迁移或重新生成档案（视版本说明而定）。
3. 管理员在界面中修改的全局/平台设置，应写回对应配置文件或由应用持久化，请勿只改模板而忽略运行实例。

## 安全考虑

- API 密钥等仅应存放在 **`secrets.json`** 及平台配置中，勿写入用户档案或公开仓库。
- 默认账号 **`admin` / `Changeme`** 仅适用于空用户库的首次启动；生产环境必须修改。
- 支持配置备份；`local_users.json` 与 `secrets.json` 需限制文件权限（如仅服务账户可读）。

## 故障排除

### 配置文件损坏或缺失

- 从同目录的 **`*.template`** 复制并重命名为对应配置文件，再填入本地值。
- 用户档案可使用 `profile_manager.py validate` / `restore`（若适用）。

### 无法登录

- 确认 `configs/local_users.json` 是否存在且格式正确。
- 若为首次部署且文件为空，重启服务后应生成默认 `admin` / `Changeme`；若已有预置用户，请使用预置密码或走管理员重置流程。

### 权限问题（Linux/macOS）

```bash
chmod 755 user_profiles/
chmod 644 user_profiles/*.json 2>/dev/null || true
chmod 640 configs/secrets.json configs/local_users.json 2>/dev/null || true
```
