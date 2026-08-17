from fastapi import APIRouter
from fastapi import HTTPException
import redis
import logging
from app.core.ws_manager import ws_manager
from starlette.websockets import WebSocketState
r = redis.Redis(host="localhost", port=6379, decode_responses=True)
logger = logging.getLogger("calibracion")
logger.setLevel(logging.DEBUG)
router = APIRouter(prefix="/calib", tags=["calibracion"])

@router.get("/progress/{session_id}")
def calib_progress(session_id: str):
    """
    Progreso de calibración en curso: lee `calib:{session_id}` (acumulado
    por `PostureMonitor` mientras `save_metrics=False`) y lo resume en
    segundos buenos/malos más un booleano `correcta` que el frontend usa
    para pintar el círculo de progreso.
    """
    data = r.hgetall(f"calib:{session_id}")
    good = float(data.get("good_time", 0))
    bad  = float(data.get("bad_time", 0))
    return {
        "good_time": good,
        "bad_time": bad,
        "correcta": good > bad
    }

@router.post("/mode/reset/{device_id}")
def reset_mode(device_id: str):
    """
    Borra el campo `mode` de `shpd-data:{device_id}` para que `video_input`
    vuelva a decidir calibración vs. normal por el query string de la
    próxima conexión, en vez del último modo que haya quedado fijado.
    """
    key = f"shpd-data:{device_id}"
    r.hdel(key, "mode")
    return {"device_id": device_id, "mode": None, "status": "reset"}

@router.post("/mode/{device_id}/{mode}")
def set_mode(device_id: str, mode: str):
    """
    Fija explícitamente el modo de un dispositivo ("calib" o "normal") en
    Redis. El frontend llama esto con "normal" al terminar la calibración.
    """
    if mode not in ("calib", "normal"):
        raise HTTPException(status_code=400, detail="mode must be 'calib' or 'normal'")

    key = f"shpd-data:{device_id}"
    r.hset(key, mapping={"mode": mode})
    return {"device_id": device_id, "mode": mode}


@router.post("/force-restart/{device_id}")
async def force_restart(device_id: str):
    """
    Corta a la fuerza el WebSocket de entrada de un dispositivo (si está
    conectado), para que la Raspberry Pi/PC reconecte desde cero — usado al
    cerrar la calibración para forzar que el próximo frame recree el
    `PostureMonitor` ya en modo normal.
    """
    ws = ws_manager.inputs.get(device_id)
    if not ws:
        return {"closed": False, "reason": "not_connected"}
    if ws.application_state == WebSocketState.CONNECTED:
        await ws.close(code=4000, reason="force_restart")
    return {"closed": True}
