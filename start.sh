#!/usr/bin/env sh
# CropDoc GB: one command to install (first run) and start the app on http://127.0.0.1:8000
# Usage: ./start.sh            (opens your browser)
#        ./start.sh --no-browser --port 8080
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in python3.11 python3.12 python3.13 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      PY="$candidate"
      break
    fi
  done
fi
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is required (3.11 recommended): https://www.python.org/downloads/"
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating a virtual environment in .venv ..."
  "$PY" -m venv .venv
fi
.venv/bin/python scripts/ensure_deps.py
exec .venv/bin/python backend/run.py "$@"
