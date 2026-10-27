#!/usr/bin/env bash
# macOS quick start; installs dependencies once then starts all four local services.
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from python.org or Homebrew." >&2
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -r requirements.txt
exec python run_demo.py
