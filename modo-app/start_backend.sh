#!/usr/bin/env bash
source /home/rodo/shpd11/bin/activate
export DATABASE_URL="postgresql://postgres:user@localhost:5432/shpd_db"
cd /home/rodo/shpd/shpd-all/backend
exec uvicorn main:app \
  --host 0.0.0.0 --port 8765 \
  --ws 'websockets' --ws-ping-interval 20 --ws-ping-timeout 20
