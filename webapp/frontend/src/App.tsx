import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { QueueProvider } from "./components/QueueProvider";
import { ExperimentsPage } from "./pages/experiments";
import { DetailPage } from "./pages/experiments/DetailPage";
import { ComparisonPage } from "./pages/experiments/ComparisonPage";
import { NewExperimentPage } from "./pages/new-experiment";
import { ConfigurationsPage } from "./pages/configurations";
import { SettingsPage } from "./pages/settings";

export function App() {
  return (
    <QueueProvider><Routes>
      <Route path="/" element={<Navigate to="/experimentos" replace />} />
      <Route
        path="/experimentos"
        element={
          <Shell key="experiments" title="Experimentos">
            <ExperimentsPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/nuevo"
        element={
          <Shell key="new-experiment" title="Nuevo experimento">
            <NewExperimentPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/:id/comparacion"
        element={
          <Shell key="comparison" title="Comparación">
            <ComparisonPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/:id"
        element={
          <Shell key="detail" title="Experimento">
            <DetailPage />
          </Shell>
        }
      />
      <Route
        path="/configuraciones"
        element={
          <Shell key="configurations" title="Estrategias guardadas">
            <ConfigurationsPage />
          </Shell>
        }
      />
      <Route
        path="/ajustes"
        element={
          <Shell key="settings" title="Ajustes">
            <SettingsPage />
          </Shell>
        }
      />
      <Route
        path="*"
        element={
          <Shell key="not-found" title="Página no encontrada">
            <p className="max-w-prose text-text-secondary">Esta dirección no corresponde a una página del laboratorio. Elegí una sección de la navegación para continuar.</p>
          </Shell>
        }
      />
    </Routes></QueueProvider>
  );
}
