# Presentation review

Prepared on 5 October 2026. The submission artifact is presentation.pdf: seven 16:9 pages with an explicit architecture flow, worked stress calculation, evaluation limits and attribution. Native Gamma and Canva decks are working drafts; their private links are retained in the chat rather than public repository files.

## Design direction and self-review

The audience is a financial-risk hackathon jury. The main question is which positions are exposed and how an explicit shock changes value. An editorial serif heading and readable sans-serif body distinguish the deck from the dashboard while retaining warm-white surfaces, graphite text and one muted-green accent. Figures and exposure assumptions take priority over imagery or decoration.

The first generated Gamma diagram reduced the architecture to an incorrect generic shape and omitted essential stages. Canva's extracted text did not expose several requested evaluation metrics and added a generic reliability assertion. Neither draft was promoted to the canonical PDF. The controlled layout separates pretrained sentiment from event/impact heuristics and connects eligibility, calculation and saved results in their actual order. The evaluation slide uses two short columns with the 4/12 impact result visible, instead of a dense table and bullet list. A wrapped impact formula was shortened without changing its arithmetic.

Visual inspection uses a rendered seven-slide contact sheet plus full-size slides. It checks legibility, hierarchy, mathematical signs, architecture direction and absence of clipped content. Automated PDF checks enforce seven pages, 16:9 aspect ratio, required names/figures and absence of registered personal email/assessment tokens. Font subsets are embedded in the PDF; no model weights or input corpus are embedded.

## Humanizer light-mode review

Draft rewrite: presentation-content.md records the evidence-grounded first copy. Final rewrite: presentation.pdf contains the final, condensed slide wording. Spoken narration is provided in the chat.

What read as generated: Gamma's repeated “Two channels share one publisher” statement added no information; its diagram was generic rather than project-specific. Canva added “confirm robustness” without a bounded claim. Native prose also introduced em-dash signposts. These did not survive in the canonical PDF.

Anything fabricated? No invented measurements, sources, interviews, model training, independent accuracy or candidate approval were added. Numeric ranges and pipeline details are taken from README and stress/scoring notes; amounts and evaluation counts match phase5-verification.md and stress-model.md. Native additions were removed or replaced by the narrower source claim.

What was cut: unsupported reliability phrasing (C2), em-dash wording (C5), repeated connective explanation (C8) and redundant content. Light mode preserves necessary qualifications and does not remove hedges to imply certainty. The mechanical light-mode gate passed for the draft slide copy and recording guide; the final PDF text is checked separately before publication.

What's left to watch: “untuned” refers only to these archive cases not being used to tune this rule version; it does not mean human-validated ground truth. “Passed” describes named local engineering checks, not universal correctness or model accuracy. The candidate must still review draft labels and understand the arithmetic.

## Remaining human gates

Candidate walkthrough/labels, model/data-use notices, naming and cutoff clarification, recording/upload and assessment submission remain pending. Publication or preparing a deck does not complete those gates.

## Handoff wording review

Supplementary answer/email prose passed Humanizer light-mode checks during preparation. Those documents were removed at the candidate's request; the following notes describe that historical review, not additional submission artifacts.

What makes the draft read as generated? No filler cluster required a rewrite. The answer's engineering-count paragraph could sound like an accuracy assertion without its explicit qualification; the phrase "two channels" could imply independent sources without "same publisher". Those qualifications are retained. The email questions are concrete requests, not a claim that replies or approvals already exist.

Anything fabricated? No. Candidate identity, project scope, values, source/version details and stated requirements come from the project evidence and supplied documents. No human understanding, recording, sent email, permission or completed submission was invented.

What I cut: no cosmetic rewrite was needed after the mechanical pass. The new copy uses plain verbs and direct questions, avoiding C2 filler, C5 em dashes and C8 signpost phrases. It leaves unresolved-use and evaluation caveats intact.

What's left to watch: historical test counts retain their stated scope. The missing video and model-use confirmation are not resolved by editing prose or removing preparation documents.
