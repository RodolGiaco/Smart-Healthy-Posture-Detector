#!/usr/bin/env bash
# Starts the frontend on a regular PC for local testing.
# Talks to the backend via window.location.hostname:8765, so as long as you
# open it as http://localhost:3000 it will reach a backend running on
# localhost:8765 (started with modo-pc/start_backend.sh).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

if [ ! -d node_modules ]; then
  echo "📦 Instalando dependencias del frontend (primera vez)..."
  npm install
fi

export HOST="0.0.0.0"
echo "🚀 Frontend disponible en http://localhost:3000"
exec npm start
