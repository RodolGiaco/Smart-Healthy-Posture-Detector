// src/components/HistoryChart.tsx
import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { HistorialPosturalItem } from "../types";

interface Props {
  sesionId: string;
}

const POSTURAS_FIJAS = [
  "Tronco flexionado hacia delante",
  "Tronco extendido hacia atras",
  "Inclinación lateral izquierda del tronco",
  "Inclinación lateral derecha del tronco",
  "Mentón apoyado en mano",
  "Piernas cruzadas",
  "Rodillas elevadas o muy bajas",
  "Hombros elevados/encogidos",
  "Antebrazo sin apoyo",
  "Cabeza adelantada",
  "Hipercifosis torácica",
  "Deslizamiento pélvico anterior",
];

const HistoryChart: React.FC<Props> = ({ sesionId }) => {
  const [historial, setHistorial] = useState<HistorialPosturalItem[]>([]);

  // Polling para obtener conteo de posturas desde el endpoint /postura_counts/{sesionId}
  useEffect(() => {
    const fetchData = () => {
      fetch(`http://${window.location.hostname}:8765/postura_counts/${sesionId}`)
        .then((res) => res.json())
        .then((data: { posture_label: string; count: number }[]) => {
          // Convertimos la respuesta a HistorialPosturalItem[]
          const items: HistorialPosturalItem[] = data.map((entry) => ({
            nombre: entry.posture_label,
            conteo: entry.count,
          }));
          setHistorial(items);
        })
        .catch(console.error);
    };

    // Llamada inmediata para no esperar el primer intervalo
    fetchData();
    // Hacemos polling cada segundo
    const interval = setInterval(fetchData, 1000);

    return () => clearInterval(interval);
  }, [sesionId]);

  // Preparamos los datos para el gráfico de barras,
  // garantizando que todas las posturas fijas estén presentes (incluso si conteo = 0)
  const data = POSTURAS_FIJAS.map((postura) => {
    const found = historial.find(
      // Comparamos strings exactos. Si en algún momento cambian mayúsculas/minúsculas,
      // podríamos normalizar con .toLowerCase()
      (item) => item.nombre === postura
    );

    return {
      postura,
      conteo: found ? found.conteo : 0,
    };
  });

  return (
    <div className="p-4 bg-white border rounded-lg shadow">
      <h2 className="text-lg font-bold mb-2">📊 Historial de Posturas</h2>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="postura"
            angle={-25}
            textAnchor="end"
            interval={0}
            height={70}
          />
          <YAxis />
          <Tooltip />
          <Bar dataKey="conteo" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default HistoryChart;
