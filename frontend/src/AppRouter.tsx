import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import App from "./App";
import CalibracionPage from "./pages/CalibracionPage";

const Decision: React.FC = () => {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const force = params.get("forceCalib") === "1";
  /* const calibrado = !force && localStorage.getItem("calibrado") === "1"; */
  const calibrado = localStorage.getItem("calibrado") === "1";
  if (calibrado) {
    return <App />; // interfaz normal
  }

  // No calibrado: redirige a /calibracion conservando query
  return <Navigate to={`/calibracion${location.search}`} replace />;
};

const AppRouter: React.FC = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/calibracion" element={<CalibracionPage />} />
      <Route path="/*" element={<Decision />} />
    </Routes>
  </BrowserRouter>
);

export default AppRouter; 
