#!/usr/bin/env bash
set -euo pipefail
echo "[Omar Gate] starting"
npm ci --ignore-scripts
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build
source .venv/bin/activate
pip install -r apps/api/requirements.txt
pip install -r apps/api/requirements-dev.txt
pytest -q
ruff check .
mypy apps/api
echo "[Omar Gate] passed"
