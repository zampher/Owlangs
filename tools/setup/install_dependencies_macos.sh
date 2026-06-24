#!/usr/bin/env bash
# Install runtime dependencies for Owlangs on macOS via Homebrew.
# Bundled into Owlangs.app as 3rdParty/macos/install_dependencies.sh (see build_macos.sh).
#
# Usage:
#   ./tools/setup/install_dependencies_macos.sh install
#   ./tools/setup/install_dependencies_macos.sh          # same as install
#
# MenuBar invokes: /bin/bash -l install_dependencies.sh install

set -euo pipefail

ACTION="${1:-install}"

if [[ "$ACTION" != "install" ]]; then
  echo "Usage: $0 [install]"
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[ERROR] This script supports macOS only."
  exit 1
fi

echo "=== Owlangs macOS dependency installer ==="
echo "Installing: Redis, Pandoc, Typst, XeLaTeX (optional, large download)"
echo ""

if ! command -v brew &>/dev/null; then
  echo "[ERROR] Homebrew not found. Install from https://brew.sh"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
echo "[Homebrew] $(brew --version | head -1)"

# Redis (session / cache)
if command -v redis-server &>/dev/null || command -v redis-cli &>/dev/null; then
  echo "[Redis] Already installed"
else
  echo "[Redis] Installing..."
  brew install redis
  echo "[Redis] Installed. Start with: brew services start redis"
fi

# Pandoc (DOCX / reflow PDF)
if command -v pandoc &>/dev/null; then
  echo "[Pandoc] Already installed ($(pandoc --version | head -1))"
else
  echo "[Pandoc] Installing..."
  brew install pandoc
  echo "[Pandoc] Installed"
fi

# Typst (PDF in-place translation / typst_overlay renderer)
if command -v typst &>/dev/null; then
  echo "[Typst] Already installed ($(typst --version 2>/dev/null | head -1 || echo typst))"
else
  echo "[Typst] Installing..."
  brew install typst
  echo "[Typst] Installed. Verify with: typst --version"
fi

# XeLaTeX (Pandoc reflow PDF with math)
if command -v xelatex &>/dev/null; then
  echo "[XeLaTeX] Already installed ($(xelatex --version | head -1))"
else
  echo "[XeLaTeX] Not found."
  echo "[XeLaTeX] Attempting BasicTeX (smaller than full MacTeX)..."
  if brew install --cask basictex; then
    echo "[XeLaTeX] BasicTeX installed. Add to PATH if needed:"
    echo "  export PATH=\"/Library/TeX/texbin:\$PATH\""
  else
    echo "[WARN] BasicTeX install failed or was skipped."
    echo "  Install manually: brew install --cask mactex-no-gui"
    echo "  Or: brew install --cask tinytex"
  fi
fi

echo ""
echo "=== Done ==="
echo "Verify:"
echo "  redis-server --version"
echo "  pandoc --version"
echo "  typst --version"
echo "  xelatex --version"
echo ""
