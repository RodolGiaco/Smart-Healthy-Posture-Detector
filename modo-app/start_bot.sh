#!/usr/bin/env bash
# activa el virtualenv
source /home/rodo/shpd/shpd-all/shpd11/bin/activate
# exporta la DB
export DATABASE_URL="postgresql://postgres:user@localhost:5432/shpd_db"
# cambia al directorio del bot
cd /home/rodo/shpd/shpd-all/bot
# ejecuta con el python del venv
exec python3 app/bot.py
