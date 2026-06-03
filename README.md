# Owlangs

> 中文说明：[README_zh.md](README_zh.md)

A powerful AI-powered document translation platform designed for professionals who need accurate, format-preserving translations across a wide range of document types. **You can run it fully on-premise** (local backend, Ollama, or other OpenAI-compatible endpoints) or connect to cloud AI providers.

<img width="1000" height="1000" alt="40db738c439a580cc6fa49c0b3b0fc86" src="https://github.com/user-attachments/assets/131afdf3-c0a2-4b1f-a4a3-03c170b678d8" />


## Key Features

### Multi-Format Support with High-Fidelity Layout
- **15+ formats**: PDF, DOCX, XLSX, PPTX, HTML, TXT, PNG, EPUB, MOBI, and more
- **Layout preservation**: Maintains original formatting, layout, and styles in translated output
- **Large files**: Handles massive PDFs and e-books with automatic split-file processing

### 20+ AI Platform Integrations
- Major cloud providers: OpenAI, Claude, DeepSeek, Google Gemini, and more
- Self-hosted options: Ollama, local OpenAI-compatible endpoints

### Precision Translation Control
- **Segment-level editing**: Review and refine individual translation segments
- **Bilingual reading**: Side-by-side source and target text comparison
- **Bilingual export**: Generate bilingual documents for review and collaboration

### Smart Glossary Management
- **Auto-detection**: Automatically identify and extract terminology from documents
- **Glossary import**: Import CSV glossaries and TBX professional terminology databases
- **Consistency**: Maintain terminology consistency across all translations

### Flexible Deployment
- **Cross-platform**: Windows, macOS, Linux desktop apps + Web access
- **On-premise**: Fully local deployment with no external network required
- **Team collaboration**: Domain controller integration for enterprise environments

### Batch Processing & Queue Management
- **Batch import**: Import multiple files or ZIP archives at once
- **Translation queue**: Manage, prioritize, and track all translation tasks
- **Re-edit tasks**: Re-enter completed tasks in the queue for revision and editing
- **Batch export**: Export multiple tasks in a single archive, preserving original relative paths

### Integration
- **MCP & CLI**: Integrates with mainstream AI agent frameworks
- **Document pre-processing**: Prepare documents for knowledge base construction


<img width="1000" height="477" alt="image001" src="https://github.com/user-attachments/assets/0c4e42f6-5ed1-41c1-9db6-c5b4c57871b9" />

## Features

### 📄 Multi-Format Translation

- **15+ Supported Formats**: DOCX, PPTX, PDF, Markdown, HTML, EPUB, MOBI, XLSX, JSON, SRT, Qt `.ts`, images, and more
- **Format Preservation**: Maintains original formatting, layouts, and styles in translated documents
- **Text Mode**: Quick translations for plain text input
- **Real-time Preview**: View translation results with segment-by-segment editing
- **Undo/Redo**: Full editing history with undo and redo functionality

### 🤖 AI Platform Flexibility

- **20+ Preconfigured Platform Profiles** in `configs/platforms.json`, including major cloud APIs **and self-hosted options**:
  - **Local / self-hosted**: OpenAI-compatible (`local`), **Ollama**, optional Anthropic-compatible local, **MinerU** / **Mineru_local** for parsing pipelines
  - **Cloud examples**: OpenAI, Azure OpenAI, Anthropic, Google Gemini, DeepSeek, DashScope, VolcEngine ARK, Zhipu, Groq, Together, Mistral, Cohere, xAI, SiliconFlow, DMX API, OpenRouter, Tencent Hunyuan, Baidu, Moonshot, Aleph Alpha, Rinna, Naver, and more
- **Custom Platform Support**: Integrate any OpenAI-compatible API via the `local` profile (base URL + model + optional API key)
- **Centralized Management**: Unified API key and configuration management in settings
- **Easy Switching**: Seamlessly switch between different AI providers

### 📚 Intelligent Glossary Management

- **Automatic Generation**: Automatically extract and generate glossaries from documents
- **Manual Creation**: Create and edit glossaries manually with full control
- **Multi-Glossary Support**: Use multiple glossaries per project for comprehensive terminology coverage
- **Consistency**: Ensure terminology consistency across all translations

### 🔒 Privacy & Anonymization

- **Document Anonymization**: Automatically identify and anonymize sensitive information before translation
- **Entity Recognition**: Advanced entity recognition and management
- **Sensitive Data Protection**: Protect personal information, financial data, and other sensitive content
- **Customizable Rules**: Configure anonymization rules to match your specific requirements

### 💼 Workspace & Task Management

- **Multi-Task Workspace**: Manage multiple translation projects simultaneously
- **Flow-Based Architecture**: Organized workflow for complex translation projects
- **State Persistence**: Automatic task state saving and recovery
- **Version Management**: Track and manage different versions of your translations
- **Task History**: Complete history of all translation activities

### 🔌 Integration & Extensibility

- **MCP & CLI**: Integrate with mainstream AI agent frameworks for automated workflows
- **Document Pre-Processing**: Prepare documents for knowledge base construction and RAG pipelines
- **PBX Support**: Import and export PBX professional terminology databases

### 🌐 Cross-Platform Access

- **Windows**: Native desktop application
- **macOS**: Native desktop application (including menu bar workflows where packaged)
- **Linux**: Native desktop application
- **Android**: Mobile application (TBD)
- **iOS**: Mobile application (TBD)
- **Web**: Browser-based access to the bundled Flutter Web UI
- **Team Collaboration**: Domain controller integration for enterprise environments

### 🎨 User Experience

