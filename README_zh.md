# Owlangs

面向需要**准确、保格式**文档翻译的专业场景的 AI 翻译平台，支持多种文档类型。**可完全私有化部署**（本地后端、Ollama 或其它 OpenAI 兼容端点），也可对接云端大模型服务。

> English: [README.md](README.md)

## 功能概览

### 📄 多格式翻译

- **15+ 种格式**：DOCX、PPTX、PDF、Markdown、HTML、EPUB、MOBI、XLSX、JSON、SRT、Qt `.ts`、图片等
- **格式保留**：在译文中尽量保持原版式、布局与样式
- **文本模式**：支持纯文本快速翻译
- **实时预览**：按片段查看译文并支持逐段编辑
- **撤销 / 重做**：完整的编辑历史与撤销重做

### 🤖 AI 平台与模型

- 在 `configs/platforms.json` 中预置 **27+** 类平台配置，覆盖主流云端 API **与自建方案**：
  - **本地 / 自建**：OpenAI 兼容（`local`）、**Ollama**、可选 Anthropic 兼容本地端、解析管线用的 **MinerU** / **Mineru_local** 等
  - **云端示例**：OpenAI、Azure OpenAI、Anthropic、Google Gemini、DeepSeek、DashScope、火山方舟、智谱、Groq、Together、Mistral、Cohere、xAI、硅基流动、DMX API、OpenRouter、腾讯混元、百度、月之暗面、Aleph Alpha、Rinna、Naver 等
- **自定义平台**：通过 `local` 等 profile 接入任意 OpenAI 兼容 API（Base URL + 模型 + 可选 API Key）
- **集中管理**：在设置中统一管理 API Key 与相关配置
- **快速切换**：可在不同 AI 提供商之间切换使用

### 📚 术语表（词汇表）

- **自动生成**：从文档中抽取并生成术语表
- **手动维护**：完全可控地创建与编辑术语表
- **多术语表**：同一项目可挂载多份术语表，覆盖更全面
- **一致性**：在多次翻译中保持术语翻译一致

### 🔒 隐私与脱敏

- **文档脱敏**：翻译前自动识别并脱敏敏感信息
- **实体识别**：实体识别与管理能力
- **敏感数据保护**：保护个人信息、财务数据等敏感内容
- **可配置规则**：按需配置脱敏规则

### 💼 工作台与任务

- **多任务工作台**：同时管理多个翻译项目
- **流程化组织**：适合复杂翻译项目的流程化编排
- **状态持久化**：自动保存与恢复任务状态
- **版本管理**：跟踪与管理不同版本的译文
- **任务历史**：完整的翻译活动记录

### 🌐 跨平台

- **Windows**：原生桌面应用
- **macOS**：原生桌面应用（部分打包形态含菜单栏流程）
- **Linux**：原生桌面应用
- **Android**：移动应用（规划中）
- **iOS**：移动应用（规划中）
- **Web**：浏览器访问随包提供的 Flutter Web 界面

### 🌙 界面与体验

- **深色模式**：完整深色主题
- **多语言界面**：界面支持多种语言
- **清晰布局**：简洁有序的用户界面
- **响应式布局**：适配不同屏幕尺寸

## 适用场景

- **译员与翻译机构**：专业翻译流程与术语管理
- **内容创作者**：文档、博客与内容的本地化
- **企业**：多语言内容与文档管理
- **开发者**：软件文档与界面文案翻译
- **隔离网或强隐私环境**：本地 LLM（如 Ollama）与本地解析（按配置）下的私有化部署

## 快速开始

### 环境要求

- **Python 3.11+**（精确约束见 `pyproject.toml`）
- **Redis**（推荐用于会话等；若不用默认配置，请在 `configs/local.json` 中配置）
- 所选云端 AI 的 API Key，**或** 已运行的 **Ollama** / 其它 OpenAI 兼容本地服务，以搭建可完全离线的翻译栈

### 安装步骤

1. 克隆本仓库  
2. 创建虚拟环境并安装后端依赖（`pip install -e .` 或按内部打包规范）  
3. 将 `configs/*.json.template` 复制为 `configs/*.json`（按需）并填写密钥（见下文 **配置**）  
4. 在 Web 界面中配置 AI 平台，或直接编辑 `configs/platforms.json`  
5. 启动后端（例如 `python -m backend.cli -i`），在浏览器中打开应用  

