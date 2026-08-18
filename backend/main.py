from dotenv import load_dotenv
load_dotenv()  # carga backend/.env o el .env de la raíz del repo antes de leer cualquier variable

import os
import asyncio
import logging
import json
import time
import cv2
import numpy as np
import time
import redis
import base64
import logging.config
from contextlib import asynccontextmanager
from openai import OpenAI
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn
from api.models import Sesion, Paciente, MetricaPostural, PosturaCount
from api.database import Base, engine, SessionLocal
from posture_monitor import PostureMonitor
from neural_network.pose_recognition import LocalPostureClassifier
from api.routers import sesiones, pacientes, metricas, analysis, postura_counts, timeline, calibracion
from datetime import datetime
from app.core.ws_manager import ws_manager
from telegram import Bot
from fastapi import Request
from telegram.request import HTTPXRequest

# Configurar el backend HTTPX con pool de 8 conexiones y timeout de conexión de 5 seg
request = HTTPXRequest(connection_pool_size=8, connect_timeout=5.0)

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

input_ws_by_device: dict[str, WebSocket] = {}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is not set")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "posture_monitor": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False
        },
        "api_analysis_worker": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False
        }, 
        "uvicorn.access": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False
        },
        "uvicorn.error": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False
        },

    },
    # El logger raíz queda en WARNING, filtrando todo lo demás
    "root": {
        "handlers": ["console"],
        "level": "WARNING"
    }
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("shpd-backend")
logger.setLevel(logging.DEBUG)


# ——— SELECTOR DE CLASIFICADOR DE POSTURA (local TFLite vs. OpenAI) ———
# "local" corre el modelo entrenado en shpd-edge-vision (TFLite, sobre los
# landmarks de MediaPipe) y es el default: no necesita OPENAI_API_KEY para
# el camino principal. "openai" es la alternativa explícita, para comparar
# contra GPT-4o-mini (visión). Ver README.md, sección "Variables de entorno".
_raw_posture_classifier = os.getenv("POSTURE_CLASSIFIER", "local")
POSTURE_CLASSIFIER = _raw_posture_classifier.strip().lower()
if POSTURE_CLASSIFIER not in ("local", "openai"):
    logger.warning(
        f"POSTURE_CLASSIFIER={_raw_posture_classifier!r} no reconocido "
        "(valores válidos: 'local', 'openai'); usando 'local'"
    )
    POSTURE_CLASSIFIER = "local"

# ——— CONFIGURACIÓN DEL CLIENTE DE OPENAI ———
# Solo se exige OPENAI_API_KEY cuando realmente se va a usar: con
# POSTURE_CLASSIFIER=local el backend corre sin ella.
API_KEY = os.getenv("OPENAI_API_KEY")
client = None
if POSTURE_CLASSIFIER == "openai":
    if not API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set "
            "(requerida porque POSTURE_CLASSIFIER=openai)"
        )
    client = OpenAI(api_key=API_KEY)
MODEL = "gpt-4o-mini"

