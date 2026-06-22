#!/usr/bin/env bash
# Native local backend (macOS/Linux) — SQLite + in-process jobs, no Docker.
set -e
cd "$(dirname "$0")/backend"

[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements-local.txt
[ -f .env ] || cp .env.example .env

python -m scripts.init_db
echo ""
echo "  Backend running  ->  http://localhost:8000   (API docs: /docs)"
echo ""
exec uvicorn app.main:app --reload --port 8000
