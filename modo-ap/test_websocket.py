#!/usr/bin/env python3
import asyncio
import cv2
import websockets
import argparse
from websockets import ConnectionClosed

async def stream_camera(uri):
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara")
        return

    # Buffer mínimo, MJPEG por hardware, resolución y FPS controlados
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 10)

    while True:
        try:
            async with websockets.connect(
                uri, ping_interval=20, ping_timeout=20
            ) as ws:
                print(f"✅ Conectado a {uri}")
                count = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        await asyncio.sleep(0.1)
                        continue

                    ok, buf = cv2.imencode(
                        '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50]
                    )
                    if not ok:
                        continue

                    await ws.send(buf.tobytes())
                    count += 1
                    if count % 30 == 0:
                        print(f"  Enviados {count} frames")
                    await asyncio.sleep(0.03)

        except ConnectionClosed:
            print("❌ Conexión cerrada, reconectando en 2s...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"❌ Error: {e}, reconectando en 5s...")
            await asyncio.sleep(5)
        finally:
            # nada que liberar para mantener la cámara abierta
            pass

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--uri", default="ws://192.168.100.13:8765/video/input/shpd-123?calibracion=1")
    args = p.parse_args()
    uri = args.uri
    asyncio.run(stream_camera(uri))

