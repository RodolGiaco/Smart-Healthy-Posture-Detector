from fastapi import APIRouter
import redis
import json


router = APIRouter()
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

@router.get("/metricas/{sesion_id}")
def obtener_metricas(sesion_id: str):
    """Última métrica guardada de la sesión (lista `metricas:{sesion_id}`
    en Redis, la va empujando `PostureMonitor.save_data_to_redis`)."""
    key = f"metricas:{sesion_id}"
    ultimas = r.lrange(key, -1, -1)  # última métrica
    return json.loads(ultimas[0]) if ultimas else {}
