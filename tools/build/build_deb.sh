#!/usr/bin/env bash
set -euo pipefail

# Build Owlangs .deb package on Linux
# Frontend: Flutter Web (served by backend at http://localhost:8800)
# Usage:
#   tools/build/build_deb.sh            # build lite version

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script supports Linux only."
  exit 1
fi

show_usage() {
  cat <<'EOF'
Usage: tools/build/build_deb.sh [options]

Build Owlangs for Linux (Python backend + Flutter Web frontend).

OPTIONS:
  --skip-deps            Skip dependency installation step (use with caution).
  --no-deb               Skip .deb creation; keep the binary in dist/.
  -h, --help             Show this help message and exit.

OUTPUT:
  dist/Owlangs-linux                      The backend binary (onefile)
  build/deb/Owlangs_<ver>_amd64.deb       Install package (unless --no-deb)

DEPENDENCIES (host machine):
  - Python 3.11+ (uv package manager recommended)
  - Flutter SDK 3.x (for Web frontend)
  - PyInstaller 6.x
EOF
}

want_deb=true
skip_deps=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-deb)
      want_deb=false
      shift
      ;;
    --skip-deps)
      skip_deps=true
      shift
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" 1>&2
      echo "Run 'tools/build/build_deb.sh --help' for usage." 1>&2
      exit 1
      ;;
  esac
done

echo "Frontend: Flutter Web"
echo "  Backend serves Web UI at http://localhost:8800"

ensure_venv() {
  # Use uv for dependency management (preferred)
  if command -v uv >/dev/null 2>&1; then
    echo "[env] Using uv for dependency management..."
    if [[ ! -d .venv ]]; then
      uv venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo "[env] Installing dependencies with uv..."
    uv sync --quiet
    # Install PyInstaller (not in pyproject.toml dependencies)
    uv pip install pyinstaller --quiet
  else
    # Fallback to pip
    echo "[env] Using pip for dependency management..."
    if [[ ! -d .venv ]]; then
      python3 -m venv .venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m pip install --upgrade pip >/dev/null
    # Install project and PyInstaller
    python -m pip install . pyinstaller >/dev/null
  fi
}

get_version() {
  python - <<'PY'
import backend
print(backend.__version__)
PY
}

