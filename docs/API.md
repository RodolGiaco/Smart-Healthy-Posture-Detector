# API del backend

Referencia completa de los endpoints expuestos por `backend/main.py` y sus routers (`backend/api/routers/`). Todos corren bajo el mismo proceso FastAPI, por default en `http://localhost:8765`.

> No hay autenticación: la API confía en que solo el frontend, el bot y los dispositivos de la propia red la llaman. No exponer este puerto a internet sin agregar una capa de auth antes.

## Índice

- [Sesiones](#sesiones)
- [Pacientes](#pacientes)
- [Métricas y análisis](#métricas-y-análisis)
- [Calibración](#calibración)
- [Video (WebSockets)](#video-websockets)
- [Notificaciones](#notificaciones)

## Sesiones

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/sesiones/` | Crea una sesión. Body: `{intervalo_segundos, modo}`. En la práctica el bot crea las sesiones escribiendo directo a la base, no llamando a este endpoint. |
| `GET` | `/sesiones/` | Lista todas las sesiones, sin filtrar por paciente ni dispositivo. El frontend usa la última de la lista como sesión activa. |
| `GET` | `/sesiones/progress/{session_id}` | `{intervalo_segundos, elapsed}` — progreso calculado desde `shpd-session:{id}` en Redis. |
| `POST` | `/sesiones/end/{device_id}` | Cierra la sesión activa del dispositivo: manda el reporte final al especialista por Telegram y limpia las claves temporales de Redis. Requiere que exista exactamente un Especialista registrado. |
| `POST` | `/sesiones/reiniciar/{session_id}?device_id=` | Revive una sesión (usado por "Iniciar nueva sesión" en el frontend): resetea el cronómetro y borra métricas/análisis/timeline previos de esa sesión. |

## Pacientes

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/pacientes/{device_id}` | Datos del paciente registrado con ese `device_id`. `404` si no existe. |

## Métricas y análisis

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/metricas/{sesion_id}` | Última métrica calculada por `PostureMonitor` para la sesión (porcentaje correcta/incorrecta, tiempo sentado/parado, alertas). |
| `GET` | `/analysis/{sesion_id}` | Último resultado de clasificación de OpenAI: las 12 posturas con su porcentaje estimado. |
| `GET` | `/postura_counts/{session_id}` | Conteo acumulado de veces que cada postura fue la más predominante en la sesión. |
| `GET` | `/timeline/{session_id}` | Historial de eventos de postura de la sesión (timestamp, postura detectada, tiempo en mala postura). |

## Calibración

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/calib/progress/{session_id}` | `{good_time, bad_time, correcta}` — progreso de la calibración en curso. |
| `POST` | `/calib/mode/reset/{device_id}` | Borra el modo fijado del dispositivo, para que vuelva a decidirse por el query string de la próxima conexión de video. |
| `POST` | `/calib/mode/{device_id}/{mode}` | Fija el modo del dispositivo (`calib` o `normal`). El frontend lo llama con `normal` al terminar la calibración. |
| `POST` | `/calib/force-restart/{device_id}` | Corta el WebSocket de entrada del dispositivo para forzar una reconexión (y con eso, un `PostureMonitor` nuevo con el modo correcto). |

## Video (WebSockets)

| Ruta | Dirección | Descripción |
|---|---|---|
| `WS /video/input/{device_id}` | dispositivo → backend | El productor de frames (`modo-ap/test_websocket.py` en la Pi, `modo-pc/stream_webcam.py` en PC) manda frames JPEG crudos. Query opcional `?calibracion=1` para arrancar en modo calibración. |
| `WS /video/output` | backend → cliente | Canal compartido (no filtra por dispositivo/sesión) donde se retransmiten los frames ya procesados por MediaPipe, con el overlay de ángulos dibujado. El frontend se conecta acá para mostrar el video en vivo. |

## Notificaciones

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/send_report` | Reenvía un mensaje `{telegram_id, resumen}` por Telegram vía el bot del backend. Ningún cliente de este repo lo llama actualmente. |

---

Swagger interactivo disponible en `/docs` mientras el backend está corriendo (`http://localhost:8765/docs`).