def build_openai_messages(b64: str) -> list[dict]:
    """
    Construye la lista de mensajes para enviar a la API de OpenAI GPT-4 Vision,
    solicitando que, en lugar de booleanos, devuelva porcentajes (0–100) 
    que indiquen la predominancia estimada de cada postura.

    - b64: cadena Base64 de la imagen (sin prefijo MIME).
    Devuelve una lista de diccionarios con los roles y contenidos formateados.
    """

    # 1) Prompt del sistema: define el rol y las 13 posturas, 
    #    indicando que debe devolver porcentajes 0–100 en JSON.
    SYSTEM_PROMPT = """Eres un asistente de clasificación de posturas basado en visión.
Cuando recibas una imagen, analiza la postura de la persona 
qué tan predominante es cada una de las siguientes 12 posturas al sentarse.
Las posturas son:
- Tronco flexionado hacia delante
- Tronco extendido hacia atras
- Inclinación lateral izquierda del tronco 
- Inclinación lateral derecha del tronco 
- Mentón apoyado en mano
- Piernas cruzadas
- Rodillas elevadas o muy bajas
- Hombros elevados/encogidos
- Antebrazo sin apoyo
- Cabeza adelantada
- Hipercifosis torácica
- Deslizamiento pélvico anterior


Determina y devuelve estrictamente un objeto JSON, sin cercos de código circundante,
formato markdown o cualquier texto extra-sólo el propio JSON».
En lugar de un valor booleano, para cada postura devuelve un porcentaje entre 0 y 100 
(0 = nada probable / no se aprecia, 100 = completamente predominante). 
El JSON debe tener cada postura como clave exacta y su valor numérico como porcentaje.
Proporciona ÚNICAMENTE el objeto JSON como salida, sin texto adicional."""

    # 2) Prompt del usuario (texto): instrucción breve para clasificar la imagen con porcentajes.
    user_prompt = (
        "Analiza la imagen adjunta y genera un JSON con los 12 tipos de postura "
        "listados en el mensaje de sistema. Para cada postura, coloca un número "
        "entero de 0 a 100 que indique la probabilidad o predominancia estimada. "
        "No incluyas explicaciones; solo devuelve el objeto JSON."
    )

    # 3) Construcción de content para el usuario, usando tipo "text" + "image_url"
    user_content = [
        {"type": "text", "text": user_prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "details": "high"
            }
        }
    ]

    # 4) Devolver la lista de mensajes con roles "system" y "user"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content}
    ]

# ——— COLAS ASÍNCRONAS ———
processed_frames_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
api_analysis_queue: asyncio.Queue = asyncio.Queue()
local_analysis_queue: asyncio.Queue = asyncio.Queue()
_triggered_sessions = set()  # para disparar clasificación sólo una vez por umbral
_local_posture_classifier: LocalPostureClassifier | None = None  # instanciado lazy, ver local_analysis_worker


async def _apply_classification_result(
    session_id: str, device_id: str, bad_time: str, result: dict[str, float]
) -> None:
    """
    Post-procesamiento común a cualquier mecanismo de clasificación de
    postura (OpenAI o el modelo local TFLite, ver POSTURE_CLASSIFIER):
    guarda `result` en Redis bajo analysis:{session_id}, hace upsert del
    label ganador en PosturaCount, agrega el evento a la timeline de la
    sesión y dispara la alerta al paciente por Telegram.

    `result` tiene que ser {postura_canónica: porcentaje 0-100} con las 12
    claves -- el mismo shape sin importar qué mecanismo lo generó, para que
    /analysis/{id} y el frontend sigan funcionando igual.
    """
    r.hset(f"analysis:{session_id}", mapping=result)
    logger.debug(f"✔️ Analysis saved for session {session_id}")

    if not result:
        return

    # Encontrar la clave cuyo valor sea máximo
    top_label, top_value = max(result.items(), key=lambda kv: kv[1])
    # Abrir sesión de DB para hacer upsert en PosturaCount
    db = SessionLocal()
    try:
        # Intentar obtener la fila existente
        fila = (
            db.query(PosturaCount)
            .filter(
                PosturaCount.session_id == session_id,
                PosturaCount.posture_label == top_label
            )
            .first()
        )
        if fila:
            # Si existe, incrementamos el contador
            fila.count += 1
            db.add(fila)
        else:
            # Si no existe, creamos una nueva fila
            nueva = PosturaCount(
                session_id=session_id,
                posture_label=top_label,
                count=1
            )
            db.add(nueva)
        db.commit()
        logger.debug(f"✔️ PostureCount updated: {session_id} - {top_label}")
        # Guardar evento de timeline
        try:
            evt = {
                "timestamp": datetime.utcnow().isoformat(),
                "postura": top_label,
                "tiempo_mala_postura": bad_time
            }
            r.rpush(f"timeline:{session_id}", json.dumps(evt))
            r.ltrim(f"timeline:{session_id}", -200, -1)
            asyncio.create_task(
                 enviar_alerta_paciente_bg(device_id, top_label, bad_time)
            )
            logger.info("Alerta enviada al paciente.")
        except Exception:
            logger.exception("Error guardando timeline")
    except Exception:
        logger.exception("Error actualizando PosturaCount en DB")
        db.rollback()
    finally:
        db.close()


