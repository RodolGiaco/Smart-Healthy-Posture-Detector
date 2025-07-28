from fastapi import APIRouter
from datetime import datetime
import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

router = APIRouter(prefix="/timeline", tags=["timeline"])

@router.get("/{session_id}")
def obtener_timeline(session_id: str):
    """Devuelve la lista de eventos de postura (timestamp, postura, tiempo acumulado).
    Por ahora, si la lista no existe en Redis, devuelve datos dummy para demo.
    """
    key = f"timeline:{session_id}"
    raw = r.lrange(key, 0, -1)
    eventos = []
    for item in raw:
        try:
            ev = json.loads(item)
            # Formatear timestamp a HH:MM:SS local
            ts = datetime.fromisoformat(ev.get("timestamp"))
            ev["timestamp"] = ts.strftime("%H:%M:%S")
            eventos.append(ev)
        except Exception:
            continue
    return eventos  # puede ser lista vacía 
