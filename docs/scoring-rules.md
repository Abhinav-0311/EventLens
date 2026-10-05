# Event rules v2 and impact rubric v1

This is an inspectable heuristic baseline. It is not a trained severity predictor, calibrated confidence, or an estimate of realized portfolio loss. Broad financial language and unseen issuer names may be missed; those limitations need evaluation, not hidden fallback guesses.

## Supported phrases and magnitude

| Subtype | Baseline evidence | Magnitude points |
| --- | --- | --- |
| rate_hike / rate_cut | Policy context plus a direct raise/increase/hike or cut/lower/reduce of rates/target range | 0 bp: 0; positive below 25 bp: 2; 25-49 bp: 3; 50-74 bp: 4; 75+ bp: 5 |
| rate_hike / rate_cut, amount absent | Supported direction, no recognized change amount | 2 and magnitude_unspecified review flag |
| credit_deterioration | Default on debt | 5 |
| credit_deterioration | Downgrade or missed debt/bond payment | 3 |
| supply_disruption | Explicit supply/shipping/oil/energy disruption plus war/conflict/sanction/blockade/attack | 4 |
| supply_disruption, cause unclear | Disruption phrase without explicit geopolitical cause | 3 and geopolitical_cause_unclear review flag |
| acquisition | Acquire/merge/acquisition/merger phrase | 3; no supported automatic banking scenario |
| product_launch | Launch of product/service/platform | 1; no supported automatic banking scenario |
| macro_announcement / geopolitical_event | Broad inflation/GDP/unemployment/CPI or war/conflict/sanctions/attack phrase only | 0; unclear assertion, no inferred shock direction |
| unknown / ambiguous | No supported event, or conflicting types/directions | 0 |

Amounts use an explicit `by ... basis points` or `by ... percentage point` construction, including simple fractions and explicit quarter/half/three-quarter wording. A target rate level is not treated as a change amount. This grammar does not cover every valid policy phrasing. Extremely large amounts are not a validated economic case; the rubric saturates at its top bucket. A debt-default match requires a directly attached financial obligation; software configuration defaults are not credit events. Policy context without a supported directional shock is informational Macro.

## Scope and execution boundaries

Scope points: explicitly global/worldwide/cross-border = 4; policy context or explicit national/systemic scope = 3; otherwise a matched issuer = 1, explicit sector/supply/shipping scope = 2, or unspecified = 0. Global context is not inferred from online publication. A recognized negation sets both magnitude and scope to zero, giving impact 1.

Issuer recognition is an explicit fictional watchlist: Aster Energy, Meridian Transport, Forge Manufacturing, Cedar Technology, and Harbor Financial. Their sector labels support the synthetic portfolio. This is not general named-entity recognition. Unresolved credit exposure and non-US policy decisions require review.

Impact = 1 + magnitude + scope. For example, a recognized 50 bp Federal Reserve decision has impact 8. A single fictional issuer default scores 7 and does not cross the strict `> 7` automatic threshold. An explicit recorded manual comparison can select another impact setting; it does not change the original signal or turn the event into an automatic verified result.

Negation/speculation and historical-context checks are local phrase heuristics. Conflicting event types/directions produce ambiguous output. Repeated current clauses are flagged. Exact evidence spans are offsets into stored text. [Phase 5 evaluation](phase5-verification.md) records conservative mixed-clause/region misses and limited impact agreement on archived releases; it does not establish general language accuracy. Existing snapshots keep their original rule versions.

Sentiment is independent. Severity on a speculative event can remain high while execution is blocked. Source reliability, freshness, region/exposure applicability, and portfolio availability are separate review reasons. API-supplied text never becomes verified merely because it mentions an official institution.

Live event age uses the configurable 72-hour limit. Synthetic replay uses its explicit simulation clock and retains synthetic provenance. Current event eligibility and exposure matching are implemented in Phase 3; completed-run snapshots retain the original signal and eligibility. See [stress-model notes](stress-model.md) for live versus simulation gates, batch completion, manual comparisons, units, arithmetic and limitations.
