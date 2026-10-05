# Evaluation contract, frozen v1

Created before Phase 5 prediction runs. This is an academic demonstrator, not a production promotion decision.

Goal: expose errors that could mislead an analyst about sentiment, event direction or automatic stress. No model training, threshold search or claimed calibrated confidence is planned.

Decision owner: candidate/analyst. False asserted high-impact events are more harmful than a disclosed review/abstention. Model unavailability, provenance spoofing and an automatic run on speculative/negated/unsupported evidence are unacceptable. Conservative abstention is acceptable when its reason is visible.

## Data lanes and leakage

1. Financial PhraseBank, all-annotator-agreement subset: immutable upstream revision `8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964`. Select 30 examples per sentiment class by smallest SHA-256 of the sentence (deduplicated); no choice based on predictions. Upstream human labels remain unchanged. FinBERT was fine-tuned using PhraseBank, and exact membership of its training split is unavailable. Report this as a potentially overlapping diagnostic, never an independent held-out accuracy claim. Raw data stays in ignored `.cache`; no dataset sentences are packaged under the code's MIT license.
2. Project-authored development challenge cases: freeze text, class/subtype, assertion and rubric expectations before inference. They deliberately test grammar and safety boundaries; they are AI-authored/provisionally AI-labelled, not real news or independent human labels. Any refinement may use this lane, with baseline and revised results retained. Metrics mean agreement with these draft labels, not real-world accuracy.
3. Archived Federal Reserve releases: fixed source dates/URLs and independently drafted expectations for the main policy decision. Freeze extracted text/hashes before classification. This is a narrow, template-correlated single-publisher policy slice. Do not tune rules on its output; record errors and abstentions. Historical publication dates must not be relabelled recent live evidence. Candidate label review remains pending and must be disclosed.

No random split is used to hide duplicate stories. The development and archive lanes are separate. Changing a draft label after seeing output requires a new label revision and explicit rationale; old results are retained. Repeated evaluation after tuning is not a new held-out result.

## Metrics declared in advance

- Sentiment: argmax of all three model probabilities; accuracy, macro F1, class support/confusion matrix, majority-class baseline. The dashboard's signed score/neutral display band is a separate quantity, not a calibrated confidence or the benchmark classifier.
- Events: class accuracy/macro F1, subtype and assertion agreement, impact exact agreement and mean absolute error; include case counts and every mismatch. Impact labels evaluate the project's declared illustrative rubric, not observed economic loss.
- Safety: identify negated/speculative/unsupported or non-debt development cases misread as asserted supported events; inspect high-impact errors. No accuracy target is invented to make the model appear production-ready.
- Runtime: model load time, per-record warm inference/classification wall time, median and nearest-rank p95, token/chunk counts. Small serial CPU measurements are not a traffic/load/SLA benchmark.
- Reproducibility: hashes of datasets, labels, relevant scoring source and model revision; Python/Node/package versions; zero hidden notebook state. Saved result snapshots/Decimal reconciliation remain separate tested functional gates.

## Clean setup boundary

The supplied GitHub repository currently has no commits. Verify a fresh local source export with its own environment/build/model cache first; do not describe that as a successful public GitHub clone. Root Git state must not be committed or pushed without publishing approval. Record separately any clean dependency install, one-time model acquisition, cached offline startup and browser proof. A reused model cache is not a fresh model download.

## Evidence and use restrictions

PhraseBank's dataset card declares CC BY-NC-SA 3.0; its annotators label financial sentiment from an investor perspective. Commercial competition/redistribution rights are not assumed. Use it only as a local diagnostic here and retain source/license notes for submission review. Do not copy corpus text into public reports. The model card and upstream implementation identify PhraseBank fine-tuning, which is why overlap is disclosed.

Sources: [dataset card](https://huggingface.co/datasets/takala/financial_phrasebank), [FinBERT model card](https://huggingface.co/ProsusAI/finbert), [upstream implementation](https://github.com/ProsusAI/finBERT), [Federal Reserve text-use policy](https://www.federalreserve.gov/disclaimer.htm).
