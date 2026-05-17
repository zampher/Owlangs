#!/usr/bin/env bash

rm -rf build/ dist/ .eggs/ Owlangs.egg-info/

set -euo pipefail

# Build Owlangs macOS app (lite or full) and create DMG by default.
# Frontend: Web only (Desktop mode removed to simplify architecture)
#   Web: Backend serves Flutter Web at /; user opens http://localhost:8800 in browser

show_usage() {
  cat <<'EOF'
Usage: tools/build/build_macos.sh [build-type] [options]

Build Owlangs for macOS (MenuBar launcher + Python backend + Flutter Web frontend).

BUILD TYPE (positional, optional — defaults to 'lite'):
  lite                   Build lite version (faster, smaller; no LaTeX/Pandoc included)
  full                   Build full version (includes all translation features)

ARCHITECTURE OPTIONS:
  --arm64                Build for Apple Silicon (M1/M2/M3). Default if not specified.
  --x86_64               Build for Intel Macs (requires Rosetta 2 on Apple Silicon host).
  --universal2           Build a fat binary supporting both arm64 and x86_64 (largest).
  --dual-arch            Build arm64 and x86_64 installers in one run (two DMGs; skips universal2).
  --all-archs            Build all three architectures sequentially (arm64 → x86_64 → universal2).

OTHER OPTIONS:
  --no-dmg               Skip DMG creation; keep the .app bundle in dist/.
  --skip-deps            Skip dependency installation step (use with caution).
  -h, --help             Show this help message and exit.

EXAMPLES:
  tools/build/build_macos.sh                         # Default: lite + arm64 + DMG
  tools/build/build_macos.sh full                    # Full version for arm64
  tools/build/build_macos.sh --x86_64                # Intel-only build
  tools/build/build_macos.sh --universal2            # Universal fat binary
  tools/build/build_macos.sh --dual-arch             # arm64 + x86_64 DMGs (no universal2 pass)
  tools/build/build_macos.sh --all-archs             # Build all three architectures
  tools/build/build_macos.sh full --no-dmg           # Full build without DMG
  tools/build/build_macos.sh --dual-arch --no-dmg    # arm64 + x86_64, no DMG
  tools/build/build_macos.sh --all-archs --no-dmg    # All architectures, no DMG

OUTPUT:
  dist/Owlangs.app                      The signed .app bundle
  dist/Owlangs-{ver}-mac-{arch}.dmg     DMG: auto-opens install window with drag-to-Applications guide (unless --no-dmg)

DEPENDENCIES (host machine):
  - Python 3.12 (python.org universal2 recommended for cross-arch builds)
  - Flutter SDK (for Web frontend)
  - PyInstaller 6.x
  - Rosetta 2 (for --x86_64, --dual-arch, or --all-archs on Apple Silicon)
EOF
}

# Quick one-line examples (kept for convenience):
#   tools/build/build_macos.sh                  # build lite + Web frontend + DMG (default, arm64)
#   tools/build/build_macos.sh lite             # build lite + Web frontend + DMG (arm64)
#   tools/build/build_macos.sh full             # build full + Web frontend + DMG (arm64)
#   tools/build/build_macos.sh --x86_64         # build x86_64 only (smaller, Intel Macs)
#   tools/build/build_macos.sh --universal2     # build universal2 (Intel + Apple Silicon, largest)
#   tools/build/build_macos.sh --dual-arch      # build arm64 + x86_64 (two DMGs, no universal2)
#   tools/build/build_macos.sh --all-archs      # build arm64 + x86_64 + universal2
#   tools/build/build_macos.sh lite --no-dmg    # build lite only, no DMG
#   tools/build/build_macos.sh full --no-dmg    # build full only, no DMG

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script supports macOS only."
  exit 1
fi

build_type=lite
want_dmg=true
skip_deps=false
build_arch=arm64

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    lite)
      build_type=lite
      shift
      ;;
    full)
      build_type=full
      shift
      ;;
    --no-dmg)
      want_dmg=false
      shift
      ;;
    --skip-deps)
      skip_deps=true
      shift
      ;;
    --universal2)
      build_arch=universal2
      shift
      ;;
    --x86_64)
      build_arch=x86_64
      shift
      ;;
    --all-archs)
      build_arch=all
      shift
      ;;
    --dual-arch)
      build_arch=dual
      shift
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" 1>&2
      echo "Run 'tools/build/build_macos.sh --help' for usage." 1>&2
      exit 1
      ;;
  esac
done

echo "Frontend: Web"
echo "  Backend serves Web UI at http://localhost:8800"

ensure_venv() {
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null
  # 检查是否已安装 numpy，如果没有则安装
  if ! python -c "import numpy" 2>/dev/null; then
    echo "[env] numpy not found, installing..."
    python -m pip install numpy
  else
    echo "[env] numpy already installed, skipping"
  fi

  # Install core dependencies (docling is not used on macOS)
  echo "[env] Installing dependencies..."
  python -m pip install ".[pdf_export]" pyinstaller >/dev/null
}

get_version() {
  python - <<'PY'
import backend
print(backend.__version__)
PY
}

