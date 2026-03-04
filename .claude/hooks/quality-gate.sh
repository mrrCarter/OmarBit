#!/usr/bin/env bash
set -euo pipefail
echo "[Omar Gate] starting"

# Node.js gates — deterministic install
if [ -f package-lock.json ]; then
  npm ci
else
  echo "[Omar Gate] ERROR: package-lock.json not found. Run 'npm install' first."
  exit 1
fi
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build

# Python gates — create venv if missing
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi

pip install --require-hashes -r apps/api/requirements-locked.txt
pip install --require-hashes -r apps/api/requirements-dev-locked.txt
ruff check .
pytest -q
mypy apps/api --exclude 'tests/'
echo "[Omar Gate] passed"
