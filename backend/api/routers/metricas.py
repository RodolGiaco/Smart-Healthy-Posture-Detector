from fastapi import APIRouter
import redis
import json


router = APIRouter()
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

@router.get("/metricas/{sesion_id}")
def obtener_metricas(sesion_id: str):
    key = f"metricas:{sesion_id}"
    ultimas = r.lrange(key, -1, -1)  # última métrica
    return json.loads(ultimas[0]) if ultimas else {}
