#!/bin/sh
set -eu
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "Python 3.10+ is required (found: $("$PY" --version 2>&1 || echo none))." >&2
  echo "Install it with: brew install python" >&2
  exit 1
fi

"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
chmod +x top-views

echo
echo "Installed. Try: ./top-views https://www.tiktok.com/@abi_asija"
