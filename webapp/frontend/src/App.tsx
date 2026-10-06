import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Shell, type PrimaryAction } from "./components/Shell";
import { QueueProvider } from "./components/QueueProvider";
import { ExperimentsPage } from "./pages/experiments";
import { BacktestCreatePage, BacktestDetailPage, BacktestsPage } from "./pages/backtests";
import { DetailPage } from "./pages/experiments/DetailPage";
import { ComparisonPage } from "./pages/experiments/ComparisonPage";
import { NewExperimentPage } from "./pages/new-experiment";
import { ProfileExperimentPage } from "./pages/new-experiment/ProfileExperimentPage";
import { ProfileBatchPage } from "./pages/new-experiment/ProfileBatchPage";
import { ConfigurationsPage } from "./pages/configurations";
import { SettingsPage } from "./pages/settings";
import { DataPage } from "./pages/data";

const newSimulation: PrimaryAction = { label: "Nueva simulación", to: "/simulaciones/nueva" };
const newHistoricalRun: PrimaryAction = { label: "Nueva corrida histórica", to: "/simulaciones/nueva-historica" };

function LegacyExperimentRedirect() {
  const { pathname, search, hash } = useLocation();
  const nextPath = pathname
    .replace(/^\/experimentos\/nuevo(?=\/|$)/, "/simulaciones/nueva")
    .replace(/^\/experimentos/, "/simulaciones");
  return <Navigate to={{ pathname: nextPath, search, hash }} replace />;
}

export function App() {
  return <QueueProvider><Routes>
    <Route path="/" element={<Navigate to="/simulaciones" replace />} />
    <Route path="/experimentos" element={<LegacyExperimentRedirect />} />
    <Route path="/experimentos/*" element={<LegacyExperimentRedirect />} />
    <Route path="/simulaciones" element={<Shell key="experiments" title="Simulaciones" primaryAction={newSimulation}><ExperimentsPage /></Shell>} />
    <Route path="/simulaciones/historicas" element={<Shell key="backtests" title="Corridas históricas" primaryAction={newHistoricalRun}><BacktestsPage /></Shell>} />
    <Route path="/simulaciones/historicas/:id" element={<Shell key="backtest-detail" title="Resultado de corrida histórica" mobileTitle="Resultado"><BacktestDetailPage /></Shell>} />
    <Route path="/simulaciones/nueva-historica" element={<Shell key="new-backtest" title="Nueva corrida histórica"><BacktestCreatePage /></Shell>} />
    <Route path="/simulaciones/nueva" element={<Shell key="new-experiment" title="Crear simulación"><NewExperimentPage /></Shell>} />
    <Route path="/simulaciones/nueva/sesion" element={<Shell key="new-profile-batch" title="Crear varias simulaciones"><ProfileBatchPage /></Shell>} />
    <Route path="/simulaciones/nueva/perfil" element={<Shell key="new-profile-experiment" title="Crear simulación con perfil de juego"><ProfileExperimentPage /></Shell>} />
    <Route path="/simulaciones/:id/comparacion" element={<Shell key="comparison" title="Comparar simulaciones" mobileTitle="Comparación"><ComparisonPage /></Shell>} />
    <Route path="/simulaciones/:id" element={<Shell key="detail" title="Resultado de la simulación" mobileTitle="Resultado"><DetailPage /></Shell>} />
    <Route path="/configuraciones" element={<Shell key="configurations" title="Estrategias" primaryAction={newSimulation}><ConfigurationsPage /></Shell>} />
    <Route path="/datos" element={<Shell key="data" title="Datos e historial"><DataPage /></Shell>} />
    <Route path="/ajustes" element={<Shell key="settings" title="Ajustes"><SettingsPage /></Shell>} />
    <Route path="*" element={<Shell key="not-found" title="Página no encontrada" primaryAction={newSimulation}>
      <p className="mb-4 max-w-prose text-text-secondary">Esta dirección no corresponde a una página del laboratorio. Elegí una sección de la navegación para continuar.</p>
      <a className="btn btn-primary" href="/simulaciones">Ir a Simulaciones</a>
    </Shell>} />
  </Routes></QueueProvider>;
}
