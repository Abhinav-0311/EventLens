# Phase 2 verification

Completed 5 October 2026 IST on Windows 11, Python 3.12.14. Risk-engine backend only: no portfolio, dashboard, deployment, presentation, or final submission claim.

## Recorded gates

| Gate | Observed result |
| --- | --- |
| Full backend suite, including cached-model test | 102 passed; 97% combined statement/branch-aware coverage |
| Classification, sentiment, schemas, config, errors, SQLite modules | 100% measured coverage in that suite; not model accuracy |
| Lint / formatting / dependencies | Ruff clean; format check clean; pip check found no broken requirements |
| Real live-source pipeline, 20-record limit | 20 RSS + 20 social records analyzed; 2 successful sources; 0 failed records/sources |
| Grouping | 40 live records -> 35 live events; both families retained; independent-publisher evidence not claimed |
| Official release expansion | 1 full release retrieved and analyzed through the allowlisted adapter |
| Synthetic replay | 9 records -> 8 events; repeated run returned 9 duplicates, 0 new analyses, unchanged event results |
| Supplied text | Real model negative score about -0.956326 on the synthetic debt-default smoke sentence; user provenance remains unverified |
| Exports | 50 signals in JSON for the broader live verification; CSV endpoint also passed |
| Persistence | Same database reopened in a new app lifecycle retained event counts |
| Actual HTTP server | Loopback Uvicorn health, docs/OpenAPI, token protection, same-origin analysis, 422/404 paths passed; owned server stopped afterward |

Final live run: 2026-10-04T20:34:24Z through 20:34:32Z, which is 5 October 02:04 IST. Its local machine-readable report is `runtime/phase2-proof-57872602c95e4f7c9969a4967a2feaba.json`; raw evidence/signals remain in its corresponding verification SQLite file. These runtime artifacts are deliberately ignored, not repository attachments. The commands below generate new proof.

The expanded official release at `https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm` yielded a recognized 25 bp rate-hike phrase and impact 7. Its stored publication time also produced a stale_event review reason. This checks extraction and rule behavior on one real release; it does not establish general event-classification quality or a current market fact.

## Failure and boundary checks

Tests cover negation, speculation, historical context, conflicting directions, plural rates, percentage-point fractions, unrelated rate mentions, unknown input, explicit entity/scope rules, required score ranges, probabilities, and exact evidence spans.

Integration checks cover canonical grouping, same-publisher evidence, changed/text-identical-but-different identities, stable signal IDs, replay provenance, simulation clocks, future/stale timestamps, restart interruption, source cooldown/Retry-After persistence, partial/all-source failures, retention of failed inputs, inference failures, worker recovery, and no lexical fallback.

Request/source checks cover bounded streamed bodies, validated fields and timezone-aware inputs, restricted host/origin access, write-token checks, unknown IDs, allowlisted URLs, no followed redirects, official social DID checks, XML entity rejection, bounded source responses/retries, explicit text/token truncation, and CSV formula protection.

Source fetching, some HTTP-framework edge cases, and defensive internal branches do not have 100% coverage. Coverage proves which code ran, not absence of defects. Public deployment, distributed workers, arbitrary-language understanding, calibrated uncertainty, and a security audit are not claimed.

## Repeat the checks

From the repository root, after installing dependencies and caching the pinned model:

```powershell
New-Item -ItemType Directory -Path .cache/test-runs -Force | Out-Null
$eventlensTestPath = Join-Path (Resolve-Path .cache/test-runs) ([guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -m "not live" --basetemp $eventlensTestPath --cov=eventlens --cov-branch --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check eventlens tests scripts
.\.venv\Scripts\python.exe -m ruff format --check eventlens tests scripts
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\phase2_verify.py --live --source-limit 20
.\.venv\Scripts\python.exe scripts\http_verify.py
```

Do not repeatedly rerun the live check inside the publishers' refresh interval. Unit/API tests use explicit test doubles; the recorded live and HTTP scripts use the real cached FinBERT model. Synthetic cases are functional examples, not a frozen real-text accuracy set.

## Remaining work

Phase 3 must add the portfolio and scenario/exposure mapping, verified financial units/arithmetic, idempotent stress runs, and saved comparisons. Later phases must test the dashboard, freeze/review real-text labels, assess error examples, prove fresh-clone setup/model acquisition, finish notices, teach the candidate the full project, and package/verify presentation and submission links.
