# Font Download Script

This script downloads Chinese, Korean, and Emoji fonts from Google Fonts for use in the Flutter web application.

## Prerequisites

- Node.js (v14 or higher)
- npx (comes with Node.js)

## Usage

### Windows (PowerShell)

```powershell
.\tools\setup\download_fonts.ps1
```

Or specify a custom output directory:

```powershell
.\tools\setup\download_fonts.ps1 -OutputDir "frontend/assets/fonts"
```

### Linux/Mac (Bash)

```bash
chmod +x tools/setup/download_fonts.sh
./tools/setup/download_fonts.sh
```

Or specify a custom output directory:

```bash
./tools/setup/download_fonts.sh frontend/assets/fonts
```

## Downloaded Fonts

The script downloads the following fonts in WOFF2 format:

- **Noto Sans SC** (Chinese Simplified): weights 400, 700
- **Noto Sans KR** (Korean): weights 400, 700
- **Noto Color Emoji**: weight 400

## Output Location

By default, fonts are downloaded to `frontend/assets/fonts/`.

## Notes

- The script uses `google-font-downloader` via npx, so no local installation is required
- Fonts are downloaded in WOFF2 format for optimal web performance
- If fonts already exist, they will be overwritten

