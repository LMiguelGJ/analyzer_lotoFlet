import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { ListPage } from "./pages/runs/ListPage";
import { NewRunPage } from "./pages/runs/NewRunPage";

function PlaceholderPage({ name }: { name: string }) {
  return <p className="max-w-prose text-text-secondary">La pantalla de {name} se está reconstruyendo.</p>;
}

export function App() {
  return <Routes>
    <Route path="/" element={<Navigate to="/corridas" replace />} />
    <Route path="/corridas/nueva" element={<Shell title="Nueva corrida"><NewRunPage /></Shell>} />
    <Route path="/corridas/:id" element={<Shell title="Resultado"><PlaceholderPage name="Resultado" /></Shell>} />
    <Route path="/corridas" element={<Shell title="Corridas"><ListPage /></Shell>} />
    <Route path="/ajustes" element={<Shell title="Ajustes"><PlaceholderPage name="Ajustes" /></Shell>} />
    <Route path="*" element={<Navigate to="/corridas" replace />} />
  </Routes>;
}