- **Dark Mode**: Full dark mode support for comfortable viewing
- **Multi-Language Interface**: Interface available in multiple languages
- **Intuitive Design**: Clean and organized user interface
- **Responsive Layout**: Optimized for different screen sizes

## Use Cases

Owlangs is suitable for:

- **Translators and Translation Agencies**: Professional translation workflows with terminology management
- **Content Creators**: Localizing documentation, blogs, and content
- **Businesses**: Managing multilingual content and documentation
- **Developers**: Translating software documentation and user interfaces
- **Air-gapped or privacy-sensitive environments**: On-premise deployment with local LLMs (e.g. Ollama) and local parsing when configured

## Getting Started

### Prerequisites

- **Python 3.11+** (see `pyproject.toml` for the exact constraint)
- **Redis** (recommended for sessions; configure in `configs/local.json` if not using defaults)
- API keys for your chosen cloud AI provider(s), **or** a running **Ollama** / OpenAI-compatible local service for fully offline-capable translation stacks

### Installation

1. Clone the repository
2. Create a virtual environment and install backend dependencies (`pip install -e .` or follow your internal packaging guide)
3. Copy `configs/*.json.template` to `configs/*.json` where needed and set secrets (see **Configuration** below)
4. Configure AI platforms in the web UI or edit `configs/platforms.json`
5. Launch the backend (e.g. `python -m backend.cli -i`) and open the app in the browser

### Default login (first self-hosted install)

When **`configs/local_users.json` has no users yet**, the backend creates a default super-admin on startup:

| Field | Default |
|--------|---------|
| Username | `admin` (overridable via `DEFAULT_USERNAME` / auth config) |
| Password | `Changeme` |

**Change this password immediately after first login.** If your installer ships a pre-populated `local_users.json`, use the credentials provided with that release instead.

For deployment paths, config file layout, and a Chinese-language operations guide, see **[backend/config/README.md](backend/config/README.md)**.

Default local URL (typical dev / packaged launcher): **http://127.0.0.1:8800** (port may vary).

#### Windows Download Packages

| Package | Architecture | Recommended For | File Size |
|---------|-------------|-----------------|-----------|
| `Owlangs-Installer-{ver}.exe` | x64 (64-bit) | Windows 10/11 | ~180 MB |

#### macOS Download Packages

When downloading the macOS release, choose the package that matches your Mac:

| Package | Architecture | Recommended For | File Size |
|---------|-------------|-----------------|-----------|
| `Owlangs-{ver}-mac-arm64.dmg` | Apple Silicon (M1/M2/M3/M4) | M-series Macs | ~170 MB |
| `Owlangs-{ver}-mac-x86_64.dmg` | Intel 64-bit | Intel-based Macs | ~180 MB |
| `Owlangs-{ver}-mac-universal2.dmg` | Universal (arm64 + x86_64) | Shared across teams / unsure | ~330 MB |

**Choosing the right package:**

- **arm64** — Best for Apple Silicon Macs. Smallest size, native performance. Does **not** run on Intel Macs.
- **x86_64** — Best for Intel Macs. Smallest size for Intel. Requires Rosetta 2 on Apple Silicon.
- **universal2** — Works on **both** Apple Silicon and Intel Macs. Convenient if you distribute the app to multiple users with different Mac models, or are unsure which Mac you have. Roughly double the size.

#### Alternative Download (Baidu Netdisk)

If the GitHub release download is slow, you can also download from Baidu Netdisk:

- **Link**: https://pan.baidu.com/s/1w_ZIBnD5lFVl8XjbUG_1aw
- **Extraction Code**: `78rp`

### Quick Start (using the app)

1. **Upload a Document**: Select a document file or paste text
2. **Choose AI Platform**: Select your preferred AI translation service (cloud or local)
3. **Configure Settings**: Set target language and translation parameters
4. **Generate Glossary** (optional): Let the system automatically extract terminology
5. **Translate**: Start the translation process
6. **Review & Edit**: Review results and make adjustments as needed
7. **Download**: Export your translated document

## Configuration

- **System, platforms, secrets, and users** live under **`configs/`** (see templates `*.json.template`). Do not commit real `secrets.json` or production `local_users.json`.
- Detailed field notes, feature flags (e.g. DOCX math repair), and Chinese documentation: **[backend/config/README.md](backend/config/README.md)**

### AI Platform Setup

Configure API keys and endpoints in the settings UI or edit `configs/platforms.json`. Local profiles (`local`, `ollama`, etc.) support deployment without cloud keys when your service does not require authentication.

### Glossary Management

Create and manage glossaries through the glossary settings. You can:

- Import existing glossaries
- Generate glossaries from documents
- Manually add and edit terminology entries
- Assign glossaries to specific projects

### Translation Settings

Customize translation behavior:

- Target language selection
- Custom translation prompts
- Chunk size and concurrency (also configurable per platform in `platforms.json`)
- Format-specific options

## License

MIT License - see [LICENSE](LICENSE) file for details

## Support

For issues, questions, or contributions:

1. Check the documentation under `backend/config/` and repository docs
2. Search existing issues
3. Create a new issue
4. Contact the maintainers

## Community

交流微信号Wechat：zzmaimeng

<img width="280" alt="47172c0cb3a72190acf77a48417f425e" src="https://github.com/user-attachments/assets/fd3edadf-bbff-4494-bc53-f0e966999e64" />

欢迎加入技术交流微信群（有时会过期，可加微信号）：

<img src="WeChat_Help_技术交流微信群.png" alt="WeChat Help" width="280">

---

**Owlangs** — Professional AI-powered document translation, cloud or on-premise.
