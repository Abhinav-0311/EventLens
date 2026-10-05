# Clarification email drafts

These drafts have **not been sent**. Review them before sending. Assessment URLs, tokens and the registered personal email are intentionally absent from this public file.

## A. Reply in the existing organizer thread

Subject: Code to Connect Phase 3: submission clarifications for EventLens

Hi Anshu / Code to Connect Team,

Thank you for sharing the assessment link and confirming that the recorded submission video can be 5–10 minutes.

I am preparing EventLens for Module B, Strategic Portfolio Stress Testing, with the required NLP risk engine. Could you please clarify these points before I finalize my submission?

1. The guidelines specify `<college>-<candidate-name>-hackathon`, but my current public repository is https://github.com/Abhinav-0311/EventLens. May I keep this repository name, or should I rename it to `vit-bhopal-abhinav-jain-hackathon` and retain EventLens as the project title?
2. My live text adapters use Federal Reserve release/RSS content and the Board's official Bluesky posts. These are distinct news/social channels from the same publisher, and that limitation is disclosed. Does this satisfy the two-source requirement, or is a second independent publisher required?
3. Please confirm the exact 11 October 2026 submission cutoff and timezone.
4. The application demo uses project-authored synthetic CSV/JSON included in the repository. An optional sentiment diagnostic used Financial PhraseBank, whose corpus has use restrictions and is not redistributed. Is submitting the diagnostic's source/version and aggregate results sufficient, or must the underlying optional evaluation corpus also be included? It is not needed to run the app or demo.

Candidate: Abhinav Jain
College: Vellore Institute of Technology, Bhopal
College email: abhinav.23bcg10130@vitbhopal.ac.in

I will include the seven-slide PDF in the public repository and an unlisted YouTube walkthrough as requested.

Best regards,
Abhinav Jain

## B. Model-owner clarification

Use the contact route listed in the [pinned model card](https://huggingface.co/ProsusAI/finbert/blob/4556d13015211d73dccd3fdd39d39232506f3e43/README.md). It lists Dogu Araci and Zulkuf Genc; verify the listed contact details before sending. An organizer's acceptance does not grant model rights on the owner's behalf.

Subject: License clarification for ProsusAI/finbert weights in an academic hackathon

Hello FinBERT maintainers,

I am Abhinav Jain, a student at Vellore Institute of Technology, Bhopal. I am preparing an individual entry for the S&P Global / Crisil Code to Connect 2026 hackathon.

My project uses local inference with `ProsusAI/finbert` at revision `4556d13015211d73dccd3fdd39d39232506f3e43`. I have not trained or fine-tuned the model. The public project repository contains my application code, synthetic demonstration inputs and attribution, but no model weights. Setup downloads the pinned weights separately from Hugging Face. I intend to demonstrate inference in a publicly viewable video and at the jury assessment.

The related implementation repository carries Apache-2.0, but I could not find an explicit weight-specific license in the pinned model card/files. Could you please confirm the applicable license and whether this academic competition use, setup download instructions and public demonstration are permitted? Please also advise any required attribution or restrictions arising from the model's training datasets. I do not assume competition use is covered solely because it is academic.

Project: https://github.com/Abhinav-0311/EventLens
College email: abhinav.23bcg10130@vitbhopal.ac.in

Thank you,
Abhinav Jain

## Optional diagnostic dataset

The [pinned PhraseBank card](https://huggingface.co/datasets/takala/financial_phrasebank/blob/8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964/README.md) states CC BY-NC-SA 3.0 and provides author contacts for commercial-use questions. Do not download again, redistribute corpus text or assume the organizer can grant dataset rights. If repeating or expanding this optional diagnostic is necessary, clarify the actual use with the rights holder first. The normal demo does not require it.
