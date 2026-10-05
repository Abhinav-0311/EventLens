import { afterEach, describe, expect, it, vi } from "vitest";
import { Api, ApiError, errorMessage, pause } from "./api";
import { parseRoute } from "./hooks";

afterEach(() => vi.useRealTimers());
describe("API contract", () => {
  it("only accepts same-origin API paths and keeps tokens in the request header", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));
    const api = new Api("private-session-token");
    await expect(api.get("https://example.com/api/health")).rejects.toThrow(
      "same-origin",
    );
    await api.post("/api/signals/analyze", { text: "text" });
    const [url, options] = fetcher.mock.calls[0];
    expect(String(url)).toBe(`${window.location.origin}/api/signals/analyze`);
    expect(options?.headers).toEqual({
      "Content-Type": "application/json",
      "X-EventLens-Token": "private-session-token",
    });
    expect(options?.body).toBe('{"text":"text"}');
  });
  it("explains unauthorized writes, retry intervals, and non-JSON failures safely", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json(
          { error: { code: "AUTH", message: "Token required." } },
          { status: 401 },
        ),
      )
      .mockResolvedValueOnce(
        new Response("untrusted <html>", {
          status: 503,
          headers: { "Retry-After": "20" },
        }),
      );
    const api = new Api();
    await expect(
      api.get("/api/health").catch((error) => {
        throw new Error(errorMessage(error));
      }),
    ).rejects.toThrow("Access");
    await expect(
      api.get("/api/health").catch((error) => {
        throw new Error(errorMessage(error));
      }),
    ).rejects.toThrow("Retry in about 20 seconds");
    expect(errorMessage(new DOMException("aborted", "AbortError"))).toMatch(
      "timed out",
    );
    expect(errorMessage(new Error("secret internal text"))).not.toMatch(
      "secret",
    );
  });
  it("polls queued and running operations to completion", async () => {
    vi.useFakeTimers();
    const progress = vi.fn();
    const controller = new AbortController();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ id: "op1", status: "queued" }))
      .mockResolvedValueOnce(Response.json({ id: "op1", status: "running" }))
      .mockResolvedValueOnce(Response.json({ id: "op1", status: "completed" }));
    const result = new Api().operation("replay", progress, controller.signal);
    await vi.advanceTimersByTimeAsync(1500);
    expect((await result).status).toBe("completed");
    expect(progress).toHaveBeenCalledTimes(3);
  });
  it("reports failed operations instead of fabricating a completed result", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        id: "op1",
        status: "failed",
        error_code: "SOURCE_FAILED",
      }),
    );
    await expect(
      new Api().operation("refresh", vi.fn(), new AbortController().signal),
    ).rejects.toBeInstanceOf(ApiError);
  });
  it("cancels waiting immediately and while a timer is pending", async () => {
    const controller = new AbortController();
    const pending = pause(5000, controller.signal);
    controller.abort();
    await expect(pending).rejects.toHaveProperty("name", "AbortError");
    await expect(pause(5000, controller.signal)).rejects.toHaveProperty(
      "name",
      "AbortError",
    );
  });
  it("parses only bounded local navigation identifiers", () => {
    expect(parseRoute("#runs/run-1")).toEqual({ view: "runs", id: "run-1" });
    expect(parseRoute("#portfolio")).toEqual({ view: "portfolio", id: null });
    expect(parseRoute("#unknown/<script>")).toEqual({
      view: "events",
      id: null,
    });
  });
});