# ——— WORKER PARA LLAMADAS A OPENAI ———
async def api_analysis_worker():
    """
    Worker que consume de api_analysis_queue payloads con:
      { session_id, jpeg, bad_time, device_id }
    Arma el request a OpenAI, parsea el JSON de la respuesta y delega el
    resto (Redis, PosturaCount, timeline, alerta) a
    _apply_classification_result.
    """
    loop = asyncio.get_running_loop()
    logger.debug("🔄 API analysis worker iniciado")
    while True:
        payload = await api_analysis_queue.get()
        session_id = payload["session_id"]
        jpeg        = payload["jpeg"]
        bad_time    = payload["bad_time"]
        device_id    = payload["device_id"]
        b64 = base64.b64encode(jpeg).decode("utf-8")
        try:
            messages = build_openai_messages(b64)
            # Llamada a OpenAI en executor para no bloquear el loop
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    user=session_id,
                    model=MODEL,
                    messages=messages,
                    temperature=0,
                    max_tokens=500
                )
            )
            content = response.choices[0].message.content
            logger.debug(content)
            result: dict[str, float] = json.loads(content)
            await _apply_classification_result(session_id, device_id, bad_time, result)
        except Exception:
            logger.exception("Error en análisis OpenAI")
        finally:
            api_analysis_queue.task_done()


# ——— WORKER PARA EL CLASIFICADOR LOCAL (TFLite) ———
async def local_analysis_worker():
    """
    Worker análogo a api_analysis_worker pero para el modelo local TFLite
    (ver neural_network/pose_recognition.py). Consume de
    local_analysis_queue payloads con:
      { session_id, landmark_list, image_shape, bad_time, device_id }
    donde `landmark_list` son los `pose_landmarks` crudos de MediaPipe del
    frame que disparó el umbral (`PostureMonitor.last_pose_landmarks`) e
    `image_shape` sus dimensiones (`PostureMonitor.last_image_shape`).

    La inferencia TFLite es sincrónica y local (sin latencia de red), pero
    igual corre en un executor (`loop.run_in_executor`, mismo patrón que
    `posture_monitor.process_frame`) y detrás de esta cola propia, para no
    bloquear el loop de video_input y mantener la misma arquitectura que el
    camino OpenAI.
    """
    global _local_posture_classifier
    loop = asyncio.get_running_loop()
    logger.debug("🔄 Local analysis worker iniciado")
    while True:
        payload = await local_analysis_queue.get()
        session_id    = payload["session_id"]
        landmark_list = payload["landmark_list"]
        image_shape   = payload["image_shape"]
        bad_time      = payload["bad_time"]
        device_id     = payload["device_id"]
        try:
            if _local_posture_classifier is None:
                _local_posture_classifier = LocalPostureClassifier()
            result = await loop.run_in_executor(
                None, _local_posture_classifier.classify, landmark_list, image_shape
            )
            if result is None:
                logger.warning(f"Clasificador local sin landmarks para session {session_id}")
                continue
            logger.debug(result)
            await _apply_classification_result(session_id, device_id, bad_time, result)
        except Exception:
            logger.exception("Error en análisis local (TFLite)")
        finally:
            local_analysis_queue.task_done()

