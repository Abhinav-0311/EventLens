import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const id = randomUUID().replaceAll("-", "");
const output = resolve(root, "runtime", `phase4-browser-${id}`);
await mkdir(output, { recursive: true });
const socket = createServer();
await new Promise((r) => socket.listen(0, "127.0.0.1", r));
const port = socket.address().port;
await new Promise((r) => socket.close(r));
const base = `http://127.0.0.1:${port}`;
const skipLive = process.argv.includes("--skip-live");
const report = {
  started_at: new Date().toISOString(),
  checks: [],
  accessibility: [],
  screenshots: [],
  browser_errors: [],
  real_backend: true,
  isolated_database: true,
};
let logs = "";
let browser;
let page;
const backend = spawn(
  resolve(root, ".venv/Scripts/python.exe"),
  [
    "-m",
    "uvicorn",
    "eventlens.api:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
    "--workers",
    "1",
  ],
  {
    cwd: root,
    windowsHide: true,
    env: {
      ...process.env,
      EVENTLENS_DATABASE: resolve(output, "verification.sqlite3"),
      EVENTLENS_WRITE_TOKEN: "",
      EVENTLENS_PUBLIC: "false",
      EVENTLENS_ALLOWED_HOSTS: "127.0.0.1,localhost",
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  },
);
backend.stdout.on("data", (b) => {
  logs += b.toString();
});
backend.stderr.on("data", (b) => {
  logs += b.toString();
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const check = (name, condition) => {
  assert(condition, name);
  report.checks.push(name);
};
async function ready() {
  for (let attempt = 0; attempt < 90; attempt++) {
    if (backend.exitCode !== null)
      throw new Error("QA backend exited during startup.");
    try {
      const response = await fetch(`${base}/api/health`);
      if (response.ok) {
        const value = await response.json();
        check("Pinned real local FinBERT is ready", value.model_ready);
        return;
      }
    } catch (error) {
      if (error instanceof assert.AssertionError) throw error;
    }
    await sleep(500);
  }
  throw new Error("QA backend startup timed out.");
}
async function audit(page, name) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  report.accessibility.push({
    name,
    violations: result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({ html: n.html, summary: n.failureSummary })),
    })),
  });
  check(
    `${name}: axe WCAG A/AA reports no violations`,
    result.violations.length === 0,
  );
}
async function shot(page, name) {
  const path = resolve(output, `${name}.png`);
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
  report.screenshots.push(path);
}
async function noOverflow(page, name) {
  check(
    `${name}: no page-level horizontal overflow`,
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  );
}
try {
  await ready();
  browser = await chromium.launch({
    headless: true,
    ...(process.env.EVENTLENS_BROWSER_EXECUTABLE
      ? { executablePath: process.env.EVENTLENS_BROWSER_EXECUTABLE }
      : {}),
  });
  report.browser_version = browser.version();
  report.browser_executable_override =
    !!process.env.EVENTLENS_BROWSER_EXECUTABLE;
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
    acceptDownloads: true,
  });
  page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.on("pageerror", (error) => report.browser_errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.text().includes("Failed to load resource")
    )
      report.browser_errors.push(message.text());
  });
  await page.addInitScript(() => {
    window.__layoutShifts = [];
    window.__lcp = 0;
    new PerformanceObserver((list) =>
      list.getEntries().forEach((entry) => {
        if (!entry.hadRecentInput) window.__layoutShifts.push(entry.value);
      }),
    ).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((list) => {
      window.__lcp = list.getEntries().at(-1).startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
  });
  await page.goto(base);
  await page.getByRole("heading", { name: "No events yet" }).waitFor();
  check(
    "Empty startup has no automatically inserted fixtures",
    (await (await fetch(`${base}/api/events`)).json()).total === 0,
  );
  await page.keyboard.press("Tab");
  check(
    "Keyboard-first skip link is reachable",
    await page
      .getByRole("link", { name: "Skip to workspace" })
      .evaluate((e) => e === document.activeElement),
  );
  await page.keyboard.press("Enter");
  check(
    "Skip link focuses workspace",
    await page.locator("main").evaluate((e) => e === document.activeElement),
  );
  await audit(page, "Desktop empty");
  await shot(page, "desktop-empty");
  await page
    .getByRole("button", { name: "Load sample events", exact: true })
    .click();
  await page
    .getByText(
      /Fictional replay completed: 9 analyzed, 0 duplicates, 3 new stress runs/,
    )
    .waitFor();
  const events = (
    await (await fetch(`${base}/api/events?mode=synthetic&limit=100`)).json()
  ).items;
  check(
    "Fictional replay has eight events and three automatic simulations",
    events.length === 8 &&
      (await (await fetch(`${base}/api/stress-runs`)).json()).total === 3,
  );
  const hike = events.find(
    (e) =>
      e.primary_signal.event_subtype === "rate_hike" &&
      e.primary_signal.assertion_status === "asserted",
  );
  await page.goto(`${base}/#events/${hike.id}`);
  await page.getByRole("button", { name: "View stress result" }).waitFor();
  check(
    "Synthetic provenance remains visible",
    (await page.getByText("Fictional event.", { exact: false }).count()) === 1,
  );
  await audit(page, "Desktop selected event");
  await shot(page, "desktop-event");
  await page.getByRole("button", { name: "View stress result" }).click();
  await page.getByRole("heading", { name: "Stress result" }).waitFor();
  check(
    "Rate scenario shows exact hand-checked P&L",
    (await page.getByText("−$2,618,000.00", { exact: true }).count()) > 0,
  );
  check(
    "All twenty position contributions are shown",
    (await page
      .getByRole("table", { name: "Stress position results" })
      .locator("tbody tr")
      .count()) === 20,
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV", exact: true }).click();
  const download = await downloadPromise;
  const csvPath = resolve(output, "stress-export.csv");
  await download.saveAs(csvPath);
  const lines = (await readFile(csvPath, "utf8")).trim().split(/\r?\n/);
  check("Downloaded CSV contains twenty position rows", lines.length === 21);
  report.csv_export = csvPath;
  await audit(page, "Desktop result");
  await shot(page, "desktop-result");
  await page.getByRole("link", { name: "Portfolio", exact: true }).click();
  await page.getByRole("table", { name: "Base portfolio positions" }).waitFor();
  check(
    "Portfolio shows twenty base positions",
    (await page
      .getByRole("table", { name: "Base portfolio positions" })
      .locator("tbody tr")
      .count()) === 20,
  );
  await audit(page, "Desktop portfolio");
  await shot(page, "desktop-portfolio");
  const credit = events.find(
    (e) => e.primary_signal.event_subtype === "credit_deterioration",
  );
  await page.goto(`${base}/#events/${credit.id}`);
  await page
    .getByRole("button", { name: /^(Review|Compare) scenario$/ })
    .click();
  check(
    "Comparison requires a written reason",
    await page.getByRole("button", { name: "Save comparison" }).isDisabled(),
  );
  await page.getByLabel("Comparison impact").selectOption("8");
  await page
    .getByLabel("Comparison reason")
    .fill(
      "Illustrative issuer-specific impact-eight credit comparison from original base.",
    );
  await audit(page, "Manual comparison form");
  await shot(page, "desktop-comparison");
  await page.getByRole("button", { name: "Save comparison" }).click();
  await page.getByRole("heading", { name: "Stress result" }).waitFor();
  check(
    "Manual credit comparison is labelled and hand-checked",
    (await page.getByText("Manual comparison", { exact: true }).count()) ===
      1 &&
      (await page.getByText("−$1,308,000.00", { exact: true }).count()) > 0,
  );
  check(
    "Manual comparison leaves original base unchanged",
    (await (await fetch(`${base}/api/portfolio`)).json()).base_total_usd ===
      "100000000.00",
  );
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await page.getByRole("heading", { name: "Runs", exact: true }).waitFor();
  await audit(page, "Desktop history");
  await page.getByRole("link", { name: "Events", exact: true }).click();
  await page.getByRole("button", { name: "Load sample events" }).click();
  await page
    .getByText(
      /Fictional replay completed: 0 analyzed, 9 duplicates, 0 new stress runs/,
    )
    .waitFor();
  check(
    "Repeated replay creates no duplicate stress run or loss compounding",
    (await (await fetch(`${base}/api/stress-runs`)).json()).total === 4,
  );
  const unsupported = events.find(
    (e) => e.primary_signal.event_subtype === "product_launch",
  );
  await page.goto(`${base}/#events/${unsupported.id}`);
  await page
    .getByText("This event has no supported banking stress scenario.")
    .waitFor();
  check(
    "Unsupported event offers no invented comparison",
    (await page
      .getByRole("button", { name: "Compare scenario", exact: true })
      .count()) === 0,
  );
  const speculative = events.find(
    (e) => e.primary_signal.assertion_status === "speculative",
  );
  await page.goto(`${base}/#events/${speculative.id}`);
  await page.getByRole("button", { name: "Review scenario" }).waitFor();
  check(
    "High-impact speculation requires review instead of automatic execution",
    (await page
      .getByText("Automatic execution is blocked.", { exact: false })
      .count()) === 1 &&
      (await page
        .getByRole("button", { name: "View stress result" })
        .count()) === 0,
  );
  await page.getByText("Analyze supplied text", { exact: true }).click();
  await page
    .getByLabel("Source text", { exact: true })
    .fill("The Federal Reserve raised its policy rate by 50 basis points.");
  await page.getByRole("button", { name: "Analyze text", exact: true }).click();
  await page
    .getByText("User input · no verified source link", { exact: true })
    .waitFor();
  check(
    "User text remains unverified and cannot automatically run",
    (await page
      .getByText("Publisher is not verified.", { exact: true })
      .count()) === 1 &&
      (await (await fetch(`${base}/api/stress-runs`)).json()).total === 4,
  );
  await audit(page, "Supplied text evidence");
  if (!skipLive) {
    await page
      .getByRole("button", { name: "Refresh live sources", exact: true })
      .click();
    await page
      .getByText(/Live refresh completed:/)
      .waitFor({ timeout: 120000 });
    report.live_health = await (await fetch(`${base}/api/health`)).json();
    report.live_events = (
      await (await fetch(`${base}/api/events?mode=live&limit=100`)).json()
    ).total;
    check(
      "Both real live channels refreshed successfully",
      report.live_health.sources.length === 2 &&
        report.live_health.sources.every(
          (source) => source.last_success_at && !source.error_code,
        ),
    );
    check(
      "Live refresh retained real evidence records",
      report.live_events > 0,
    );
    report.live_gate = "passed";
  } else {
    report.live_gate = "not_attempted";
    await page.getByRole("combobox", { name: /^Origin/ }).selectOption("live");
  }
  await page.locator(".source-status summary").click();
  await audit(page, "Expanded source freshness");
  await shot(page, "desktop-live");
  await page.locator(".source-status summary").click();
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto(`${base}/#events/${hike.id}`);
  await page.getByRole("button", { name: "View stress result" }).waitFor();
  await noOverflow(page, "Tablet event");
  await shot(page, "tablet-event");
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`${base}/#events/${hike.id}`);
  await page.getByRole("button", { name: "View stress result" }).waitFor();
  check(
    "Mobile detail hides queue until back navigation",
    !(await page.locator(".event-queue").isVisible()),
  );
  await noOverflow(page, "Mobile event");
  await audit(page, "Mobile event");
  await shot(page, "mobile-event");
  await page.getByRole("link", { name: "← Event queue" }).click();
  await page.locator(".event-queue").waitFor({ state: "visible" });
  await page.waitForFunction(
    () =>
      document.querySelector(".queue-heading h2") === document.activeElement,
  );
  check(
    "Mobile back restores queue-heading focus when the filter excludes the event",
    (await page.locator(".event-queue").isVisible()) &&
      (await page
        .locator(".queue-heading h2")
        .evaluate((e) => e === document.activeElement)),
  );
  await page
    .getByRole("combobox", { name: /^Origin/ })
    .selectOption("synthetic");
  await page.locator(`[data-event-id="${hike.id}"]`).waitFor();
  await page.locator(`[data-event-id="${hike.id}"]`).press("Enter");
  await page.getByRole("button", { name: "View stress result" }).waitFor();
  await page.getByRole("link", { name: "← Event queue" }).click();
  await page.locator(".event-queue").waitFor({ state: "visible" });
  await page.waitForFunction(
    (id) =>
      document.querySelector(`[data-event-id="${id}"]`) ===
      document.activeElement,
    hike.id,
  );
  check(
    "Mobile back restores selected-row focus when that event is in the queue",
    await page
      .locator(`[data-event-id="${hike.id}"]`)
      .evaluate((e) => e === document.activeElement),
  );
  await page.locator(`[data-event-id="${hike.id}"]`).press("Enter");
  await page.getByRole("button", { name: "View stress result" }).waitFor();
  await page.getByRole("button", { name: "View stress result" }).click();
  await page.getByRole("heading", { name: "Stress result" }).waitFor();
  await noOverflow(page, "Mobile result");
  await audit(page, "Mobile result");
  await shot(page, "mobile-result");
  await page.getByRole("link", { name: "Portfolio", exact: true }).click();
  await page.getByRole("table", { name: "Base portfolio positions" }).waitFor();
  await noOverflow(page, "Mobile portfolio");
  await audit(page, "Mobile portfolio");
  await shot(page, "mobile-portfolio");
  await page.getByRole("button", { name: "Access", exact: true }).click();
  await page
    .getByLabel("Optional write token")
    .fill("qa-only-not-a-real-secret");
  await audit(page, "Mobile access form");
  await page.getByRole("button", { name: "Set token" }).click();
  check(
    "Access panel restores focus after saving",
    await page
      .getByRole("button", { name: "Access · set" })
      .evaluate((e) => e === document.activeElement),
  );
  check(
    "Token is not persisted in browser storage",
    await page.evaluate(() => !localStorage.length && !sessionStorage.length),
  );
  await page.reload();
  await page.getByRole("button", { name: "Access", exact: true }).waitFor();
  check("Reload clears optional token", true);
  check(
    "Reduced-motion preference disables interface animation",
    await page
      .locator(".source-status")
      .evaluate((e) => getComputedStyle(e).animationName === "none"),
  );
  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "QA_UNAVAILABLE", message: "QA: engine unavailable." },
      }),
    }),
  );
  await page.reload();
  await page.getByRole("button", { name: "Retry connection" }).waitFor();
  await audit(page, "Connection error");
  await shot(page, "mobile-error");
  await page.unroute("**/api/health");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await page.getByRole("table", { name: "Base portfolio positions" }).waitFor();
  check("Connection retry returns to real saved portfolio", true);
  report.observed_browser_metrics = await page.evaluate(() => ({
    cls_unexpected_shifts: window.__layoutShifts.reduce((a, b) => a + b, 0),
    lcp_ms: window.__lcp,
  }));
  check(
    "No browser application errors occurred",
    report.browser_errors.length === 0,
  );
  report.status = "passed";
} catch (error) {
  report.status = "failed";
  report.failure = error.message;
  process.exitCode = 1;
  if (page) {
    report.failure_focus = await page
      .evaluate(() => ({
        hash: location.hash,
        focused: document.activeElement.outerHTML.slice(0, 1200),
      }))
      .catch(() => null);
    await shot(page, "failure-state").catch(() => {});
  }
} finally {
  if (browser) await browser.close();
  backend.kill();
  await Promise.race([
    new Promise((r) => backend.once("exit", r)),
    sleep(3000),
  ]);
  report.finished_at = new Date().toISOString();
  await writeFile(
    resolve(output, "report.json"),
    JSON.stringify(report, null, 2),
  );
  await writeFile(resolve(output, "backend.log"), logs);
  console.log(
    JSON.stringify({
      status: report.status,
      checks: report.checks.length,
      report: resolve(output, "report.json"),
      failure: report.failure,
    }),
  );
}
