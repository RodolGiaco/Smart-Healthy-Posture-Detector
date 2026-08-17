//  AppRouter.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import App from "./App";
import CalibracionPage from "./pages/CalibracionPage";

/** === TOGGLE ===
 * Poner en true para forzar "reset de fábrica" UNA SOLA VEZ.
 * Luego volver a false: al estar en false se “rear­ma” para el futuro.
 */
const CALIB_RESET_ONCE = false;

// Si querés por-dispositivo, usá `calibrado:${deviceId}` en vez de 'calibrado'
function applyOneShotReset(search: string) {
  const params = new URLSearchParams(search);
  const deviceId = params.get("device_id") || "default";
  const resetKey = `calib_reset_done:${deviceId}`;

  if (!CALIB_RESET_ONCE) {
    // Rearma el reset para la próxima vez que lo pongas en true
    localStorage.removeItem(resetKey);
    return;
  }
  if (localStorage.getItem(resetKey) !== "1") {
    localStorage.removeItem("calibrado"); // <-- se ejecuta UNA sola vez
    localStorage.setItem(resetKey, "1");
  }
}

const Decision: React.FC = () => {
  const location = useLocation();
  applyOneShotReset(location.search);
  return <App />;

  const params = new URLSearchParams(location.search);
  const force = params.get("forceCalib") === "1";
  const calibrado = localStorage.getItem("calibrado") === "1";

  return (calibrado && !force)
    ? <App />
    : <Navigate to={`/calibracion${location.search}`} replace />;
};

const CalibGate: React.FC = () => {
  const location = useLocation();
  applyOneShotReset(location.search);

  const params = new URLSearchParams(location.search);
  const force = params.get("forceCalib") === "1";
  const calibrado = localStorage.getItem("calibrado") === "1";

  return (calibrado && !force)
    ? <Navigate to={`/${location.search}`} replace />
    : <CalibracionPage />;
};

const AppRouter: React.FC = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/calibracion" element={<CalibGate />} />
      <Route path="/*" element={<Decision />} />
    </Routes>
  </BrowserRouter>
);

export default AppRouter;

