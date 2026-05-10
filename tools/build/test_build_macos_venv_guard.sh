#!/usr/bin/env bash
# Ensures the same guard used in build_macos.sh removes incomplete temp venv dirs.
set -euo pipefail

tmpdir=$(mktemp -d)
trap 'rm -rf "${tmpdir}"' EXIT

fake="${tmpdir}/owlangs_build_x86_64_venv"
mkdir -p "${fake}"

if [[ ! -f "${fake}/bin/activate" ]]; then
  rm -rf "${fake}"
fi

if [[ -e "${fake}" ]]; then
  echo "FAIL: incomplete venv dir should have been removed" >&2
  exit 1
fi

echo "ok: incomplete venv guard behaves as expected"
