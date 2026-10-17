#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd -- "$SCRIPT_DIR/../frontend" && pwd)"
cd "$FRONTEND_DIR"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 18+ and npm are required. Install them, then retry." >&2
  exit 1
fi
# npm install reconciles package.json with the included lockfile if they differ.
npm install
exec npm run dev -- --host 127.0.0.1