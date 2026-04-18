#!/usr/bin/env bash
# This script is split into dev and deploy. Use:
#   - Development (build from source): ./tools/setup/install_deps_macos_dev.sh
#   - Deployment (run packaged app, optional deps): ./tools/setup/install_deps_macos_deploy.sh
# See docs/INSTALL_MACOS.md for the index.

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
echo "Use one of:"
echo "  Development (Python, Flutter, Redis, Calibre): $SCRIPT_DIR/install_deps_macos_dev.sh"
echo "  Deployment (optional Redis, Calibre only):    $SCRIPT_DIR/install_deps_macos_deploy.sh"
echo ""
echo "See docs/INSTALL_MACOS.md for the full index."
exit 0
