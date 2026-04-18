## Owlangs 1.2.0.0

### New Features:
1. Added macOS installation and deployment support (macOS 13 and above, Web deployment).
2. In addition to the desktop application, now supports Web-based deployment.
3. In addition to the existing OpenAI API, now supports Ollama and Anthropic APIs.
4. In addition to the existing official MinerU cloud service API, now supports locally deployed MinerU.
5. Web edition user management with three user management modes:
   1. **Open Mode**: No application access control for users; only administrators can manage configuration.
   2. **LDAP Mode**: Login can connect to an AD server via LDAP. Once configured, domain users can log in without creating accounts; Owlangs does not store user account information.
   3. **Local Mode**: Owlangs stores user account information in a local server database; administrators manage users manually.
6. Added MinerU source language setting to support PDF parsing for various languages.

### Optimizations:
1. When creating a translation workflow, checks if an available LLM is configured. If not, prompts the user to configure the LLM API Key before translating.
2. Local deployments do not require API key checks.

### Bug Fixes:
1. Fixed: Retry translation results were not correctly filled back into segments.
2. Fixed: Exported EPUB files from MOBI translation could not be opened in Books on macOS.
3. Fixed: In PDF translation, when quickly clicking translate without excluding formulas, some formula segments were incorrectly excluded while others were not.

## Owlangs 1.1.0.0

### New Features:
1. Added target language for translation: Traditional Chinese.
2. Supports UI text language switching, supporting (English, Chinese, Japanese, Korean).
3. Automatically checks for new versions. When a new version is available, displays version information and changelog on the software's homepage.
4. Added three buttons in the document extraction exclusion management panel:
- **"Exclude All"**: Sets all text to not be translated. After clicking translate, all segments will be skipped. It can be used with the export function to achieve original format conversion, such as PDF to DOCX.
- **"Restore Auto-Exclusion"**: Resets user operations, restoring the exclusion state to automatic recognition.
- **"Clear All Exclusions"**: Clears all "exclusion" marks except for images, so all text will be processed for translation. A side effect is that there may be recognition errors in identifying failed text segment translations.
5. Supports ARB (JSON) document format (Pro version).
6. Supports local large language model deployment via Ollama and OpenAI interfaces (Pro version).

### Optimizations:
1. Optimized LaTeX formula conversion to Word format, can recognize LaTeX formulas within mixed text, increasing conversion success rate.
2. AI Platform connection test, the orange-red color of prompts was easily misunderstood, optimized the display style.
3. Optimized software layout for high resolutions.
4. Optimized identifier recognition, no longer identifying all-uppercase words as identifiers.

### Bug Fixes:
1. Software failed to start when the installation path contained East Asian characters.
2. After completing translation, entering Settings and then returning to the homepage, clicking download failed.
3. PDF translation process, when exporting to docx format, if there is text before an image, the output image becomes text format.
4. Translation processes created before initially configuring the MinerU or LLM KEY could not be used after configuring the key. Required recreating the process or restarting the software.
5. When language identification was not excluded during the text extraction stage, many Chinese characters (some containing Japanese) were excluded from translation after translation, causing some segments to remain untranslated.

### Known Issues:
1. In PDFs, when multiple formulas are mixed within a single paragraph, some formulas are not recognized.
2. For PDFs with double-column or multi-column formatted literature, a few paragraphs have incorrect order.

## Owlangs 1.0.0.0 – Desktop Edition Initial Release

### Overview (Desktop)

Owlangs 1.0.0.0 is the first official desktop release based on Owlangs, positioned as a "what-you-see-is-what-you-get translation workbench". It supports local installation and connects to your own large language model accounts, targeting individual users and small teams that need high‑quality document translation with faithful layout preservation. This release focuses only on the core capabilities of the desktop Standard / Pro editions and does **not** cover the enterprise Web edition.

### Core Features of the Desktop Edition

- **Fast translation for large documents**  
  - Designed for long documents such as tens to hundreds of pages of papers, technical documents, and contracts  
  - From upload to export, a single workflow can complete the translation of an entire document  

- **Multi-format document support**  
  - Supports 15+ formats: PDF, DOCX, PPTX, XLSX, HTML, EPUB, MOBI, SRT, JSON, TXT, and more  
  - Standard Edition covers common formats like PDF / DOCX, while Pro Edition unlocks all advanced formats  

- **High-fidelity layout preservation**  
  - Deeply analyzes PDF structure, recognizing tables, images, formulas, headings, references, and other elements  
  - Re-renders translations according to the original layout to keep structure and formatting as close as possible to the source  

- **Segment-based translation workbench (WYSIWYG)**  
  - Side-by-side view of source and translation, with segment-level review and editing  
  - Segment status tracking: translated, modified, excluded, needs retry, failed, etc., so issues and progress are visible at a glance  

- **Intelligent segmenting and content filtering**  
  - Automatically detects content that does not need translation (e.g., pure numbers, URLs, some code identifiers) and excludes it  
  - Allows manual per-segment flags like "exclude" or "needs retry", so only truly necessary content is translated and billed  

- **Multi-provider LLM integration and switching**  
  - Can connect to 20+ major AI platforms (such as OpenAI, Claude, Gemini, DeepSeek, etc.)  
  - Within a single project, you can flexibly switch models: use a cheaper, faster model for the first draft, then higher-quality models for polishing key segments  

- **Glossary / terminology management**  
  - Automatically extracts terms from documents to build reusable glossaries  
  - Applies glossaries during translation to keep professional terminology consistent across projects  

- **Multi-format export and editing-friendly outputs**  
  - For PDFs, results can be exported as Word, HTML, Markdown, and other formats to support further editing, layout, or publishing  

- **Cost control and local-friendly usage**  
  - Uses your own API keys with pay-as-you-go billing, typically far cheaper than subscription-based translation platforms  
  - Data is stored locally, and can be combined with local parsing / inference services to enable secure translation in intranet environments  

### Target Users and Scenarios (Summary)

- Researchers and engineers who need high-quality translations of academic papers and technical white papers  
- Business and technical users who must preserve formatting in contracts, technical agreements, and multi-format technical documents  
- Individual users or small teams who occasionally need to translate large documents but do not want to subscribe to expensive online services  

### Version Information

- **Scope of this release**: Initial launch of core features for the desktop Standard and Pro editions  
- **Enterprise Web edition**: Multi-user collaboration, domain account integration, and other enterprise features will be released separately as part of the Enterprise edition  


