#!/usr/bin/env bash
# Fetch Typst @preview packages (cmarker, mitex) into 3rdParty for offline builds.
# Usage:
#   tools/build/fetch_typst_packages.sh
#
# Requires network on first run. Re-run is a no-op when packages already exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PACKAGES_DIR="$ROOT_DIR/3rdParty/typst/packages"
CMARKER_DIR="$PACKAGES_DIR/preview/cmarker/0.1.8"
MITEX_DIR="$PACKAGES_DIR/preview/mitex/0.2.6"

packages_complete() {
  [[ -d "$CMARKER_DIR" && -d "$MITEX_DIR" ]]
}

if packages_complete; then
  echo "[typst-packages] Already present under $PACKAGES_DIR"
  exit 0
fi

TYPST_BIN=""
if [[ -d "$ROOT_DIR/3rdParty/macos" ]]; then
  while IFS= read -r candidate; do
    if [[ -x "$candidate" ]]; then
      TYPST_BIN="$candidate"
      break
    fi
  done < <(find "$ROOT_DIR/3rdParty/macos" -maxdepth 3 -name typst -type f 2>/dev/null | sort -r)
fi
if [[ -z "$TYPST_BIN" ]] && [[ -d "$ROOT_DIR/3rdParty/linux" ]]; then
  while IFS= read -r candidate; do
    if [[ -x "$candidate" ]]; then
      TYPST_BIN="$candidate"
      break
    fi
  done < <(find "$ROOT_DIR/3rdParty/linux" -maxdepth 3 -name typst -type f 2>/dev/null | sort -r)
fi
if [[ -z "$TYPST_BIN" ]] && command -v typst >/dev/null 2>&1; then
  TYPST_BIN="$(command -v typst)"
fi
if [[ -z "$TYPST_BIN" ]]; then
  echo "[typst-packages] ERROR: Typst CLI not found under 3rdParty or PATH" >&2
  exit 1
fi

echo "[typst-packages] Using Typst: $TYPST_BIN"
echo "[typst-packages] Downloading @preview packages to $PACKAGES_DIR ..."

mkdir -p "$PACKAGES_DIR"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/owlangs_typst_fetch.XXXXXX")"
cleanup() {
  rm -rf "$TEMP_DIR"
  unset TYPST_PACKAGE_CACHE_PATH || true
}
trap cleanup EXIT

cat >"$TEMP_DIR/fetch_packages.typ" <<'EOF'
#import "@preview/cmarker:0.1.8"
#import "@preview/mitex:0.2.6": mitex
EOF

export TYPST_PACKAGE_CACHE_PATH="$PACKAGES_DIR"
"$TYPST_BIN" compile "$TEMP_DIR/fetch_packages.typ" "$TEMP_DIR/fetch_packages.pdf"

if ! packages_complete; then
  echo "[typst-packages] ERROR: compile succeeded but packages missing under $PACKAGES_DIR" >&2
  exit 1
fi

echo "[typst-packages] OK: cmarker + mitex cached for offline use"
