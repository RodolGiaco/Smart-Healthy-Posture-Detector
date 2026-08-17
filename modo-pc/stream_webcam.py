#!/usr/bin/env python3
"""
Envía video de la webcam de tu PC al backend por WebSocket, para probar
el pipeline completo (detección de postura + frontend) sin necesitar una
Raspberry Pi ni una Picamera2.

Es el equivalente, para PC, de modo-ap/test_websocket.py (que usa
Picamera2 y solo corre en la Raspberry Pi).

Por default arranca en modo calibración (igual que test_websocket.py).

Uso:
    python modo-pc/stream_webcam.py --device-id shpd-123
    python modo-pc/stream_webcam.py --device-id shpd-123 --no-calibracion
"""
import asyncio
import argparse

import cv2
import websockets
from websockets import ConnectionClosed


async def stream_camera(uri: str, camera_index: int):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la cámara #{camera_index}. "
            "¿Está siendo usada por otra aplicación (Zoom, Teams, el navegador)?"
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print(f"📷 Cámara #{camera_index} abierta")

    try:
        while True:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                    print(f"✅ Conectado a {uri}")
                    count = 0

                    while True:
                        ok, frame = cap.read()
                        if not ok:
                            print("❌ No se pudo leer un frame de la cámara")
                            await asyncio.sleep(0.1)
                            continue

                        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if not ok:
                            await asyncio.sleep(0.1)
                            continue

                        await ws.send(buf.tobytes())
                        count += 1
                        if count % 30 == 0:
                            print(f"  ▶️ Enviados {count} frames")

                        await asyncio.sleep(0.03)  # ~30 fps

            except ConnectionClosed:
                print("❌ Conexión cerrada, reintentando en 2 s...")
                await asyncio.sleep(2)
            except (ConnectionRefusedError, OSError) as e:
                print(f"❌ No se pudo conectar al backend ({e}). ¿Está corriendo? Reintentando en 3 s...")
                await asyncio.sleep(3)
    finally:
        cap.release()
        print("🛑 Cámara liberada")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", default="pc-test", help="Identificador del dispositivo (default: pc-test). Tiene que coincidir con el device_id de la sesión (el que te manda el bot).")
    parser.add_argument("--host", default="localhost", help="Host del backend (default: localhost)")
    parser.add_argument("--port", type=int, default=8765, help="Puerto del backend (default: 8765)")
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara, ver /dev/video* (default: 0)")
    parser.add_argument(
        "--no-calibracion",
        dest="calibracion",
        action="store_false",
        help="Conecta en modo sesión normal en vez de calibración (por default arranca en calibración, igual que modo-ap/test_websocket.py)",
    )
    parser.set_defaults(calibracion=True)
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}/video/input/{args.device_id}"
    if args.calibracion:
        uri += "?calibracion=1"

    asyncio.run(stream_camera(uri, args.camera))
