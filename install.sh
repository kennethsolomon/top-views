#!/bin/sh
set -eu
cd "$(dirname "$0")"

# Prefer versions that have prebuilt wheels for playwright/greenlet/curl-cffi.
# Brand-new Python releases (e.g. 3.15) often lack them or ship a broken ensurepip.
if [ -z "${PYTHON:-}" ]; then
  for v in python3.13 python3.12 python3.14 python3.11 python3.10; do
    if command -v "$v" >/dev/null 2>&1; then PYTHON="$v"; break; fi
  done
fi
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  echo "No supported Python found (need 3.10-3.14)." >&2
  echo "Install one with: brew install python@3.13" >&2
  exit 1
fi
echo "Using $PY ($("$PY" --version 2>&1))"

"$PY" -m venv --clear .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
chmod +x top-views

echo
echo "Installed. Try: ./top-views https://www.tiktok.com/@abi_asija"
