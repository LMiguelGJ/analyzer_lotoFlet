import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { App } from "./App";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("missing #root element");
}

// A data router is required for the wizard's accessible in-app/back navigation blocker.
// Construct once, outside React rendering, so provider state and URLs remain stable.
const router = createBrowserRouter([{ path: "*", element: <App /> }]);

createRoot(container).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
