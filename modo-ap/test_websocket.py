#!/usr/bin/env python3
import asyncio
import cv2
import argparse
from picamera2 import Picamera2
import websockets
from websockets import ConnectionClosed

async def stream_camera(uri):
    # 1. Inicializa y configura Picamera2
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}
    )
    picam2.configure(config)
    picam2.start()
    print("📷 Cámara iniciada con Picamera2")

    try:
        while True:
            try:
                # 2. Conecta al WebSocket
                async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                    print(f"✅ Conectado a {uri}")
                    count = 0

                    # 3. Bucle de captura y envío
                    while True:
                        # Captura un frame (array NumPy, RGB888)
                        frame = picam2.capture_array()

                        # Codifica a JPEG en memoria
                        ok, buf = cv2.imencode(
                            '.jpg',
                            frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 30]
                        )
                        if not ok:
                            print("❌ Error al codificar el frame")
                            await asyncio.sleep(0.1)
                            continue

                        # Envía bytes JPEG al backend
                        await ws.send(buf.tobytes())
                        count += 1

                        # Log cada 30 frames
                        if count % 10 == 0:
                            print(f"  ▶️ Enviados {count} frames")

                        # Control de tasa (~30 fps → 0.03 s)
                        await asyncio.sleep(0.1)

            except ConnectionClosed:
                print("❌ Conexión cerrada, reintentando en 2 s...")
                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ Error inesperado: {e}\n   Volviendo a conectar en 5 s...")
                await asyncio.sleep(5)

    finally:
        # 4. Limpieza de cámara al finalizar
        picam2.stop()
        print("🛑 Cámara detenida")

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Envía vídeo de Picamera2 por WebSocket al backend"
    )
    p.add_argument(
        "--uri",
        default="ws://rodo.local:8765/video/input/shpd-123?calibracion=1",
        help="URI del WebSocket (ej. ws://host:8765/video/…)"
    )
    args = p.parse_args()
    asyncio.run(stream_camera(args.uri))
