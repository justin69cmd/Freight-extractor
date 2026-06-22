#!/usr/bin/env bash
# Frontend dev server (macOS/Linux). Run after start-backend.sh, in a 2nd terminal.
set -e
cd "$(dirname "$0")/frontend"

npm install
echo ""
echo "  Frontend running ->  http://localhost:3000"
echo ""
exec npm run dev
