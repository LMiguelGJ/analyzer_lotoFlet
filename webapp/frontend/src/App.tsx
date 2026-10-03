import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { QueueProvider } from "./components/QueueProvider";
import { ExperimentsPage } from "./pages/experiments";
import { DetailPage } from "./pages/experiments/DetailPage";
import { ComparisonPage } from "./pages/experiments/ComparisonPage";
import { NewExperimentPage } from "./pages/new-experiment";
import { ProfileExperimentPage } from "./pages/new-experiment/ProfileExperimentPage";
import { ProfileBatchPage } from "./pages/new-experiment/ProfileBatchPage";
import { ConfigurationsPage } from "./pages/configurations";
import { SettingsPage } from "./pages/settings";
import { DataPage } from "./pages/data";

export function App() {
  return (
    <QueueProvider><Routes>
      <Route path="/" element={<Navigate to="/experimentos" replace />} />
      <Route
        path="/experimentos"
        element={
          <Shell key="experiments" title="Simulaciones">
            <ExperimentsPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/nuevo"
        element={
          <Shell key="new-experiment" title="Crear simulación">
            <NewExperimentPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/nuevo/sesion"
        element={
          <Shell key="new-profile-batch" title="Lote de simulaciones">
            <ProfileBatchPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/nuevo/perfil"
        element={
          <Shell key="new-profile-experiment" title="Simulación con perfil">
            <ProfileExperimentPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/:id/comparacion"
        element={
          <Shell key="comparison" title="Comparación de simulaciones">
            <ComparisonPage />
          </Shell>
        }
      />
      <Route
        path="/experimentos/:id"
        element={
          <Shell key="detail" title="Resultado de la simulación">
            <DetailPage />
          </Shell>
        }
      />
      <Route
        path="/configuraciones"
        element={
          <Shell key="configurations" title="Estrategias">
            <ConfigurationsPage />
          </Shell>
        }
      />
      <Route
        path="/datos"
        element={
          <Shell key="data" title="Datos del laboratorio">
            <DataPage />
          </Shell>
        }
      />
      <Route
        path="/ajustes"
        element={
          <Shell key="settings" title="Administración del laboratorio">
            <SettingsPage />
          </Shell>
        }
      />
      <Route
        path="*"
        element={
          <Shell key="not-found" title="Página no encontrada">
            <p className="mb-4 max-w-prose text-text-secondary">Esta dirección no corresponde a una página del laboratorio. Elegí una sección de la navegación para continuar.</p>
            <a className="btn btn-primary" href="/experimentos">Ir a Simulaciones</a>
          </Shell>
        }
      />
    </Routes></QueueProvider>
  );
}
