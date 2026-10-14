import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError, request } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("request boundary", () => {
  it("retains typed HTTP errors and bodyless 204 responses", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "No existe" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Conflicto" }), { status: 409 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: [{ loc: ["body", "name"], msg: "invalid", type: "value_error" }] }), { status: 422 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/missing")).rejects.toMatchObject({ name: "ApiError", status: 404, detail: "No existe", fieldErrors: null, uncertainWrite: false });
    await expect(request("/conflict")).rejects.toMatchObject({ name: "ApiError", status: 409, detail: "Conflicto", fieldErrors: null, uncertainWrite: false });
    await expect(request("/invalid")).rejects.toMatchObject({ name: "ApiError", status: 422, fieldErrors: [{ loc: ["body", "name"], msg: "invalid", type: "value_error" }], uncertainWrite: false });
    await expect(request<void>("/gone", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("distinguishes network failure from caller cancellation", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/offline")).rejects.toBeInstanceOf(NetworkError);
    await expect(request("/cancel", { signal: AbortSignal.abort() })).rejects.toMatchObject({ name: "AbortError" });
  });

  it("preserves AbortError identity while parsing success and 422 response bodies", async () => {
    const errorResponse = new Response("{}", { status: 422, statusText: "Unprocessable Entity" });
    const successResponse = new Response("{}", { status: 200 });
    const errorAbort = new DOMException("Error-body read aborted", "AbortError");
    const successAbort = new DOMException("Success-body read aborted", "AbortError");
    vi.spyOn(errorResponse, "json").mockRejectedValueOnce(errorAbort);
    vi.spyOn(successResponse, "json").mockRejectedValueOnce(successAbort);
    const fetchMock = vi.fn().mockResolvedValueOnce(errorResponse).mockResolvedValueOnce(successResponse);
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/error-body-abort")).rejects.toBe(errorAbort);
    await expect(request("/success-body-abort")).rejects.toBe(successAbort);
  });

  it("keeps malformed JSON handling distinct from aborts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("not json", { status: 400, statusText: "Bad Request" }))
      .mockResolvedValueOnce(new Response("not json", { status: 200 }))
      .mockResolvedValueOnce(new Response("not json", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/error-malformed")).rejects.toMatchObject({ name: "ApiError", status: 400, detail: "Bad Request", uncertainWrite: false });
    await expect(request("/success-malformed")).rejects.toMatchObject({ name: "ApiError", status: 200, uncertainWrite: false });
    await expect(request("/write-malformed", { method: "POST" })).rejects.toMatchObject({ name: "ApiError", status: 201, uncertainWrite: true });
  });

  it("marks unreadable successful write responses uncertain but preserves GET and HEAD errors", async () => {
    const unreadable = () => {
      const response = new Response("{}", { status: 201 });
      vi.spyOn(response, "json").mockRejectedValueOnce(new SyntaxError("cannot decode body"));
      return response;
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(unreadable())
      .mockResolvedValueOnce(unreadable());
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/read-unreadable")).rejects.toMatchObject({ name: "ApiError", status: 201, uncertainWrite: false });
    await expect(request("/head-unreadable", { method: "HEAD" })).rejects.toMatchObject({ name: "ApiError", status: 201, uncertainWrite: false });
  });

  it("retains structured validation details", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "name"], msg: "invalid", type: "value_error" }] }), { status: 422 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/invalid")).rejects.toMatchObject({ name: "ApiError", fieldErrors: [{ loc: ["body", "name"], msg: "invalid", type: "value_error" }] } satisfies Partial<ApiError>);
  });
});
