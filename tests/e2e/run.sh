#!/usr/bin/env bash
# Поднимает сервер на временной БД и прогоняет сквозную проверку фронтенда. Нужны node 20+ и npm install в этой папке.
set -euo pipefail
cd "$(dirname "$0")/../.."
PORT=${PORT:-8765}
DB=$(mktemp -d)/e2e.db
DATABASE_URL="sqlite+aiosqlite:///$DB" GEMINI_API_KEY="" DEV=1 python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > /tmp/e2e-server.log 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.25; done
BASE="http://127.0.0.1:$PORT" node tests/e2e/e2e.mjs
