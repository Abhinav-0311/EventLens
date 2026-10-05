import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Api } from "./api";
import { useAction, useResource, useRoute } from "./hooks";
import type { Health, Operation, Portfolio, Run, Scenario } from "./types";
import { EventView } from "./EventView";
import { AnalyzeText } from "./AnalyzeText";
import { PortfolioView } from "./PortfolioView";
import { RunView } from "./RunView";
import { ErrorPanel, Loading, SourceStatus } from "./ui";

export default function App() {
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [accessOpen, setAccessOpen] = useState(false);
  const api = useMemo(() => new Api(token), [token]);
  const route = useRoute();
  const [revision, setRevision] = useState(0);
  const [mode, setMode] = useState("");
  const [notice, setNotice] = useState("");
  const [operation, setOperation] = useState<Operation | null>(null);
  const [attemptedKind, setAttemptedKind] = useState<"refresh" | "replay">(
    "replay",
  );
  const jobController = useRef<AbortController | null>(null);
  const accessButton = useRef<HTMLButtonElement>(null);
  const closeAccess = () => {
    setAccessOpen(false);
    accessButton.current?.focus();
  };
  const job = useAction();
  const main = useRef<HTMLElement>(null);
  const previousView = useRef(route.view);
  const health = useResource<Health>(api, "/api/health", revision);
  const portfolio = useResource<Portfolio>(api, "/api/portfolio", revision);
  const scenarios = useResource<Scenario[]>(api, "/api/scenarios", revision);
  useEffect(() => () => jobController.current?.abort(), []);
  useEffect(() => {
    document.title = `EventLens — ${route.view === "portfolio" ? "Portfolio" : route.view === "runs" ? "Stress results" : "Events"}`;
    if (previousView.current !== route.view) {
      main.current?.focus({ preventScroll: true });
      window.scrollTo({ top: 0 });
      previousView.current = route.view;
    }
  }, [route.view]);
  const ingest = (kind: "refresh" | "replay") => {
    void job.run(async () => {
      setNotice("");
      setOperation(null);
      setAttemptedKind(kind);
      const controller = new AbortController();
      jobController.current = controller;
      try {
        const completed = await api.operation(
          kind,
          setOperation,
          controller.signal,
        );
        setNotice(
          `${kind === "replay" ? "Fictional replay" : "Live refresh"} completed: ${completed.result_counts.analyzed ?? 0} analyzed, ${completed.result_counts.duplicates ?? 0} duplicates, ${completed.result_counts.stress_runs ?? 0} new stress runs. ${completed.result_counts.failed_sources || completed.result_counts.skipped_sources ? "Some sources failed or were skipped; automatic execution was suppressed." : ""}`,
        );
        setMode(kind === "replay" ? "synthetic" : "live");
        window.location.hash = "events";
      } finally {
        setRevision((value) => value + 1);
        jobController.current = null;
      }
    });
  };
  const saved = (run: Run) => {
    setRevision((value) => value + 1);
    setNotice(
      "Manual comparison saved. The original signal and base portfolio are unchanged.",
    );
    window.location.hash = `runs/${run.id}`;
  };
  const actions = (
    <div className="actions">
      <button
        className={`button ${mode === "live" ? "secondary" : "primary"}`}
        onClick={() => ingest("replay")}
        disabled={job.busy || !health.data?.model_ready}
      >
        Load sample events
      </button>
      <button
        className={`button ${mode === "live" ? "primary" : "secondary"}`}
        onClick={() => ingest("refresh")}
        disabled={job.busy || !health.data?.model_ready}
      >
        Refresh live sources
      </button>
    </div>
  );
  const bootError = health.error || portfolio.error || scenarios.error;
  const retryBoot = () => {
    health.retry();
    portfolio.retry();
    scenarios.retry();
  };
  const updateToken = (event: FormEvent) => {
    event.preventDefault();
    setToken(tokenInput.trim());
    setTokenInput("");
    closeAccess();
    setNotice(
      "Write token set for this page session only. It will be cleared when you reload.",
    );
  };
  return (
    <>
      <a
        className="skip-link"
        href="#content"
        onClick={(event) => {
          event.preventDefault();
          main.current?.focus();
        }}
      >
        Skip to workspace
      </a>
      <header className="app-header">
        <a href="#events" className="brand" aria-label="EventLens home">
          <svg aria-hidden="true" viewBox="0 0 32 32">
            <circle cx="14" cy="14" r="9" />
            <path d="m21 21 7 7M9 15l4-4 4 5 4-7" />
          </svg>
          <span>EventLens</span>
        </a>
        <nav aria-label="Main navigation">
          {(["events", "portfolio", "runs"] as const).map((view) => (
            <a
              key={view}
              href={`#${view}`}
              aria-current={route.view === view ? "page" : undefined}
            >
              {view.charAt(0).toUpperCase() + view.slice(1)}
            </a>
          ))}
        </nav>
        <div className="header-meta">
          <span>
            Synthetic portfolio <span aria-hidden="true">·</span> USD
          </span>
          <button
            ref={accessButton}
            className="button quiet access-toggle"
            aria-expanded={accessOpen}
            aria-controls={accessOpen ? "access-panel" : undefined}
            onClick={() => setAccessOpen((value) => !value)}
          >
            Access{token ? " · set" : ""}
          </button>
        </div>
      </header>
      {accessOpen && (
        <form className="access-panel" id="access-panel" onSubmit={updateToken}>
          <label htmlFor="write-token">Optional write token</label>
          <p className="small muted">
            Only needed when the backend requires one. Kept in memory, never in
            storage or the frontend bundle. Local default setup requires no
            token.
          </p>
          <div className="access-input">
            <input
              autoFocus
              id="write-token"
              type="password"
              autoComplete="off"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
            />
            <button className="button primary" type="submit">
              Set token
            </button>
            <button
              className="button quiet"
              type="button"
              onClick={() => {
                setToken("");
                setTokenInput("");
                closeAccess();
              }}
            >
              Clear token
            </button>
          </div>
        </form>
      )}
      <main ref={main} id="content" className="content" tabIndex={-1}>
        {bootError ? (
          <ErrorPanel
            message={bootError}
            retry={retryBoot}
            label="Retry connection"
          />
        ) : !health.data || !portfolio.data || !scenarios.data ? (
          <Loading />
        ) : (
          <>
            <SourceStatus health={health.data} />
            {!health.data.model_ready && (
              <ErrorPanel message="Pinned local FinBERT is unavailable. Download/verify the model, then restart the engine. Existing portfolio and saved results remain inspectable; predictions are not substituted." />
            )}
            {job.busy && (
              <div className="operation-status" role="status">
                {attemptedKind === "refresh"
                  ? "Refreshing live sources"
                  : "Processing fictional replay"}{" "}
                · {operation?.status ?? "requesting"}… Automatic results are
                confirmed only after the full batch.
              </div>
            )}
            {job.error && (
              <ErrorPanel
                message={job.error}
                retry={() => ingest(attemptedKind)}
                label="Retry operation"
              />
            )}
            {notice && (
              <div className="notice" role="status">
                <span>{notice}</span>
                <button
                  className="button quiet"
                  aria-label="Dismiss notification"
                  onClick={() => setNotice("")}
                >
                  ×
                </button>
              </div>
            )}
            {route.view === "events" ? (
              <>
                <EventView
                  api={api}
                  selectedId={route.id}
                  scenarios={scenarios.data}
                  revision={revision}
                  mode={mode}
                  setMode={setMode}
                  actions={actions}
                  engineBusy={job.busy}
                  onSaved={saved}
                />
                <AnalyzeText
                  api={api}
                  disabled={job.busy || !health.data.model_ready}
                  onAnalyzed={(id) => {
                    setRevision((value) => value + 1);
                    setMode("user");
                    window.location.hash = `events/${id}`;
                  }}
                />
              </>
            ) : route.view === "portfolio" ? (
              <PortfolioView
                api={api}
                portfolio={portfolio.data}
                scenarios={scenarios.data}
              />
            ) : (
              <RunView api={api} selectedId={route.id} revision={revision} />
            )}
          </>
        )}
      </main>
      <footer className="app-footer">
        <span>Evidence first. Assumptions explicit.</span>
        <span>Illustrative fair-value stress · not investment advice</span>
      </footer>
    </>
  );
}
