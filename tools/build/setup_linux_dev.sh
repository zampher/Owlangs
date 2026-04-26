#!/bin/bash

# Owlangs Linux Development Environment Setup (Ubuntu/Debian)
# Installs all system dependencies, Python packages, Flutter SDK, and sets up the project.
# Each step checks if already installed before proceeding.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$ROOT_DIR"

TARGET_PYTHON="3.12"
TARGET_FLUTTER="3.38.10"

print_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error()   { echo -e "${RED}[ERR]${NC} $1"; }

check_cmd() { command -v "$1" &>/dev/null; }

# ==================== Step 1: System Packages ====================
echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Owlangs Linux Dev Setup${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

print_info "[1/6] Checking system packages..."

MISSING_PKGS=()

ensure_pkg() {
    local pkg="$1"
    local cmd="${2:-$1}"
    if dpkg -l "$pkg" &>/dev/null || check_cmd "$cmd"; then
        print_success "$pkg already installed"
    else
        MISSING_PKGS+=("$pkg")
    fi
}

ensure_pkg "python3.12" "python3.12"
ensure_pkg "python3.12-venv"
ensure_pkg "python3-pip" "pip3"
ensure_pkg "redis-server" "redis-server"
ensure_pkg "pandoc" "pandoc"
ensure_pkg "texlive-xetex" "xelatex"
ensure_pkg "texlive-fonts-recommended"
ensure_pkg "texlive-latex-extra"
ensure_pkg "calibre" "ebook-convert"
ensure_pkg "git" "git"
ensure_pkg "curl" "curl"
ensure_pkg "wget" "wget"
ensure_pkg "build-essential"
ensure_pkg "libgl1"

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    print_info "Installing missing packages: ${MISSING_PKGS[*]}"
    sudo apt-get update
    sudo apt-get install -y "${MISSING_PKGS[@]}"
    print_success "System packages installed"
else
    print_success "All system packages already installed"
fi

# Ensure Redis is running
if systemctl is-active --quiet redis-server; then
    print_success "Redis service already running"
else
    print_info "Starting Redis service..."
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    print_success "Redis service started"
fi

# ==================== Step 2: Python Virtual Environment ====================
echo ""
print_info "[2/6] Setting up Python virtual environment..."

if [[ -d ".venv" ]]; then
    print_success ".venv already exists"
else
    if check_cmd python3.12; then
        python3.12 -m venv .venv
    elif check_cmd python3; then
        python3 -m venv .venv
    else
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Created .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Verify Python version in venv
VENV_PY=$(python --version 2>&1)
print_success "Virtual env active: $VENV_PY"

# ==================== Step 3: Python Dependencies ====================
echo ""
print_info "[3/6] Installing Python dependencies..."

pip install --upgrade pip wheel setuptools

# Install the project in editable mode with all extras
print_info "Running: pip install -e '.[pdf_export]'"
pip install -e ".[pdf_export]" || {
    print_error "Failed to install Python dependencies"
    exit 1
}

# Verify backend import
if python -c "import backend" &>/dev/null; then
    print_success "Python dependencies installed and backend importable"
else
    print_warning "pip install succeeded but backend import failed — check logs above"
fi

# ==================== Step 4: Flutter SDK ====================
echo ""
print_info "[4/6] Checking Flutter SDK..."

FLUTTER_DIR="${FLUTTER_DIR:-$HOME/flutter}"

if check_cmd flutter; then
    CURRENT_VER=$(flutter --version 2>/dev/null | grep -oE 'Flutter [^ ]+' | awk '{print $2}')
    if [[ "$CURRENT_VER" == "$TARGET_FLUTTER" ]]; then
        print_success "Flutter $TARGET_FLUTTER already installed"
    else
        print_warning "Flutter $CURRENT_VER found, but $TARGET_FLUTTER is required"
        read -rp "Reinstall Flutter to $TARGET_FLUTTER? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            rm -rf "$FLUTTER_DIR"
            NEED_INSTALL=1
        else
            print_warning "Skipping Flutter reinstall (you may have compatibility issues)"
            NEED_INSTALL=0
        fi
    fi
else
    NEED_INSTALL=1
fi

if [[ "${NEED_INSTALL:-0}" -eq 1 ]]; then
    print_info "Installing Flutter $TARGET_FLUTTER to $FLUTTER_DIR..."
    if [[ -d "$FLUTTER_DIR" ]]; then
        rm -rf "$FLUTTER_DIR"
    fi
    git clone https://github.com/flutter/flutter.git -b "$TARGET_FLUTTER" "$FLUTTER_DIR" --depth 1
    export PATH="$FLUTTER_DIR/bin:$PATH"
    flutter doctor
    print_success "Flutter $TARGET_FLUTTER installed"
fi

# Ensure Flutter is on PATH for future sessions
SHELL_RC=""
if [[ "$SHELL" == */zsh ]]; then
    SHELL_RC="$HOME/.zshrc"
else
    SHELL_RC="$HOME/.bashrc"
fi

if ! grep -q "$FLUTTER_DIR/bin" "$SHELL_RC" 2>/dev/null; then
    print_info "Adding Flutter to PATH in $SHELL_RC"
    echo "" >> "$SHELL_RC"
    echo "# Flutter SDK" >> "$SHELL_RC"
    echo "export PATH=\"$FLUTTER_DIR/bin:\$PATH\"" >> "$SHELL_RC"
    print_success "Flutter PATH added to $SHELL_RC"
else
    print_success "Flutter PATH already in $SHELL_RC"
fi

# Add to current session
export PATH="$FLUTTER_DIR/bin:$PATH"

# Precache web artifacts
print_info "Running flutter precache..."
flutter precache --web
print_success "Flutter precache complete"

# ==================== Step 5: Frontend Dependencies ====================
echo ""
print_info "[5/6] Installing frontend dependencies..."

cd "$ROOT_DIR/frontend"

if [[ -d ".dart_tool" ]]; then
    print_success "Flutter packages already fetched"
else
    flutter pub get
    print_success "Flutter packages installed"
fi

cd "$ROOT_DIR"

# ==================== Step 6: Verification ====================
echo ""
print_info "[6/6] Running verification..."

echo ""
$SCRIPT_DIR/check_linux_env.sh || true

# ==================== Summary ====================
echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Setup Complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "Quick start commands:"
echo ""
echo "  1. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Run the backend server:"
echo "     python -m backend.cli -i"
echo ""
echo "  3. Build the Flutter Web frontend:"
echo "     cd frontend && flutter build web --release --no-tree-shake-icons"
echo ""
echo "  4. Run the full build (backend + frontend + PyInstaller):"
echo "     TODO: create build_linux.sh"
echo ""