# Build Flutter Web and copy to backend/static/flutter-web
build_flutter_web() {
  if [[ ! -d "${ROOT_DIR}/frontend" ]]; then
    echo "[frontend] WARNING: frontend directory not found, skipping Flutter Web build"
    return 0
  fi
  echo "[frontend] Building Flutter Web..."

  # Check Flutter installation
  if ! command -v flutter >/dev/null 2>&1; then
    # Try to find Flutter in common locations
    local flutter_paths=(
      "$HOME/flutter/bin/flutter"
      "/opt/flutter/bin/flutter"
      "$HOME/.fvm/default/bin/flutter"
    )
    local flutter_found=""
    for p in "${flutter_paths[@]}"; do
      if [[ -f "$p" ]]; then
        flutter_found="$p"
        break
      fi
    done
    if [[ -z "$flutter_found" ]]; then
      echo "[frontend] WARNING: Flutter not found, skipping Web build" 1>&2
      echo "[frontend] Install Flutter SDK or set PATH to include flutter" 1>&2
      return 0
    fi
    echo "[frontend] Using Flutter at: $flutter_found"
    export PATH="$(dirname "$flutter_found"):$PATH"
  fi

  # Build Flutter Web
  ( cd "${ROOT_DIR}/frontend" && flutter clean && flutter pub get && flutter build web --release --no-tree-shake-icons ) || {
    echo "[frontend] ERROR: Flutter Web build failed." 1>&2
    return 1
  }

  # Copy fonts to build output
  local build_fonts="${ROOT_DIR}/frontend/build/web/assets/fonts"
  mkdir -p "${build_fonts}"
  if [[ -d "${ROOT_DIR}/frontend/fonts" ]]; then
    echo "[frontend] Copying fonts to build output..."
    cp -R "${ROOT_DIR}/frontend/fonts/"* "${build_fonts}/" 2>/dev/null || true
  fi

  # Copy build output to backend/static/flutter-web
  echo "[frontend] Copying build output to backend/static/flutter-web..."
  rm -rf "${ROOT_DIR}/backend/static/flutter-web"
  mkdir -p "${ROOT_DIR}/backend/static/flutter-web"
  cp -R "${ROOT_DIR}/frontend/build/web/." "${ROOT_DIR}/backend/static/flutter-web/"

  # Fix base href for PyInstaller packaged version
  echo "[frontend] Fixing base href..."
  local index_html="${ROOT_DIR}/backend/static/flutter-web/index.html"
  if [[ -f "$index_html" ]]; then
    # Fix base href (use sed -i for Linux)
    sed -i 's|<base href="/">|<base href="/static/flutter-web/">|g' "$index_html"
    sed -i 's|<base href="\$FLUTTER_BASE_HREF">|<base href="/static/flutter-web/">|g' "$index_html"

    # Fix CanvasKit path
    sed -i "s|canvasKitBaseUrl: '/canvaskit/'|canvasKitBaseUrl: '/static/flutter-web/canvaskit/'|g" "$index_html"
    sed -i 's|canvasKitBaseUrl: "/canvaskit/"|canvasKitBaseUrl: "/static/flutter-web/canvaskit/"|g' "$index_html"

    echo "[frontend] Base href and CanvasKit path fixed."
  else
    echo "[frontend] WARNING: index.html not found, skipping path fixes" 1>&2
  fi

  echo "[frontend] Flutter Web built and copied successfully."
}

build_pyinstaller() {
  local spec_file="$1"
  echo "[build] pyinstaller -y --clean ${spec_file}"
  pyinstaller -y --clean "${spec_file}"
}

verify_artifact() {
  local artifact="$1"
  if [[ ! -e "${ROOT_DIR}/dist/${artifact}" ]]; then
    echo "[verify] Build failed: dist/${artifact} not found." 1>&2
    return 1
  fi
  echo "[verify] OK: dist/${artifact}"
  return 0
}

