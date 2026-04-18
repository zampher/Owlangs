#!/usr/bin/env bash

rm -rf build/ dist/ .eggs/ Owlangs.egg-info/

set -euo pipefail

# Build Owlangs macOS app (lite or full) and create DMG by default.
# Frontend: Web only (Desktop mode removed to simplify architecture)
#   Web: Backend serves Flutter Web at /; user opens http://localhost:8800 in browser
#
# Usage:
#   tools/build/build_macos.sh              # build lite + Web frontend + DMG (default)
#   tools/build/build_macos.sh lite         # build lite + Web frontend + DMG
#   tools/build/build_macos.sh full         # build full + Web frontend + DMG
#   tools/build/build_macos.sh lite --no-dmg   # build lite only, no DMG
#   tools/build/build_macos.sh full --no-dmg   # build full only, no DMG

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
    *)
      echo "Unknown argument: $1" 1>&2
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
  python -m pip install . pyinstaller >/dev/null
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

# Build the Owlangs desktop application
build_owlangs_app() {
  local backend_binary="$1"
  local ver="$2"
  
  echo "[app] Building Owlangs application..."
  
  # Sync version numbers in spec file
  echo "[app] Syncing version numbers..."
  local version_short="${ver%.*}"  # 1.2.0 from 1.2.0.0
  sed -i '' "s/@VERSION_SHORT@/${version_short}/g" "${ROOT_DIR}/menubar_macos.spec"
  sed -i '' "s/@VERSION_FULL@/${ver}/g" "${ROOT_DIR}/menubar_macos.spec"
  echo "[app] Version set to: ${ver} (short: ${version_short})"
  
  # Verify pyobjc installation
  echo "[app] Verifying pyobjc installation..."
  python -c "import AppKit; import Foundation; print('pyobjc OK')"
  
  # Build the app
  echo "[app] Running PyInstaller..."
  pyinstaller -y --clean menubar_macos.spec
  
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
  <string>13.0</string>
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

  # Create DMG background image with installation instructions
  echo "[dmg] Creating DMG background image..."
  local bg_dir="${staging_dir}/background"
  mkdir -p "${bg_dir}"
  
  # Create a simple background image using ImageMagick or sips
  # First, let's create the background using Python with PIL
  python3 << 'PYEOF'
from PIL import Image, ImageDraw, ImageFont
import os

# Create a 800x700 background image
width, height = 800, 700
img = Image.new('RGB', (width, height), color='#f5f5f7')
draw = ImageDraw.Draw(img)

# Try to use system fonts, fallback to default
try:
    # Try to use macOS system fonts
    title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
except:
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

# Draw title
title_text = "Owlangs Installation"
subtitle_text = "Drag Owlangs.app to Applications"

# Calculate text position (centered)
bbox = draw.textbbox((0, 0), title_text, font=title_font)
title_width = bbox[2] - bbox[0]
title_x = (width - title_width) // 2
draw.text((title_x, 30), title_text, fill='#1d1d1f', font=title_font)

bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
subtitle_width = bbox[2] - bbox[0]
subtitle_x = (width - subtitle_width) // 2
draw.text((subtitle_x, 80), subtitle_text, fill='#86868b', font=subtitle_font)

# Draw installation steps
steps = [
    ("1", "Drag Owlangs.app to Applications"),
    ("2", "Run Dependencies/install_dependencies.sh"),
    ("3", "Open Owlangs from Launchpad"),
    ("4", "Use menu bar to start & open browser")
]

y_pos = 150
for num, step in steps:
    # Draw circle with number
    circle_x, circle_y = 100, y_pos + 5
    draw.ellipse([circle_x-15, circle_y-15, circle_x+15, circle_y+15], fill='#007aff')
    bbox = draw.textbbox((0, 0), num, font=text_font)
    num_width = bbox[2] - bbox[0]
    num_height = bbox[3] - bbox[1]
    draw.text((circle_x - num_width//2, circle_y - num_height//2), num, fill='white', font=text_font)
    
    # Draw step text
    draw.text((140, y_pos), step, fill='#1d1d1f', font=text_font)
    y_pos += 50

# Draw system requirements section
y_pos += 20
draw.text((50, y_pos), "System Requirements:", fill='#1d1d1f', font=subtitle_font)
y_pos += 35

requirements = [
    "• macOS 13.0 or later",
    "• 4GB RAM (8GB recommended)",
    "• 2GB free disk space"
]

for req in requirements:
    draw.text((70, y_pos), req, fill='#86868b', font=small_font)
    y_pos += 25

# Draw dependencies note
y_pos += 20
draw.text((50, y_pos), "Dependencies:", fill='#1d1d1f', font=subtitle_font)
y_pos += 35

deps = [
    "• Run: Dependencies/install_dependencies.sh",
    "• Auto-checks & installs missing items"
]

for dep in deps:
    draw.text((70, y_pos), dep, fill='#86868b', font=small_font)
    y_pos += 25

# Draw support info at bottom
support_text = "Support: github.com/zampher/owlangs"
bbox = draw.textbbox((0, 0), support_text, font=small_font)
support_width = bbox[2] - bbox[0]
support_x = (width - support_width) // 2
draw.text((support_x, height - 40), support_text, fill='#86868b', font=small_font)

# Save the image
bg_path = os.environ.get('BG_PATH', '/tmp/dmg_background.png')
img.save(bg_path, 'PNG')
print(f"Background image created: {bg_path}")
PYEOF

  # Move the background image to DMG staging
  if [[ -f "/tmp/dmg_background.png" ]]; then
    mv "/tmp/dmg_background.png" "${bg_dir}/.background.png"
    echo "[dmg] Background image created successfully"
  else
    echo "[dmg] WARNING: Failed to create background image"
  fi

  # Create a simple README file (flat structure, English filename)
  echo "[dmg] Creating README..."
  cat > "${dmg_root}/README.txt" <<'EOF'
Owlangs Installation Guide
==========================

QUICK INSTALL (Recommended: Owlangs.app)
----------------------------------------
1. Drag Owlangs.app to Applications folder
2. Open terminal and run: cd /Volumes/Owlangs/Dependencies && ./install_dependencies.sh
3. Open Owlangs from Launchpad
4. Click "Start Server" from the menu bar to start the backend
5. Select "Open Browser" to access Owlangs in your browser

FEATURES
--------
Owlangs.app provides:
  • Dock icon stays visible when running
  • Built-in console window for backend logs
  • Menu bar controls for quick access
  • Auto-start option in Preferences
  • Easy start/stop/restart

ALTERNATIVE: Legacy Launcher (Owlangs-legacy.app)
--------------------------------------------------
Owlangs-legacy.app opens Terminal for logs.
Use Owlangs.app for better integrated experience.

SYSTEM REQUIREMENTS
-------------------
• macOS 13.0 or later
• 4GB RAM (8GB recommended)  
• 2GB free disk space

DEPENDENCIES
------------
For full functionality, install these dependencies:

EASY INSTALL (Recommended)
----------------------------
Run the smart installer:

  cd /Volumes/Owlangs/Dependencies
  ./install_dependencies.sh

This will automatically check and install missing dependencies:
  • Homebrew (package manager)
  • Redis (caching & tasks)
  • Pandoc (document conversion)
  • XeLaTeX (PDF math rendering)

MANUAL INSTALL
--------------
If you prefer manual installation:

1. Homebrew
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

2. Redis
   brew install redis && brew services start redis

3. Pandoc
   brew install pandoc

4. XeLaTeX
   brew install --cask mactex
   # OR: brew install --cask tinytex

CHECK STATUS
------------
To check what's installed:

  cd /Volumes/Owlangs/Dependencies
  ./install_dependencies.sh status

TROUBLESHOOTING
---------------
• Gatekeeper blocked: System Settings > Privacy & Security > Allow
• App won't start: Check dependencies are installed
• Translation failed: Configure API KEY
• Export failed: Install Pandoc
• PDF export failed: Install XeLaTeX

SUPPORT
-------
https://github.com/zampher/owlangs
EOF

  # Provide Applications shortcut
  echo "[dmg] Creating Applications shortcut..."
  ln -s /Applications "${dmg_root}/Applications" 2>/dev/null || true
  echo "[dmg] Applications shortcut created"

  # Copy dependencies folder (only if exists, flat structure)
  if [[ -d "${ROOT_DIR}/3rdParty/macos" ]]; then
    echo "[dmg] Copying dependencies..."
    cp -R "${ROOT_DIR}/3rdParty/macos" "${dmg_root}/Dependencies"
    echo "[dmg] Dependencies copied successfully"
  fi

  echo "[dmg] Creating DMG file using hdiutil makehybrid..."
  echo "[dmg] Command: hdiutil makehybrid -hfs -hfs-volume-name \"Owlangs\" -o \"${ROOT_DIR}/dist/${dmg_name}\" \"${dmg_root}\""
  
  hdiutil makehybrid -hfs -hfs-volume-name "Owlangs" -o "${ROOT_DIR}/dist/${dmg_name}" "${dmg_root}"
  
  if [[ $? -eq 0 ]]; then
    echo "[dmg] DMG file created successfully"
    echo "[dmg] DMG file location: ${ROOT_DIR}/dist/${dmg_name}"
    if [[ -f "${ROOT_DIR}/dist/${dmg_name}" ]]; then
      local dmg_size=$(du -h "${ROOT_DIR}/dist/${dmg_name}" | cut -f1)
      echo "[dmg] DMG file size: ${dmg_size}"
    else
      echo "[dmg] WARNING: DMG command completed but file not found!" 1>&2
    fi
  else
    echo "[dmg] ERROR: hdiutil makehybrid command failed with exit code $?" 1>&2
    return 1
  fi
  
  rm -rf "${staging_dir}"
  echo "[dmg] Cleaned staging directory"
  echo "[dmg] Built: dist/${dmg_name}"
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
  build_pyinstaller "macos.spec"
  local app_name="Owlangs-${ver}-mac"
  if ! verify_artifact "${app_name}"; then
    exit 1
  fi
  
  # Build Owlangs desktop app (recommended way to run)
  build_owlangs_app "${app_name}" "${ver}"
  
  # Also create legacy app bundle for compatibility
  create_app_bundle "${app_name}" "Owlangs-legacy.app"
  
  if $want_dmg; then
    create_dmg "Owlangs.app" "Owlangs-${ver}-mac.dmg"
  fi
  echo ""
  echo "=== Build output ==="
  echo "  Executable: ${ROOT_DIR}/dist/${app_name}"
  echo "  Legacy launcher: ${ROOT_DIR}/dist/Owlangs-legacy.app"
  echo "  Owlangs.app (recommended): ${ROOT_DIR}/dist/Owlangs.app"
  if $want_dmg; then
    echo "  Install package (DMG): ${ROOT_DIR}/dist/Owlangs-${ver}-mac.dmg"
  fi
  echo ""
  echo "RECOMMENDED: Use Owlangs.app for best experience"
  echo "  - Stays in Dock when running"
  echo "  - Built-in console window for logs"
  echo "  - Menu bar controls"
  echo "  - Easy start/stop/restart"
  echo ""
  echo "macOS build finished successfully."
}

main "$@"