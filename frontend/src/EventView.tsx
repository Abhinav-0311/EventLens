import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { useResource } from "./hooks";
import type {
  EventDetail,
  EventSummary,
  Page,
  Run,
  Scenario,
  Signal,
  Source,
} from "./types";
import {
  modeLabel,
  reasonLabel,
  safeSourceUrl,
  sentimentLabel,
  title,
  utc,
} from "./format";
import { Badge, Download, Empty, ErrorPanel, Loading, Pagination } from "./ui";
import { Comparison } from "./Comparison";

function EvidenceText({ source, signal }: { source: Source; signal: Signal }) {
  const text = Array.from(source.text);
  const span = signal.evidence_spans[0];
  const valid =
    span &&
    span.start >= 0 &&
    span.end <= text.length &&
    text.slice(span.start, span.end).join("") === span.text;
  return (
    <blockquote
      className="evidence-text"
      tabIndex={0}
      aria-label="Primary source text"
    >
      {valid ? (
        <>
          {text.slice(0, span.start).join("")}
          <mark>{span.text}</mark>
          {text.slice(span.end).join("")}
        </>
      ) : (
        source.text
      )}
    </blockquote>
  );
}
function SourceLink({ source }: { source: Source }) {
  const link = safeSourceUrl(source.canonical_uri);
  return link ? (
    <a
      className="text-link"
      href={link}
      target="_blank"
      rel="noopener noreferrer"
    >
      Open original source <span aria-hidden="true">↗</span>
    </a>
  ) : (
    <span className="small muted">
      {source.provenance_mode === "synthetic"
        ? "Fictional record · no external source"
        : source.provenance_mode === "user"
          ? "User input · no verified source link"
          : "Native social record retained in evidence"}
    </span>
  );
}
function Detail({
  api,
  detail,
  scenarios,
  revision,
  engineBusy,
  onSaved,
}: {
  api: Api;
  detail: EventDetail;
  scenarios: Scenario[];
  revision: number;
  engineBusy: boolean;
  onSaved: (run: Run) => void;
}) {
  const signal = detail.event.primary_signal;
  const source = detail.evidence.find(
    (item) => item.id === signal.source_record_id,
  )!;
  const runs = useResource<Page<Run>>(
    api,
    `/api/stress-runs?event_id=${encodeURIComponent(detail.event.id)}&limit=100`,
    revision,
  );
  const [comparing, setComparing] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [detail.event.id]);
  const eligible = detail.eligibility.state.startsWith("eligible");
  const latest = runs.data?.items[0];
  const primaryAction = latest ? (
    <button
      className="button primary"
      onClick={() => {
        window.location.hash = `runs/${latest.id}`;
      }}
    >
      View stress result
    </button>
  ) : detail.eligibility.scenario_id ? (
    <button
      className="button primary"
      disabled={engineBusy || runs.loading}
      onClick={() => setComparing(true)}
    >
      {detail.eligibility.state === "needs_review"
        ? "Review scenario"
        : "Compare scenario"}
    </button>
  ) : null;
  return (
    <article className="event-detail">
      <div className="detail-topline">
        <a className="back-link" href="#events">
          ← Event queue
        </a>
        <Badge
          tone={source.provenance_mode === "synthetic" ? "amber" : "neutral"}
        >
          {modeLabel(source.provenance_mode)}
        </Badge>
        <span className="small muted">{signal.event_class}</span>
      </div>
      <h2 ref={heading} tabIndex={-1}>
        {title(signal)}
      </h2>
      <p className="detail-caption">{source.publisher}</p>
      <div className="signal-metrics">
        <div>
          <span>Impact</span>
          <strong>
            {signal.impact_score}
            <small> / 10</small>
          </strong>
        </div>
        <div>
          <span>Financial sentiment</span>
          <strong className="sentiment">
            {sentimentLabel(signal.sentiment_score)}
          </strong>
        </div>
        <div>
          <span>Matched exposure</span>
          <strong className="exposure-count">
            {detail.eligibility.rate_position_ids.length} rate <small>·</small>{" "}
            {detail.eligibility.spread_position_ids.length} credit
          </strong>
        </div>
      </div>
      <section className="section-block" aria-labelledby="evidence-heading">
        <div className="section-heading">
          <h3 id="evidence-heading">Evidence</h3>
          <span className="small muted">
            {source.verified_publisher
              ? "Verified publisher"
              : "Unverified / fictional input"}
          </span>
        </div>
        <EvidenceText source={source} signal={signal} />
        <div className="evidence-meta">
          <span>Published {utc(source.published_at)}</span>
          <SourceLink source={source} />
        </div>
        {detail.evidence.length > 1 && (
          <details>
            <summary>{detail.evidence.length} saved evidence records</summary>
            <p className="small muted">
              {detail.event.evidence_independent
                ? "Different verified publishers are represented."
                : "Multiple records are not independent confirmation."}
            </p>
            {detail.evidence.map((item) => (
              <div key={item.id} className="additional-evidence">
                <strong>{item.publisher}</strong>
                <span className="small muted">
                  {item.source_family.replaceAll("_", " ")} ·{" "}
                  {utc(item.published_at)}
                </span>
                <p>{item.text}</p>
                <SourceLink source={item} />
              </div>
            ))}
          </details>
        )}
      </section>
      <section className="section-block" aria-labelledby="scenario-heading">
        <div className="section-heading">
          <h3 id="scenario-heading">Scenario & execution</h3>
          <Badge
            tone={
              eligible
                ? "green"
                : detail.eligibility.state === "needs_review"
                  ? "amber"
                  : "neutral"
            }
          >
            {latest
              ? "Result saved"
              : eligible
                ? "Eligible"
                : detail.eligibility.state === "needs_review"
                  ? "Review required"
                  : "Informational"}
          </Badge>
        </div>
        {latest ? (
          <p className="execution-copy">
            {modeLabel(latest.mode)} saved. Calculated independently from the
            original base portfolio.
          </p>
        ) : eligible ? (
          <p className="execution-copy">
            Eligible for{" "}
            {source.provenance_mode === "synthetic"
              ? "a fictional simulation"
              : "live-source automatic stress"}
            .{" "}
            {engineBusy
              ? "Ingestion is still processing; a result is not yet confirmed."
              : "No saved run yet. Automatic execution requires a complete successful ingestion batch."}
          </p>
        ) : (
          <p className="execution-copy">
            {detail.eligibility.scenario_id
              ? "Automatic execution is blocked. A manual comparison must record your assumptions."
              : "This event has no supported banking stress scenario."}
          </p>
        )}
        {detail.eligibility.reasons.length > 0 && (
          <ul className="review-reasons">
            {detail.eligibility.reasons.map((reason) => (
              <li key={reason}>{reasonLabel(reason)}</li>
            ))}
          </ul>
        )}
        {source.provenance_mode === "synthetic" && (
          <p className="small provenance-note">
            Fictional event. Simulation clock: {utc(signal.simulation_clock)}.
            Not verified real-world evidence.
          </p>
        )}
        {runs.loading && <Loading label="Checking saved runs…" />}
        {runs.error && <ErrorPanel message={runs.error} retry={runs.retry} />}
        {!comparing && (
          <div className="actions">
            {primaryAction}
            {latest && detail.eligibility.scenario_id && (
              <button
                className="button secondary"
                disabled={engineBusy}
                onClick={() => setComparing(true)}
              >
                Compare scenario
              </button>
            )}
          </div>
        )}
        {comparing && (
          <Comparison
            api={api}
            detail={detail}
            scenarios={scenarios}
            engineBusy={engineBusy}
            onSaved={onSaved}
            onCancel={() => setComparing(false)}
          />
        )}
        {runs.data && runs.data.items.length > 1 && (
          <details>
            <summary>{runs.data.total} saved runs for this event</summary>
            {runs.data.items.map((run) => (
              <a
                className="saved-run-link"
                key={run.id}
                href={`#runs/${run.id}`}
              >
                {run.scenario_snapshot.name} · {modeLabel(run.mode)} ·{" "}
                {utc(run.created_at)}
              </a>
            ))}
          </details>
        )}
      </section>
      <details className="section-block">
        <summary>How this signal was scored</summary>
        <p>{signal.impact_components.rationale}</p>
        <dl className="audit-grid">
          <div>
            <dt>Magnitude</dt>
            <dd>{signal.impact_components.magnitude_points} / 5</dd>
          </div>
          <div>
            <dt>Scope</dt>
            <dd>{signal.impact_components.scope_points} / 4</dd>
          </div>
          <div>
            <dt>Assertion</dt>
            <dd>{signal.assertion_status}</dd>
          </div>
          <div>
            <dt>Impact rubric</dt>
            <dd>{signal.impact_components.rubric_version}</dd>
          </div>
        </dl>
        <p className="small muted">
          Sentiment is P(positive) − P(negative), not calibrated confidence and
          not shock direction. Event and impact outputs use phrase rules, not
          FinBERT event predictions.
        </p>
        <p className="small muted">
          Model {signal.sentiment_model_id} ·{" "}
          <code>{signal.model_revision}</code>
        </p>
        <p className="small muted">
          Signal <code>{signal.id}</code> · engine {signal.engine_version}
        </p>
        <p className="small muted">
          Eligibility evaluated {utc(detail.eligibility.evaluated_at)}.
          Historical signal reasons may differ from current eligibility.
        </p>
        <Download
          api={api}
          path={`/api/exports/signals?event_id=${encodeURIComponent(detail.event.id)}`}
          name={`eventlens-signal-${detail.event.id}.json`}
        >
          Export signal JSON
        </Download>
      </details>
    </article>
  );
}
export function EventView({
  api,
  selectedId,
  scenarios,
  revision,
  mode,
  setMode,
  actions,
  engineBusy,
  onSaved,
}: {
  api: Api;
  selectedId: string | null;
  scenarios: Scenario[];
  revision: number;
  mode: string;
  setMode: (value: string) => void;
  actions: React.ReactNode;
  engineBusy: boolean;
  onSaved: (run: Run) => void;
}) {
  const [offset, setOffset] = useState(0);
  const [impact, setImpact] = useState("1");
  const params = new URLSearchParams({
    limit: "25",
    offset: String(offset),
    minimum_impact: impact,
  });
  if (mode) params.set("mode", mode);
  const queue = useResource<Page<EventSummary>>(
    api,
    `/api/events?${params}`,
    revision,
  );
  const list = useRef<HTMLUListElement>(null);
  const previousSelection = useRef(selectedId);
  useEffect(() => {
    const previous = previousSelection.current;
    if (!selectedId && previous) {
      const row = Array.from(
        list.current?.querySelectorAll<HTMLButtonElement>("[data-event-id]") ??
          [],
      ).find((item) => item.dataset.eventId === previous);
      const target =
        row ?? list.current?.closest("aside")?.querySelector<HTMLElement>("h2");
      target?.focus();
    }
    previousSelection.current = selectedId;
  }, [selectedId]);
  useEffect(() => {
    const container = list.current;
    const row = container?.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (
      !container?.clientHeight ||
      !row ||
      container.scrollHeight <= container.clientHeight
    )
      return;
    const bounds = container.getBoundingClientRect();
    const selectedBounds = row.getBoundingClientRect();
    if (selectedBounds.top < bounds.top)
      container.scrollTop -= bounds.top - selectedBounds.top;
    else if (selectedBounds.bottom > bounds.bottom)
      container.scrollTop += selectedBounds.bottom - bounds.bottom;
  }, [selectedId, queue.data]);
  const selected = useResource<EventDetail>(
    api,
    selectedId ? `/api/events/${encodeURIComponent(selectedId)}` : null,
    revision,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Risk intelligence</p>
          <h1>Events</h1>
        </div>
        {queue.data?.total !== 0 && actions}
      </div>
      {queue.loading && !selectedId ? (
        <Loading label="Loading event queue…" />
      ) : queue.error ? (
        <ErrorPanel message={queue.error} retry={queue.retry} />
      ) : queue.data?.total === 0 && !selectedId && !mode && impact === "1" ? (
        <Empty title="No events yet" action={actions}>
          Load fictional samples to explore the full workflow, or refresh both
          live channels. Nothing is inserted automatically.
        </Empty>
      ) : (
        <div className={`workbench ${selectedId ? "has-selection" : ""}`}>
          <aside className="event-queue" aria-label="Event queue">
            <div className="queue-heading">
              <h2 tabIndex={-1}>Event queue</h2>
              <span className="small muted">
                {queue.data?.total ?? "…"} events
              </span>
            </div>
            <div className="filters">
              <label>
                Origin
                <select
                  value={mode}
                  onChange={(event) => {
                    setMode(event.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All origins</option>
                  <option value="synthetic">Fictional samples</option>
                  <option value="live">Live sources</option>
                  <option value="user">Supplied text</option>
                </select>
              </label>
              <label>
                Impact
                <select
                  value={impact}
                  onChange={(event) => {
                    setImpact(event.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="1">All scores</option>
                  <option value="8">Above 7</option>
                </select>
              </label>
            </div>
            {queue.loading && <Loading label="Loading events…" />}
            {queue.data?.items.length === 0 && (
              <div className="queue-empty">
                <p>No events match these filters.</p>
                <button
                  className="button quiet"
                  onClick={() => {
                    setMode("");
                    setImpact("1");
                    setOffset(0);
                  }}
                >
                  Clear filters
                </button>
                {actions}
              </div>
            )}
            <ul ref={list} className="event-list">
              {queue.data?.items.map((item) => (
                <li key={item.id}>
                  <button
                    data-event-id={item.id}
                    aria-pressed={selectedId === item.id}
                    className={`event-row ${selectedId === item.id ? "selected" : ""}`}
                    onClick={() => {
                      window.location.hash = `events/${item.id}`;
                    }}
                  >
                    <span className="event-row-top">
                      <span>{title(item.primary_signal)}</span>
                      <strong>
                        {item.primary_signal.impact_score}
                        <small> / 10</small>
                      </strong>
                    </span>
                    <span className="small muted">
                      {item.primary_signal.event_class}
                    </span>
                    <span className="event-row-foot">
                      <span className="origin-label">
                        {modeLabel(item.provenance_modes[0])}
                      </span>
                      <span
                        className={`queue-state ${item.eligibility?.state === "needs_review" ? "review" : ""}`}
                      >
                        {item.eligibility?.state === "needs_review"
                          ? "Review"
                          : item.eligibility?.state.startsWith("eligible")
                            ? "Eligible"
                            : "Informational"}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {queue.data && (
              <Pagination
                page={queue.data}
                offset={offset}
                setOffset={setOffset}
              />
            )}
          </aside>
          <div className="detail-surface">
            {selected.loading ? (
              <Loading label="Loading event evidence…" />
            ) : selected.error ? (
              <ErrorPanel message={selected.error} retry={selected.retry} />
            ) : selected.data ? (
              <Detail
                key={selected.data.event.id}
                api={api}
                detail={selected.data}
                scenarios={scenarios}
                revision={revision}
                engineBusy={engineBusy}
                onSaved={onSaved}
              />
            ) : (
              <Empty title="Select an event">
                Inspect the evidence, check matching exposure, then explain the
                result.
              </Empty>
            )}
          </div>
        </div>
      )}
    </>
  );
}
