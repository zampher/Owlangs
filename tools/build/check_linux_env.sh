#!/bin/bash

# Owlangs Linux Environment Checker (Ubuntu/Debian)
# Checks if the system meets all requirements for development and runtime.

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

TOTAL=0
PASS=0
WARN=0
FAIL=0

check_cmd() { command -v "$1" &>/dev/null; }

print_header() {
    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  Owlangs Linux Environment Check${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""
}

print_section() {
    echo -e "\n${BOLD}$1${NC}"
    echo "----------------------------------------"
}

check_result() {
    local name="$1"
    local status="$2"   # ok / warn / fail
    local detail="${3:-}"
    local required="${4:-}"
    ((TOTAL++))
    case "$status" in
        ok)
            ((PASS++))
            echo -e "  ${GREEN}✓${NC} ${name}: ${detail}"
            ;;
        warn)
            ((WARN++))
            echo -e "  ${YELLOW}!${NC} ${name}: ${detail}"
            ;;
        fail)
            ((FAIL++))
            if [[ -n "$required" ]]; then
                echo -e "  ${RED}✗${NC} ${name}: ${detail} ${RED}(required: $required)${NC}"
            else
                echo -e "  ${RED}✗${NC} ${name}: ${detail}"
            fi
            ;;
    esac
}

# ==================== Python ====================
print_section "Python Environment"

if check_cmd python3; then
    PY_FULL=$(python3 --version 2>&1 | awk '{print $2}')
    PY_MAJOR=$(echo "$PY_FULL" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_FULL" | cut -d. -f2)
    if [[ "$PY_MAJOR" -gt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -ge 11 ]]; then
        check_result "Python" "ok" "$PY_FULL"
    else
        check_result "Python" "fail" "$PY_FULL" ">= 3.11"
    fi
else
    check_result "Python" "fail" "not installed" ">= 3.11"
fi

if check_cmd pip3; then
    PIP_VER=$(pip3 --version 2>/dev/null | awk '{print $2}')
    check_result "pip" "ok" "$PIP_VER"
else
    check_result "pip" "fail" "not installed"
fi

if python3 -m venv --help &>/dev/null; then
    check_result "python3-venv" "ok" "available"
else
    check_result "python3-venv" "fail" "not installed"
fi

# ==================== System Dependencies ====================
print_section "System Dependencies"

if check_cmd redis-server; then
    REDIS_VER=$(redis-server --version 2>&1 | head -1)
    check_result "Redis" "ok" "$REDIS_VER"
else
    check_result "Redis" "fail" "not installed"
fi

if check_cmd pandoc; then
    PANDOC_VER=$(pandoc --version 2>/dev/null | head -1)
    check_result "Pandoc" "ok" "$PANDOC_VER"
else
    check_result "Pandoc" "fail" "not installed"
fi

if check_cmd xelatex; then
    XELATEX_VER=$(xelatex --version 2>/dev/null | head -1)
    check_result "XeLaTeX" "ok" "$XELATEX_VER"
else
    check_result "XeLaTeX" "fail" "not installed"
fi

if check_cmd ebook-convert; then
    check_result "Calibre (ebook-convert)" "ok" "available"
else
    check_result "Calibre (ebook-convert)" "warn" "not installed (optional, for MOBI/EPUB export)"
fi

if check_cmd git; then
    check_result "Git" "ok" "$(git --version)"
else
    check_result "Git" "fail" "not installed"
fi

if check_cmd curl; then
    check_result "curl" "ok" "available"
else
    check_result "curl" "fail" "not installed"
fi

if dpkg -l build-essential &>/dev/null; then
    check_result "build-essential" "ok" "installed"
else
    check_result "build-essential" "warn" "not installed (recommended for compiling packages)"
fi

if dpkg -l libgl1 &>/dev/null || dpkg -l libgl1-mesa-glx &>/dev/null; then
    check_result "libgl1" "ok" "installed"
else
    check_result "libgl1" "warn" "not installed (OpenCV may need it)"
fi

# ==================== Frontend ====================
print_section "Frontend"

if check_cmd flutter; then
    FLUTTER_FULL=$(flutter --version 2>/dev/null | head -1)
    FLUTTER_VER=$(echo "$FLUTTER_FULL" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if [[ "$FLUTTER_VER" == "3.38.10" ]]; then
        check_result "Flutter" "ok" "$FLUTTER_VER"
    else
        check_result "Flutter" "warn" "$FLUTTER_VER (required: 3.38.10)"
    fi
else
    check_result "Flutter" "fail" "not installed" "3.38.10"
fi

if check_cmd dart; then
    DART_VER=$(dart --version 2>&1)
    check_result "Dart" "ok" "$DART_VER"
else
    check_result "Dart" "warn" "not installed (bundled with Flutter)"
fi

# ==================== Project Virtual Environment ====================
print_section "Project Environment"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

if [[ -d "$ROOT_DIR/.venv" ]]; then
    check_result "Virtual env (.venv)" "ok" "exists at $ROOT_DIR/.venv"
    if [[ -f "$ROOT_DIR/.venv/bin/python" ]]; then
        VENV_PY=$("$ROOT_DIR/.venv/bin/python" --version 2>&1)
        check_result "  Python in .venv" "ok" "$VENV_PY"
    fi
else
    check_result "Virtual env (.venv)" "warn" "not found (run setup_linux_dev.sh to create)"
fi

# Check if Owlangs package is installed in venv
if [[ -f "$ROOT_DIR/.venv/bin/python" ]]; then
    if "$ROOT_DIR/.venv/bin/python" -c "import backend" &>/dev/null; then
        check_result "Owlangs backend" "ok" "importable in .venv"
    else
        check_result "Owlangs backend" "warn" "not installed in .venv (run pip install -e '.[pdf_export]')"
    fi
fi

# ==================== Summary ====================
echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Summary${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo -e "  Total checks: ${BOLD}$TOTAL${NC}"
echo -e "  ${GREEN}Passed:  $PASS${NC}"
echo -e "  ${YELLOW}Warnings: $WARN${NC}"
echo -e "  ${RED}Failed:  $FAIL${NC}"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}Some required dependencies are missing.${NC}"
    echo "Run the following to install them:"
    echo "  sudo tools/build/setup_linux_dev.sh"
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo -e "${YELLOW}Environment is functional but has warnings.${NC}"
    echo "You may proceed, but some features might be limited."
    exit 0
else
    echo -e "${GREEN}All checks passed! Your environment is ready.${NC}"
    exit 0
fi
