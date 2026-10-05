# Submission answer template

Draft only. **Do not submit with the video placeholder, unresolved naming/source-use questions or an unreviewed claim.** Update any links after a repository rename. Replace the video field with the actual unlisted YouTube URL after playback/access checks.

---

Project: EventLens

Candidate: Abhinav Jain
College: Vellore Institute of Technology, Bhopal
College email: abhinav.23bcg10130@vitbhopal.ac.in

Selected module: Module B, Strategic Portfolio Stress Testing, with the required NLP risk engine.

Public repository: https://github.com/Abhinav-0311/EventLens
Presentation: https://github.com/Abhinav-0311/EventLens/blob/main/docs/presentation.pdf
Architecture: https://github.com/Abhinav-0311/EventLens/blob/main/docs/architecture.png
Demo video: REPLACE_WITH_VERIFIED_UNLISTED_YOUTUBE_URL

EventLens connects financial text to inspectable event signals and conditional stress results for a fictional wholesale-banking portfolio. Federal Reserve release/RSS and official Bluesky adapters provide two channels from the same publisher. Local pretrained FinBERT supplies a signed sentiment score; separate phrase rules classify events and apply an illustrative impact rubric. Evidence, eligibility reasons and versioned calculation snapshots are retained in SQLite and exposed through FastAPI, a React dashboard and CSV/JSON exports.

The synthetic portfolio contains 10 loans, 6 bonds and 4 swaps, with $100m fair value and separately reported $194.4m principal/notional. The example policy-hike scenario applies a stated 100 bp stress: L01 loses $228,000 and total portfolio P&L is -$2.618m, giving $97.382m stressed value. These are what-if calculations, not forecasts of actual losses. Supported eligible signals can produce labelled simulations; manual comparisons require a recorded reason and preserve the original signal.

Engineering evidence records 183 backend tests, 30 frontend tests and 43 browser checks, plus a separate published-clone verification. These counts do not measure language-model accuracy. The small, one-publisher archive agreed on exact impact in only 4/12 cases; development cases were tuned on, and a PhraseBank diagnostic may overlap model training. Candidate label-review status is recorded separately. Independent broad-news accuracy and public deployment are not established.

The repository includes dependencies, setup/run instructions, synthetic CSV/JSON inputs, a seven-slide PDF and an MIT license for project code. Third-party notices are separate; model weights and diagnostic corpus text are not redistributed. AI assistance was used in development and draft evaluation labels. The simplified stress model excludes several real-bank risk factors and is intended for explained analyst review, not production autonomous decisions.

---

The portal may have separate URL and attachment fields. Use the verified links in the matching fields and attach the requested PDF if applicable. Candidate review, recording, permission checks and the final submit action are not performed by this template.
