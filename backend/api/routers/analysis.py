from fastapi import APIRouter
import redis

router = APIRouter()
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

@router.get("/analysis/{sesion_id}")
def obtener_analysis(sesion_id: str):
    """
    Devuelve el último JSON de clasificación de postura para la sesión,
    almacenado en Redis bajo el hash 'analysis:{sesion_id}'.
    Convierte cada valor a entero antes de devolverlo.
    """
    key = f"analysis:{sesion_id}"
    raw = r.hgetall(key)  # Redis devuelve un dict { campo: "valor", ... }

    if not raw:
        return {}

    result: dict[str, int] = {}
    for k, v in raw.items():
        try:
            result[k] = int(v)
        except ValueError:
            # Si no se puede convertir a entero, asignamos 0 por defecto
            try:
                result[k] = int(float(v))
            except ValueError:
                result[k] = 0

    return result
