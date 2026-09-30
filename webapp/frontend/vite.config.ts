/// <reference types="vitest/config" />
import type { IncomingMessage, ServerResponse } from "node:http";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend enforces strict same-origin Host/Origin checks (webapp/backend/laboratorio/app.py)
// and has no CORS. The dev proxy must rewrite both the Host header (changeOrigin) and the
// Origin header (the backend rejects an Origin that does not equal "http://<Host>" exactly).
const backendTarget = process.env.LABORATORIO_BACKEND_URL ?? "http://127.0.0.1:8765";
// new URL(...).origin normalizes away any trailing slash/path so the header the backend
// compares against is always a bare "scheme://host[:port]", matching _valid_origin in app.py.
function backendOriginOf(target: string): string {
  try {
    return new URL(target).origin;
  } catch (error) {
    throw new Error(`LABORATORIO_BACKEND_URL is not a valid URL: "${target}"`, { cause: error });
  }
}
const backendOrigin = backendOriginOf(backendTarget);
// Mirrors client.ts's BACKEND_UNREACHABLE_HEADER: when the backend process isn't running,
// http-proxy's "error" event fires instead of a normal proxied response. Without a handler
// that request would hang or surface as an opaque 500; this marks it so the frontend can
// tell the user "disconnected" (NetworkError) instead of misreporting a server error.
const BACKEND_UNREACHABLE_HEADER = "X-Laboratorio-Backend-Unreachable";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            proxyReq.setHeader("origin", backendOrigin);
          });
          proxy.on("error", (_error, _req, res) => {
            const response = res as ServerResponse<IncomingMessage>;
            if (response.headersSent) return;
            response.writeHead(502, {
              "Content-Type": "application/json",
              [BACKEND_UNREACHABLE_HEADER]: "1",
            });
            response.end(JSON.stringify({ detail: "No se pudo contactar al servidor local." }));
          });
        },
      },
    },
  },
  preview: {
    host: "127.0.0.1",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    css: false,
  },
});
