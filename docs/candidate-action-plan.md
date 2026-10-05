# Abhinav's final action plan

Prepared 5 October 2026. Target completion: 10 October, ahead of the communicated 11 October deadline. Exact cutoff and timezone still need confirmation. This checklist is preparation, not submission approval.

## 1. Send the clarification drafts today

- [ ] Reply to the existing organizer email using draft A in [clarification-emails.md](clarification-emails.md). Ask about repository naming, the two same-publisher channels, deadline/timezone and whether optional diagnostic data must be submitted. Do not forward the private assessment URL to other people or publish it.
- [ ] Use draft B to ask the model owner about the exact downloaded weights' terms. The implementation's Apache-2.0 license does not settle this question. Send the response here; attribution or a different model may be needed. A model change requires fresh verification, not just a name change.
- [ ] If a rename is required, authorize the exact name `vit-bhopal-abhinav-jain-hackathon`. EventLens can remain the product title. Do not rename until links and documentation can be updated together.

You can practise locally while replies are pending. Do not describe missing confirmation as permission. The optional PhraseBank diagnostic need not be downloaded again for the walkthrough or recording; its training overlap and data-use restrictions remain disclosed.

## 2. Start the prepared demo

Open a PowerShell terminal. On this prepared machine:

```powershell
Set-Location 'E:\College\Project\Chatbot\Naukri'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1
```

The execution-policy flag applies only to this new PowerShell process. The launcher builds the dashboard, verifies the cached pinned model, binds only to localhost and chooses a new database. It never resets existing results, installs dependencies, downloads weights or fetches diagnostic data. Wait for `Application startup complete`, then open `http://127.0.0.1:8019/`. Keep the terminal open; Ctrl+C stops its server.

If the port is occupied, append `-Port 8021` and use that URL. Do not kill another project. For a preflight without creating a database or starting a server, append `-CheckOnly`. A newly cloned computer still needs the [README Quickstart](../README.md) first; this is not an installer.

## 3. Complete the walkthrough with me

- [ ] In Events, select **Load sample events**. Wait for completion; these are explicitly fictional inputs, not live announcements.
- [ ] Select the policy hike. Explain the original 50 bp announcement, impact 8, the separate 100 bp stress assumption and the evidence/eligibility gates.
- [ ] Open **View stress result**. Confirm portfolio fair value $100m, P&L -$2.618m and stressed value $97.382m. Find L01: -$228,000, stressed value $5.772m. Keep $194.4m principal/notional separate from fair value.
- [ ] Inspect a blocked event and explain its reason. The issuer-default example scores 7; a manual comparison at 8 must retain a reason and the original signal.
- [ ] Use **Export CSV** on the hike run and check it opens. Saved scenarios each start from the original portfolio, not the previous loss.
- [ ] Work through the seven questions at the end of [recording-guide.md](recording-guide.md). Send questions or your answers here. I can explain the code and check your reasoning; I cannot mark understanding on your behalf.

Use **Refresh live sources** only deliberately. The two adapters share the Federal Reserve publisher. If a provider fails, show its error honestly and continue with labelled replay; do not call saved inputs fresh live news.

Latest bounded check, 5 October: Bluesky supplied five records but RSS returned `SOURCE_HTTP_ERROR`; the two-provider gate did not pass. The deterministic recording journey did pass. See [handoff verification](handoff-verification.json). Provider availability needs a new successful check before claiming both channels work live at recording time.

## 4. Review the 14 draft labels

- [ ] Read each row in [evaluation-review.md](evaluation-review.md). Reply here in the form `D01: agree/disagree/unsure, reason`; include the three archive cases too.
- [ ] Judge the text against the documented rubric, not whether it agrees with the app. An unsure answer is acceptable. Preserve disagreements and original measurements.
- [ ] Review candidate name, college and college email in the PDF and README.

The development set was used for refinement. PhraseBank can overlap FinBERT training. The 12-release archive has one class and publisher, with exact impact agreement only 4/12. None is independent broad-news model accuracy. Label changes after seeing predictions need a recorded revision and reason; do not quietly relabel the old result.

## 5. Rehearse, then record your own narration

- [ ] Review the [seven-slide PDF](presentation.pdf). Use the public PDF as the submission deck, not an unchecked Gamma/Canva draft.
- [ ] Follow [recording-guide.md](recording-guide.md): target 6–7 minutes, permitted recorded length 5–10 minutes according to the organizer's email. Briefly show startup from the README/launcher, then evidence, calculation, export, measurements and limitations.
- [ ] Rehearse the separate live jury sequence in at most 5 minutes. Have the prototype running for the eventual assigned slot; attend the pitch and Q&A.
- [ ] Test microphone and readable screen capture. Close email/assessment tabs, hide notifications and secrets, keep synthetic labels visible, and explain in your own words.
- [ ] Watch the entire recording once: audible voice, readable math, correct identity, no secrets, no fictional-live or unperformed-review claims.

Do not claim event classification is a trained model: FinBERT provides sentiment; event/impact are inspectable rules. Avoid autonomous-risk, actual-loss prediction and independent-accuracy claims. AI-assisted development is disclosed.

## 6. Upload to YouTube as unlisted and send the link here

- [ ] The supplied guidelines explicitly require an **unlisted YouTube video**. Do not substitute Drive/OneDrive without organizer approval.
- [ ] Wait for processing, then open the video link in a signed-out/private browser and play it. Check the full duration and readable playback.
- [ ] Send the final video URL here. I can update the README's demo link, cross-check artifacts and run the final packaging checks. Do not send passwords, upload credentials or the assessment access token.
- [ ] Check [public repository](https://github.com/Abhinav-0311/EventLens) and [public PDF](https://github.com/Abhinav-0311/EventLens/blob/main/docs/presentation.pdf) from the same signed-out browser. If renamed, replace these links everywhere before submitting.

## 7. Submit only after the final checks

- [ ] Send organizer/model-owner replies, label decisions and video URL here. Confirm assessment access privately; if the upload fields differ from the expected links, share a cropped screenshot with tokens and personal details hidden.
- [ ] Use [submission-answer-template.md](submission-answer-template.md), replacing the video placeholder and any renamed URLs. Review the text yourself. Attach the PDF or other requested deliverables if the portal asks; do not invent a ZIP requirement.
- [ ] Confirm every [submission-checklist.md](submission-checklist.md) gate is genuinely complete. A notice file or unanswered email is not a resolved permission check.
- [ ] Submit through your own DoSelect account before the confirmed deadline. Keep the success screen/receipt privately and verify the status changed from pending. Preparing GitHub files does not submit the assessment.

## What to send back

Organizer reply; model-use response or decision to evaluate an alternative; 14 label-review answers; questions from the walkthrough; final unlisted YouTube link; sanitized portal fields if needed. No new paid API, hosting purchase, private banking data or fabricated evaluation evidence is needed for this handoff.
