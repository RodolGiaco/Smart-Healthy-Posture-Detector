#!/usr/bin/env bash
# Starts the backend on a regular PC for local testing (no Raspberry Pi
# required). Brings up the local dev Postgres/Redis first, then runs
# uvicorn with --reload so code changes restart the server automatically.
#
# Requires: .venv created and populated (see requirements-pc.txt) and a
# .env file at the repo root (copy .env.example) with TELEGRAM_TOKEN and
# OPENAI_API_KEY filled in with real values.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo "⚠️  No hay .env en la raíz del repo. Copiá .env.example a .env y completá las variables." >&2
  exit 1
fi

bash "$ROOT_DIR/modo-pc/start_db.sh"

source "$ROOT_DIR/.venv/bin/activate"
cd "$ROOT_DIR/backend"

echo ""
echo "🚀 Backend disponible en http://localhost:8765 (docs en /docs)"
exec uvicorn main:app \
  --host 0.0.0.0 --port 8765 \
  --reload \
  --ws websockets --ws-ping-interval 20 --ws-ping-timeout 20
