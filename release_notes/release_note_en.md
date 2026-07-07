# Owlangs Release Notes (English)

## Owlangs 1.5.2.0

### New Features

1. **Editable bbox and text for multi-block paragraphs**: In layout-preserving PDF translation, when a single logical paragraph spans multiple layout text blocks (e.g. two columns or cross-page), you can edit bbox and translated text per block; changes apply to preview and export.
2. **Segment rotation and auto-rotation**: In PDF preview editing, manually set rotation for text segments; optionally auto-detect and rotate tall narrow sideways text blocks by bbox aspect ratio (threshold and angle configurable in the toolbar; enabled by default).

### Bug Fixes

1. **Hunyuan model API URL**: Updated the Hunyuan (TokenHub) model API endpoint to fix 401 failures on list-models and related calls.
2. **Intermittent PDF download failure**: Fixed occasional failures when exporting or downloading PDFs.

---

## Owlangs 1.5.1.0

### Bug Fixes

1. **Missing overlay for some PDF segments**: Fixed an issue where certain segments that failed translation were not rendered in layout-preserving exported PDFs, leaving blank areas.
2. **Preview tab switch crash**: Fixed a frontend crash when closing one preview tab and activating another after enabling preview editing in the PDF translation workflow.
3. **Non-ASCII filename export failure**: Fixed intermittent export failures when PDF filenames contain non-ASCII characters (e.g. Chinese), caused by HTTP `Content-Disposition` header latin-1 encoding limits.
4. **Missing formula tag numbers**: Fixed an issue where tag/subscript numbers in exported PDF formulas were missing or not displayed correctly.
5. **Inline LaTeX in body text not rendered**: Fixed incorrect rendering of inline LaTeX formulas mixed within body text after PDF translation (e.g. `$^{1}$`, `$P_{c,t}$` shown as plain text).
6. **PaddleOCR local deployment business failure**: Fixed an issue where locally deployed PaddleOCR passed connectivity tests but document parsing (layout recognition) failed at runtime; local endpoint switched to `/layout-parsing` with capability probing and user-facing warnings.
7. **Split cross-column paragraph translation loss**: Fixed an issue where a single logical paragraph split across multiple bboxes on the same page (e.g. two-column layout) only received translation in the first block while the second still showed source text, or caused duplicate rendering/overflow; improved Paddle same-page cross-column pairing and deep-split paragraph-to-block mapping.

---

## Owlangs 1.5.0.0

### New Features

1. **Layout-preserving PDF preview, editing, and download**: For layout-preserving PDF translation tasks, view original and translated PDFs side-by-side with the segment list. Supports segment filtering, batch font adjustments, linked scrolling, and **Follow segment page** for segment-by-segment review with live layout preview. The download panel also offers layout-preserving translated document export.
2. **Task management page**: Manage each uploaded task (list and download). For batch jobs, download all completed results as a package or download individual translated files. Quick selection for all files in a batch is supported. When starting a batch, you can enter a batch remark for later batch selection by remark.
3. **Console config shortcuts**: Added **Clear** and **Restore defaults** buttons on the console.
4. **PaddleOCR configuration**: Added PaddleOCR-related configuration options.

### Optimizations

1. **PDF chart recognition and parsing**: Improved recognition and parsing of charts in PDF documents.
2. **Glossary templates and help**: Added template download and help information in the glossary section.
3. **Dedicated prompt settings page**: Moved prompt configuration from Quick Settings to a standalone page for easier management.

### Bug Fixes

1. **Image file translation export**: Fixed an issue where exported results from image file translation showed text only and missing images.

---

## Owlangs 1.4.0.0

### New Features

1. **Bilingual document export**: Support exporting bilingual documents.
2. **Batch document upload**: Support uploading folders with recursive extraction of compressed archives inside, then adding all files to the translation queue.
3. **Multi-select and batch download in task queue**: In the task queue, users can multi-select tasks and batch download processed documents by type; downloaded documents retain the original folder directory structure.
4. **Task statistics and relative path**: In task management, display success/failure segment statistics for each translated task, and show the document's relative path.
5. **MCP interface**: Implemented MCP interface supporting document translation, document format conversion, and more.
6. **CLI interface**: Implemented CLI interface allowing users to perform format conversion and translation locally via command line.
7. **PBX glossary import/export**: Support importing and exporting glossaries in PBX format.
8. **MinerU local model versions**: Support configuring 5 model versions for locally deployed MinerU.
9. **Configurable segment count per LLM API call**: Support configuring the maximum number of translation segments processed per LLM API call, adjustable based on the model's processing capability.
10. **Auto-retry failed segments after translation**: After translation completes, automatically detect failed segments (source text unchanged) and trigger retranslation; defaults to 2 retry rounds, configurable by the user.
11. **Default target language and export suffix settings**: Added default target language setting in translation settings; export filename suffix is now configurable (defaults: _translated/_converted).
12. **Portable edition includes both desktop and web frontends with configurable auto-start**: The portable edition now includes both the desktop frontend and web frontend, and it can be configured for auto-start via the Launcher.

