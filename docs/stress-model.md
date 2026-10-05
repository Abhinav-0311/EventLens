# Portfolio stress model

EventLens estimates conditional fair-value changes for a fictional asset portfolio. It does not forecast losses, measure regulatory capital, price a complete banking balance sheet, or provide investment advice.

## Data and units

The initial `usd-demo-v1` portfolio has 10 corporate loans (five fixed, five floating), six bonds (two government, four corporate), and four simple interest-rate swaps (two payer-fixed, two receiver-fixed). All names, valuations, positions and sensitivities are fictional. Inputs are in [portfolio.csv](../data/portfolio.csv), with assumptions in [portfolio.json](../data/portfolio.json).

Base fair value is **USD 100,000,000.00**. Total principal/notional is **USD 194,400,000.00** and is reported separately, never added to portfolio fair value. Derivative fair values can be negative; the four swaps net to zero base fair value but have nonzero risk sensitivities.

Money, sensitivities and shocks use Python `Decimal`, SQLite JSON decimal strings, and decimal strings in API responses. Durations are synthetic modified-duration sensitivities in years. A basis point is 0.0001 in decimal rate units: divide bp by 10,000, not 100.

## Arithmetic

For each matched cash position:

```text
rate P&L   = -base fair value × rate duration × rate shock bp / 10,000
spread P&L = -base fair value × spread duration × spread shock bp / 10,000
```

For a matched swap:

```text
rate P&L = signed USD P&L per bp × rate shock bp
```

Payer-fixed sensitivities are positive and receiver-fixed sensitivities negative for an upward parallel rate shock, under this simplified convention. Swap fair-value sign does not determine sensitivity sign. Swap notional is not used as its fair value, and cash duration formulas are not applied to swaps.

Each position's rate and spread components are independently rounded to cents using half-even rounding. Position P&L is the sum of those displayed components. Stressed fair value is base fair value plus position P&L. Portfolio totals are sums of the rounded position results; reconciliation is required before saving. This makes the displayed/exported components add up exactly. Very small inputs can differ by a cent from rounding only a final unrounded aggregate.

The [BIS application guidance, SRP98.44 footnote 9](https://www.bis.org/committees/bcbs/basel-framework/standard/srp/98/inforce/2026-01-01/published/2024-07-16) describes modified duration as a marginal, parallel-yield-curve approximation and notes its limitations. EventLens uses that first-order idea for teaching, not the BIS standardised measurement framework. Floating loans have shorter rate-reset sensitivities while retaining corporate spread sensitivities.

## Scenario definitions

Profiles are versioned in [scenarios.json](../data/scenarios.json). Reference shocks are analyst-defined examples at impact 8, not observed policy changes or calibrated market reactions.

| Profile | Reference rate / spread shock | Exposure matching |
| --- | --- | --- |
| Monetary tightening | +100 bp / 0 | USD rate-sensitive positions, with US policy scope identified |
| Monetary easing | -100 bp / 0 | Same USD rate matching |
| Credit deterioration | 0 / +200 bp | Identified corporate issuers; explicit sector only if no issuer is identified |
| Supply disruption | +50 bp / +200 bp | USD rate exposures; spread only on explicitly affected energy/transport cash positions |

Applied shocks equal reference shocks × `min(impact / 8, 1.25)`. Sentiment sign is not used. A 50 bp policy announcement can score 8 and select the illustrative 100 bp stress; these are deliberately different quantities.

Issuer identification takes precedence over sector matching: a default by Aster Energy does not shock every energy company. Unrelated positions and sovereign bonds are excluded from corporate spread shocks. Swaps have no modeled credit/CVA shock. An unresolved supply sector is review-only even though a rate shock could otherwise be computed. Other geopolitical subtypes do not acquire this scenario automatically.

No additional recovery/default-loss overlay is added to spread losses. Excluded effects include convexity, nonparallel curves, basis risk, FX, optionality, liquidity, recovery/default cash flows, funding costs and net interest income. Results represent changes in asset fair value, not accounting income or a complete bank's economic value of equity.

## Eligibility versus execution

The API returns freshly evaluated `eligibility` on each event, separate from immutable signal-time `review_reasons` and `stress_readiness`. Current eligibility uses the current portfolio, current evidence group and clock. It is not a claim that a run is already queued or completed; inspect the operation and `stress_run_ids` for execution status.

Automatic live execution requires impact **strictly greater than 7**, a supported asserted subtype, English eligible verified-publisher evidence, clear exposure, publication within the configured 72 hours, and no blocking source/classification/truncation/ambiguity/conflict flags. Different directions or asserted-versus-negated evidence in the same event group block a new automatic run. Two channels from the same publisher remain one publisher, not independent confirmation.

The worker evaluates automatic runs only after the entire refresh/replay batch has been processed. Failed records, failed sources or cooldown-skipped sources suppress automatic execution for that batch. Operation counts and source health expose this; existing successful runs remain historical results, not rescinded forecasts. Refresh/replay are explicit actions, not a background polling scheduler.

The allowlisted fictional replay uses its explicit simulation clock and separately permits `automatic_simulation` under the same impact/assertion/exposure/conflict rules. Sources still have `verified_publisher=false` and `provenance_mode=synthetic`. This is functional proof, not live-source or model-accuracy evidence. Supplied text cannot assign either trusted live or synthetic provenance.

## Manual comparisons and history

`POST /api/stress-runs` creates only `manual_comparison` runs. It always requires an explicit override reason and an idempotency key; impact override is optional. It can compare the opposite policy direction, but cannot invent an issuer/sector or cross into a different event family. Unverified or stale inputs may support a clearly labelled what-if comparison; their original eligibility reasons remain saved.

An idempotency-key retry returns the original result, even after restart. Reusing that key for different request contents returns 409. A new comparison key deliberately creates a separate run. Automatic uniqueness includes event, primary signal, portfolio/scenario versions and hashes, and calculation version. Changed evidence can produce a new versioned reconsideration; it never compounds an earlier result.

Every run starts from the same original portfolio snapshot. It stores all input positions, scenario/reference shocks, actual shocks, signal and grouped source evidence, original eligibility, calculation version, per-position results and totals. Existing portfolio/scenario versions cannot be silently reused with changed contents.

Calculations are bounded synchronous operations: requested/running are transient in-process states, and only fully validated completed runs are transactionally persisted. No partially saved or successful-looking failed run is emitted. The run and retry-key binding are saved in one SQLite transaction; failure rolls both back and leaves the base unchanged. Ingestion operations retain their separate queued/running/completed/failed/interrupted lifecycle. A process restart during automatic work requires an explicit retry; run keys prevent repeating already completed work. Run one Uvicorn process.

## Hand-checks

These examples are synthetic conditional results:

| Example | Applied shocks | P&L / stressed fair value |
| --- | --- | --- |
| Policy hike, impact 8 | +100 bp rate, 0 spread | -$2,618,000.00 / $97,382,000.00 |
| Policy cut, impact 8 | -100 bp rate, 0 spread | +$2,618,000.00 / $102,618,000.00 |
| Global oil supply disruption, impact 9 | +56.25 bp rate, +225 bp matched energy spread | -$2,944,125.00 / $97,055,875.00 |
| Manual Aster Energy credit comparison, impact 8 | 0 rate, +200 bp issuer spread | -$1,308,000.00 / $98,692,000.00 |

The original issuer-default signal remains impact **7** and does not automatically run. The manual credit comparison affects exactly L01, L02 and B03. At zero shocks, every position and the portfolio remain unchanged. Repeating a run or comparing another scenario always uses the $100 million base, never a preceding stressed total.
