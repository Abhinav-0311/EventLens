# EventLens recording and live-demo guide

Review draft for Abhinav. Explain this in your own words after the walkthrough; do not claim an understanding or label review that has not happened. Recorded submission: 5–10 minutes, target 6–7. Live jury demonstration: at most 5 minutes. Rehearse with a timer; timings below include dashboard navigation.

## Before recording

- Read the stress-model and scoring-rules notes, then complete the candidate review in evaluation-review.md. Preserve disagreements and original scores.
- Use a separate demo database. Do not delete or reset the existing runtime database. Keep the server loopback-only and use a free port; port 8000 may belong to another project.
- Build the frontend, cache the pinned model and start the server before recording. Test the microphone and screen readability. Hide email tabs, credentials, notifications, private assessment URLs and unrelated windows.
- Show synthetic labels clearly. Prepare sample events using the dashboard; do not present cached replay as live news. Refresh live sources only deliberately; if a provider fails, show the degraded state honestly.
- Export a sample signal CSV and stress-result CSV beforehand. Choose the policy-hike run whose displayed P&L is −$2,618,000. Its portfolio/scenario versions must match the guide.
- Use a 16:9 screen recording. Keep the cursor visible, avoid fast scrolling, and ensure source spans and monetary values are readable at normal playback size.

Example isolated demo start, from the repository root after Quickstart setup:

```powershell
$env:EVENTLENS_DATABASE = Join-Path (Get-Location) ('runtime/recording-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
.\.venv\Scripts\python.exe -m uvicorn eventlens.api:app --host 127.0.0.1 --port 8019 --workers 1
```

First check that 8019 is free, or choose another free port. The new empty database is intentional and does not overwrite an existing one. End the owned server with Ctrl+C after recording. The environment variable applies to this shell, not a public deployment.

## Recorded narrative: approximately 6 minutes 40 seconds

### 0:00–0:35 | Slide 1: introduction

“I’m Abhinav Jain from Vellore Institute of Technology, Bhopal. EventLens is my AI-assisted Code to Connect project. I selected Module B, Strategic Portfolio Stress Testing, alongside the required NLP risk engine. The demonstration traces financial text to an explained what-if result for a fictional banking portfolio.”

### 0:35–1:05 | Slide 2: analyst question

“A risk analyst needs to know what happened, which evidence supports that interpretation, which positions are exposed and what changes under a stated stress. EventLens keeps those steps connected. Its live adapters accept Federal Reserve releases and official Bluesky posts. These are two channels from one publisher, so I do not count them as independent corroboration.”

### 1:05–1:50 | Slide 3: architecture

“Both source adapters enter the same evidence pipeline. The pretrained FinBERT model runs locally and supplies sentiment. The signed score is positive probability minus negative probability. Event classification and impact use separate, inspectable phrase rules and an illustrative rubric. I did not train an event-classification model. SQLite retains evidence and signals. Eligibility checks sit between an event and the stress calculator. Completed runs save their input versions and position results. FastAPI supplies the React dashboard and CSV or JSON exports.”

### 1:50–2:55 | Dashboard Events + slide 4: evidence and gates

Action: load sample events, select the synthetic policy-hike event, and inspect its evidence, impact, eligibility and saved run.

“This input says the Federal Reserve increased its policy rate by 50 basis points. It is labelled fictional replay. The impact score is eight: one plus four magnitude points plus three policy-scope points. The threshold is strictly greater than seven, but the score alone does not permit execution. An asserted supported event, acceptable evidence, clear exposure and no blocking flags are also required. Live evidence has a freshness check; replay uses an explicit simulation clock. User-pasted text remains unverified. Negation, speculation and conflicting directions block automatic execution. Sentiment sign does not choose tightening or easing.”

Action: show a blocked or review-only event and its reasons. Point to the default event's original impact 7; do not create an override silently.

### 2:55–4:20 | Portfolio and Runs + slide 5: explain the mathematics

“The portfolio contains ten loans, six bonds and four swaps. Its fair value is 100 million dollars. Principal and notional total 194.4 million and are reported separately; adding them to fair value would be wrong. At impact eight, the tightening profile applies an illustrative 100 basis-point rate shock. That stress assumption is separate from the 50 basis-point announcement.