### Optimizations

1. **Portable edition multi-file layout**: Changed portable edition from single-file to multi-file to reduce startup time.
2. **Removed heading font size processing in PDF export**: Cancelled title and subtitle font size processing in exported PDF translation files to avoid font size confusion caused by MinerU incorrectly identifying headings.
3. **Table export defaults to image**: Exported tables now use images by default.
4. **MinerU source language descriptions**: In MinerU's source language options, provide detailed descriptions of languages supported by the selected model.
5. **Home and toolbar button styling**: Optimized the appearance of home page buttons and toolbar buttons.
6. **Translation timeout in LLM settings**: Moved translation timeout configuration into LLM settings so different models can have different timeout values.
7. **Startup config loading optimization**: Shared an inflight future among multiple config file callers at startup to avoid redundant loading and reduce startup time.
8. **Startup stats rendering optimization**: Reused ConfigService's Dio instance for fetching info at startup, preventing translation statistics from stalling for the 30-second timeout before rendering.

### Bug Fixes

1. **Reading mode undo/redo refresh**: In reading mode, undo/redo changes were applied but the frontend did not refresh.
2. **Retry button in labeled review mode**: In the task queue, when entering labeled review mode, the Retry button was unclickable, preventing LLM re-translation of failed segments.
3. **PDF export image option for tables and formulas**: In PDF translation, when selecting image export, tables and formulas were still exported as text.
4. **OpenAI Local communication failure**: Fixed communication failure with OpenAI Local endpoints.
5. **Local user management create user failure**: Fixed create user failure in local user management.

---

## Owlangs 1.3.4.0

### New Features

1. **Dual review modes**: Renamed the original preview modes as follows —
   - **Labeled Review Mode**: Quickly locate failed segments and resend them to the LLM for rapid translation repair
   - **Reading Review Mode**: Side-by-side bilingual reading without labels, more compact layout for manual polishing
2. **Clear queue button**: Added a button to clear all tasks from the task queue
3. **Clear statistics button**: Added a button in Settings to reset translation statistics
4. **Font size control in toolbar**: Added a font size adjuster to the translation review toolbar for easier reading

### Optimizations

1. **Streamlined task list**: Reduced queue entries to two-line compact information with direct buttons to switch between Labeled and Reading review modes
2. **Reorganized toolbar**: Buttons are now grouped by function for easier access
3. **TXT paragraph-based splitting**: Changed TXT segmentation from chunk-based to paragraph-based for better reading-mode layout

### Bug Fixes

1. **False LLM warning during format conversion**: Fixed an erroneous "LLM not configured" prompt when running format-only conversion (e.g. PDF ↔ DOCX) without any LLM configured

---

## Owlangs 1.3.3.0

### New Features

1. **Portable edition**: A new no-install portable version is now available — just download, extract, and run.

### Optimizations

1. **Fetch URL cancellation**: In-progress URL fetch tasks can now be cancelled or interrupted.
2. **UI Look & Feel refresh**: Refined the UI layout and visual styling for a cleaner, more modern look.

### Bug Fixes

1. **Image extraction in Fetch URL**: Fixed an issue where images from fetched Wechat web pages were not being extracted correctly.
2. **Missing translated output after Fetch URL**: Fixed an issue where translated content could not be exported correctly after a URL fetch → translation workflow.

---

## Owlangs 1.3.2.0

### New Features

1. **Queue task editing**: Tasks that are still in memory can now be edited directly from the task queue; tasks no longer in memory can only be downloaded.
2. **GitHub button**: Added a GitHub button to the toolbar for quick access to the latest release downloads.
3. **Flow close confirmation**: When closing a translation flow, the app now asks whether to save the current result to the queue before closing. 
4. **Offline flow close safeguard**: If the connection is lost, the result is automatically saved to the queue by default.

