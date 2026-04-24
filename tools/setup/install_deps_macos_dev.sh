#!/usr/bin/env bash
# Install third-party dependencies for **development** on macOS (build from source, run backend, package app).
# Usage:
#   ./tools/setup/install_deps_macos_dev.sh              # required + optional (Redis, Pandoc)
#   ./tools/setup/install_deps_macos_dev.sh --required   # only required (Python, Flutter)
#
# After running, in project root: python3 -m venv .venv && source .venv/bin/activate
# Then: pip install --upgrade pip && pip install -e .

set -euo pipefail

SKIP_OPTIONAL=false
if [[ "${1:-}" == "--required" ]] || [[ "${1:-}" == "--skip-optional" ]]; then
  SKIP_OPTIONAL=true
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script supports macOS only. Current OS: $(uname -s)"
  exit 1
fi

echo "=== Owlangs macOS **development** dependency installer ==="

# 1. Xcode Command Line Tools
if ! xcode-select -p &>/dev/null; then
  echo ""
  echo "[Xcode] Command Line Tools not found. Install with: xcode-select --install"
  echo "Then run this script again."
  exit 1
fi
echo "[Xcode] Command Line Tools: OK"

# 2. Homebrew
if ! command -v brew &>/dev/null; then
  echo ""
  echo "[Homebrew] Not found. Install from https://brew.sh"
  echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  exit 1
fi
echo "[Homebrew] $(brew --version | head -1)"

# 3. Python 3.11+
NEED_PYTHON=false
if ! command -v python3 &>/dev/null; then
  NEED_PYTHON=true
elif ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
  echo "[Python] Found python3 ($PYVER) but need 3.11+"
  NEED_PYTHON=true
else
  echo "[Python] $(python3 --version): OK"
fi
if [[ "$NEED_PYTHON" == "true" ]]; then
  echo "[Python] Installing python@3.12 via Homebrew..."
  brew install python@3.12
  if [[ -x "/opt/homebrew/opt/python@3.12/bin/python3" ]]; then
    export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"
  elif [[ -x "/usr/local/opt/python@3.12/bin/python3" ]]; then
    export PATH="/usr/local/opt/python@3.12/bin:$PATH"
  fi
  echo "[Python] Add to shell profile if needed: export PATH=\"/opt/homebrew/opt/python@3.12/bin:\$PATH\""
fi

# 4. Flutter (recommended: 3.38.10 via FVM)
FLUTTER_VERSION="3.38.10"
if command -v flutter &>/dev/null; then
  echo "[Flutter] $(flutter --version 2>/dev/null | head -1 || echo 'installed')"
  if ! flutter --version 2>/dev/null | grep -q "3\.38\.10"; then
    echo "  Recommended version: ${FLUTTER_VERSION}. Use FVM: brew tap leoafarias/fvm && brew install fvm && fvm install ${FLUTTER_VERSION} && fvm global ${FLUTTER_VERSION}"
    echo "  Then add to PATH: export PATH=\"\$HOME/.pub-cache/bin:\$PATH\""
  fi
  echo "  Run 'flutter doctor' if you plan to build the app."
else
  if ! command -v fvm &>/dev/null; then
    echo "[Flutter] Installing FVM (Flutter Version Manager) for ${FLUTTER_VERSION}..."
    brew tap leoafarias/fvm 2>/dev/null || true
    brew install fvm
  fi
  echo "[Flutter] Installing Flutter ${FLUTTER_VERSION} via FVM..."
  fvm install "${FLUTTER_VERSION}"
  fvm global "${FLUTTER_VERSION}"
  export PATH="$HOME/.pub-cache/bin:$PATH"
  if command -v flutter &>/dev/null; then
    echo "[Flutter] $(flutter --version 2>/dev/null | head -1)"
    echo "  Add to your shell profile: export PATH=\"\$HOME/.pub-cache/bin:\$PATH\""
  else
    echo "[Flutter] WARNING: Flutter not in PATH. Add: export PATH=\"\$HOME/.pub-cache/bin:\$PATH\" then run: flutter --version"
  fi
  echo "  Run 'flutter doctor' if you plan to build the app."
fi

# 5. Redis (optional)
if [[ "$SKIP_OPTIONAL" == "true" ]]; then
  echo "[Redis] Skipped (--skip-optional)"
else
  if command -v redis-cli &>/dev/null; then
    echo "[Redis] Already installed"
  else
    echo "[Redis] Installing Redis..."
    brew install redis
    echo "[Redis] Start with: brew services start redis"
  fi
fi

# 6. Pandoc (optional, for DOCX/PDF and format conversion)
if [[ "$SKIP_OPTIONAL" == "true" ]]; then
  echo "[Pandoc] Skipped (--skip-optional)"
else
  if command -v pandoc &>/dev/null; then
    echo "[Pandoc] Already installed ($(pandoc --version | head -1))"
  else
    echo "[Pandoc] Installing Pandoc..."
    brew install pandoc
    echo "[Pandoc] Installed. Verify with: pandoc --version"
  fi
fi

# 7. Calibre (for MOBI/EPUB export via ebook-convert)
if [[ "$SKIP_OPTIONAL" == "true" ]]; then
  echo "[Calibre] Skipped (--skip-optional)"
else
  if command -v ebook-convert &>/dev/null || [[ -x "/Applications/calibre.app/Contents/MacOS/ebook-convert" ]] || [[ -x "/Applications/Calibre.app/Contents/MacOS/ebook-convert" ]]; then
    echo "[Calibre] Already installed (ebook-convert found)"
  else
    echo "[Calibre] Installing Calibre..."
    echo "  Calibre is required for MOBI/EPUB export."
    brew install --cask calibre
    echo "[Calibre] Installed. Verify with: ebook-convert --version"
  fi
fi

# 8. XeLaTeX (for PDF math rendering via Pandoc)
if [[ "$SKIP_OPTIONAL" == "true" ]]; then
  echo "[XeLaTeX] Skipped (--skip-optional)"
else
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
fi

echo ""
echo "=== Next steps (development) ==="
echo "  python3 -m venv .venv && source .venv/bin/activate"
echo "  pip install --upgrade pip && pip install -e ."
echo "  Optional: playwright install chromium"
echo "  Build: ./tools/build/build_macos.sh lite"
echo ""
