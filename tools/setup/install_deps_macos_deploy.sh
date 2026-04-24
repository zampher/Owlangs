#!/usr/bin/env bash
# Install **optional** third-party dependencies for **deployment/runtime** on macOS.
# For end users who run the packaged app (DMG). The app itself needs no extra deps;
# this script installs: Redis (session), Pandoc (DOCX/PDF and format conversion),
# Calibre (MOBI/EPUB export), and XeLaTeX (PDF math rendering).
#
# Usage:
#   ./tools/setup/install_deps_macos_deploy.sh
#
# Requires: Homebrew (https://brew.sh). Install with:
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script supports macOS only. Current OS: $(uname -s)"
  exit 1
fi

echo "=== Owlangs macOS **deployment** optional dependencies ==="
echo "Installing: Redis (session), Pandoc (DOCX/PDF and format conversion)."
echo "Optional: Calibre (MOBI/EPUB export), XeLaTeX (PDF math rendering)."
echo ""

if ! command -v brew &>/dev/null; then
  echo "[Homebrew] Not found. Install from https://brew.sh"
  echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  echo "Then add brew to PATH and run this script again."
  exit 1
fi
echo "[Homebrew] OK"

# Redis (optional)
if command -v redis-cli &>/dev/null; then
  echo "[Redis] Already installed. Start with: brew services start redis"
else
  echo "[Redis] Installing Redis..."
  brew install redis
  echo "[Redis] Installed. Start with: brew services start redis"
fi

# Pandoc (for DOCX/PDF export in PDF workflow)
if command -v pandoc &>/dev/null; then
  echo "[Pandoc] Already installed ($(pandoc --version | head -1))"
else
  echo "[Pandoc] Installing Pandoc..."
  brew install pandoc
  echo "[Pandoc] Installed. Verify with: pandoc --version"
fi

# Calibre (for MOBI/EPUB export via ebook-convert)
if command -v ebook-convert &>/dev/null || [[ -x "/Applications/calibre.app/Contents/MacOS/ebook-convert" ]] || [[ -x "/Applications/Calibre.app/Contents/MacOS/ebook-convert" ]]; then
  echo "[Calibre] Already installed (ebook-convert found)"
else
  echo "[Calibre] Not found. Installing Calibre..."
  echo "  Calibre is required for MOBI/EPUB export."
  brew install --cask calibre
  echo "[Calibre] Installed. Verify with: ebook-convert --version"
fi

# XeLaTeX (for PDF math rendering via Pandoc)
if command -v xelatex &>/dev/null; then
  echo "[XeLaTeX] Already installed ($(xelatex --version | head -1))"
else
  echo "[XeLaTeX] Not found. Installing MacTeX (includes XeLaTeX)..."
  echo "  XeLaTeX is required for PDF export with math formulas."
  echo "  This is a large download (~4GB). Alternative: brew install --cask mactex-no-gui (smaller, ~1.3GB)"
  read -r -p "Install MacTeX? This may take a while. [y/N] " response </dev/tty || true
  if [[ "$response" =~ ^[Yy]$ ]]; then
    brew install --cask mactex
    echo "[XeLaTeX] Installed. You may need to add /Library/TeX/texbin to PATH."
  else
    echo "[XeLaTeX] Skipped. PDF math rendering will not work."
    echo "  To install later: brew install --cask mactex"
  fi
fi

echo ""
echo "=== Done ==="
echo "Start Redis (if needed): brew services start redis"
echo "Run Owlangs app, then open http://localhost:8800 in browser."
echo ""
