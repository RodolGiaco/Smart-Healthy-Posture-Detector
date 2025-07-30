// src/components/CalibracionMonitor.tsx
import React, { useEffect, useRef, useState } from "react";

interface Props {
  onFinish: () => void;
  autoStart?: boolean;
}

const CalibracionMonitor: React.FC<Props> = ({ onFinish, autoStart = true }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [calibrando, setCalibrando] = useState<boolean>(true);
  const faseColor = "#4caf50";
  const faseLabel = "Mantén la espalda recta";
  const [enMarco, setEnMarco] = useState(false);
  const [progreso, setProgreso] = useState(0);
  const [finalizando, setFinalizando] = useState(false);
  const [modoCambiado, setModoCambiado] = useState(false);

  // nuevo: mostrar botón tras cerrar WS
  const [rebootOk, setRebootOk] = useState(false);
  const [checkingReboot, setCheckingReboot] = useState(false);

  const [deviceId] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    return p.get("device_id") || "demo";
  });

  const [sessionId, setSessionId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("session_id")
  );

  useEffect(() => {
    if (sessionId || !deviceId) return;
    (async () => {
      try {
        const res = await fetch(
          `http://${window.location.hostname}:8765/sesiones/?device_id=${deviceId}`
        );
        if (!res.ok) return;
        const sesiones: { id: string; modo: string }[] = await res.json();
        if (sesiones.length > 0) {
          setSessionId(sesiones[sesiones.length - 1].id.toString());
        }
      } catch {/* ignorar */}
    })();
  }, [sessionId, deviceId]);

  /* —— Video WebSocket —— */
  useEffect(() => {
    const host = window.location.hostname;
    const ws = new WebSocket(`ws://${host}:8765/video/output?device_id=${deviceId}`);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (e) => {
      if (typeof e.data === "string") {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "modo" && msg.calibracion === true) {
            setCalibrando(true);
            setProgreso(0);
            setFinalizando(false);
            return;
          }
        } catch {}
      }
      const blob = new Blob([e.data], { type: "image/jpeg" });
      const img = new Image();
      img.src = URL.createObjectURL(blob);
      img.onload = () => {
        const ctx = canvasRef.current?.getContext("2d");
        if (ctx && canvasRef.current) {
          ctx.drawImage(img, 0, 0, canvasRef.current.width, canvasRef.current.height);
        }
        URL.revokeObjectURL(img.src);
      };
    };
    return () => ws.close();
  }, [deviceId]);

  /* —— Polling al backend con tiempos —— */
  useEffect(() => {
    if (!calibrando || !sessionId) return;
    const interval = setInterval(async () => {
      try {
        const url = `http://${window.location.hostname}:8765/calib/progress/${sessionId}`;
        const { good_time, correcta } = await fetch(url).then(r => r.json());

        if (!correcta) {
          setEnMarco(false);
          setProgreso(0);
          return;
        }

        const pct = Math.min(100, (good_time / 10) * 100);
        setProgreso(pct);
        setEnMarco(pct > 0);

        if (pct >= 100) {
          setFinalizando(true);
          setCalibrando(false);
        }
      } catch {/* ignora */}
    }, 800);
    return () => clearInterval(interval);
  }, [calibrando, sessionId]);

  /* —— Cambiar modo a normal apenas finalizamos —— */
  useEffect(() => {
    if (finalizando && !modoCambiado) {
      localStorage.setItem('calibrado', '1');
      (async () => {
        try {
          await fetch(
            `http://${window.location.hostname}:8765/calib/mode/${deviceId}/normal`,
            { method: "POST" }
          );
          setModoCambiado(true);
        } catch {/* ignorar */}
      })();
    }
  }, [finalizando, modoCambiado, deviceId]);

  /* —— Llamar endpoint para cerrar WS y habilitar botón —— */
  useEffect(() => {
    if (!finalizando || rebootOk || checkingReboot) return;
    (async () => {
      try {
        setCheckingReboot(true);
        await fetch(
          `http://${window.location.hostname}:8765/calib/force-restart/${deviceId}`,
          { method: "POST" }
        );
        setRebootOk(true);
      } catch {/* ignorar */} 
      finally {
        setCheckingReboot(false);
      }
    })();
  }, [finalizando, rebootOk, checkingReboot, deviceId]);

  if (!calibrando && !finalizando) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-blue-50 to-white">
      <h1 className="text-2xl font-semibold mb-6 text-blue-700">
        Calibración de dispositivo
      </h1>

      {calibrando && (
        <div className="relative w-[28rem] h-[28rem] flex items-center justify-center">
          <div
            className={`absolute inset-0 border-4 rounded-xl transition-colors duration-300 ${
              enMarco ? "border-green-400" : "border-blue-300"
            }`}
          />
          <canvas ref={canvasRef} width={420} height={420} className="rounded object-cover" />

          {progreso > 0 && progreso < 100 && (
            <svg className="absolute w-full h-full">
              <circle
                cx="50%"
                cy="50%"
                r="46%"
                stroke={faseColor}
                strokeWidth="6"
                fill="none"
                strokeDasharray="314"
                strokeDashoffset={314 - (314 * progreso) / 100}
                className="transition-[stroke-dashoffset] duration-100"
              />
            </svg>
          )}
        </div>
      )}

      {!enMarco && calibrando && (
        <p className="mt-4 text-gray-600 text-center max-w-xs">
          {faseLabel}
        </p>
      )}
      {progreso > 0 && progreso < 100 && calibrando && (
        <p className="mt-4 text-blue-600">Calibrando… {Math.floor(progreso)}%</p>
      )}

      {progreso >= 100 && finalizando && (
        <div className="flex flex-col items-center mt-4 bg-white/70 backdrop-blur-md px-8 py-10 rounded-xl shadow-xl border border-green-200 max-w-md">
          <span className="text-5xl mb-4">🎉</span>
          <h2 className="text-2xl font-semibold text-green-700 mb-2 text-center">
            ¡Calibración completada!
          </h2>
          <p className="text-gray-700 text-center mb-6">
            Todo listo. Pulsa el botón para comenzar la sesión normal.
          </p>

          {rebootOk && (
            <button
              onClick={() => {
                onFinish?.();
                const url = new URL(window.location.href);
                /*  url.searchParams.delete("calibracion"); */
                url.searchParams.delete("forceCalib");
                url.pathname = "/";
                window.location.href =
                  url.pathname +
                  (url.searchParams.toString()
                    ? "?" + url.searchParams.toString()
                    : "");
              }}
              className="px-8 py-3 bg-gradient-to-r from-green-500 to-blue-500 text-white rounded-full shadow-lg hover:scale-105 transition-all duration-300 text-lg font-semibold focus:outline-none focus:ring-4 focus:ring-green-200"
            >
              🏁 Iniciar sesión
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default CalibracionMonitor;