async def enviar_alerta_paciente_bg(device_id: str,
                                etiqueta: str,
                                bad_time: str):
    """
    Manda al paciente, por Telegram, la alerta de la postura que acaba de
    clasificar OpenAI. Resuelve el chat_id del paciente a partir del
    device_id (clave `shpd-data:{device_id}` en Redis); si no hay
    telegram_id asociado, no hace nada.
    """
    redis_shpd_key = f"shpd-data:{device_id}"
    telegram_id = r.hget(redis_shpd_key, "telegram_id")
    if not telegram_id:
        logger.warning(f"No hay telegram_id para device_id={device_id}")
        return
    
    resumen = (
        f"🚨 <b>Alerta postural</b>\n"
        f"Postura detectada: <b>{etiqueta}</b>\n"
        f"Tiempo en mala postura: {bad_time}seg\n"
    )

    payload = {"telegram_id": telegram_id, "resumen": resumen}
    try:
        # arrancar un event‑loop en este hilo para await
        await telegram_bot.send_message(
                chat_id=int(telegram_id),
                text=resumen,
                parse_mode="HTML"
        )
        logger.info("✔️ Alerta enviada al paciente.")
    except Exception as e:
        logger.error(f"Error enviando alerta a paciente: {e}")
        

# En startup, lanza el worker en background
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la app: crea el cliente de Telegram (`telegram_bot`,
    usado por las alertas y el reporte final) y lanza `api_analysis_worker`
    y `local_analysis_worker` como tareas de fondo antes de aceptar
    requests -- solo uno de los dos recibe payloads en runtime, según
    POSTURE_CLASSIFIER (ver video_input), pero ambos arrancan siempre para
    mantener la arquitectura simétrica entre los dos mecanismos.
    """
    request = HTTPXRequest(connection_pool_size=8, connect_timeout=5.0)
    global telegram_bot
    telegram_bot = Bot(token=TELEGRAM_TOKEN, request=request)
    asyncio.create_task(api_analysis_worker())
    asyncio.create_task(local_analysis_worker())
    logger.debug(f"✅ Analysis workers scheduled (POSTURE_CLASSIFIER={POSTURE_CLASSIFIER!r})")
    yield
    
app = FastAPI(lifespan=lifespan)
app.state.input_ws_by_device = {}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sesiones.router)
app.include_router(pacientes.router)
app.include_router(metricas.router)
app.include_router(analysis.router)
app.include_router(postura_counts.router)
app.include_router(timeline.router)
app.include_router(calibracion.router)
processed_frames_queue = asyncio.Queue(maxsize=10)


@app.post("/send_report")
async def send_report(request: Request):
    """
    Reenvía un mensaje arbitrario a un chat_id de Telegram vía el bot del
    backend. Recibe `{telegram_id, resumen}` en el body. Ningún cliente de
    este repo lo llama actualmente (ni frontend, ni bot, ni el propio
    backend) — queda expuesto como endpoint genérico de notificación.
    """
    data = await request.json()
    telegram_id = data.get("telegram_id")
    resumen     = data.get("resumen")
    if not telegram_id or not resumen:
        return {"ok": False, "error": "Faltan datos"}
    try:
        await telegram_bot.send_message(
            chat_id=telegram_id,
            text=resumen,
            parse_mode="HTML"
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.websocket("/video/input/{device_id}")
async def video_input(websocket: WebSocket, device_id: str):
    """
    Recibe el stream de frames JPEG crudos de un dispositivo (Picamera2 en
    la Raspberry Pi, o `modo-pc/stream_webcam.py` en PC).

    Por cada frame: resuelve el session_id activo del device en Redis,
    (re)crea el `PostureMonitor` si la sesión cambió, procesa el frame
    (dibuja ángulos/esqueleto) y lo publica en `processed_frames_queue`
    para que `/video/output` lo retransmita. Si Redis marcó un frame como
    disparador de alerta (`raw_frame:{session_id}`), lo encola para su
    clasificación según `POSTURE_CLASSIFIER`: en `api_analysis_queue`
    (`api_analysis_worker`, vía OpenAI) o en `local_analysis_queue`
    (`local_analysis_worker`, vía el modelo TFLite local).

    El modo calibración se decide por el query string de esta conexión
    (`?calibracion=1`) mientras no haya un `mode` explícito en
    `shpd-data:{device_id}`; una vez que el frontend marca `mode=normal`
    (fin de la calibración), ese valor manda.
    """
    await websocket.accept()
    ws_manager.inputs[device_id] = websocket
    loop = asyncio.get_running_loop()
    
    # Detectar modo calibración: query ?calibracion=1
    calibrating_query = websocket.scope.get("query_string", b"").decode().find("calibracion=1") >= 0
    if calibrating_query:
        await websocket.send_text(json.dumps({"type": "modo", "calibracion": True}))
    else:
        await websocket.send_text(json.dumps({"type": "modo", "calibracion": False}))

    # Variables para manejar PostureMonitor dinámicamente
    posture_monitor = None
    current_session_id = None
    calibrating = None
    mode = None
    try:
        while True:
            # 1. Verificar el session_id desde Redis en cada iteración
            redis_shpd_key = f"shpd-data:{device_id}"
            session_id = r.hget(redis_shpd_key, "session_id")

            # ——— Determinar si seguimos en modo calibración ———
            mode = r.hget(redis_shpd_key, "mode")
            if mode is None:
                calibrating = calibrating_query  # aún no hay session_id: usa flag de la URL
            elif mode == "normal":
                calibrating = False
           
            # 2. Si el session_id cambió, reinicializar PostureMonitor con el modo correcto
            if session_id != current_session_id:
                logger.info(f"📋 Session ID cambió de {current_session_id} a {session_id}")
                posture_monitor = PostureMonitor(session_id, save_metrics=not calibrating, device_id=device_id)
                current_session_id = session_id
                logger.info(f"✅ PostureMonitor reinicializado para session {session_id}")

            # 3. Procesar frame normalmente
            data = await websocket.receive_bytes()
            frame = await loop.run_in_executor(None, _decode_jpeg, data)
            if frame is None:
                continue

            # Solo procesar si tenemos un PostureMonitor válido
            if posture_monitor is None:
                # Si no hay PostureMonitor, enviar frame sin procesar
                jpeg = await loop.run_in_executor(None, _encode_jpeg, frame)
            else:
                processed = await loop.run_in_executor(None, posture_monitor.process_frame, frame)
                jpeg = await loop.run_in_executor(None, _encode_jpeg, processed)
            
            if processed_frames_queue.full():
                processed_frames_queue.get_nowait()
            await processed_frames_queue.put(jpeg)

            # 4. Dispara análisis (OpenAI o local, según POSTURE_CLASSIFIER)
            #    si guardaron un frame crudo (solo si hay session_id válido)
            if posture_monitor is not None and not calibrating:
                raw_key = f"raw_frame:{session_id}"
                flag_value = r.hget(raw_key, "flag_alert")
                bad_time = r.hget(raw_key, "bad_time")
                if flag_value == "1":
                    if POSTURE_CLASSIFIER == "openai":
                        await api_analysis_queue.put({
                            "session_id": session_id,
                            "jpeg": jpeg,
                            "bad_time": bad_time,
                            "device_id": device_id
                        })
                    else:  # "local"
                        await local_analysis_queue.put({
                            "session_id": session_id,
                            "landmark_list": posture_monitor.last_pose_landmarks,
                            "image_shape": posture_monitor.last_image_shape,
                            "bad_time": bad_time,
                            "device_id": device_id
                        })
                    r.delete(raw_key)
                    logger.debug(f"✔️ Disparo para analisis ejecutado para sesión {session_id}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado para device_id: {device_id}")
    except Exception as e:
        logger.error(f"Error en video_input: {e}")
        logger.exception("Detalles del error:")
    finally:
        ws_manager.inputs.pop(device_id, None)
        logger.info(f"Cerrando WebSocket para device_id: {device_id}")

@app.websocket("/video/output")
async def video_output(websocket: WebSocket):
    """
    Retransmite a quien esté conectado (típicamente el frontend) los frames
    ya procesados que cualquier `/video/input/{device_id}` fue dejando en
    `processed_frames_queue`. Es un único canal compartido por todo el
    backend, no filtra por dispositivo ni por sesión.
    """
    await websocket.accept()
    try:
        while True:
            jpeg = await processed_frames_queue.get()
            await websocket.send_bytes(jpeg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

def _decode_jpeg(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def _encode_jpeg(frame):
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
    return buf.tobytes()

Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="warning",
        access_log=True
    )

