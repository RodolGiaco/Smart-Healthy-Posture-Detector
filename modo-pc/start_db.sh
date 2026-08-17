#!/usr/bin/env bash
# Starts a project-local PostgreSQL instance and a local Redis instance for
# development on a regular PC (no Raspberry Pi involved).
#
# - PostgreSQL data lives in .devdata/postgres (git-ignored), listens on
#   127.0.0.1:5433 only, so it never touches your system-wide Postgres
#   cluster on 5432.
# - Redis listens on the default port 6379, since backend/, bot/ and
#   posture_monitor.py all connect to that port directly (not configurable
#   via env var today).
#
# Safe to re-run: if either service is already up, it's left as-is.
set -euo pipefail

# initdb/pg_ctl no siempre están en el PATH (Debian/Ubuntu los deja en
# /usr/lib/postgresql/<versión>/bin). pg_config sí está en el PATH y sabe
# dónde viven.
PG_BIN="$(pg_config --bindir)"
export PATH="$PG_BIN:$PATH"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PGDATA="$ROOT_DIR/.devdata/postgres"
PGPORT=5433
PGLOG="$ROOT_DIR/.devdata/postgres.log"
REDIS_PORT=6379
REDIS_LOG="$ROOT_DIR/.devdata/redis.log"
REDIS_PID="$ROOT_DIR/.devdata/redis.pid"

mkdir -p "$ROOT_DIR/.devdata"

# --- PostgreSQL ---
if ! pg_isready -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
  if [ ! -d "$PGDATA" ]; then
    echo "🐘 Inicializando base de datos local en $PGDATA ..."
    initdb -D "$PGDATA" -U shpd --auth=trust >/dev/null
  fi
  echo "🐘 Levantando PostgreSQL local en 127.0.0.1:$PGPORT ..."
  pg_ctl -D "$PGDATA" \
    -o "-p $PGPORT -c listen_addresses='127.0.0.1' -c unix_socket_directories=''" \
    -l "$PGLOG" start
  sleep 1
  psql -h 127.0.0.1 -p "$PGPORT" -U shpd -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'shpd_db'" | grep -q 1 \
    || psql -h 127.0.0.1 -p "$PGPORT" -U shpd -d postgres -c "CREATE DATABASE shpd_db;" >/dev/null
  echo "✅ PostgreSQL listo (db: shpd_db, user: shpd, sin password)"
else
  echo "✅ PostgreSQL ya estaba arriba en el puerto $PGPORT"
fi

# --- Redis ---
if ! redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
  echo "🧠 Levantando Redis local en el puerto $REDIS_PORT ..."
  redis-server --port "$REDIS_PORT" --daemonize yes --dir "$ROOT_DIR/.devdata" \
    --pidfile "$REDIS_PID" --logfile "$REDIS_LOG"
  sleep 1
  redis-cli -p "$REDIS_PORT" ping >/dev/null && echo "✅ Redis listo"
else
  echo "✅ Redis ya estaba arriba en el puerto $REDIS_PORT"
fi

echo ""
echo "DATABASE_URL para tu .env:"
echo "  postgresql://shpd@127.0.0.1:$PGPORT/shpd_db"
