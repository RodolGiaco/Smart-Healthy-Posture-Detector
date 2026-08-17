#!/usr/bin/env bash
# Starts the Telegram bot on a regular PC for local testing (no Raspberry
# Pi required). Brings up the local dev Postgres/Redis first.
#
# Requires: .venv created and populated (see requirements-pc.txt) and a
# .env file at the repo root (copy .env.example) with a real TELEGRAM_TOKEN.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo "⚠️  No hay .env en la raíz del repo. Copiá .env.example a .env y completá las variables." >&2
  exit 1
fi

bash "$ROOT_DIR/modo-pc/start_db.sh"

source "$ROOT_DIR/.venv/bin/activate"
cd "$ROOT_DIR/bot"

echo ""
echo "🤖 Bot escuchando por polling. Buscalo en Telegram y mandale /start."
exec python3 app/bot.py