# Create .deb package
make_deb() {
  local ver="$1"
  local out_dir="${ROOT_DIR}/build/deb"
  local pkg_root="${out_dir}/Owlangs_${ver}_amd64"
  local appbin="${ROOT_DIR}/dist/Owlangs-linux"

  if [[ ! -f "${appbin}" ]]; then
    echo "[deb] binary not found: ${appbin}"
    return 1
  fi

  rm -rf "${pkg_root}"
  mkdir -p "${pkg_root}/DEBIAN" "${pkg_root}/opt/Owlangs" "${pkg_root}/usr/bin" "${pkg_root}/etc/default" "${pkg_root}/etc/Owlangs/configs" "${pkg_root}/lib/systemd/system"

  install -m755 "${appbin}" "${pkg_root}/opt/Owlangs/Owlangs"

  # Install configuration templates to /etc/Owlangs/configs (matches path_utils.py logic)
  local config_templates=(
    "system.json.template"
    "platforms.json.template"
    "ui.json.template"
    "secrets.json.template"
    "local.json.template"
    "local_users.json.template"
    "static.json.template"
    "translation_config.json.template"
  )
  for tmpl in "${config_templates[@]}"; do
    if [[ -f "${ROOT_DIR}/configs/${tmpl}" ]]; then
      install -m644 "${ROOT_DIR}/configs/${tmpl}" "${pkg_root}/etc/Owlangs/configs/"
    fi
  done
  # Also copy existing config files if present
  for tmpl in "${config_templates[@]}"; do
    local cfg_name="${tmpl%.template}"
    if [[ -f "${ROOT_DIR}/configs/${cfg_name}" ]]; then
      install -m640 "${ROOT_DIR}/configs/${cfg_name}" "${pkg_root}/etc/Owlangs/configs/"
    fi
  done

  cat > "${pkg_root}/DEBIAN/control" <<EOF
Package: Owlangs
Version: ${ver}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Owlangs <noreply@owlangs.app>
Description: Owlangs document translation service
 This package installs the Owlangs server under /opt/Owlangs and a runner script at /usr/bin/owlangs.
 Web UI is served at http://localhost:8800
Depends: systemd
EOF

  cat > "${pkg_root}/etc/default/Owlangs" <<'EOF'
# Default options for Owlangs service
OWLANGS_PORT=8800
OWLANGS_WORKDIR=/opt/Owlangs
# Ensure runtime data/config paths are explicit for service user
XDG_DATA_HOME=/var/lib
OWLANGS_CONFIG_PATH=/etc/Owlangs
EOF

  cat > "${pkg_root}/usr/bin/owlangs" <<'EOF'
#!/usr/bin/env bash
set -e
PORT=${OWLANGS_PORT:-8800}
WORKDIR=${OWLANGS_WORKDIR:-/opt/Owlangs}
export OWLANGS_PORT="$PORT"
# Propagate data/config directories
export XDG_DATA_HOME="${XDG_DATA_HOME:-/var/lib}"
export OWLANGS_CONFIG_PATH="${OWLANGS_CONFIG_PATH:-/etc/Owlangs}"
cd "$WORKDIR"
exec "$WORKDIR/Owlangs" "$@"
EOF
  chmod 755 "${pkg_root}/usr/bin/owlangs"

  cat > "${pkg_root}/lib/systemd/system/owlangs.service" <<'EOF'
[Unit]
Description=Owlangs Document Translation Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/default/Owlangs
# Set home directory and XDG paths for owlangs user
Environment=HOME=/var/lib/Owlangs
Environment=XDG_CONFIG_HOME=/var/lib/Owlangs/config
Environment=XDG_DATA_HOME=/var/lib/Owlangs
ExecStart=/usr/bin/owlangs -i
Restart=on-failure
User=owlangs
Group=owlangs
WorkingDirectory=/opt/Owlangs

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "${pkg_root}/lib/systemd/system/owlangs.service"

  # Add postinst script
  cat > "${pkg_root}/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e

# Reload systemd configuration
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    echo "systemd configuration reloaded"
fi

# Create owlangs user and group with home directory (if not exists)
if ! id owlangs >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/Owlangs --shell /bin/false owlangs || true
fi

# Ensure home directory exists with correct permissions
install -d -m 750 /var/lib/Owlangs || true
chown owlangs:owlangs /var/lib/Owlangs || true

# Create XDG config directory for lock file
install -d -m 750 /var/lib/Owlangs/config || true
chown owlangs:owlangs /var/lib/Owlangs/config || true
install -d -m 750 /var/lib/Owlangs/config/Owlangs || true
chown owlangs:owlangs /var/lib/Owlangs/config/Owlangs || true

# Configuration directory setup
CFG_DIR="/etc/Owlangs"
CFG_SUBDIR="/etc/Owlangs/configs"
install -d -m 755 "$CFG_DIR"
chown root:owlangs "$CFG_DIR" || true
chmod 2755 "$CFG_DIR" || true

# Create configs subdirectory (for actual config files)
install -d -m 775 "$CFG_SUBDIR" || true
chown root:owlangs "$CFG_SUBDIR" || true
chmod 2775 "$CFG_SUBDIR" || true

# Initialize config files from templates in configs subdirectory (if missing)
for tmpl in system.json.template platforms.json.template ui.json.template secrets.json.template local.json.template local_users.json.template static.json.template translation_config.json.template; do
  cfg_name="${tmpl%.template}"
  if [[ ! -f "$CFG_SUBDIR/$cfg_name" && -f "$CFG_SUBDIR/$tmpl" ]]; then
    cp -f "$CFG_SUBDIR/$tmpl" "$CFG_SUBDIR/$cfg_name"
    chmod 660 "$CFG_SUBDIR/$cfg_name" || true
    chown root:owlangs "$CFG_SUBDIR/$cfg_name" || true
    echo "Created $CFG_SUBDIR/$cfg_name from template"
  fi
done

# Set permissions on config files in configs subdirectory
for cfg in system.json platforms.json ui.json secrets.json local.json local_users.json static.json translation_config.json; do
  if [[ -f "$CFG_SUBDIR/$cfg" ]]; then
    chown root:owlangs "$CFG_SUBDIR/$cfg" || true
    chmod 660 "$CFG_SUBDIR/$cfg" || true
  fi
done

# Create runtime data directories
RUNTIME_DIR="/var/lib/Owlangs"
install -d -m 750 "$RUNTIME_DIR" || true
chown -R owlangs:owlangs "$RUNTIME_DIR" || true
install -d -m 750 "$RUNTIME_DIR/user_profiles" || true
chown -R owlangs:owlangs "$RUNTIME_DIR/user_profiles" || true
install -d -m 750 "$RUNTIME_DIR/prompts" || true
chown -R owlangs:owlangs "$RUNTIME_DIR/prompts" || true
install -d -m 750 "$RUNTIME_DIR/glossaries" || true
chown -R owlangs:owlangs "$RUNTIME_DIR/glossaries" || true
install -d -m 750 "$RUNTIME_DIR/cache" || true
chown -R owlangs:owlangs "$RUNTIME_DIR/cache" || true

# Set ownership on app directory
chown -R owlangs:owlangs /opt/Owlangs || true

echo "Owlangs service installed successfully"
echo "To start the service: sudo systemctl start owlangs"
echo "To enable auto-start: sudo systemctl enable owlangs"
echo "Web UI: http://localhost:8800"
EOF
  chmod 755 "${pkg_root}/DEBIAN/postinst"

  # Add prerm script
  cat > "${pkg_root}/DEBIAN/prerm" <<'EOF'
#!/bin/bash
set -e

# Stop service
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop owlangs || true
    systemctl disable owlangs || true
fi
EOF
  chmod 755 "${pkg_root}/DEBIAN/prerm"

  # Add postrm script
  cat > "${pkg_root}/DEBIAN/postrm" <<'EOF'
#!/bin/bash
set -e

# Reload systemd configuration
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
fi
EOF
  chmod 755 "${pkg_root}/DEBIAN/postrm"

  dpkg-deb --build "${pkg_root}"
  echo "[deb] Built: ${pkg_root}.deb"
}

main() {
  if [[ "$skip_deps" == false ]]; then
    ensure_venv
  else
    echo "[env] Skipping dependency installation (using existing environment)"
    if [[ -d .venv ]]; then
      # shellcheck disable=SC1091
      source .venv/bin/activate
      echo "[env] Activated existing virtual environment"
    else
      echo "[env] ERROR: Virtual environment not found. Please run without --skip-deps first."
      exit 1
    fi
  fi

  local ver
  ver=$(get_version)

  # Build Flutter Web frontend
  build_flutter_web

  # Build backend with PyInstaller
  build_pyinstaller "lite.spec"

  if ! verify_artifact "Owlangs-linux"; then
    exit 1
  fi

  # Create .deb package
  if $want_deb; then
    mkdir -p build/deb
    make_deb "$ver"
  fi

  echo ""
  echo "=== Build output ==="
  echo "  Executable: ${ROOT_DIR}/dist/Owlangs-linux"
  if $want_deb; then
    echo "  Install package: ${ROOT_DIR}/build/deb/Owlangs_${ver}_amd64.deb"
  fi
  echo ""
  echo "Linux build finished successfully."
}

main "$@"