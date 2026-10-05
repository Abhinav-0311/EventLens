# EventLens presentation source

Seven-slide review draft. Claims are grounded in docs/phase5-verification.md and docs/stress-model.md. Native Gamma/Canva layouts must preserve the qualifications below. Candidate label approval and final submission are not implied.

# EventLens

Financial events → explained portfolio stress
Module B: Strategic Portfolio Stress Testing
Abhinav Jain | Vellore Institute of Technology, Bhopal
Code to Connect 2026 | S&P Global × CRISIL × Naukri Campus

---

# From a financial event to an analyst decision

Question: which positions are exposed, and what changes under a stated stress?
Inputs: Federal Reserve RSS/full releases and official Bluesky posts.
Two channels share one publisher; they are not independent corroboration.
Output: source evidence, structured risk signals and position-level what-if results.

---

# One traceable pipeline

RSS / Bluesky / labelled synthetic replay → normalise and retain evidence
Two analysis branches: local pretrained FinBERT sentiment; phrase_rules_v2 event classification + severity_v1 impact
SQLite signals → evidence/exposure eligibility → versioned scenarios + Decimal calculations → immutable run snapshots
FastAPI + CSV/JSON exports → React Events / Portfolio / Runs dashboard
FinBERT supplies sentiment only. Event and impact rules are project-authored heuristics.

---

# A high score still needs evidence checks

Synthetic demo input: “The Federal Reserve increased its policy rate by 50 basis points.”
Impact = 1 + magnitude 4 + policy scope 3 = 8; automatic threshold is strictly > 7.
Execution also requires an asserted supported event, trusted eligible evidence, fresh publication, clear exposure and no blocking flags.
Labelled replay uses a simulation clock; user-pasted text stays unverified. Negation, speculation, conflicts and failed refresh batches block automation.
Sentiment sign does not decide the shock direction.

---

# An explicit stress, explained position by position

Fictional portfolio: 20 positions; USD 100m fair value; USD 194.4m principal/notional reported separately.
At impact 8, the illustrative tightening scenario applies +100 bp. The 50 bp announcement and 100 bp stress are different quantities.
Loan L01: −$6m × 3.8 × 100/10,000 = −$228,000; stressed value $5.772m.
Portfolio P&L: loans −$1.074m + bonds −$1.564m + swaps +$0.020m = −$2.618m; stressed fair value $97.382m.
Cash uses duration; swaps use signed USD/bp. Every scenario starts from the original base. Conditional what-if, not a loss forecast.

---

# Engineering proof and language limits

Software: 183 backend tests, 30 frontend tests and 43 real-backend/model browser checks passed. Browser rerun did not recheck live providers.
Isolated local source export: all 15 clean-install verification steps passed; not yet a published GitHub clone.
Untuned archive: 12 historical Fed releases; class/subtype 11/12, assertion 9/12, exact impact 4/12. One class/publisher; AI-drafted labels await candidate review.
Development: 30/30 class agreement after rule refinement; tuning evidence, not held-out accuracy. PhraseBank diagnostic may overlap FinBERT training and is not independent accuracy.
Main weaknesses: mixed clauses, dissenting alternatives, target levels without prior-rate state and sentence-local region matching.

---

# Scope, handoff and next iteration

Delivered locally: source, MIT code license, Quickstart, API, dashboard, synthetic inputs, versioned scenarios, evidence exports and saved stress snapshots.
Before submission: candidate walkthrough/label review, model/data-use notices, repo-naming clarification, published-clone check and a 5–10 minute recording.
Next validation: independent publishers, human-reviewed unseen events and explicit policy-state parsing; a new rule version needs new untouched test sources.
Excluded: convexity, nonparallel curves, liquidity, FX, recovery/default cash flows and swap CVA. No production risk or investment-performance claim.
Project: github.com/Abhinav-0311/EventLens | AI-assisted development. Sources/attribution: ProsusAI/finbert; Federal Reserve; project-authored synthetic portfolio.
