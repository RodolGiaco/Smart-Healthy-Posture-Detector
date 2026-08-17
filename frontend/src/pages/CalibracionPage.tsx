import React, { useState } from "react";
import CalibracionMonitor from "../components/CalibracionMonitor";

const CalibracionPage: React.FC = () => {
  const [finalizado, setFinalizado] = useState(false);

  return (
    <>
      {!finalizado && (
        <CalibracionMonitor
          onFinish={() => {
            localStorage.setItem("calibrado", "1");
            setFinalizado(true);
          }}
        />
      )}
      {/* El componente muestra su propio mensaje de éxito */}
    </>
  );
};

export default CalibracionPage; 