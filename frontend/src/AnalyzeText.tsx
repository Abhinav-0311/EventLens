import { useState, type FormEvent } from "react";
import type { Api } from "./api";
import { useAction } from "./hooks";
import type { Signal } from "./types";

export function AnalyzeText({
  api,
  disabled,
  onAnalyzed,
}: {
  api: Api;
  disabled: boolean;
  onAnalyzed: (id: string) => void;
}) {
  const [text, setText] = useState("");
  const action = useAction();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      const result = await api.post<{ signal: Signal }>(
        "/api/signals/analyze",
        { text: text.trim() },
      );
      setText("");
      onAnalyzed(result.signal.event_id);
    });
  };
  return (
    <details className="section-block supplied-text">
      <summary>Analyze supplied text</summary>
      <form onSubmit={submit}>
        <fieldset disabled={disabled || action.busy}>
          <legend className="sr-only">Supplied text analysis</legend>
          <p className="small muted" id="analysis-help">
            Paste English financial news or a social post (up to 12,000
            characters). Saved as unverified user input at submission time; it
            cannot trigger automatic stress.
          </p>
          <label htmlFor="analysis-text">Source text</label>
          <textarea
            id="analysis-text"
            rows={4}
            required
            maxLength={12000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-describedby={
              action.error ? "analysis-help analysis-error" : "analysis-help"
            }
            aria-invalid={!!action.error}
          />
          {action.error && (
            <p role="alert" id="analysis-error" className="inline-error">
              {action.error}
            </p>
          )}
          <button
            className="button secondary"
            type="submit"
            disabled={!text.trim()}
          >
            {action.busy ? "Analyzing text…" : "Analyze text"}
          </button>
        </fieldset>
      </form>
    </details>
  );
}
