#!/usr/bin/env bash
# Install **optional** third-party dependencies for **deployment/runtime** on macOS.
# For end users who run the packaged app (DMG). The app itself needs no extra deps;
# this script installs: Redis (session), Pandoc (DOCX/PDF and format conversion).
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

echo ""
echo "=== Done ==="
echo "Start Redis (if needed): brew services start redis"
echo "Run Owlangs app, then open http://localhost:8800 in browser."
echo ""