### 默认登录（首次自建）

当 **`configs/local_users.json` 中尚无任何用户** 时，后端会在启动时创建默认超级管理员：

| 项 | 默认值 |
|----|--------|
| 用户名 | `admin`（可通过 `DEFAULT_USERNAME` / 认证配置覆盖） |
| 密码 | `Changeme` |

**首次登录后请立即修改密码。** 若安装包已预置 `local_users.json`，请以该版本随附的说明为准。

部署路径、配置文件布局及**中文运维说明**见 **[backend/config/README.md](backend/config/README.md)**。

本地默认访问地址（常见开发 / 打包启动器）：**http://127.0.0.1:8800**（端口以实际配置为准）。

#### Windows 安装包

| 安装包 | 架构 | 适用 | 约体积 |
|--------|------|------|--------|
| `Owlangs-Installer-{ver}.exe` | x64（64 位） | Windows 10/11 | ~180 MB |

#### macOS 安装包

请根据 Mac 芯片选择对应安装包：

| 安装包 | 架构 | 适用 | 约体积 |
|--------|------|------|--------|
| `Owlangs-{ver}-mac-arm64.dmg` | Apple Silicon (M1/M2/M3/M4) | M 系列 Mac | ~170 MB |
| `Owlangs-{ver}-mac-x86_64.dmg` | Intel 64 位 | Intel Mac | ~180 MB |
| `Owlangs-{ver}-mac-universal2.dmg` | Universal（arm64 + x86_64） | 团队分发 / 不确定机型 | ~330 MB |

**如何选择：**

- **arm64**：Apple Silicon 首选，体积小、原生性能；**不能**在 Intel Mac 上运行。  
- **x86_64**：Intel Mac 首选；在 Apple Silicon 上需 Rosetta 2。  
- **universal2**：**同时**支持 Apple Silicon 与 Intel，适合多人多机型或不确定芯片时使用；体积约为单一架构的两倍。  

#### 备用下载（百度网盘）

若 GitHub Release 下载较慢，可使用百度网盘：

- **链接**：https://pan.baidu.com/s/1w_ZIBnD5lFVl8XjbUG_1aw  
- **提取码**：`78rp`  

### 使用应用（简要流程）

1. **上传文档**：选择文件或粘贴文本  
2. **选择 AI 平台**：选择云端或本地翻译服务  
3. **配置参数**：目标语言及翻译相关选项  
4. **生成术语表**（可选）：由系统自动抽取术语  
5. **开始翻译**  
6. **审阅与编辑**：按需修改片段  
7. **下载**：导出译文文档  

## 配置说明

- **系统、平台、密钥与用户** 位于 **`configs/`**（模板为 `*.json.template`）。请勿将真实的 `secrets.json` 或生产环境 `local_users.json` 提交入库。  
- 字段说明、功能开关（如 DOCX 公式修复）及更多中文文档：**[backend/config/README.md](backend/config/README.md)**  

### AI 平台

在设置界面配置 API Key 与端点，或编辑 `configs/platforms.json`。本地类 profile（`local`、`ollama` 等）在服务不要求鉴权时可无需云端 Key。

### 术语表

在术语表设置中创建与管理。支持：

- 导入已有术语表  
- 从文档生成术语表  
- 手动增删改条目  
- 将术语表绑定到具体项目  

### 翻译设置

可自定义例如：

- 目标语言  
- 自定义翻译提示词  
- 分块大小与并发（亦可在 `platforms.json` 中按平台配置）  
- 各格式相关选项  

## 许可证

MIT License，详见 [LICENSE](LICENSE)。

## 支持与反馈

1. 查阅 `backend/config/` 及仓库内其它文档  
2. 搜索已有 Issue  
3. 新建 Issue  
4. 联系维护者  

## 社区

交流微信号 Wechat：**zzmaimeng**  
欢迎加入技术交流微信群（群二维码可能过期，可加微信号入群）：

<img src="WeChat_Help_技术交流微信群.png" alt="WeChat Help" width="280">

---

**Owlangs** — 专业 AI 文档翻译，云端或私有化皆可。
