import { useRef, useState, type FormEvent } from "react";
import type { Api } from "./api";
import { useAction } from "./hooks";
import type { EventDetail, Run, Scenario } from "./types";

export function Comparison({
  api,
  detail,
  scenarios,
  onSaved,
  onCancel,
  engineBusy,
}: {
  api: Api;
  detail: EventDetail;
  scenarios: Scenario[];
  onSaved: (run: Run) => void;
  onCancel: () => void;
  engineBusy: boolean;
}) {
  const signal = detail.event.primary_signal;
  const options = scenarios.filter(
    (scenario) =>
      scenario.event_subtype === signal.event_subtype ||
      (["rate_hike", "rate_cut"].includes(signal.event_subtype) &&
        ["rate_hike", "rate_cut"].includes(scenario.event_subtype)),
  );
  const [scenarioId, setScenarioId] = useState(
    detail.eligibility.scenario_id ?? options[0]?.id ?? "",
  );
  const [impact, setImpact] = useState(signal.impact_score);
  const [reason, setReason] = useState("");
  const requestIdentity = useRef<{ fingerprint: string; key: string } | null>(
    null,
  );
  const action = useAction();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      const body = {
        event_id: detail.event.id,
        scenario_id: scenarioId,
        impact_score: impact,
        override_reason: reason.trim(),
      };
      const fingerprint = JSON.stringify(body);
      if (requestIdentity.current?.fingerprint !== fingerprint)
        requestIdentity.current = { fingerprint, key: crypto.randomUUID() };
      onSaved(
        await api.post<Run>("/api/stress-runs", {
          ...body,
          idempotency_key: requestIdentity.current.key,
        }),
      );
    });
  };
  return (
    <form className="comparison" onSubmit={submit}>
      <fieldset disabled={action.busy || engineBusy}>
        <legend>Manual comparison</legend>
        <p className="muted">
          A labelled what-if result, not automatic confirmation. The original
          signal and base portfolio remain unchanged.
        </p>
        <div className="form-grid">
          <label>
            Scenario
            <select
              value={scenarioId}
              onChange={(event) => setScenarioId(event.target.value)}
            >
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Comparison impact
            <select
              value={impact}
              onChange={(event) => setImpact(Number(event.target.value))}
            >
              {Array.from({ length: 10 }, (_, index) => (
                <option key={index} value={index + 1}>
                  {index + 1} / 10
                </option>
              ))}
            </select>
          </label>
        </div>
        <label htmlFor="comparison-reason">Comparison reason</label>
        <textarea
          id="comparison-reason"
          rows={3}
          required
          minLength={8}
          maxLength={1000}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          aria-describedby={
            action.error
              ? "comparison-help comparison-error"
              : "comparison-help"
          }
          aria-invalid={!!action.error}
          placeholder="Explain the assumption you want to compare."
        />
        <p id="comparison-help" className="small muted">
          At least 8 meaningful characters. This reason is saved with the
          result.
        </p>
        {action.error && (
          <p id="comparison-error" role="alert" className="inline-error">
            {action.error}
          </p>
        )}
        <div className="actions">
          <button
            className="button primary"
            disabled={reason.trim().length < 8 || !scenarioId}
            type="submit"
          >
            {action.busy ? "Saving comparison…" : "Save comparison"}
          </button>
          <button className="button quiet" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </fieldset>
    </form>
  );
}
