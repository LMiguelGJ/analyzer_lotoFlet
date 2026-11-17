import { Link } from "react-router-dom";

/** Shown instead of an error screen when the active list has no reference laboratories (HTTP 409). */
export function ListNotice({ message }: { message: string }) {
  return <div className="reference-list-notice" role="status">
    <p>{message}</p>
    <p>Los laboratorios de referencia solo existen para Loteka Chance Express. <Link to="/ajustes">Cambiar la lista en Ajustes</Link></p>
  </div>;
}