### Bug Fixes

1. **Auth config load failure**: Fixed a configuration loading failure after switching from "no login required" to "local user auth" and restarting the app.

---

## Owlangs 1.3.1.0

### New Features

1. **Web page extraction (Fetch URL)**: Import content by URL. The service fetches the page and extracts body text and images, then you can run format conversion or translation directly. Two extraction modes are available: **Content** (main article text) and **Full HTML** (entire page).

### Optimizations

1. **Removed “Recent activity”** from the home screen. With the **task queue** already surfacing ongoing and finished work, the extra activity strip was redundant and has been dropped for a cleaner home layout.
2. **Exclusion state after “exclude all”**: After excluding every segment and then restoring automatic exclusion, the translate phase no longer keeps a stale “all excluded” state, so translated output no longer incorrectly reflects segments that should be translatable.
3. **MinerU import parameters**: Fixed `convert_engine` not being passed correctly during import. MinerU parsing options and error messages are aligned so import and conversion use the same parser engine configuration.

### Bug Fixes

1. **Queued translation — completed downloads**: For TXT, XLSX, PPTX, EPUB, MOBI (and similar) workflows, when a job reached **completed** in the task queue, the `downloads` map sometimes omitted **`md`** and **`md_zip`** (Markdown and Markdown with images packaged as ZIP) download URLs.
2. **HTML layout and EPUB/MOBI exports**: Exported HTML could render with inconsistent or broken layout, which also affected **EPUB** and **MOBI** built from that HTML. The HTML generation and EPUB/MOBI export pipeline was improved for more consistent layout.
3. **Translation progress bar**: Fixed missing or stuck progress indicators during translation for **TXT**, **SRT**, **QT_TS**, **EPUB**, and **HTML** workflows.

---

## Owlangs 1.3.0.0

Compared with **1.2.1.0**, this release introduces **two translation modes** and a **task queue**: keep the familiar immersive workbench, or switch to **queued** runs and manage jobs centrally.

### New Features

1. **Two translation modes (main change vs 1.2.1)**  
   - **Immersive translation**: Upload, extract, glossary, and side‑by‑side review inside the workspace flow—the same interactive pattern as in 1.2.1.  
   - **Queued translation**: Submit work as queued jobs so the UI is not tied up for the whole run; the server schedules execution while you track status and download outputs from the **task queue**.  
   Use immersive for interactive editing; use queued when you want background execution and centralized tracking.

2. **Task queue (new)**  
   A dedicated **task queue** lists queued and running translation jobs with refresh, cancel/remove actions, and downloads when jobs finish (available formats depend on server configuration). It is the home for results produced through **queued translation**.

3. **Where to start**  
   - **Toolbar**: **Queued translation** sits beside **Immersive translation** for a one‑tap queued submission; **Task queue** opens the full list.  
   - **Task queue page**: Use **Queued translation** to enqueue new work—same behavior as the toolbar.  
   - **Queued translation (standalone screen)**: **Back to task queue** via toolbar or system back; if edits are not persisted to the queue snapshot, you are prompted to **save**, **leave without saving**, or **stay**.

### Fixes & Stability

1. **DOCX rebuild**: Refined segment metadata and paragraph targeting so exported/rebuilt documents behave more reliably in edge layouts.

---

## Owlangs 1.2.1.0

### Optimizations

1. **Large PDFs and MinerU limits**: When a PDF exceeds MinerU’s per-request limits, Owlangs can **split** it first (by pages or size) and send segments sequentially. Split granularity is configured under **Settings → Parsing Engine**.
2. **Pre-flight LLM connectivity check**: Before a translation run starts, the app performs a **one-shot LLM connectivity test**. If the test fails, translation **does not start**, avoiding wasted queue time and failed batches.
3. **Per-platform translation parameters**: **Max output tokens** and **concurrency** are now configured **per LLM platform**, so each provider can use its own values (for example **Ollama** at concurrency **1**, while a hosted **DeepSeek** endpoint can use **10**).
4. **Formula LaTeX repair**: When extracted formula LaTeX from PDF is poor or invalid, an **automatic LLM repair** path improves results. **DeepSeek** models generally repair well in testing; **translategemma** on **Ollama** may underperform compared with **DeepSeek V4 Flash**—choose the repair model accordingly.

---

## Owlangs 1.2.0.0

### New Features

