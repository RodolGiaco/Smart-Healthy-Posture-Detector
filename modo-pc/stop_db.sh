#!/usr/bin/env bash
# Stops the project-local PostgreSQL and Redis instances started by
# modo-pc/start_db.sh. Data is preserved (Postgres data dir stays in
# .devdata/postgres); this only stops the running processes.
set -euo pipefail

PG_BIN="$(pg_config --bindir)"
export PATH="$PG_BIN:$PATH"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PGDATA="$ROOT_DIR/.devdata/postgres"
REDIS_PORT=6379

if [ -d "$PGDATA" ] && pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "🐘 Deteniendo PostgreSQL local ..."
  pg_ctl -D "$PGDATA" stop
else
  echo "PostgreSQL local no estaba corriendo"
fi

if redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
  echo "🧠 Deteniendo Redis local ..."
  redis-cli -p "$REDIS_PORT" shutdown nosave
else
  echo "Redis local no estaba corriendo"
fi
