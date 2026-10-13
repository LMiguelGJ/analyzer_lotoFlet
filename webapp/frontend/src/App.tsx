import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { ListPage } from "./pages/runs/ListPage";
import { NewRunPage } from "./pages/runs/NewRunPage";
import { ResultPage } from "./pages/runs/ResultPage";
import { SettingsPage } from "./pages/settings/SettingsPage";
import { Workspace } from "./pages/laboratories/Workspace";

export function App() {
  return <Routes>
    <Route path="/" element={<Navigate to="/laboratorios" replace />} />
    <Route path="/corridas/nueva" element={<Shell title="Nueva corrida"><NewRunPage /></Shell>} />
    <Route path="/corridas/:id" element={<Shell title="Resultado"><ResultPage /></Shell>} />
    <Route path="/corridas" element={<Shell title="Corridas"><ListPage /></Shell>} />
    <Route path="/laboratorios" element={<Shell title="Laboratorios"><Workspace /></Shell>} />
    <Route path="/laboratorios/:labId" element={<Shell title="Laboratorios"><Workspace /></Shell>} />
    <Route path="/ajustes" element={<Shell title="Ajustes"><SettingsPage /></Shell>} />
    <Route path="*" element={<Navigate to="/laboratorios" replace />} />
  </Routes>;
}