1. Added macOS installation and deployment support (macOS 13 and above, Web deployment).
2. In addition to the desktop application, supports Web-based deployment.
3. In addition to the existing OpenAI API, supports Ollama and Anthropic APIs.
4. In addition to the official MinerU cloud API, supports locally deployed MinerU.
5. Web edition user management with three modes:
   1. **Open Mode**: No application-level access gating for users; only administrators can change configuration.
   2. **LDAP Mode**: Authenticate against AD over LDAP; once configured, domain users can sign in without pre-provisioning accounts in Owlangs; Owlangs does not store user account data for those users.
   3. **Local Mode**: User accounts are stored in a local server-side database; administrators manage users directly.
6. Added MinerU source language settings for broader language coverage in PDF parsing.
7. Added document **Convert** flow for format conversion (e.g. PDF ↔ DOCX and related workflows).

### Optimizations

1. When creating a translation workflow, checks whether an LLM is available; if not, prompts to configure the LLM API key before translating.
2. Local deployments skip mandatory API key validation where appropriate.

### Bug Fixes

1. Retry translation results were not always merged back into segments correctly.
2. EPUB exported after MOBI translation could not be opened in Apple Books on macOS.
3. In PDF translation without formula exclusion, quickly starting translation could inconsistently exclude some formula segments and leave others.

---

## Owlangs 1.1.0.0

### New Features

1. Added Traditional Chinese as a target language.
2. UI language switching (English, Chinese, Japanese, Korean).
3. Automatic update checks; when a new version exists, the home page shows availability and release notes.
4. Three new buttons in the extraction exclusion panel:
   - **Exclude All**: Marks all text as non-translatable; translate skips every segment. Can be combined with export for format-only conversion (e.g. PDF to DOCX).
   - **Restore Auto-Exclusion**: Resets manual exclusions back to automatic detection.
   - **Clear All Exclusions**: Removes exclusion marks except images so all text is translated; may increase mis-detection on difficult segments.
5. ARB (JSON) document format (Pro).
6. Local LLM deployment via Ollama and OpenAI-compatible APIs (Pro).

### Optimizations

1. Improved LaTeX-to-Word conversion for mixed text containing inline formulas.
2. Softer styling for AI platform connection-test messages (previously easy to misread as errors).
3. Layout improvements on high-DPI displays.
4. Identifier detection: all-uppercase words are no longer always treated as identifiers.

### Bug Fixes

1. Startup failed when the install path contained East Asian characters.
2. After translation, opening Settings and returning home, download could fail.
3. PDF → DOCX export: text placed before an image could be emitted with wrong block styling.
4. Workflows created before MinerU/LLM keys were configured stayed unusable until recreated or the app restarted.
5. When language filtering was not excluded at extract time, some Chinese (occasionally mixed with Japanese) segments were wrongly excluded from translation.

### Known Issues

1. Multiple formulas in one PDF paragraph: some formulas may not be detected.
2. Two- or multi-column PDFs: occasional paragraph order drift.

---

## Owlangs 1.0.0.0 — Desktop Initial Release

### Overview (Desktop)

Owlangs 1.0.0.0 is the first desktop release, a WYSIWYG translation workbench for local installation and bring-your-own-model usage. It targets individuals and small teams that need high-quality, layout-preserving translation. This release covers Standard / Pro desktop features only—not the enterprise Web edition.

### Core Features

- **Large-document throughput**: tens to hundreds of pages per workflow, upload to export in one pass.
- **15+ formats**: PDF, DOCX, PPTX, XLSX, HTML, EPUB, MOBI, SRT, JSON, TXT, and more (Pro unlocks the full set).
- **Layout fidelity**: structure-aware PDF parsing (tables, images, formulas, headings, references) with layout-preserving export.
- **Segment workbench**: side-by-side review, per-segment states (translated, edited, excluded, retry, failed).
- **Smart filtering**: auto-exclude numbers, URLs, code-like tokens; manual exclude/retry per segment.
- **20+ LLM providers**: switch models within a project for cost/quality trade-offs.
- **Glossaries**: extract and reuse terminology across projects.
- **Exports**: Word, HTML, Markdown, and more for downstream editing.
- **Cost & privacy**: use your own API keys; data stays local when you pair with on-prem inference.

### Audience

Researchers, engineers, legal/technical teams, and anyone needing occasional large-document translation without expensive SaaS lock-in.

### Scope

- **This release**: Desktop Standard / Pro core features.
- **Enterprise Web**: collaboration and directory integration ship separately.
