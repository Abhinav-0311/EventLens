# Phase 5: evaluation and reproducibility

Measured on 5 October 2026. Contract/input labels frozen before prediction. No model training, probability calibration, threshold search or severity-label fitting. ECC's ML workflow guided leakage separation, baseline/error inspection and regression-first refinement. Functional gates are separate from label agreement.

## Results and boundaries

| Lane | Measured result | What it means |
| --- | --- | --- |
| PhraseBank all-agreement diagnostic: 90 sentences, 30/class | Argmax 90/90; macro F1 1.000; majority baseline 33.3% | FinBERT used PhraseBank in training; exact membership unknown. Possible overlap: **not independent accuracy**. Small, high-agreement subset. |
| AI-authored development: 30 cases | Class 28/30 → 30/30; macro F1 0.943 → 1.000 | Rules were refined on this lane; AI draft labels await candidate review. Development agreement, not held-out accuracy. |
| Same development: assertion / impact / safety | Assertion 28/30 → 29/30; impact exact 28/30 → 30/30; impact MAE 0.333 → 0; unsafe assertions 1 → 0 | Zero observed errors on these constructed cases is not general language-safety proof. |
| Archived Fed full releases: 12/12 fetched | Class/subtype 11/12; assertion 9/12; impact exact 4/12; impact MAE 1.833 | One publisher, one true class, correlated templates. AI-drafted main-decision labels await review. Tested after development refinement, **not used to tune v2**. Historical, not live. |

Archive majority-class baseline is 100%; class agreement 91.7% does not beat always-Macro. Six-declared-class macro F1 is 0.1594: five absent classes have zero F1. Macro-only F1 is 0.9565. Neither establishes broad multiclass validation. There is no independently human-labelled broad-news benchmark yet.

## Refinements and retained errors

New analysis uses `phrase_rules_v2` / `rules2-finbert1`; impact remains `severity_v1`.

- D14 software configuration was wrongly asserted debt default, impact 10. A default now requires a directly attached financial obligation. Software/settings/preferences and verified-source automatic-execution regression tests pass.
- D01 worded rate amounts now support explicit quarter/half/three-quarter changes. A target level is still not a change amount.
- D04 policy holds can be informational Macro without an inferred shock.
- D09 remains speculative because a factual decision shares a sentence with an outlook. The conservative review/abstention is disclosed.

| Archive cases | Retained limitation |
| --- | --- |
| A01 | Main decision and dissenting alternative trigger conflicting directions: ambiguous, impact 1. |
| A02–A03 | Factual action plus forward-looking wording in one sentence becomes speculative. |
| A02–A08 | Main decision gives a new target range, not an explicit `by` amount. Disclosed unspecified baseline yields impact 6; absent previous-rate state is not invented. |
| A10 | Repeated main/dissenting clauses are flagged even when the main amount matches. |
| A02–A08, A10–A12 | Matched sentence says Committee rather than US/Fed. Sentence-local region matching requires review; publisher identity is not silently turned into exposure. |

Scope conclusion: an evidence-to-scenario demonstrator with analyst review, not general autonomous event understanding or risk prediction. Downgrade/payment phrases, acquisitions, negation, speculation, unseen entities and multilingual inputs need broader independently reviewed challenge data. Archive-driven refinement would require a new version and new untouched test sources; these 12 could no longer be called untouched tests.

Existing stored signals/run snapshots retain their original versions. Already processed identical input is deduplicated, not silently reanalyzed under v2. Do not reset a user's DB to hide historical output.

## CPU timing

Pinned real FinBERT, CPU, four Torch threads, serial records, warm-up excluded. Model load 10.56 s. Refined inference median / nearest-rank p95:

| Input | Median | p95 | Count |
| --- | --- | --- | --- |
| PhraseBank sentences | 83.41 ms | 120.60 ms | 90 |
| Development sentences | 55.95 ms | 68.87 ms | 30 |
| Archived full releases | 778.68 ms | 828.92 ms | 12 |

Rule medians: development 0.215 ms, archive 1.046 ms. Other local verification work was active. One machine/run, not throughput or SLA. Raw reports retain tokens/chunks/truncation/probabilities.

## Functional gates

Backend: **183 passed**, 98.88% statement coverage (1,415/1,431). Classification, evaluation helpers, sentiment, finance, store and stress have 100% statement coverage. This is code coverage, not model accuracy. Ruff lint/format pass.