For loan L01, the first-order change is minus six million times a rate duration of 3.8 times 100 divided by 10,000. That is a loss of 228,000 dollars, giving a stressed value of 5.772 million. Swaps use signed dollar sensitivity per basis point, not this cash-duration formula. Portfolio losses of 1.074 million on loans and 1.564 million on bonds are partly offset by a 20,000-dollar swap gain. Net P&L is minus 2.618 million, leaving 97.382 million.

These are conditional synthetic values, not forecasts. Each scenario starts from the original portfolio; results do not compound. The saved run contains its evidence, scenario assumptions, versions and position breakdown.”

Action: open the hike run, find L01, then show/download its CSV. Briefly show the manual-comparison reason field and explain that an impact override leaves the original signal unchanged. If showing credit, use its explicit issuer match; the documented comparison affects L01, L02 and B03.

### 4:20–5:30 | Slide 6: proof and errors

“The engineering checks passed 183 backend tests, 30 frontend tests and 43 browser checks against the real backend and cached model. A separate local source export passed 15 clean-install steps. Those counts prove tested software behaviour; they are not model accuracy.

The harder language test used twelve archived Federal Reserve releases that were not used to tune this rule version. Class and subtype agreed on eleven, assertion on nine, and exact impact on only four. All releases belong to one class and publisher, and the draft labels still need my review. Mixed decision and outlook clauses, dissenting alternatives and a new target rate without prior-rate state are important failure cases. Development examples were used for refinement. The PhraseBank sentiment diagnostic may overlap FinBERT training, so neither is an independent accuracy claim.”

### 5:30–6:40 | Slide 7: boundaries and handoff

“The current system demonstrates traceable analyst review and explicit stress calculations. Its duration approach excludes convexity, nonparallel yield curves, liquidity, FX, recovery cash flows and derivative counterparty adjustments. It is not a complete bank balance-sheet model or a production autonomous decision system.

The repository includes source, setup instructions, fictional input data, scenario definitions, code licensing and verification notes. Model weights are downloaded separately, and third-party notices remain distinct from the code license. AI assistance was used in development and draft evaluation labels. The next validation step is human-reviewed unseen events from independent publishers and improved policy-state parsing. Any archive-driven rule change needs a new version and new untouched test data. Before final submission I will verify the published repository, review the labels and notices, resolve the naming requirement and check the video link.”

Use the final sentence's future tense only while those tasks remain pending. Once completed, refer to the actual commit and reviewed artifacts instead of claiming an unperformed step.

## Live jury version: target 4 minutes 30 seconds

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:25 | Title + analyst question | Module B, fictional portfolio, evidence-to-stress purpose. |
| 0:25–1:20 | Events: hike, evidence, eligibility | Sentiment versus subtype; score 8 and evidence gates. |
| 1:20–2:30 | Portfolio + saved hike run | L01 hand-check, portfolio total, fair value versus notional. |
| 2:30–3:10 | Blocked event + comparison controls | Strict >7, synthetic provenance, reasoned manual override. |
| 3:10–4:05 | Evaluation slide | Passing engineering checks; archive impact 4/12 and retained errors. |
| 4:05–4:30 | Handoff slide | Explicit limitations, repository and next validation. |

If a live source is unavailable, show the error and saved evidence, then continue with explicitly labelled replay. If the model is unavailable, show the unavailable state and explain the separately saved demonstration; do not present a recording as live inference.

## Questions to answer before recording

1. Why can a rate hike have positive sentiment while the scenario direction is tightening?
2. Why does impact 8 still sometimes fail automatic eligibility?
3. Why is the 100 bp stress different from a 50 bp news announcement?
4. Why do swaps use signed USD/bp and not notional as fair value?
5. Why does the impact-7 issuer default need a manual comparison to demonstrate an impact-8 shock?
6. Which archival errors remain, and why cannot the development score be called held-out accuracy?
7. What is saved so that a later rule version does not silently rewrite an old result?

## Final video checks

Confirm 5–10 minutes, audible speech, readable figures, visible synthetic labels, no secrets, correct candidate/college identity and correct repository link. Open the uploaded link while signed out to test jury access. Upload and assessment submission are candidate actions; preparation does not submit anything.
