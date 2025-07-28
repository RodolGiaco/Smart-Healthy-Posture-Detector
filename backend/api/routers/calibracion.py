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

# Nuevo endpoint de progreso numérico
@router.get("/progress/{session_id}")
def calib_progress(session_id: str):
    data = r.hgetall(f"calib:{session_id}")
    good = float(data.get("good_time", 0))
    bad  = float(data.get("bad_time", 0))
    return {
        "good_time": good,
        "bad_time": bad,
        "correcta": good > bad
    }

# Endpoint para resetear (borrar) el flag 'mode' y dejar que el backend lo regenere
@router.post("/mode/reset/{device_id}")
def reset_mode(device_id: str):
    key = f"shpd-data:{device_id}"
    r.hdel(key, "mode")
    return {"device_id": device_id, "mode": None, "status": "reset"}

# Endpoint para cambiar el modo de un dispositivo
@router.post("/mode/{device_id}/{mode}")
def set_mode(device_id: str, mode: str):
    if mode not in ("calib", "normal"):
        raise HTTPException(status_code=400, detail="mode must be 'calib' or 'normal'")

    key = f"shpd-data:{device_id}"
    r.hset(key, mapping={"mode": mode})
    return {"device_id": device_id, "mode": mode}


@router.post("/force-restart/{device_id}")
async def force_restart(device_id: str):
    ws = ws_manager.inputs.get(device_id)
    if not ws:
        return {"closed": False, "reason": "not_connected"}
    if ws.application_state == WebSocketState.CONNECTED:
        await ws.close(code=4000, reason="force_restart")
    return {"closed": True}
