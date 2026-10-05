import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { detail, event, health, portfolio, run, scenarios } from "./fixtures";
export const page = <T>(items: T[]) => ({
  items,
  total: items.length,
  limit: 25,
  offset: 0,
});
export const server = setupServer(
  http.get("*/api/health", () => HttpResponse.json(health)),
  http.get("*/api/portfolio", () => HttpResponse.json(portfolio)),
  http.get("*/api/scenarios", () => HttpResponse.json(scenarios)),
  http.get("*/api/events", () => HttpResponse.json(page([event]))),
  http.get("*/api/events/event1", () => HttpResponse.json(detail)),
  http.get("*/api/stress-runs", () => HttpResponse.json(page([run]))),
  http.get("*/api/stress-runs/run1", () => HttpResponse.json(run)),
);
