import type { Operation } from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 0,
    public retryAfter: number | null = null,
  ) {
    super(message);
  }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const help =
      error.status === 401
        ? " Set the write token under Access and retry."
        : error.retryAfter
          ? ` Retry in about ${error.retryAfter} seconds.`
          : "";
    return error.message + help;
  }
  if (
    (error instanceof Error || error instanceof DOMException) &&
    ["AbortError", "TimeoutError"].includes(error.name)
  )
    return "The request timed out or was cancelled. Check the engine and retry.";
  return "Could not reach the risk engine. Start the backend, then retry. No sample data has been substituted.";
}
export class Api {
  constructor(private token = "") {}
  async response(
    path: string,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<Response> {
    if (!path.startsWith("/api/"))
      throw new Error("Only same-origin API paths are permitted");
    const timeout = AbortSignal.timeout(body === undefined ? 20000 : 90000);
    const response = await fetch(new URL(path, window.location.origin), {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(this.token ? { "X-EventLens-Token": this.token } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      const value = await response.json().catch(() => null);
      const retry = Number(response.headers.get("retry-after"));
      throw new ApiError(
        value?.error?.code ?? "HTTP_ERROR",
        value?.error?.message ?? `Request failed (${response.status}).`,
        response.status,
        Number.isFinite(retry) && retry > 0 ? retry : null,
      );
    }
    return response;
  }
  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return (await this.response(path, undefined, signal)).json();
  }
  async post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    return (await this.response(path, body, signal)).json();
  }
  async operation(
    kind: "refresh" | "replay",
    progress: (operation: Operation) => void,
    signal: AbortSignal,
  ): Promise<Operation> {
    let current = await this.post<Operation>(
      `/api/ingestion/${kind}`,
      {},
      signal,
    );
    const deadline = Date.now() + 120000;
    while (["queued", "running"].includes(current.status)) {
      progress(current);
      if (Date.now() >= deadline)
        throw new ApiError(
          "POLL_TIMEOUT",
          "The operation is still running. Reload the workspace to inspect saved results; do not start a duplicate operation.",
        );
      await pause(700, signal);
      current = await this.get<Operation>(
        `/api/operations/${encodeURIComponent(current.id)}`,
        signal,
      );
    }
    progress(current);
    if (current.status !== "completed")
      throw new ApiError(
        current.error_code ?? "OPERATION_FAILED",
        "The operation did not complete successfully. Existing evidence was retained; inspect source status and retry.",
      );
    return current;
  }
  async download(path: string, filename: string) {
    const blob = await (await this.response(path)).blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
export function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    const cancel = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, ms);
    signal.addEventListener("abort", cancel, { once: true });
  });
}