# Build Flutter Web and copy to backend/static/flutter-web (same as build_win.ps1)
build_flutter_web() {
  if [[ ! -d "${ROOT_DIR}/frontend" ]]; then
    echo "[frontend] WARNING: frontend directory not found, skipping Flutter Web build"
    return 0
  fi
  echo "[frontend] Building Flutter Web..."
  # Note: --web-renderer was removed in Flutter 3.22+; CanvasKit is default. CSP in index.html allows https://www.gstatic.com for CanvasKit.
  ( cd "${ROOT_DIR}/frontend" && flutter clean && flutter pub get && flutter build web --release --no-tree-shake-icons ) || {
    echo "[frontend] ERROR: Flutter Web build failed." 1>&2
    return 1
  }
  local build_fonts="${ROOT_DIR}/frontend/build/web/assets/fonts"
  mkdir -p "${build_fonts}"
  if [[ -d "${ROOT_DIR}/frontend/fonts" ]]; then
    echo "[frontend] Copying fonts to build output..."
    cp -R "${ROOT_DIR}/frontend/fonts/"* "${build_fonts}/" 2>/dev/null || true
  fi
  echo "[frontend] Copying build output to backend/static/flutter-web..."
  rm -rf "${ROOT_DIR}/backend/static/flutter-web"
  mkdir -p "${ROOT_DIR}/backend/static/flutter-web"
  cp -R "${ROOT_DIR}/frontend/build/web/." "${ROOT_DIR}/backend/static/flutter-web/"
  
  # Fix base href and CanvasKit path for PyInstaller packaged version
  echo "[frontend] Fixing base href and CanvasKit path..."
  local index_html="${ROOT_DIR}/backend/static/flutter-web/index.html"
  if [[ -f "$index_html" ]]; then
    # Fix base href
    sed -i '' 's|<base href="/">|<base href="/static/flutter-web/">|g' "$index_html"
    sed -i '' 's|<base href="\$FLUTTER_BASE_HREF">|<base href="/static/flutter-web/">|g' "$index_html"
    sed -i '' "s|<base href='/'||g" "$index_html"
    sed -i '' "s|<base href='\$FLUTTER_BASE_HREF'||g" "$index_html"
    
    # Fix CanvasKit path
    sed -i '' "s|canvasKitBaseUrl: '/canvaskit/'|canvasKitBaseUrl: '/static/flutter-web/canvaskit/'|g" "$index_html"
    sed -i '' 's|canvasKitBaseUrl: "/canvaskit/"|canvasKitBaseUrl: "/static/flutter-web/canvaskit/"|g' "$index_html"
    
    # Add v8BreakIterator polyfill for Safari/Firefox compatibility (if not present)
    if ! grep -q "v8BreakIterator" "$index_html"; then
      echo "[frontend] Adding v8BreakIterator polyfill for Safari/Firefox..."
      # Create a temporary file with the polyfill
      cat > /tmp/polyfill_script.txt << 'POLYFILL_EOF'

  <!-- v8BreakIterator Polyfill for Safari/Firefox compatibility -->
  <script>
    (function() {
      if (typeof Intl === 'undefined') window.Intl = {};
      if (!Intl.v8BreakIterator) {
        console.log('[POLYFILL] Adding Intl.v8BreakIterator for Safari/Firefox');
        Intl.v8BreakIterator = function(locale) {
          this.locale = locale || 'en';
          this.text = '';
          this.pos = 0;
        };
        Intl.v8BreakIterator.prototype.adoptText = function(text) {
          this.text = String(text || '');
          this.pos = 0;
        };
        Intl.v8BreakIterator.prototype.first = function() {
          this.pos = 0;
          return 0;
        };
        Intl.v8BreakIterator.prototype.next = function() {
          if (this.pos >= this.text.length) return -1;
          var remaining = this.text.substring(this.pos);
          var match = remaining.match(/^[\s\n\r\t]+|^[-,.;:!?()[\]{}'"\/\\]+|^./);
          if (match) {
            this.pos += match[0].length;
            return this.pos;
          }
          this.pos++;
          return this.pos;
        };
        Intl.v8BreakIterator.prototype.current = function() {
          return this.pos;
        };
        Intl.v8BreakIterator.prototype.breakType = function() {
          return 'word';
        };
      }
    })();
  </script>
POLYFILL_EOF
      # Insert polyfill after <head> tag
      awk '/<head>/{print; while((getline line < "/tmp/polyfill_script.txt") > 0) print line; close("/tmp/polyfill_script.txt"); next}1' "$index_html" > "${index_html}.tmp" && mv "${index_html}.tmp" "$index_html"
      rm -f /tmp/polyfill_script.txt
      echo "[frontend] v8BreakIterator polyfill added."
    else
      echo "[frontend] v8BreakIterator polyfill already present."
    fi
    
    # Fix HTML structure: ensure </body> tag exists before </html>
    if ! grep -q "</body>" "$index_html"; then
      echo "[frontend] Fixing HTML structure (adding missing </body> tag)..."
      sed -i '' 's|</html>|</body>\n</html>|' "$index_html"
      echo "[frontend] HTML structure fixed."
    fi    
    echo "[frontend] Base href and CanvasKit path fixed."
  else
    echo "[frontend] WARNING: index.html not found, skipping path fixes"
  fi
  
  echo "[frontend] Flutter Web built and copied successfully."
}

build_pyinstaller() {
  local spec_file="$1"
  echo "[build] pyinstaller -y --clean ${spec_file} (build_type=${build_type})"
  OWLANGS_BUILD_TYPE="${build_type}" pyinstaller -y --clean "${spec_file}"
}

# Find or prepare a universal2 Python 3.12 for building
find_universal2_python() {
  # 1. Check for python.org installed Python 3.12
  local py312="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
  if [[ -f "$py312" ]]; then
    echo "$py312"
    return 0
  fi

  # 2. Check cached temporary Python
  local tmp_dir="/tmp/owlangs_build_py312"
  if [[ -f "$tmp_dir/Python.framework/Versions/3.12/bin/python3.12" ]]; then
    echo "$tmp_dir/Python.framework/Versions/3.12/bin/python3.12"
    return 0
  fi

  # 3. Try to download and extract python.org universal2 Python 3.12
  echo "[universal2] Python 3.12 universal2 not found, attempting to download..." >&2
  mkdir -p "$tmp_dir"
  local pkg_file="/tmp/python-3.12.10-macos11.pkg"

  if [[ ! -f "$pkg_file" ]]; then
    echo "[universal2] Downloading Python 3.12.10 universal2 pkg..." >&2
    if ! curl -fsSL -o "$pkg_file" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg" 2>/dev/null; then
      echo "[universal2] ERROR: Failed to download Python 3.12.10" >&2
      return 1
    fi
  fi

  echo "[universal2] Extracting Python package..." >&2
  (cd "$tmp_dir" && xar -xf "$pkg_file") || {
    echo "[universal2] ERROR: Failed to extract pkg with xar" >&2
    return 1
  }

  (cd "$tmp_dir/Python_Framework.pkg" && cat Payload | gunzip -c | cpio -i 2>/dev/null) || {
    echo "[universal2] ERROR: Failed to extract Payload" >&2
    return 1
  }

  ln -sf Python_Framework.pkg "$tmp_dir/Python.framework" 2>/dev/null || true

  if [[ -f "$tmp_dir/Python.framework/Versions/3.12/bin/python3.12" ]]; then
    echo "[universal2] Installing pip for temporary Python..." >&2
    curl -sS https://bootstrap.pypa.io/get-pip.py | \
      DYLD_FRAMEWORK_PATH="$tmp_dir" "$tmp_dir/Python.framework/Versions/3.12/bin/python3.12" - >/dev/null 2>&1
    echo "$tmp_dir/Python.framework/Versions/3.12/bin/python3.12"
    return 0
  fi

  echo "[universal2] ERROR: Could not prepare universal2 Python 3.12" >&2
  echo "[universal2] Please install from: https://www.python.org/downloads/release/python-31210/" >&2
  return 1
}

# Build backend for a specific architecture using universal2 Python
build_backend_for_arch() {
  local ver="$1"
  local target_arch="$2"  # arm64 or x86_64
  local app_name="Owlangs-${ver}-mac"

  echo "[${target_arch}] Building ${target_arch} backend..."

  local uni_py
  uni_py=$(find_universal2_python) || {
    echo "[${target_arch}] ERROR: Cannot find universal2 Python 3.12"
    exit 1
  }
  if [[ -z "$uni_py" ]] || [[ ! -f "$uni_py" ]]; then
    echo "[${target_arch}] ERROR: Cannot find universal2 Python 3.12"
    exit 1
  fi
  echo "[${target_arch}] Using Python: $uni_py"

  local py_dir
  py_dir=$(cd "$(dirname "$uni_py")/../.." && pwd)
  export DYLD_FRAMEWORK_PATH="$py_dir"

  local venv_path="/tmp/owlangs_build_${target_arch}_venv"
  # A directory can exist without bin/activate (interrupted venv, manual /tmp cleanup, etc.).
  # Only skip creation when the venv is actually usable.
  if [[ ! -f "$venv_path/bin/activate" ]]; then
    if [[ -d "$venv_path" ]]; then
      echo "[${target_arch}] Removing incomplete venv (missing bin/activate): ${venv_path}" >&2
      rm -rf "$venv_path"
    fi
    echo "[${target_arch}] Creating venv at ${venv_path}..."
    if [[ "$target_arch" == "x86_64" ]]; then
      if ! arch -x86_64 "$uni_py" -m venv "$venv_path"; then
        echo "[${target_arch}] ERROR: arch -x86_64 python -m venv failed." >&2
        echo "[${target_arch}] On Apple Silicon, install Rosetta: sudo softwareupdate --install-rosetta --agreed-to-license" >&2
        echo "[${target_arch}] Use python.org Python 3.12 (universal2) for cross-arch venvs." >&2
        exit 1
      fi
    else
      if ! "$uni_py" -m venv "$venv_path"; then
        echo "[${target_arch}] ERROR: python -m venv failed." >&2
        exit 1
      fi
    fi
  fi

  if [[ ! -f "$venv_path/bin/activate" ]]; then
    echo "[${target_arch}] ERROR: Expected ${venv_path}/bin/activate after venv creation." >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source "$venv_path/bin/activate"
  echo "[${target_arch}] Installing dependencies..."

  if [[ "$target_arch" == "x86_64" ]]; then
    arch -x86_64 pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
      -e ".[pdf_export]" pyinstaller >/dev/null 2>&1
    echo "[${target_arch}] Running PyInstaller..."
    PYI_TARGET_ARCH=x86_64 arch -x86_64 python -m PyInstaller -y --clean macos.spec
  else
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
      -e ".[pdf_export]" pyinstaller >/dev/null 2>&1
    echo "[${target_arch}] Running PyInstaller..."
    PYI_TARGET_ARCH=arm64 pyinstaller -y --clean macos.spec
  fi

  if [[ ! -f "${ROOT_DIR}/dist/${app_name}" ]]; then
    echo "[${target_arch}] ERROR: backend build failed"
    exit 1
  fi

  # Rename to architecture-specific name (for universal2 merge)
  mv "${ROOT_DIR}/dist/${app_name}" "${ROOT_DIR}/dist/${app_name}-${target_arch}"
  echo "[${target_arch}] Backend built: dist/${app_name}-${target_arch}"
  file "${ROOT_DIR}/dist/${app_name}-${target_arch}"

  # For single-arch builds, restore original filename so app bundling works
  if [[ "$build_arch" != "universal2" ]]; then
    mv "${ROOT_DIR}/dist/${app_name}-${target_arch}" "${ROOT_DIR}/dist/${app_name}"
  fi

  # Re-activate main venv
  if [[ -d "${ROOT_DIR}/.venv" ]]; then
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.venv/bin/activate"
  fi
}

# Build universal2 backend by building arm64 + x86_64 separately and merging with lipo
build_backend_universal2() {
  local ver="$1"
  local app_name="Owlangs-${ver}-mac"

  echo "[universal2] =========================================="
  echo "[universal2] Building universal2 backend (arm64 + x86_64)"
  echo "[universal2] =========================================="

  build_backend_for_arch "$ver" "arm64"
  build_backend_for_arch "$ver" "x86_64"

  # Merge with lipo
  echo "[universal2] Merging arm64 + x86_64 with lipo..."
  lipo -create "${ROOT_DIR}/dist/${app_name}-arm64" "${ROOT_DIR}/dist/${app_name}-x86_64" \
    -output "${ROOT_DIR}/dist/${app_name}"
  rm -f "${ROOT_DIR}/dist/${app_name}-arm64" "${ROOT_DIR}/dist/${app_name}-x86_64"

  echo "[universal2] Verifying universal2 backend..."
  file "${ROOT_DIR}/dist/${app_name}"

  echo "[universal2] =========================================="
  echo "[universal2] Universal2 backend build complete!"
  echo "[universal2] =========================================="
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

# Build the Owlangs desktop application
build_owlangs_app() {
  local backend_binary="$1"
  local ver="$2"
  local use_universal2="${3:-false}"

  echo "[app] Building Owlangs application..."

  # Sync version numbers in spec file
  echo "[app] Syncing version numbers..."
  local version_short="${ver%.*}"  # 1.2.0 from 1.2.0.0
  sed -i '' "s/@VERSION_SHORT@/${version_short}/g" "${ROOT_DIR}/menubar_macos.spec"
  sed -i '' "s/@VERSION_FULL@/${ver}/g" "${ROOT_DIR}/menubar_macos.spec"
  echo "[app] Version set to: ${ver} (short: ${version_short})"

  if [[ "$use_universal2" == true ]]; then
    echo "[app] Building universal2 MenuBar..."
    local uni_py
    uni_py=$(find_universal2_python) || {
      echo "[app] ERROR: Cannot find universal2 Python 3.12 for MenuBar build"
      return 1
    }
    local py_dir
    py_dir=$(cd "$(dirname "$uni_py")/../.." && pwd)
    export DYLD_FRAMEWORK_PATH="$py_dir"

    local mb_venv="/tmp/owlangs_build_mb_universal2_venv"
    if [[ ! -f "$mb_venv/bin/activate" ]]; then
      if [[ -d "$mb_venv" ]]; then
        echo "[app] Removing incomplete MenuBar venv (missing bin/activate): ${mb_venv}" >&2
        rm -rf "$mb_venv"
      fi
      if ! "$uni_py" -m venv "$mb_venv"; then
        echo "[app] ERROR: MenuBar venv creation failed." >&2
        return 1
      fi
    fi
    if [[ ! -f "$mb_venv/bin/activate" ]]; then
      echo "[app] ERROR: Missing ${mb_venv}/bin/activate" >&2
      return 1
    fi
    # shellcheck disable=SC1091
    source "$mb_venv/bin/activate"
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
      pyinstaller pyobjc pyobjc-framework-Cocoa >/dev/null 2>&1
    pyinstaller -y --clean menubar_macos.spec

    # Re-activate main venv
    if [[ -d "${ROOT_DIR}/.venv" ]]; then
      # shellcheck disable=SC1091
      source "${ROOT_DIR}/.venv/bin/activate"
    fi
  elif [[ "$use_universal2" == "x86_64" ]]; then
    echo "[app] Building x86_64 MenuBar..."
    local uni_py
    uni_py=$(find_universal2_python) || {
      echo "[app] ERROR: Cannot find universal2 Python 3.12 for MenuBar build"
      return 1
    }
    local py_dir
    py_dir=$(cd "$(dirname "$uni_py")/../.." && pwd)
    export DYLD_FRAMEWORK_PATH="$py_dir"

    local mb_venv="/tmp/owlangs_build_mb_x86_venv"
    if [[ ! -f "$mb_venv/bin/activate" ]]; then
      if [[ -d "$mb_venv" ]]; then
        echo "[app] Removing incomplete MenuBar x86_64 venv (missing bin/activate): ${mb_venv}" >&2
        rm -rf "$mb_venv"
      fi
      if ! arch -x86_64 "$uni_py" -m venv "$mb_venv"; then
        echo "[app] ERROR: arch -x86_64 venv failed for MenuBar (Rosetta / universal2 Python?)." >&2
        return 1
      fi
    fi
    if [[ ! -f "$mb_venv/bin/activate" ]]; then
      echo "[app] ERROR: Missing ${mb_venv}/bin/activate" >&2
      return 1
    fi
    # shellcheck disable=SC1091
    source "$mb_venv/bin/activate"
    arch -x86_64 pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
      pyinstaller pyobjc pyobjc-framework-Cocoa >/dev/null 2>&1
    PYI_TARGET_ARCH=x86_64 arch -x86_64 python -m PyInstaller -y --clean menubar_macos.spec

    # Re-activate main venv
    if [[ -d "${ROOT_DIR}/.venv" ]]; then
      # shellcheck disable=SC1091
      source "${ROOT_DIR}/.venv/bin/activate"
    fi
  else
    # Verify pyobjc installation
    echo "[app] Verifying pyobjc installation..."
    python -c "import AppKit; import Foundation; print('pyobjc OK')"

    # Build the app
    echo "[app] Running PyInstaller..."
    pyinstaller -y --clean menubar_macos.spec
  fi
  
  if [[ ! -d "${ROOT_DIR}/dist/Owlangs.app" ]]; then
    echo "[app] ERROR: Failed to build Owlangs.app" 1>&2
    return 1
  fi
  
  # Copy backend binary into the app bundle
  local resources_dir="${ROOT_DIR}/dist/Owlangs.app/Contents/Resources"
  mkdir -p "${resources_dir}"
  cp "${ROOT_DIR}/dist/${backend_binary}" "${resources_dir}/OwlangsBackend"
  chmod +x "${resources_dir}/OwlangsBackend"
  
  echo "[app] Owlangs app built: dist/Owlangs.app"
  
  # Verify the app bundle
  echo "[app] Verifying app bundle..."
  local exe_path="${ROOT_DIR}/dist/Owlangs.app/Contents/MacOS/Owlangs"
  if [[ -f "${exe_path}" ]]; then
    echo "[app] Executable found: ${exe_path}"
    ls -lh "${exe_path}"
  else
    echo "[app] WARNING: Executable not found at expected path" 1>&2
    find "${ROOT_DIR}/dist/Owlangs.app" -type f -name "Owlangs*" 2>/dev/null || true
  fi
  
  # Restore placeholders in menubar_macos.spec (keep git clean)
  echo "[app] Restoring version placeholders..."
  sed -i '' "s/'CFBundleShortVersionString': '${version_short}'/'CFBundleShortVersionString': '@VERSION_SHORT@'/g" "${ROOT_DIR}/menubar_macos.spec"
  sed -i '' "s/'CFBundleVersion': '${ver}'/'CFBundleVersion': '@VERSION_FULL@'/g" "${ROOT_DIR}/menubar_macos.spec"
}

# Legacy app bundle creation (kept for compatibility)
create_app_bundle() {
  local src_name="$1"
  local app_name="${2:-Owlangs.app}"
  local src_path="${ROOT_DIR}/dist/${src_name}"
  local app_dir="${ROOT_DIR}/dist/${app_name}"
  local macos_dir="${app_dir}/Contents/MacOS"
  local resources_dir="${app_dir}/Contents/Resources"
  local launcher_path="${macos_dir}/OwlangsLauncher"
  local icon_file=""
  local icon_base="Owlangs"
  local generated_icns="${ROOT_DIR}/assets/Owlangs.icns"
  local launch_target=""

  if [[ ! -e "${src_path}" ]]; then
    echo "[bundle] Expected artifact not found: ${src_path}" 1>&2
    return 1
  fi

  rm -rf "${app_dir}"
  mkdir -p "${macos_dir}" "${resources_dir}"

  if [[ -f "${src_path}" ]]; then
    # onefile artifact: put binary directly into app bundle
    cp "${src_path}" "${macos_dir}/${src_name}"
    chmod +x "${macos_dir}/${src_name}"
    launch_target="\$SCRIPT_DIR/${src_name}"
  elif [[ -d "${src_path}" ]]; then
    # onedir artifact: keep full payload in Resources
    cp -R "${src_path}" "${resources_dir}/payload"
    if [[ ! -x "${resources_dir}/payload/${src_name}/${src_name}" ]]; then
      echo "[bundle] Expected executable not found: ${resources_dir}/payload/${src_name}/${src_name}" 1>&2
      return 1
    fi
    launch_target="\$APP_ROOT/Resources/payload/${src_name}/${src_name}"
  else
    echo "[bundle] Unsupported artifact type: ${src_path}" 1>&2
    return 1
  fi

  # Create launcher script with singleton check
  cat > "${launcher_path}" <<'ENDOFSCRIPT'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCK_FILE="${HOME}/Library/Application Support/Owlangs/owlangs.lock"
PORT=8800

check_process_running() {
    local pid=$1
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

check_port_in_use() {
    if lsof -i ":${PORT}" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Singleton check
if [[ -f "${LOCK_FILE}" ]]; then
    LOCK_PID=$(cat "${LOCK_FILE}" 2>/dev/null || echo "")
    if [[ -n "${LOCK_PID}" ]] && check_process_running "${LOCK_PID}"; then
        echo "[LAUNCHER] Owlangs is already running (PID: ${LOCK_PID})"
        echo "[LAUNCHER] Opening browser..."
        open "http://localhost:${PORT}"
        exit 0
    else
        rm -f "${LOCK_FILE}"
    fi
fi

if check_port_in_use; then
    echo "[LAUNCHER] Port ${PORT} is in use, Owlangs may already be running"
    echo "[LAUNCHER] Opening browser..."
    open "http://localhost:${PORT}"
    exit 0
fi

# Start backend service in Terminal window
echo "[LAUNCHER] Starting Owlangs..."

TERMINAL_SCRIPT=$(mktemp /tmp/owlangs_terminal.XXXXXX)
cat > "${TERMINAL_SCRIPT}" << EOFSCRIPT
#!/bin/bash
echo "=========================================="
echo "  Owlangs Backend Console"
echo "=========================================="
echo ""
echo "This window shows the backend logs."
echo "You can minimize this window, but DO NOT close it."
echo "Closing this window will stop Owlangs."
echo ""
echo "Press Ctrl+C to stop the server."
echo ""
echo "=========================================="
echo ""
cd "${SCRIPT_DIR}"
"${SCRIPT_DIR}/Owlangs-1.2.0.0-mac" -i
# Keep window open after server stops
echo ""
echo "=========================================="
echo "Owlangs has stopped."
echo "Press Enter to close this window."
read
EOFSCRIPT
chmod +x "${TERMINAL_SCRIPT}"

osascript << OSAEOF
tell application "Terminal"
    activate
    do script "${TERMINAL_SCRIPT}; rm -f ${TERMINAL_SCRIPT}"
    set custom title of front window to "Owlangs Console"
end tell
OSAEOF

sleep 2

ENDOFSCRIPT
  chmod +x "${launcher_path}"

  # Use existing icns file
  if [[ -f "${generated_icns}" ]]; then
    cp "${generated_icns}" "${resources_dir}/Owlangs.icns"
    icon_file="${icon_base}"
  else
    echo "[bundle] WARNING: generated icns not found: ${generated_icns}" 1>&2
    echo "[bundle] Please run: python tools/build/macos_create_icns_from_icon_composer.py" 1>&2
    return 1
  fi

  cat > "${app_dir}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Owlangs</string>
  <key>CFBundleDisplayName</key>
  <string>Owlangs</string>
  <key>CFBundleIdentifier</key>
  <string>com.owlangs.desktop</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>OwlangsLauncher</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>CFBundleIconFile</key>
  <string>${icon_file}</string>
  <key>LSMultipleInstancesProhibited</key>
  <true/>
  <key>LSUIElement</key>
  <false/>
  <key>NSUIElement</key>
  <false/>
  <key>LSBackgroundOnly</key>
  <false/>
</dict>
</plist>
EOF

  echo "[bundle] Built app bundle: dist/${app_name}"
}

# Finder drag-install window + auto-open on mount (Docker-style: double-click DMG → window pops up).
configure_dmg_finder_layout() {
  local mount_point="$1"
  local volname="$2"
  local app_item="$3"
  local bg_png="${mount_point}/.background/background.png"
  local ds_store="${mount_point}/.DS_Store"

  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "[dmg] Skipping Finder layout (not macOS)" >&2
    return 0
  fi

  if [[ ! -f "${bg_png}" ]]; then
    echo "[dmg] ERROR: Background image missing: ${bg_png}" >&2
    return 1
  fi

  # Extended attributes on the background file can prevent Finder from binding it.
  xattr -c "${bg_png}" 2>/dev/null || true

  echo "[dmg] Waiting for Finder (avoid AppleScript disk -1728)..."
  sleep 3

  local ds_mtime_before=0
  if [[ -f "${ds_store}" ]]; then
    ds_mtime_before=$(stat -f %m "${ds_store}" 2>/dev/null || echo 0)
  fi

  echo "[dmg] Configuring Finder install window (background + icon layout)..."
  if ! /usr/bin/osascript "${SCRIPT_DIR}/dmg_finder_layout.applescript" "${volname}" "${app_item}"; then
    echo "[dmg] ERROR: dmg_finder_layout.applescript failed." >&2
    echo "[dmg] Grant Automation: System Settings → Privacy → Automation → Terminal → Finder" >&2
    return 1
  fi

  sync
  sleep 2

  local wait=0 ds_ok=false
  while [[ $wait -lt 30 ]]; do
    if [[ -f "${ds_store}" ]]; then
      local ds_mtime_now
      ds_mtime_now=$(stat -f %m "${ds_store}" 2>/dev/null || echo 0)
      if [[ "${ds_mtime_now}" -gt "${ds_mtime_before}" ]]; then
        ds_ok=true
        break
      fi
    fi
    sleep 1
    wait=$((wait + 1))
  done
  if [[ "$ds_ok" == true ]]; then
    echo "[dmg] .DS_Store updated after Finder layout (${wait}s)"
    if strings "${ds_store}" 2>/dev/null | grep -q "background"; then
      echo "[dmg] Verified: .DS_Store references background image"
    else
      echo "[dmg] WARNING: .DS_Store updated but background reference not found in file." >&2
    fi
  else
    echo "[dmg] WARNING: .DS_Store was not updated; install background may be missing." >&2
  fi

  if ! [[ -r "${bg_png}" ]]; then
    echo "[dmg] ERROR: background.png not readable at ${bg_png}" >&2
    return 1
  fi
  chmod 644 "${bg_png}" 2>/dev/null || true

  echo "[dmg] Fixing DMG permissions (excluding .background)..."
  for entry in "${mount_point}"/*; do
    [[ -e "$entry" ]] || continue
    [[ "$(basename "$entry")" == ".background" ]] && continue
    chmod -Rf go-w "$entry" 2>/dev/null || true
  done
  # Do not SetFile -a V .background — causes Write Permissions Error (-61) and can break background binding.
  rm -rf "${mount_point}/.fseventsd" 2>/dev/null || true

  echo "[dmg] Enabling open-on-mount (bless)..."
  if [[ "$(uname -m)" == "arm64" ]]; then
    bless --folder "${mount_point}" 2>/dev/null || true
    bless --folder "${mount_point}" --openfolder "${mount_point}" 2>/dev/null || true
  elif bless --folder "${mount_point}" --openfolder "${mount_point}" 2>/dev/null; then
    :
  elif bless --folder "${mount_point}" --openfolder "${mount_point}" --fsstub "${mount_point}" 2>/dev/null; then
    :
  else
    echo "[dmg] WARNING: bless failed; user may need to open the mounted volume manually." >&2
  fi
  echo "[dmg] Volume will open automatically when DMG is mounted (if bless succeeded)"

  return 0
}

create_dmg() {
  local src_name="$1"
  local dmg_name="$2"
  local staging_dir="${ROOT_DIR}/build/dmg_staging"
  local dmg_root="${staging_dir}/dmg_root"
  
  echo "[dmg] Starting DMG creation process..."
  echo "[dmg] Source: ${src_name}"
  echo "[dmg] Target: ${dmg_name}"
  echo "[dmg] Staging directory: ${staging_dir}"
  echo "[dmg] DMG root: ${dmg_root}"
  
  rm -rf "${staging_dir}"
  echo "[dmg] Cleaned old staging directory"
  
  mkdir -p "${dmg_root}"
  echo "[dmg] Created DMG root directory"

  # Add DMG volume logo (Finder left-top icon).
  # Use existing icns file (should be generated separately)
  local generated_icns="${ROOT_DIR}/assets/Owlangs.icns"
  echo "[dmg] Checking for ICNS file: ${generated_icns}"
  
  if [[ -f "${generated_icns}" ]]; then
    echo "[dmg] Found ICNS file, copying to DMG root..."
    cp "${generated_icns}" "${dmg_root}/.VolumeIcon.icns"
    echo "[dmg] Copied ICNS file successfully"
    
    # Set the volume icon attribute
    if command -v SetFile >/dev/null 2>&1; then
      echo "[dmg] Setting volume icon attribute..."
      SetFile -a C "${dmg_root}"
      echo "[dmg] Volume icon attribute set successfully"
    else
      echo "[dmg] WARNING: SetFile command not found, volume icon may not display correctly"
      echo "[dmg] SetFile is part of Xcode Command Line Tools"
    fi
  else
    echo "[dmg] WARNING: Owlangs.icns not available, skip DMG logo" 1>&2
  fi

  echo "[dmg] Checking for source: ${ROOT_DIR}/dist/${src_name}"
  
  if [[ -f "${ROOT_DIR}/dist/${src_name}" ]]; then
    echo "[dmg] Found source file, copying to DMG root..."
    cp "${ROOT_DIR}/dist/${src_name}" "${dmg_root}/"
    echo "[dmg] Copied source file successfully"
  elif [[ -d "${ROOT_DIR}/dist/${src_name}" ]]; then
    echo "[dmg] Found source directory, copying to DMG root..."
    cp -R "${ROOT_DIR}/dist/${src_name}" "${dmg_root}/"
    echo "[dmg] Copied source directory successfully"
  else
    echo "[dmg] ERROR: Not found: dist/${src_name}" 1>&2
    echo "[dmg] Available files in dist directory:"
    ls -la "${ROOT_DIR}/dist/" 1>&2
    return 1
  fi

  # Drag-to-Applications background (arrow + short title); no README in DMG root.
  echo "[dmg] Rendering drag-install background..."
  mkdir -p "${dmg_root}/.background"
  local dmg_py=python3
  if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ -x "${VIRTUAL_ENV}/bin/python" ]]; then
    dmg_py="${VIRTUAL_ENV}/bin/python"
  elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    dmg_py="${ROOT_DIR}/.venv/bin/python"
  fi
  if ! "${dmg_py}" "${SCRIPT_DIR}/render_dmg_background.py" "${dmg_root}/.background/background.png"; then
    echo "[dmg] ERROR: Failed to render DMG background (need Pillow: pip install pillow)" >&2
    return 1
  fi
  # Do not hide .background before DMG is built; Finder layout runs after mount.

  # Provide Applications shortcut
  echo "[dmg] Creating Applications shortcut..."
  ln -s /Applications "${dmg_root}/Applications" 2>/dev/null || true
  echo "[dmg] Applications shortcut created"
  # install_dependencies.sh is bundled inside Owlangs.app (menubar_macos.spec); no DMG Dependencies folder.

  local volname="Owlangs"
  local rw_dmg="${staging_dir}/${volname}-rw.dmg"
  local out_dmg="${ROOT_DIR}/dist/${dmg_name}"
  mkdir -p "${ROOT_DIR}/dist"
  rm -f "${rw_dmg}" "${out_dmg}"

  if [[ -d "/Volumes/${volname}" ]]; then
    echo "[dmg] Detaching stale /Volumes/${volname} ..."
    hdiutil detach "/Volumes/${volname}" -force 2>/dev/null || true
    sleep 1
  fi

  echo "[dmg] Creating read-write disk image..."
  hdiutil create -srcfolder "${dmg_root}" -volname "${volname}" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW -ov "${rw_dmg}" || {
    echo "[dmg] ERROR: hdiutil create failed" >&2
    return 1
  }

  local attach_line mount_point device
  attach_line=$(hdiutil attach -readwrite -noverify -noautofsck -nobrowse -noautoopen "${rw_dmg}" 2>&1) || {
    echo "[dmg] ERROR: hdiutil attach failed: ${attach_line}" >&2
    return 1
  }
  device=$(echo "${attach_line}" | awk '/^\/dev\// { print $1; exit }')
  if [[ -z "${device}" ]]; then
    echo "[dmg] ERROR: Could not parse hdiutil attach device from: ${attach_line}" >&2
    return 1
  fi
  mount_point=$(echo "${attach_line}" | awk '/\/Volumes\// { print $3; exit }')
  if [[ -z "${mount_point}" ]]; then
    mount_point="/Volumes/${volname}"
  fi
  echo "[dmg] Mounted at ${mount_point} (${device})"

  mkdir -p "${mount_point}/.background"
  cp -f "${dmg_root}/.background/background.png" "${mount_point}/.background/background.png"
  xattr -c "${mount_point}/.background/background.png" 2>/dev/null || true
  chmod 644 "${mount_point}/.background/background.png" 2>/dev/null || true
  if command -v sips >/dev/null 2>&1; then
    sips -s format tiff "${mount_point}/.background/background.png" \
      --out "${mount_point}/.background/background.tiff" >/dev/null 2>&1 || true
  fi
  echo "[dmg] Background image installed on volume ($(du -h "${mount_point}/.background/background.png" | awk '{print $1}'))"

  configure_dmg_finder_layout "${mount_point}" "${volname}" "${src_name}" || {
    hdiutil detach "${device}" -force 2>/dev/null || true
    return 1
  }
  sync
  hdiutil detach "${device}" -force || hdiutil detach "${device}" -force

  echo "[dmg] Compressing DMG → ${out_dmg}"
  hdiutil convert "${rw_dmg}" -format UDZO -imagekey zlib-level=9 -o "${out_dmg}" || {
    echo "[dmg] ERROR: hdiutil convert failed" >&2
    return 1
  }
  rm -f "${rw_dmg}"

  if [[ -f "${out_dmg}" ]]; then
    echo "[dmg] DMG file created successfully"
    echo "[dmg] DMG file location: ${out_dmg}"
    local dmg_size
    dmg_size=$(du -h "${out_dmg}" | cut -f1)
    echo "[dmg] DMG file size: ${dmg_size}"
  else
    echo "[dmg] ERROR: DMG not found after convert" >&2
    return 1
  fi

  rm -rf "${staging_dir}"
  echo "[dmg] Cleaned staging directory"
  echo "[dmg] Built: dist/${dmg_name}"
}

# Copy every top-level .dmg from a partial build directory into dist/ (multi-arch merge safety).
# Full-tree cp can still drop an arch-specific DMG in edge cases; this pass guarantees all installers remain.
copy_dmgs_into_dist() {
  local label="$1"
  local from_dir="$2"
  if [[ ! -d "$from_dir" ]]; then
    echo "[${label}] WARN: missing partial build dir: ${from_dir}" >&2
    return 0
  fi
  shopt -s nullglob
  local dmg_files=("${from_dir}"/*.dmg)
  shopt -u nullglob
  if [[ ${#dmg_files[@]} -eq 0 ]]; then
    echo "[${label}] WARN: no .dmg found under ${from_dir} (that arch build may have failed before DMG step)" >&2
    return 0
  fi
  local f
  for f in "${dmg_files[@]}"; do
    cp -f "$f" "${ROOT_DIR}/dist/"
    echo "[${label}] Preserved DMG: $(basename "$f")"
  done
}

print_macos_launch_debug_hints() {
  echo ""
  echo "If the installed app fails to start, check (in order):"
  echo "  1) Menu bar app log: ~/Library/Logs/Owlangs/menubar.log"
  echo "  2) Run the binary in Terminal (shows stderr):"
  echo "       /Applications/Owlangs.app/Contents/MacOS/Owlangs"
  echo "     (adjust path if you copied the app elsewhere)"
  echo "  3) Console.app: filter for Owlangs or com.owlangs.desktop"
  echo "  4) Crash reports: ~/Library/Logs/DiagnosticReports/ (Owlangs*.ips / .crash)"
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

  build_flutter_web

  local app_name="Owlangs-${ver}-mac"

  if [[ "$build_arch" == "universal2" ]]; then
    build_backend_universal2 "$ver"
  elif [[ "$build_arch" == "x86_64" ]]; then
    build_backend_for_arch "$ver" "x86_64"
  else
    build_pyinstaller "macos.spec"
    if ! verify_artifact "${app_name}"; then
      exit 1
    fi
  fi

  # Build Owlangs desktop app (recommended way to run)
  if [[ "$build_arch" == "universal2" ]]; then
    build_owlangs_app "${app_name}" "${ver}" true
  elif [[ "$build_arch" == "x86_64" ]]; then
    build_owlangs_app "${app_name}" "${ver}" "x86_64"
  else
    build_owlangs_app "${app_name}" "${ver}"
  fi
  
  # Also create legacy app bundle for compatibility
  create_app_bundle "${app_name}" "Owlangs-legacy.app"
  
  # Determine DMG filename based on architecture
  local dmg_name="Owlangs-${ver}-mac"
  if [[ "$build_arch" == "x86_64" ]]; then
    dmg_name="${dmg_name}-x86_64"
  elif [[ "$build_arch" == "arm64" ]]; then
    dmg_name="${dmg_name}-arm64"
  elif [[ "$build_arch" == "universal2" ]]; then
    dmg_name="${dmg_name}-universal2"
  fi

  if $want_dmg; then
    create_dmg "Owlangs.app" "${dmg_name}.dmg"
  fi
  echo ""
  echo "=== Build output ==="
  echo "  Executable: ${ROOT_DIR}/dist/${app_name}"
  echo "  Legacy launcher: ${ROOT_DIR}/dist/Owlangs-legacy.app"
  echo "  Owlangs.app (recommended): ${ROOT_DIR}/dist/Owlangs.app"
  if $want_dmg; then
    echo "  Install package (DMG): ${ROOT_DIR}/dist/${dmg_name}.dmg"
  fi
  echo ""
  if [[ "$build_arch" == "universal2" ]]; then
    echo ""
    echo "✅ Universal2 build: Supports both Intel and Apple Silicon Macs"
  elif [[ "$build_arch" == "x86_64" ]]; then
    echo ""
    echo "✅ x86_64 build: For Intel Macs (smaller size)"
  else
    echo ""
    echo "✅ arm64 build: For Apple Silicon Macs"
  fi
  echo "RECOMMENDED: Use Owlangs.app for best experience"
  echo "  - Stays in Dock when running"
  echo "  - Built-in console window for logs"
  echo "  - Menu bar controls"
  echo "  - Easy start/stop/restart"
  echo ""
  echo "macOS build finished successfully."
}

# If --dual-arch is specified, build arm64 + x86_64 and merge dist (no universal2 pass)
if [[ "$build_arch" == "dual" ]]; then
  echo "========================================"
  echo "  Building arm64 + x86_64 (dual-arch)"
  echo "========================================"

  rm -rf "${ROOT_DIR}/dist_arm64_build" "${ROOT_DIR}/dist_x86_64_build"

  script_path="$0"
  other_args=()
  for arg in "$@"; do
    [[ "$arg" != "--dual-arch" ]] && other_args+=("$arg")
  done

  echo ""
  echo ">>> [1/2] Building arm64..."
  bash "$script_path" ${other_args[@]+"${other_args[@]}"}
  mv "${ROOT_DIR}/dist" "${ROOT_DIR}/dist_arm64_build"

  echo ""
  echo ">>> [2/2] Building x86_64..."
  bash "$script_path" --x86_64 ${other_args[@]+"${other_args[@]}"}
  mv "${ROOT_DIR}/dist" "${ROOT_DIR}/dist_x86_64_build"

  echo ""
  echo ">>> Merging builds to dist/..."
  mkdir -p "${ROOT_DIR}/dist"
  # Copy x86_64 first, then arm64 so shared names (e.g. Owlangs.app) favor arm64 on Apple Silicon hosts.
  cp -R "${ROOT_DIR}/dist_x86_64_build"/* "${ROOT_DIR}/dist/" 2>/dev/null || true
  cp -R "${ROOT_DIR}/dist_arm64_build"/* "${ROOT_DIR}/dist/" 2>/dev/null || true
  # Re-copy all DMGs from each partial build so no arch-specific installer is lost during merge.
  copy_dmgs_into_dist "dual-arch" "${ROOT_DIR}/dist_arm64_build"
  copy_dmgs_into_dist "dual-arch" "${ROOT_DIR}/dist_x86_64_build"
  rm -rf "${ROOT_DIR}/dist_arm64_build" "${ROOT_DIR}/dist_x86_64_build"

  echo ""
  echo "========================================"
  echo "  Dual-arch build finished successfully"
  echo "========================================"
  echo ""
  echo "Output files:"
  ls -lh "${ROOT_DIR}/dist/"*.dmg 2>/dev/null || true
  print_macos_launch_debug_hints
  exit 0
fi

# If --all-archs is specified, build all three architectures sequentially
if [[ "$build_arch" == "all" ]]; then
  echo "========================================"
  echo "  Building all architectures"
  echo "========================================"

  rm -rf "${ROOT_DIR}/dist_arm64_build" "${ROOT_DIR}/dist_x86_64_build" "${ROOT_DIR}/dist_universal2_build"
  
  script_path="$0"
  other_args=()
  for arg in "$@"; do
    [[ "$arg" != "--all-archs" ]] && other_args+=("$arg")
  done
  
  # Build arm64
  echo ""
  echo ">>> [1/3] Building arm64..."
  bash "$script_path" ${other_args[@]+"${other_args[@]}"}
  mv "${ROOT_DIR}/dist" "${ROOT_DIR}/dist_arm64_build"
  
  # Build x86_64
  echo ""
  echo ">>> [2/3] Building x86_64..."
  bash "$script_path" --x86_64 ${other_args[@]+"${other_args[@]}"}
  mv "${ROOT_DIR}/dist" "${ROOT_DIR}/dist_x86_64_build"
  
  # Build universal2
  echo ""
  echo ">>> [3/3] Building universal2..."
  bash "$script_path" --universal2 ${other_args[@]+"${other_args[@]}"}
  mv "${ROOT_DIR}/dist" "${ROOT_DIR}/dist_universal2_build"
  
  # Merge all to final dist
  echo ""
  echo ">>> Merging all builds to dist/..."
  mkdir -p "${ROOT_DIR}/dist"
  cp -R "${ROOT_DIR}/dist_arm64_build"/* "${ROOT_DIR}/dist/" 2>/dev/null || true
  cp -R "${ROOT_DIR}/dist_x86_64_build"/* "${ROOT_DIR}/dist/" 2>/dev/null || true
  cp -R "${ROOT_DIR}/dist_universal2_build"/* "${ROOT_DIR}/dist/" 2>/dev/null || true
  copy_dmgs_into_dist "all-archs" "${ROOT_DIR}/dist_arm64_build"
  copy_dmgs_into_dist "all-archs" "${ROOT_DIR}/dist_x86_64_build"
  copy_dmgs_into_dist "all-archs" "${ROOT_DIR}/dist_universal2_build"
  rm -rf "${ROOT_DIR}/dist_arm64_build" "${ROOT_DIR}/dist_x86_64_build" "${ROOT_DIR}/dist_universal2_build"
  
  echo ""
  echo "========================================"
  echo "  All architectures built successfully!"
  echo "========================================"
  echo ""
  echo "Output files:"
  ls -lh "${ROOT_DIR}/dist/"*.dmg 2>/dev/null || true
  print_macos_launch_debug_hints
  exit 0
fi

main "$@"