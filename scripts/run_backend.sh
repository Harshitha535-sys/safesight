#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd -- "$SCRIPT_DIR/../backend" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.10+ and python3-venv, then retry." >&2
  exit 1
fi
"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "SafeSight needs Python 3.10 or newer. Current interpreter: $($PYTHON_BIN --version)" >&2
  exit 1
}

cd "$BACKEND_DIR"
if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -r requirements.txt
if [[ ! -s models/yolox_nano.onnx ]]; then
  python -m app.cv.fetch_model
fi
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000