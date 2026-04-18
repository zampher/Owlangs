#!/usr/bin/env bash
set -euo pipefail

# Build Owlangs .deb packages (lite/full) on Linux
# Usage:
#   tools/build_deb.sh            # build both
#   tools/build_deb.sh --lite     # build lite only
#   tools/build_deb.sh --full     # build full only

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script supports Linux only."
  exit 1
fi

want_lite=true
want_full=true
if [[ "${1:-}" == "--lite" ]]; then
  want_full=false
elif [[ "${1:-}" == "--full" ]]; then
  want_lite=false
fi

ensure_venv() {
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  # Pin numpy to 1.26.4 (compatible with Python 3.12, stable with PyInstaller)
  echo "[env] Installing numpy==1.26.4 for stable PyInstaller builds (Py3.12 compatible)"
  python -m pip install --force-reinstall 'numpy==1.26.4' >/dev/null
  # Install project and PyInstaller after numpy is pinned
  python -m pip install . pyinstaller >/dev/null
}

get_version() {
  python - <<'PY'
import backend
print(backend.__version__)
PY
}

build_pyinstaller() {
  local spec_file="$1"
  echo "[build] pyinstaller -y ${spec_file}"
  pyinstaller -y "${spec_file}"
}

make_deb_lite() {
  local ver="$1"
  local out_dir="${ROOT_DIR}/build/deb"
  local pkg_root="${out_dir}/Owlangs_${ver}_amd64"
  local appbin="${ROOT_DIR}/dist/Owlangs-${ver}-linux"

  if [[ ! -f "${appbin}" ]]; then
    echo "[lite] binary not found: ${appbin}"
    return 1
  fi

  rm -rf "${pkg_root}"
  mkdir -p "${pkg_root}/DEBIAN" "${pkg_root}/opt/Owlangs" "${pkg_root}/usr/bin" "${pkg_root}/etc/default" "${pkg_root}/etc/Owlangs" "${pkg_root}/lib/systemd/system"

  install -m755 "${appbin}" "${pkg_root}/opt/Owlangs/"
  
  # Install configuration files to /etc/Owlangs
  # New config structure
  if [[ -f "${ROOT_DIR}/configs/system.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/system.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/platforms.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/platforms.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/ui.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/ui.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/secrets.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/secrets.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/local.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/local.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/local_users.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/local_users.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  # Existing config files (if present)
  if [[ -f "${ROOT_DIR}/configs/local.json" ]]; then
    install -m640 "${ROOT_DIR}/configs/local.json" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/app_config.json" ]]; then
    install -m640 "${ROOT_DIR}/configs/app_config.json" "${pkg_root}/etc/Owlangs/"
  fi

  cat > "${pkg_root}/DEBIAN/control" <<EOF
Package: Owlangs-lite
Version: ${ver}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Owlangs <noreply@example.com>
Description: Owlangs document translation service - lite
 This package installs the Owlangs server under /opt/Owlangs and a runner script at /usr/bin/Owlangs.
Depends: systemd
EOF

  cat > "${pkg_root}/etc/default/Owlangs" <<'EOF'
# Default options for Owlangs service
OWLANGS_PORT=8800
OWLANGS_WORKDIR=/opt/Owlangs
# Ensure runtime data/config paths are explicit for service user (www-data)
XDG_DATA_HOME=/var/lib
OWLANGS_CONFIG_PATH=/etc/Owlangs
EOF

  cat > "${pkg_root}/usr/bin/Owlangs" <<'EOF'
#!/usr/bin/env bash
set -e
PORT=${OWLANGS_PORT:-8800}
WORKDIR=${OWLANGS_WORKDIR:-/opt/Owlangs}
export DOCUTRANSLATE_PORT="$PORT"
# Propagate data/config directories (can be overridden via /etc/default/Owlangs)
export XDG_DATA_HOME="${XDG_DATA_HOME:-/var/lib}"
export OWLANGS_CONFIG_PATH="${OWLANGS_CONFIG_PATH:-/etc/Owlangs}"
cd "$WORKDIR"
exec "$WORKDIR"/Owlangs-*-linux "$@"
EOF
  chmod 755 "${pkg_root}/usr/bin/Owlangs"

  cat > "${pkg_root}/lib/systemd/system/Owlangs.service" <<'EOF'
[Unit]
Description=Owlangs Document Translation Service (lite)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/default/Owlangs
ExecStart=/usr/bin/Owlangs
Restart=on-failure
User=www-data
Group=www-data
SupplementaryGroups=Owlangs
WorkingDirectory=/opt/Owlangs

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "${pkg_root}/lib/systemd/system/Owlangs.service"

  # Add postinst script
  cat > "${pkg_root}/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e

# Reload systemd configuration
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    echo "systemd configuration reloaded"
fi

# Create www-data user and group (if not exists)
if ! id www-data >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /bin/false www-data || true
fi

# Create collaboration group and grant permissions
if ! getent group Owlangs >/dev/null 2>&1; then
    groupadd Owlangs || true
fi
usermod -aG Owlangs www-data || true

# Configuration file permissions and ownership
CFG_DIR="/etc/Owlangs"
install -d -m 755 "$CFG_DIR"
chgrp Owlangs "$CFG_DIR" || true
chmod 2755 "$CFG_DIR" || true  # Directory setgid for group inheritance

# Key configuration files: new config structure
if [[ -f "$CFG_DIR/system.json" ]]; then
  chown root:Owlangs "$CFG_DIR/system.json" || true
  chmod 660 "$CFG_DIR/system.json" || true
fi
if [[ -f "$CFG_DIR/platforms.json" ]]; then
  chown root:Owlangs "$CFG_DIR/platforms.json" || true
  chmod 660 "$CFG_DIR/platforms.json" || true
fi
if [[ -f "$CFG_DIR/ui.json" ]]; then
  chown root:Owlangs "$CFG_DIR/ui.json" || true
  chmod 660 "$CFG_DIR/ui.json" || true
fi
if [[ -f "$CFG_DIR/secrets.json.template" ]]; then
  chown root:Owlangs "$CFG_DIR/secrets.json.template" || true
  chmod 640 "$CFG_DIR/secrets.json.template" || true
fi
if [[ -f "$CFG_DIR/secrets.json" ]]; then
  chown root:Owlangs "$CFG_DIR/secrets.json" || true
  chmod 660 "$CFG_DIR/secrets.json" || true
fi
if [[ -f "$CFG_DIR/local.json" ]]; then
  chown root:Owlangs "$CFG_DIR/local.json" || true
  chmod 660 "$CFG_DIR/local.json" || true
fi
if [[ -f "$CFG_DIR/app_config.json" ]]; then
  chown root:Owlangs "$CFG_DIR/app_config.json" || true
  chmod 660 "$CFG_DIR/app_config.json" || true
fi

echo "Owlangs service installed successfully"
echo "To start the service: sudo systemctl start Owlangs"
echo "To enable auto-start: sudo systemctl enable Owlangs"

# Initialize /etc/Owlangs/local.json (if missing and template exists)
CFG_DIR="/etc/Owlangs"
if [[ ! -f "$CFG_DIR/local.json" && -f "$CFG_DIR/local.json.template" ]]; then
  cp -f "$CFG_DIR/local.json.template" "$CFG_DIR/local.json"
  chmod 660 "$CFG_DIR/local.json" || true
  echo "Created /etc/Owlangs/local.json from template"
fi
# Initialize /etc/Owlangs/secrets.json (if missing and template exists)
if [[ ! -f "$CFG_DIR/secrets.json" && -f "$CFG_DIR/secrets.json.template" ]]; then
  cp -f "$CFG_DIR/secrets.json.template" "$CFG_DIR/secrets.json"
  chmod 660 "$CFG_DIR/secrets.json" || true
  echo "Created /etc/Owlangs/secrets.json from template"
fi
# Initialize /etc/Owlangs/app_config.json (if missing and template exists)
if [[ ! -f "$CFG_DIR/app_config.json" && -f "$CFG_DIR/app_config.json.template" ]]; then
  cp -f "$CFG_DIR/app_config.json.template" "$CFG_DIR/app_config.json"
  chmod 660 "$CFG_DIR/app_config.json" || true
  echo "Created /etc/Owlangs/app_config.json from template"
fi
# Initialize /etc/Owlangs/app_config.json (if missing and template exists)
if [[ ! -f "$CFG_DIR/app_config.json" && -f "$CFG_DIR/app_config.json.template" ]]; then
  cp -f "$CFG_DIR/app_config.json.template" "$CFG_DIR/app_config.json"
  chmod 660 "$CFG_DIR/app_config.json" || true
  echo "Created /etc/Owlangs/app_config.json from template"
fi

# Create runtime data directories and grant permissions (user profiles, cache, etc.)
RUNTIME_DIR="/var/lib/Owlangs"
install -d -m 750 "$RUNTIME_DIR" || true
chown -R www-data:Owlangs "$RUNTIME_DIR" || true
install -d -m 750 "$RUNTIME_DIR/user_profiles" || true
chown -R www-data:Owlangs "$RUNTIME_DIR/user_profiles" || true
install -d -m 750 "$RUNTIME_DIR/prompts" || true
chown -R www-data:Owlangs "$RUNTIME_DIR/prompts" || true
install -d -m 750 "$RUNTIME_DIR/glossaries" || true
chown -R www-data:Owlangs "$RUNTIME_DIR/glossaries" || true

# Create symbolic links for default write paths pointing to writable directories
install -d -m 755 /opt/Owlangs || true
if [[ ! -L "/opt/Owlangs/user_profiles" ]]; then
  ln -sfn "$RUNTIME_DIR/user_profiles" "/opt/Owlangs/user_profiles" || true
fi
if [[ ! -L "/opt/Owlangs/prompts" ]]; then
  ln -sfn "$RUNTIME_DIR/prompts" "/opt/Owlangs/prompts" || true
fi
if [[ ! -L "/opt/Owlangs/glossaries" ]]; then
  ln -sfn "$RUNTIME_DIR/glossaries" "/opt/Owlangs/glossaries" || true
fi
EOF
  chmod 755 "${pkg_root}/DEBIAN/postinst"

  # Add prerm script
  cat > "${pkg_root}/DEBIAN/prerm" <<'EOF'
#!/bin/bash
set -e

# Stop service
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop Owlangs || true
    systemctl disable Owlangs || true
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
  echo "[lite] Built: ${pkg_root}.deb"
}

make_deb_full() {
  local ver="$1"
  local out_dir="${ROOT_DIR}/build/deb"
  local pkg_root="${out_dir}/Owlangs-full_${ver}_amd64"
  local appbin="${ROOT_DIR}/dist/Owlangs_full-${ver}-linux"

  if [[ ! -f "${appbin}" ]]; then
    echo "[full] binary not found: ${appbin}"
    return 1
  fi

  rm -rf "${pkg_root}"
  mkdir -p "${pkg_root}/DEBIAN" "${pkg_root}/opt/Owlangs" "${pkg_root}/usr/bin" "${pkg_root}/etc/default" "${pkg_root}/etc/Owlangs" "${pkg_root}/lib/systemd/system"

  install -m755 "${appbin}" "${pkg_root}/opt/Owlangs/"
  
  # Install configuration files to /etc/Owlangs
  # Install new config structure templates
  if [[ -f "${ROOT_DIR}/configs/system.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/system.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/platforms.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/platforms.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/ui.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/ui.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/secrets.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/secrets.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/local.json.template" ]]; then
    install -m644 "${ROOT_DIR}/configs/local.json.template" "${pkg_root}/etc/Owlangs/"
  fi
  if [[ -f "${ROOT_DIR}/configs/local.json" ]]; then
    install -m640 "${ROOT_DIR}/configs/local.json" "${pkg_root}/etc/Owlangs/"
  fi

  cat > "${pkg_root}/DEBIAN/control" <<EOF
Package: Owlangs-full
Version: ${ver}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Owlangs <noreply@example.com>
Description: Owlangs document translation service - full
 This package installs the Owlangs full server under /opt/Owlangs and a runner script at /usr/bin/Owlangs-full.
Depends: systemd
EOF

  cat > "${pkg_root}/etc/default/Owlangs-full" <<'EOF'
# Default options for Owlangs FULL service
OWLANGS_PORT=8800
OWLANGS_WORKDIR=/opt/Owlangs
# Ensure runtime data/config paths are explicit for service user (www-data)
XDG_DATA_HOME=/var/lib
OWLANGS_CONFIG_PATH=/etc/Owlangs
EOF

  cat > "${pkg_root}/usr/bin/Owlangs-full" <<'EOF'
#!/usr/bin/env bash
set -e
PORT=${OWLANGS_PORT:-8800}
WORKDIR=${OWLANGS_WORKDIR:-/opt/Owlangs}
export DOCUTRANSLATE_PORT="$PORT"
# Propagate data/config directories (can be overridden via /etc/default/Owlangs-full)
export XDG_DATA_HOME="${XDG_DATA_HOME:-/var/lib}"
export OWLANGS_CONFIG_PATH="${OWLANGS_CONFIG_PATH:-/etc/Owlangs}"
cd "$WORKDIR"
exec "$WORKDIR"/Owlangs_full-*-linux "$@"
EOF
  chmod 755 "${pkg_root}/usr/bin/Owlangs-full"

  cat > "${pkg_root}/lib/systemd/system/Owlangs-full.service" <<'EOF'
[Unit]
Description=Owlangs Document Translation Service (full)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/default/Owlangs-full
ExecStart=/usr/bin/Owlangs-full
Restart=on-failure
User=www-data
Group=www-data
SupplementaryGroups=Owlangs
WorkingDirectory=/opt/Owlangs

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "${pkg_root}/lib/systemd/system/Owlangs-full.service"

  # Add postinst script
  cat > "${pkg_root}/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e

# Reload systemd configuration
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    echo "systemd configuration reloaded"
fi

# Create www-data user and group (if not exists)
if ! id www-data >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /bin/false www-data || true
fi

echo "Owlangs full service installed successfully"
echo "To start the service: sudo systemctl start Owlangs-full"
echo "To enable auto-start: sudo systemctl enable Owlangs-full"

CFG_DIR="/etc/Owlangs"
if [[ ! -f "$CFG_DIR/auth_config.json" && -f "$CFG_DIR/auth_config.json.template" ]]; then
  cp -f "$CFG_DIR/auth_config.json.template" "$CFG_DIR/auth_config.json"
  chmod 660 "$CFG_DIR/auth_config.json" || true
  echo "Created /etc/Owlangs/auth_config.json from template"
fi
EOF
  chmod 755 "${pkg_root}/DEBIAN/postinst"

  # Add prerm script
  cat > "${pkg_root}/DEBIAN/prerm" <<'EOF'
#!/bin/bash
set -e

# Stop service
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop Owlangs-full || true
    systemctl disable Owlangs-full || true
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
  echo "[full] Built: ${pkg_root}.deb"
}


main() {
  ensure_venv
  local ver
  ver=$(get_version)

  mkdir -p build/deb

  if $want_lite; then
    build_pyinstaller "lite.spec"
    make_deb_lite "$ver"
  fi

  if $want_full; then
    build_pyinstaller "full.spec"
    make_deb_full "$ver"
  fi

}

main "$@"


