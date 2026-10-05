# Phase 3 verification — portfolio stress backend

Completed on 5 October 2026 IST. This verifies backend portfolio functionality, not frontend readiness, classification accuracy, fresh-clone setup or final submission readiness.

## Implemented

- Exactly 20 fictional USD positions: 10 loans, six bonds and four swaps; $100 million base fair value, $194.4 million separately reported principal/notional.
- Four versioned illustrative profiles: monetary tightening/easing, corporate credit deterioration and geopolitical supply disruption.
- Conservative current eligibility, issuer-first matching, government/unrelated exclusions, signed swap sensitivity and Decimal cent-level reconciliation.
- Batch-end automatic live execution and explicitly labelled automatic synthetic simulations; reason-required manual comparisons with impact override and idempotency keys.
- Immutable portfolio/scenario/input/result snapshots, saved history, event-to-run links, paginated run API, JSON and numeric-safe CSV exports.
- Version-1-to-2 SQLite migration, version-reuse protection, transactional rollback and retry-safe independent-base calculations.

## Test and hygiene evidence

Command: workspace Python 3.12.14, `pytest -m "not live" --cov=eventlens --cov-branch --cov-report=term-missing`, with a unique workspace-local `--basetemp`.

Result: **156 passed**, **98% combined statement/branch coverage**. `finance.py`, `stress.py`, and `store.py` each have **100% statement and branch coverage**. The run includes the real cached FinBERT test, plus explicit test doubles for controlled API/source/error cases. Coverage measures exercised code, not model accuracy or absence of every possible bug.

Financial checks include independently computed cash rate/spread cases; one-bp unit conversion; zero/opposite shocks; both swap directions with negative fair value; issuer precedence over same-sector unrelated exposure; sector-only matching; sovereign exclusion; scaling; cent reconciliation; frozen input validation; no compounding; and nonfinite/inconsistent data rejection.

Safety checks include speculative/negated/conflicting evidence, future/stale publication, unknown language, truncated source/model text, unresolved credit/supply exposure, incomplete refresh batches, manual-write admission, rejected automatic-mode spoofing, required meaningful reasons, different-family rejection, idempotency conflicts and restart snapshots. Injected calculation inconsistency creates no run. A controlled SQLite request-insert failure rolls back both result and retry binding. The migration test reconstructs a version-1 layout without Phase 3 tables and preserves its existing event/signal.

Ruff check and formatting check pass for all 27 Python files. `pip check` reports no broken requirements. No code was committed, staged or pushed as part of Phase 3.

## Real-model and live pipeline

Command: `python scripts/phase3_verify.py --live`.

Measured window: **2026-10-05 05:23:05–05:23:32 UTC**, **10:53:05–10:53:32 IST**.

Local proof: `runtime/phase3-proof-3ba8e19c1f2d43928a608c8ac50426fd.json`; isolated database: `runtime/phase3-verification-3ba8e19c1f2d43928a608c8ac50426fd.sqlite3`. These machine proofs are ignored runtime outputs, not required public demo datasets.

Pinned real model revision: `ProsusAI/finbert@4556d13015211d73dccd3fdd39d39232506f3e43`. No prediction fallback or live-to-synthetic substitution was used.

| Check | Observed result |
| --- | --- |
| First fictional replay | Nine analyzed records, eight grouped events, three automatic simulations |
| Repeated replay | Nine cached duplicates, zero new stress runs; exact saved-run equality |
| Tightening simulation, impact 8 | +100 bp rate; -$2,618,000.00 P&L |
| Easing simulation, impact 8 | -100 bp rate; +$2,618,000.00 P&L |
| Oil-supply disruption simulation, impact 9 | +56.25 bp rate / +225 bp matched energy spread; -$2,944,125.00 P&L |
| Manual fictional Aster Energy comparison | Impact 8 / +200 bp issuer spread; -$1,308,000.00 P&L; original signal remains impact 7 |
| Both actual live adapters | 40 analyzed records, 35 grouped live events, zero record/source failures |
| Actual live automatic stress | Zero runs; all 35 primary events below the strict automatic threshold |
| Exports | JSON equals the saved snapshot; each simulated CSV has 20 rows, with exact P&L reconciliation |
| Base and restart | Base remains $100 million; all four saved runs and snapshots survive a fresh app lifecycle |

The RSS and social adapters still share the Federal Reserve Board publisher; channel count is not independent corroboration. Automatic **live-mode** execution is covered by controlled adapter tests; this actual measured live batch did not contain an eligible trigger. Simulated outcomes are conditional examples, not historical or predicted real losses.

## Actual HTTP check

Command: `python scripts/http_verify.py` starts an owned single-worker localhost Uvicorn process, makes real HTTP requests, then stops only that process.

Measured at **2026-10-05 05:28:19 UTC / 10:58:19 IST**. Proof: `runtime/http-proof-74d69b68ed3f4b3f822b18af9a9fe364.json`.

Health, portfolio, interactive docs/OpenAPI, supplied-text analysis, write-token enforcement and same-origin writes passed. A manual stress POST without authorization was rejected; an authorized manual run produced -$2,618,000.00, its retry returned the same snapshot, history showed one run, and CSV export succeeded. The supplied rate-hike text's FinBERT score was **+0.7444612793624401**: stress direction came from the event/scenario, not sentiment. The verification server was stopped, and no listener remained on its temporary port 58660.

## Remaining gates

Phase 4: dashboard, user-facing review/run states, keyboard/mobile/error journeys and browser evidence. Phase 5: frozen reviewed real-text evaluation, latency evidence, broader source analysis and fresh-clone installation. Later: candidate walkthrough, final model/source notices, public hosting/access choice, repository naming and exact deadline cutoff, presentation PDF, unlisted video, and final submission checks. No real-market accuracy or full regulatory stress model is claimed.

See [stress arithmetic and assumptions](stress-model.md) before interpreting any result.