Frontend: **30 passed**, 90.46% line / 90.25% statement / 83.67% branch / 88.80% function coverage. TypeScript/production build, Prettier and npm audit pass (zero reported vulnerabilities).

Real-backend/model browser rerun: **43 checks passed**, desktop/tablet/mobile, with no additional live-provider requests (`--skip-live`). Report: `runtime/phase4-browser-808d714e150340d3a8cb636ba2f3f8cd/report.json`. An earlier attempt failed to locate Chromium because the invocation used the wrong cache path; rerun used the existing pinned binary. No UI code was changed.

## Isolated clean installation: passed

`runtime/phase5-clean-3deb06a326fe4ce2ac34881b6a51f2aa/report.json`: all 15 steps passed, completed at 08:21:53 UTC. Python 3.12.14, Node 24.16.0, npm 11.13.0. Source manifest SHA-256: `d3bc54ed5c4b8c818862de772ee8ee556d9f353bc7664717a0d40a993d77d4a1`.

The export has its own venv (`include-system-site-packages = false`), npm install, frontend build and initially absent model cache. No original environment, node_modules, generated build or model weights were copied. Installer wheel/download caches and host Python/Node runtimes may be reused; this is not a new OS installation.

- Pinned Python dependencies installed; `pip check` passed. Fresh `npm ci`, build, 30 frontend tests and audit passed.
- Before model acquisition: 181 tests passed, 2 model tests deselected. Missing-model behavior is tested; no inference fallback.
- Fresh pinned weight acquisition and SHA-256 verification passed. A CDN read timeout was handled by the SDK's resume path; acquisition took 626.2 s. The existing project model cache was not counted as a fresh download.
- After acquisition: all 183 backend tests passed. Offline real-model replay/export/restart proof passed: three automatic simulations, one manual comparison, unchanged $100m base, duplicate idempotency and persisted snapshots. Outcomes: rate hike -$2,618,000; rate cut +$2,618,000; supply disruption -$2,944,125; manual credit -$1,308,000. These are fictional conditional results, not forecasts.
- Exported application/dependency hashes were reconciled with the current source. Subsequent handoff-document updates are not presented as byte-identical to the original export.

An earlier export (`runtime/phase5-clean-8c13714ebab24878b188ec28866e7c2d/report.json`) failed because the verifier omitted pytest's temporary-directory parent. The script was fixed and the complete process repeated in a new export. The failed report/logs are preserved.

This is a **local source export, not an actual GitHub clone**. The remote still has no refs and no files have been staged/committed/pushed. Publishing approval and a clone of the published commit remain submission gates. No live-provider calls were made by this offline clean gate.

## Reproduction and artifacts

```powershell
.\.venv\Scripts\python.exe scripts\prepare_evaluation.py --archive
.\.venv\Scripts\python.exe scripts\evaluate.py --label refined --include-archive
.\.venv\Scripts\python.exe scripts\clean_setup_verify.py
```

Preparation freezes ignored cache files once; existing freezes are reused. Selection uses no predictions. Repeating evaluation is a rerun, not new held-out evidence. Original v1 baseline is retained locally; reproducing it needs the original rule source, not merely a `--label baseline` argument against v2.

Ignored local reports:

- `runtime/phase5-evaluation-baseline-b800893a3ecf4ddf804a7d057a61943a.json`
- `runtime/phase5-evaluation-refined-b6ee71dd73b649008291366abbb829bd.json`
- `runtime/phase5-coverage-final.json`

Frozen file SHA-256:

- Development manifest: `2417956dbf67d01c2c7a1bddc06030b6fe979d007b39b39e8e74b50809d943ce`
- Archive labels/URLs: `2bcea7e4766287712226585cba4725b136bded3620be858c24e3d01df801a6d9`
- Selected PhraseBank cache: `bf17bfafa4db2dffe663f8df7bed3e9eb2e5ec43bac18ab0a8cd6af3d951b543`
- Extracted archive cache: `ed5ca0f9396432b1cc5e924bcc078a5df37ba90b5ea902c561458dba5a177906`

Reports include scoring-source hashes, model revision and weight checksum. Corpus text is excluded from public reports/repository. See [contract](evaluation-contract.md), [candidate review](evaluation-review.md), and [notices](../THIRD_PARTY_NOTICES.md). Candidate review, model/data-use notices, published-repository clone verification and submission packaging remain gates.
