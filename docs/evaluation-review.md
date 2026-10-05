# Candidate label review: pending

For Abhinav's walkthrough: mark each item **agree**, **disagree with reason**, or **unsure**. The examples and draft event labels were authored by AI before scoring; they are not human-reviewed ground truth. Do not approve a label just because the application produced it.

Impact uses our illustrative `1 + magnitude + scope` rubric, not actual economic severity or predicted loss. Speculation may retain a high number while execution is blocked.

| Case | Text / source | Draft expectation | Check |
| --- | --- | --- | --- |
| D01 | The FOMC lowered its policy rate by a quarter percentage point. | Macro / cut / asserted / 7 | 25 bp; magnitude 3 + scope 3 + 1. |
| D02 | The Federal Reserve increased its policy rate by 50 basis points. | Macro / hike / asserted / 8 | Sentiment sign must not decide scenario direction. |
| D04 | The Federal Reserve left its policy rate unchanged. | Macro / informational / unclear / 1 | No directional shock; `unclear` is our non-actionable schema status, not doubt that a hold occurred. |
| D06 | The Federal Reserve did not increase its policy rate by 50 basis points. | Macro / hike phrase / negated / 1 | Negated phrases must not execute hikes. |
| D07 | The Federal Reserve might lower its policy rate by 75 basis points. | Macro / cut / speculative / 9 | Not an accomplished decision. |
| D09 | The Federal Reserve raised its policy rate by 50 basis points, while analysts expect slower growth. | Macro / hike / asserted / 8 | Current rules conservatively flag the whole sentence speculative. Known mismatch. |
| D11 | Aster Energy defaulted on its bonds. | Credit / debt default / asserted / 7 | Fictional issuer match; 7 does not satisfy `> 7`. |
| D14 | Global Aster Energy defaulted on its software configuration, not a financial obligation. | Other/Unknown / unclear / 1 | Software defaults are not debt defaults. Fixed regression. |
| D18 | Global oil supply was disrupted by war. | Geopolitical / disruption / asserted / 9 | Global scope 4 and magnitude 4; fictional text. |
| D22 | Oil supply was disrupted by routine maintenance. | Supply phrase / asserted / 6, review required | No geopolitical cause; challenge the broad category convention if misleading. |
| D26 | Harbor Financial acquired Meridian Transport. | Merger/Acquisition / asserted / 5 | No supported automatic banking scenario. |
| A01 | [15 June 2022 decision](https://www.federalreserve.gov/newsevents/pressreleases/monetary20220615a.htm) | Main decision: hike, 75 bp, impact 9 | Dissenting alternative makes rules abstain. Amount labels require prior-rate context, not guessing from a new target. |
| A09 | [20 September 2023 decision](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230920a.htm) | Hold / informational / 1 | Historical publication is not fresh live evidence. |
| A10 | [18 September 2024 decision](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm) | Main decision: cut, 50 bp, impact 8 | Distinguish the main action from a dissenting alternative. |

Review log: **pending**. A post-prediction label change requires a new revision with a reason; retain original scores. No retrospective editing to improve scores.

Separate submission checks: college name/email, organizer cutoff/timezone, and EventLens naming-guideline acceptability. Registered personal email stays out of public files.
