# Phase 7: presentation and publication checks

Prepared on 5 October 2026. This phase packages verified work; it does not approve candidate understanding or submit the assessment.

## Presentation and recording preparation

- Seven-page 16:9 PDF at presentation.pdf; exact candidate/college identity, ranges, financial amounts and evaluation counts checked by PDF text extraction.
- Rendered all seven pages and inspected the contact sheet. Full-size decision/evaluation slides were checked after correcting a wrapped impact formula. No clipped content observed; key figures and limitations are readable.
- Architecture image at architecture.png preserves the distinct FinBERT sentiment and heuristic event/impact branches, evidence store, eligibility checks, stress calculations and saved-run handoff.
- Native Gamma and Canva working decks were generated. Their diagrams/text needed review, so neither generated draft was used unchanged as the submission PDF. The corrected seven-page PDF was subsequently imported into a separate Canva review deck; extracted text retained 4/12, 183, $97.382m, $228,000, $194.4m and the pending-label qualifier. Working links remain in the chat; private deck URLs are not required for accessing the public PDF.
- Humanizer light-mode gate passed for presentation-content.md, recording-guide.md and the final extracted PDF text. No measurements or candidate approvals were invented. See presentation-review.md.
- Recording guide includes a 6–7 minute narrative, labelled synthetic demonstration, manual-comparison boundary, live-provider failure handling and a 4:30 jury sequence. No video has been recorded or uploaded by this preparation.

## Pre-publication rerun

- Backend: 183 tests passed in 60.20 seconds, including the cached real model; live-provider tests excluded. Ruff lint and formatting passed (33 files).
- Frontend: 30 tests passed; TypeScript/production build and Prettier checks passed.
- Prior browser evidence remains 43 passing checks from Phase 5; no new browser/live-provider run is implied here.
- All publishable text scanned for the registered personal email, assessment gateway/access-code text, private-key markers and common model/GitHub token patterns: no matches. PDF extracted text also passed the privacy scan. This is a bounded check, not a universal secret-detection guarantee.
- Git author will use the candidate's college email, not the registered personal email. Model weights, corpus cache, databases, runtime reports, node_modules, virtual environments and builds remain ignored.

## Publication and published-clone gate

Candidate authorized commit and push after checks. Initial remote inspection showed no refs; local branch main had no commits. The public repository was populated with root commit `4cb975a` on main (90 files). The author uses the college email. A normal non-force push succeeded, and an unauthenticated repository-page request returned HTTP 200. The GitHub metadata API was rate-limited, so no visibility claim relies on that API response.

Anonymous Git cloning succeeded with credential helpers and prompts disabled. The first verifier attempt stopped on a raw CSV byte comparison: Windows Git converted LF to CRLF. The verifier now compares text after line-ending normalization while requiring exact PDF/PNG bytes; no application fix was needed. The failed report remains at `runtime/published-clone-ded3517543c046e9a05dca42592e20ab/report.json`.

Actual published-clone verification **passed all 11 steps** for application commit `4cb975a8167fea6462671fd258cdaa18abf4bcf6`. Local report: `runtime/published-clone-c5341a31cd4c4411a0a040bbe33bd8d2/report.json`; sanitized public results: [published-clone-results.json](published-clone-results.json).

- A new Python venv has `include-system-site-packages = false`; pinned Python dependencies and pip check passed. Fresh node_modules, npm ci, production build and all 30 frontend tests passed.
- All 183 backend tests passed in the cloned project. Real-model replay/export/restart passed, preserving three automatic simulations plus the explicitly reasoned manual comparison, original portfolio base and saved snapshots.
- Loopback HTTP/dashboard/OpenAPI, write authorization, same-origin writes, stress idempotency and exports passed. HTTP stress P&L was −$2,618,000. The verifier stopped its owned server; it did not use or reset the candidate's original database.
- The model cache was copied locally and its 437,992,753-byte weight checked against SHA-256 `e15a7b5738df7f17553399b6d94c6e2ff69c89245d066e8e5d183f5803a554e3`. This is disclosed cache reuse, not another fresh-weight download. Phase 5 independently verified acquisition into an absent cache.
- PDF/PNG bytes match the published artifacts; text inputs/lockfile match after Git newline normalization. Generated files remain ignored and cloned Git status is clean.

Later follow-up commits change only documentation to record this result. This gate did not rerun the full browser suite or live providers; the 43 browser checks remain separately documented Phase 5 evidence.

## Outstanding submission gates

Candidate walkthrough/label review; model/data-use notices; organizer naming/cutoff clarification; recorded video and public access checks; explicit assessment submission. These remain unchecked in submission-checklist.md. Preparing or publishing a repository does not establish final submission readiness or broad independent NLP accuracy.
