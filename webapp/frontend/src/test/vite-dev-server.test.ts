// @vitest-environment node
// Importing vite.config.ts pulls in esbuild via @vitejs/plugin-react, which is
// incompatible with the project's default jsdom test environment (TextEncoder
// realm mismatch); this file only inspects plain config objects, no DOM needed.
import { describe, expect, it, vi } from "vitest";
import viteConfig from "../../vite.config";

describe("vite dev/preview server binding (explicit loopback)", () => {
  it("# F-UTIL-027 binds the dev server explicitly to 127.0.0.1", () => {
    expect(viteConfig.server?.host).toBe("127.0.0.1");
  });

  it("# F-UTIL-027 binds the preview server explicitly to 127.0.0.1", () => {
    expect(viteConfig.preview?.host).toBe("127.0.0.1");
  });
});

describe("vite dev proxy: Origin normalization and backend-down handling", () => {
  const proxy = viteConfig.server?.proxy?.["/api"];

  it("# F-UTIL-028 is configured for /api", () => {
    expect(proxy).toBeDefined();
  });

  it("# F-UTIL-028 normalizes the Origin header via new URL(target).origin, not the raw target string", () => {
    const handlers: Record<string, (...args: never[]) => void> = {};
    const fakeProxy = {
      on: (event: string, handler: (...args: never[]) => void) => {
        handlers[event] = handler;
      },
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (proxy as any)?.configure?.(fakeProxy);

    const proxyReq = { setHeader: vi.fn() };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (handlers.proxyReq as any)(proxyReq);

    const target = String((proxy as { target?: unknown })?.target ?? "");
    expect(proxyReq.setHeader).toHaveBeenCalledWith("origin", new URL(target).origin);
  });

  it("# F-UTIL-028 responds 502 with a disconnection marker header when the backend is unreachable", () => {
    const handlers: Record<string, (...args: never[]) => void> = {};
    const fakeProxy = {
      on: (event: string, handler: (...args: never[]) => void) => {
        handlers[event] = handler;
      },
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (proxy as any)?.configure?.(fakeProxy);

    const res = { headersSent: false, writeHead: vi.fn(), end: vi.fn() };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (handlers.error as any)(new Error("ECONNREFUSED"), {}, res);

    expect(res.writeHead).toHaveBeenCalledWith(
      502,
      expect.objectContaining({ "X-Laboratorio-Backend-Unreachable": "1" }),
    );
    expect(res.end).toHaveBeenCalled();
  });
});
