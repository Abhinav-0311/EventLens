# Phase 4: analyst dashboard verification

Measured locally on 5 October 2026. These are implementation and functional checks, not sentiment/classification accuracy results or a final submission certification.

## Implemented journey

React/TypeScript/Vite provides three surfaces: Events, Portfolio and Runs. FastAPI serves only the built frontend directory, on the same origin as the API. Hash navigation does not need an API-shadowing SPA fallback. An unbuilt frontend leaves the API available.

- Explicit fictional replay or manual live refresh; startup inserts no sample events.
- Origin/impact filters, paginated event/history lists, exact source spans and UTC dates.
- Current eligibility separate from historical signal reasons and actual saved execution.
- Positive/negative financial sentiment separate from scenario direction.
- Supported, reason-required manual comparisons with stable retry identity; unsupported events have no invented scenario.
- Unverified supplied-text analysis, model-unavailable controls, source freshness and partial-failure disclosure.
- Twenty original portfolio positions, fair value separate from notional, versioned assumptions, signed result totals, position contributions and JSON/CSV exports.
- In-memory optional write token, loading/empty/error/retry states, keyboard focus, narrow layouts, reduced motion and horizontally scrollable data tables.

Financial display/reconciliation uses integer cents, not binary-float rounding. Numeric conversion for relative chart widths does not change saved or displayed money.

## Automated gates

- TypeScript check and production Vite build pass.
- Frontend: 30 tests pass; 90.46% line, 90.25% statement, 88.80% function and 83.67% branch coverage. HTTP fixtures/test doubles are explicit and never an application fallback.
- Backend: 158 tests pass; 99% reported statement coverage, including frontend serving and path isolation. Finance, stress and store remain 100% covered by that measurement.
- Ruff check/format and frontend Prettier check pass.
- Full npm audit reports zero vulnerabilities at this check; this is not a permanent security guarantee.

The browser runner uses the real pinned local FinBERT model, actual APIs and a unique test-owned SQLite database. It closes its own browser/backend and retains proof under ignored `runtime/`. Chromium 153.0.8010.12 is the pinned Playwright revision used for final browser checks. No public deployment or authenticated candidate access is implied.

## Real-browser and live evidence

The full run `runtime/phase4-browser-03905e4ffdcd4aad8022e33b6927625c/report.json`, 06:28:37–06:29:15 UTC, passed 43 checks. Desktop was 1440 × 1000, tablet 768 × 1024, mobile 375 × 812. Thirteen axe scans covering WCAG A/AA and 2.1 AA tags found no violations in tested states. This is not comprehensive WCAG certification or proof for all browsers/assistive technologies.

That real run verified eight fictional events, three automatic simulations, a downloaded 20-row CSV, and a labelled manual issuer-credit comparison. Rate-hike P&L was −$2,618,000.00; impact-eight credit comparison P&L was −$1,308,000.00. Repeated replay produced no extra runs, and the original $100,000,000.00 base remained unchanged. Speculation required review; unsupported events and unverified text did not produce automatic results.

Both real source channels succeeded in that run: five RSS and five social records yielded seven live events and zero new live automatic runs. The two channels still share one publisher. Publication freshness/eligibility is distinct from a successful feed refresh.

A later run at approximately 06:36 UTC recorded `SOURCE_HTTP_ERROR` for RSS while social succeeded. Its report failed the required two-live-channel gate; the UI disclosed degraded freshness and suppressed automatic execution. It did not substitute samples. Proof: `runtime/phase4-browser-d6ba198af35047b7aefc362fe8769212/report.json`. Earlier success is historical evidence, not a promise of continuing provider availability.

`npm.cmd run verify:browser` requires both providers. `npm.cmd run verify:browser -- --skip-live` checks the real-model local UI without provider calls and records `live_gate: not_attempted`; it must not be described as a fresh live-source pass.

After the final mobile-header and focus refinements, the provider-independent run `runtime/phase4-browser-c44c870da70b4bcc9755c7f6250c9aeb/report.json` passed 43 checks. This run additionally verifies both queue-heading and selected-row focus restoration. Its screenshots were inspected directly. Live ingestion was intentionally not attempted; the successful full live run and later provider failure above remain separate evidence.

## Design self-review and refinements

The ECC design/testing/accessibility skills guided implementation; the workspace's Emil Kowalski, Impeccable Taste and Elite Product Design constraints guided the visual review.

- Simplicity: retain three surfaces and a restrained off-white/graphite palette. Keep source details, scoring, supplied text and audit fields collapsed until needed. No decorative images, external fonts or marketing cards.
- Composition: the first screenshot showed a tall queue stretching the detail surface. Bound desktop list scrolling and keep the selected row visible; mobile retains the full list and successive list/detail views. Financial figures use tabular numerals and explicit units/signs.
- Product clarity: provenance, review reasons and saved execution remain explicit. Token configuration is secondary. A failed refresh retry now preserves refresh rather than switching to replay; a regression test caught and verifies this fix.
- Accessibility: correct conditional description/control references, retain native links/selects/details, restore focus after token changes and list/detail navigation, and compact the mobile status header without hiding source freshness.

Desktop event/result and mobile event/result/portfolio screenshots were inspected directly, not merely generated. The final keyboard refinement adds queue-heading focus when the current filter excludes the selected event, and selected-row focus otherwise.

## Remaining gates

Phase 5 must freeze/review evaluation labels, measure model/rule errors, verify fresh setup and tighten submission notices. Candidate understanding, public hosting/authentication, complete manual accessibility testing, broad publisher coverage, final repository naming, deck/video and submission links remain separate work. Nothing in Phase 4 establishes model accuracy, forecast validity or submission readiness.
