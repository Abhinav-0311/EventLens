import { beforeAll, afterAll, afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "./App";
import { server, page } from "./test/server";
import {
  detail,
  run,
  signal,
  health,
  event as eventFixture,
} from "./test/fixtures";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  window.location.hash = "";
});
afterAll(() => server.close());
describe("analyst journey", () => {
  it("restores keyboard focus to the selected event when returning to the queue", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    );
    await user.click(
      await screen.findByRole("link", { name: "← Event queue" }),
    );
    expect(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    ).toHaveFocus();
  });
  it("analyzes supplied text without claiming verified provenance", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/signals/analyze", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ signal });
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByText("Analyze supplied text", { exact: true }),
    );
    expect(screen.getByRole("button", { name: "Analyze text" })).toBeDisabled();
    await user.type(
      screen.getByLabelText("Source text"),
      "The Federal Reserve raised its policy rate by 50 basis points.",
    );
    await user.click(screen.getByRole("button", { name: "Analyze text" }));
    expect(await screen.findByText("Positive +0.744")).toBeInTheDocument();
    expect(body).toEqual({
      text: "The Federal Reserve raised its policy rate by 50 basis points.",
    });
  });
  it("keeps rejected supplied text and explains the retryable failure", async () => {
    server.use(
      http.post("*/api/signals/analyze", () =>
        HttpResponse.json(
          { error: { code: "AUTH", message: "Write token required." } },
          { status: 401 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByText("Analyze supplied text", { exact: true }),
    );
    await user.type(
      screen.getByLabelText("Source text"),
      "Aster Energy defaulted on its debt.",
    );
    await user.click(screen.getByRole("button", { name: "Analyze text" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Access");
    expect(screen.getByLabelText("Source text")).toHaveValue(
      "Aster Energy defaulted on its debt.",
    );
  });
  it("shows successful replay counts, switches to fictional origin, and dismisses notification", async () => {
    server.use(
      http.post("*/api/ingestion/replay", () =>
        HttpResponse.json({
          id: "op1",
          kind: "replay",
          status: "completed",
          result_counts: { analyzed: 9, duplicates: 0, stress_runs: 3 },
          error_code: null,
        }),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Load sample events" }),
    );
    expect(
      await screen.findByText(/Fictional replay completed: 9 analyzed/),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("Origin")).toHaveValue("synthetic");
    await user.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    expect(
      screen.queryByText(/Fictional replay completed:/),
    ).not.toBeInTheDocument();
  });
  it("reports partial live refresh rather than promising automatic execution", async () => {
    server.use(
      http.post("*/api/ingestion/refresh", () =>
        HttpResponse.json({
          id: "op1",
          kind: "refresh",
          status: "completed",
          result_counts: { analyzed: 5, failed_sources: 1 },
          error_code: null,
        }),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Refresh live sources" }),
    );
    expect(
      await screen.findByText(/automatic execution was suppressed/),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("Origin")).toHaveValue("live");
  });
  it("stores optional access only in memory and restores focus on close", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("button", { name: "Load sample events" });
    await user.click(screen.getByRole("button", { name: "Access" }));
    await user.type(
      screen.getByLabelText("Optional write token"),
      "test-only-token",
    );
    await user.click(screen.getByRole("button", { name: "Set token" }));
    expect(screen.getByRole("button", { name: "Access · set" })).toHaveFocus();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    await user.click(screen.getByRole("button", { name: "Access · set" }));
    expect(screen.getByLabelText("Optional write token")).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Clear token" }));
    expect(screen.getByRole("button", { name: "Access" })).toHaveFocus();
  });
  it("allows saved inspection but disables inference if the local model is unavailable", async () => {
    server.use(
      http.get("*/api/health", () =>
        HttpResponse.json({ ...health, model_ready: false }),
      ),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "predictions are not substituted",
    );
    expect(
      screen.getByRole("button", { name: "Load sample events" }),
    ).toBeDisabled();
    expect(screen.getByRole("link", { name: "Portfolio" })).toBeInTheDocument();
  });
  it("clears empty filters without inserting new data", async () => {
    server.use(
      http.get("*/api/events", ({ request }) =>
        HttpResponse.json(
          page(
            new URL(request.url).searchParams.get("minimum_impact") === "8"
              ? []
              : [eventFixture],
          ),
        ),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.selectOptions(await screen.findByLabelText("Impact"), "8");
    expect(
      await screen.findByText("No events match these filters."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    ).toBeInTheDocument();
  });
  it("does not offer an invented scenario for unsupported events", async () => {
    server.use(
      http.get("*/api/events/event1", () =>
        HttpResponse.json({
          ...detail,
          eligibility: {
            ...detail.eligibility,
            scenario_id: null,
            state: "informational",
            reasons: ["scenario_unsupported"],
          },
        }),
      ),
      http.get("*/api/stress-runs", () => HttpResponse.json(page([]))),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    );
    expect(
      await screen.findByText(
        "This event has no supported banking stress scenario.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Compare scenario" }),
    ).not.toBeInTheDocument();
  });
  it("shows an empty saved history and a reload action", async () => {
    server.use(
      http.get("*/api/stress-runs", () => HttpResponse.json(page([]))),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("link", { name: "Runs" }));
    expect(
      await screen.findByRole("heading", { name: "No saved runs" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reload history" }));
    expect(
      await screen.findByRole("heading", { name: "No saved runs" }),
    ).toBeInTheDocument();
  });
  it("retries a failed live refresh without replacing it with fictional replay", async () => {
    let live = 0;
    let replay = 0;
    server.use(
      http.post("*/api/ingestion/refresh", () => {
        live++;
        return HttpResponse.json(
          { error: { code: "COOLDOWN", message: "Source cooldown." } },
          { status: 429, headers: { "Retry-After": "30" } },
        );
      }),
      http.post("*/api/ingestion/replay", () => {
        replay++;
        return HttpResponse.json(
          { error: { code: "WRONG_OPERATION", message: "Unexpected replay." } },
          { status: 409 },
        );
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Refresh live sources" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Retry in about 30 seconds",
    );
    await user.click(screen.getByRole("button", { name: "Retry operation" }));
    await screen.findByRole("button", { name: "Retry operation" });
    expect(live).toBe(2);
    expect(replay).toBe(0);
  });
  it("loads an empty workspace without silently inserting fictional data", async () => {
    server.use(http.get("*/api/events", () => HttpResponse.json(page([]))));
    render(<App />);
    expect(await screen.findByText("No events yet")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Load sample events" }),
    ).toBeEnabled();
    expect(screen.queryByText("Policy rate increase")).not.toBeInTheDocument();
  });
  it("traces synthetic evidence to a saved result and separates sentiment from shock direction", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    );
    expect(await screen.findByText("Positive +0.744")).toBeInTheDocument();
    expect(screen.getByText("Fictional scenario feed")).toBeInTheDocument();
    await user.click(
      await screen.findByRole("button", { name: "View stress result" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Stress result" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("−$40,000.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Automatic simulation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
  });
  it("explains offline errors and allows a retry", async () => {
    server.use(http.get("*/api/health", () => HttpResponse.error()));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Could not reach the risk engine/,
    );
    expect(
      screen.getByRole("button", { name: "Retry connection" }),
    ).toBeEnabled();
  });
  it("requires a meaningful comparison reason and sends a stable manual retry key", async () => {
    server.use(
      http.get("*/api/events/event1", () =>
        HttpResponse.json({
          ...detail,
          stress_run_ids: [],
          eligibility: {
            ...detail.eligibility,
            state: "needs_review",
            reasons: ["source_not_verified"],
          },
        }),
      ),
      http.get("*/api/stress-runs", () => HttpResponse.json(page([]))),
    );
    const requests: Record<string, unknown>[] = [];
    server.use(
      http.post("*/api/stress-runs", async ({ request }) => {
        requests.push((await request.json()) as Record<string, unknown>);
        return requests.length === 1
          ? HttpResponse.json(
              {
                error: {
                  code: "ENGINE_BUSY",
                  message: "Engine busy; retry shortly.",
                },
              },
              { status: 409 },
            )
          : HttpResponse.json({ ...run, mode: "manual_comparison" });
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: /Policy rate increase/ }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Review scenario" }),
    );
    expect(
      screen.getByRole("button", { name: "Save comparison" }),
    ).toBeDisabled();
    await user.type(
      screen.getByLabelText("Comparison reason"),
      "Illustrative manual comparison of the original base.",
    );
    await user.click(screen.getByRole("button", { name: "Save comparison" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Engine busy");
    await user.click(screen.getByRole("button", { name: "Save comparison" }));
    expect(
      await screen.findByRole("heading", { name: "Stress result" }),
    ).toBeInTheDocument();
    expect(requests).toHaveLength(2);
    expect(requests[0].idempotency_key).toBe(requests[1].idempotency_key);
    expect(requests[0]).not.toHaveProperty("mode");
  });
  it("navigates portfolio and run history with native links", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("button", { name: /Policy rate increase/ });
    await user.click(screen.getByRole("link", { name: "Portfolio" }));
    expect(
      await screen.findByRole("table", { name: "Base portfolio positions" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Runs" }));
    expect(
      await screen.findByRole("button", { name: /Monetary tightening/ }),
    ).toBeInTheDocument();
  });
});
