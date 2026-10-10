import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";

function PlaceholderPage({ name }: { name: string }) {
  return <p className="max-w-prose text-text-secondary">La pantalla de {name} se está reconstruyendo.</p>;
}

export function App() {
  return <Routes>
    <Route path="/" element={<Navigate to="/corridas" replace />} />
    <Route path="/corridas" element={<Shell title="Corridas"><PlaceholderPage name="Corridas" /></Shell>} />
    <Route path="/ajustes" element={<Shell title="Ajustes"><PlaceholderPage name="Ajustes" /></Shell>} />
    <Route path="*" element={<Navigate to="/corridas" replace />} />
  </Routes>;
}
